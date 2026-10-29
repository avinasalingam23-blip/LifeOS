"""SQLite lifecycle, transactional access and validated backups; no UI dependencies."""
from __future__ import annotations
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

SCHEMA_VERSION = 2
DEFAULTS = {
    'theme': 'Current Theme', 'dsa_target': 2, 'study_target': 45, 'calories': 2200, 'protein': 100,
    'carbs': 275, 'fat': 70, 'fibre': 30, 'water_ml': 2500,
    'weight_unit': 'kg', 'distance_unit': 'km', 'nutrition_mode': 'Simple',
    'focus_minutes': 25, 'reminders': 'Yes', 'ai_model': 'qwen3:1.7b',
    'ai_url': 'http://127.0.0.1:11434', 'ai_context': 4096,
}

def data_directory() -> Path:
    override = os.environ.get('LIFEOS_DATA_DIR')
    return Path(override) if override else Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share')) / 'LifeOS'

class Database:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else data_directory() / 'lifeos.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, timeout=15)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute('PRAGMA busy_timeout=15000')
        self.migrate()

    def migrate(self):
        version = self.conn.execute('PRAGMA user_version').fetchone()[0]
        if version > SCHEMA_VERSION:
            raise ValueError('This database was created by a newer LifeOS version. Update LifeOS to open it.')
        if version < 1:
            schema = Path(__file__).with_name('schema.sql').read_text(encoding='utf-8')
            self.conn.executescript('BEGIN IMMEDIATE;\n' + schema + '\nPRAGMA user_version=1;\nCOMMIT;')
        if version < 2:
            if version==1:
                self.backup()
            migration=Path(__file__).with_name('migration_2.sql').read_text(encoding='utf-8')
            self.conn.executescript('BEGIN IMMEDIATE;\n'+migration+'\nPRAGMA user_version=2;\nCOMMIT;')
        with self.conn:
            for key, value in DEFAULTS.items():
                self.conn.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', (key, json.dumps(value)))
            if not self.conn.execute('SELECT 1 FROM goal_history LIMIT 1').fetchone():
                self.conn.execute('INSERT INTO goal_history VALUES (?,?)', (date.today().isoformat(), json.dumps(self.settings())))

    @contextmanager
    def transaction(self):
        with self.conn:
            yield self.conn

    def query(self, sql, params=()):
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def one(self, sql, params=()):
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def execute(self, sql, params=()):
        with self.conn:
            return self.conn.execute(sql, params).lastrowid

    def settings(self):
        return {r['key']: json.loads(r['value']) for r in self.query('SELECT * FROM settings')}

    def revision(self):
        """Local writes plus other connections' commits; no row mutation."""
        return (self.conn.total_changes,self.conn.execute('PRAGMA data_version').fetchone()[0])

    def save_settings(self, values, effective_date=None):
        with self.conn:
            for key, value in values.items():
                if key not in DEFAULTS:
                    raise ValueError(f'Unknown setting: {key}')
                self.conn.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, json.dumps(value)))
            self.conn.execute('INSERT OR REPLACE INTO goal_history VALUES (?,?)',
                              (effective_date or date.today().isoformat(), json.dumps(self.settings())))

    def goals_on(self, day):
        row = self.one('SELECT values_json FROM goal_history WHERE effective_date<=? ORDER BY effective_date DESC LIMIT 1', (day,))
        return json.loads(row['values_json']) if row else dict(DEFAULTS)

    def backup(self, destination=None):
        directory = self.path.parent / 'backups'
        directory.mkdir(exist_ok=True)
        target = Path(destination) if destination else directory / f'lifeos-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite3'
        if target.resolve() == self.path.resolve():
            raise ValueError('Choose a separate backup file, not the active database.')
        if target.exists():
            raise ValueError('Backup destination already exists. Choose a new filename.')
        with sqlite3.connect(target) as backup:
            self.conn.backup(backup)
        return target

    def automatic_backup(self):
        directory = self.path.parent / 'backups'
        if not directory.exists() or not list(directory.glob(f'lifeos-{date.today():%Y%m%d}-*.sqlite3')):
            return self.backup()

    def restore(self, source):
        source = Path(source).resolve()
        if not source.is_file() or source.resolve() == self.path.resolve():
            raise ValueError('Select an existing LifeOS backup separate from the active database.')
        with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as backup:
            if backup.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('Backup failed its integrity check.')
            version=backup.execute('PRAGMA user_version').fetchone()[0]
            if version not in (1,SCHEMA_VERSION):
                raise ValueError('Backup schema version is incompatible with this LifeOS version.')
            # Upgrade an in-memory copy first, so version-1 backups remain usable
            # and a failed migration never changes the live database or source.
            staged=sqlite3.connect(':memory:')
            try:
                backup.backup(staged)
                if version==1:
                    migration=Path(__file__).with_name('migration_2.sql').read_text(encoding='utf-8')
                    staged.executescript('BEGIN IMMEDIATE;\n'+migration+'\nPRAGMA user_version=2;\nCOMMIT;')
            except sqlite3.DatabaseError as error:
                staged.close()
                raise ValueError('Backup cannot be upgraded: '+str(error)) from None
            backup=staged
            required = {r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            found = {r[0] for r in backup.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not required <= found or backup.execute('PRAGMA foreign_key_check').fetchone():
                raise ValueError('Backup is missing LifeOS tables or has broken record links.')
            # Validate every expected column before changing the live database.
            for table in required:
                expected = {r[1] for r in self.conn.execute(f'PRAGMA table_info("{table}")')}
                actual = {r[1] for r in backup.execute(f'PRAGMA table_info("{table}")')}
                if not expected <= actual:
                    raise ValueError(f'Backup has an incompatible {table} table.')
            safety = self.backup()
            backup.backup(self.conn)
            staged.close()
        self.migrate()
        return safety

    def close(self):
        self.conn.close()

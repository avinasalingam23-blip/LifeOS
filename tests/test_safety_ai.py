import json
import sqlite3
from datetime import date
import pytest
from lifeos.db import Database

def test_backup_restore_and_safety_snapshot(service,db,tmp_path):
    p=service.save('paths',{'name':'Original'})
    backup=db.backup(tmp_path/'backup.sqlite3')
    service.save('paths',{'name':'Later'})
    safety=db.restore(backup)
    assert [r['name'] for r in service.list('paths')]==['Original']
    with sqlite3.connect(safety) as snapshot:
        assert snapshot.execute('SELECT COUNT(*) FROM paths').fetchone()[0]==2
    assert db.one('PRAGMA quick_check')['quick_check']=='ok'
    assert db.query('PRAGMA foreign_key_check')==[]

def test_corrupt_and_incompatible_backups_leave_live_data_intact(service,db,tmp_path):
    service.save('paths',{'name':'Keep me'})
    corrupt=tmp_path/'bad.sqlite3'
    corrupt.write_text('not a database')
    with pytest.raises((sqlite3.DatabaseError,ValueError)):
        db.restore(corrupt)
    incomplete=tmp_path/'empty.sqlite3'
    with sqlite3.connect(incomplete) as conn:
        conn.execute('PRAGMA user_version=1')
    with pytest.raises(ValueError):
        db.restore(incomplete)
    assert len(service.list('paths'))==1

def test_backups_cannot_overwrite_database_or_existing_file(db,tmp_path):
    with pytest.raises(ValueError):
        db.backup(db.path)
    backup=db.backup(tmp_path/'fixed.sqlite3')
    with pytest.raises(ValueError):
        db.backup(backup)
    assert db.automatic_backup().exists()
    assert db.automatic_backup() is None

def test_retired_modules_and_entry_points_are_absent():
    import importlib.util
    from lifeos.ui.app import LifeOS, PAGES
    from lifeos.ui.nutrition import NutritionReviewDialog
    from lifeos.ui.settings import GROUPS
    from lifeos.ui.icons import NAV_ICONS,TITLE_ICONS,action_icon
    assert importlib.util.find_spec('lifeos.ai') is None
    assert importlib.util.find_spec('lifeos.ui.assistant') is None
    assert not hasattr(LifeOS,'open_ai')
    assert not hasattr(NutritionReviewDialog,'ai')
    assert len(PAGES)==len(NAV_ICONS)==8
    assert all('ai' not in heading.casefold().split() for heading,fields in GROUPS)
    assert 'brain' not in TITLE_ICONS.values()
    assert action_icon('Ask AI') is None


def test_application_has_no_provider_transport_or_ui_references():
    import ast
    import re
    from pathlib import Path
    source=Path(__file__).parents[1]/'lifeos'
    # Legacy SQLite defaults remain deliberately; this audits active presentation
    # and metadata help strings rather than stored user text or old artifacts.
    forbidden=re.compile(r'\bai\b|ollama|assistant|ai[_-]|qwen|\bbrain\b',re.I)
    for file in [*source.joinpath('ui').glob('*.py'),source/'models.py']:
        assert not forbidden.search(file.read_text(encoding='utf-8')),file.name
    for file in source.rglob('*.py'):
        if file.name=='smoke.py':
            continue
        tree=ast.parse(file.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                modules=[alias.name for alias in node.names]
            elif isinstance(node,ast.ImportFrom):
                modules=[node.module or '']
            else:
                continue
            assert not any(m.split('.')[0] in {'ollama','openai','requests','httpx','socket'} or
                m in {'urllib','urllib.request','urllib.error'} for m in modules),(file.name,modules)


def test_saving_normal_preferences_preserves_inactive_ai_settings(db):
    from types import SimpleNamespace
    from lifeos.ui.settings import SettingsPage, GROUPS
    # Legacy settings must never prevent saving unrelated goals, even if invalid.
    legacy={'ai_url':'old invalid address','ai_model':'','ai_context':0}
    db.save_settings(legacy)
    class Input:
        def __init__(self,value): self.value=str(value)
        def get(self): return self.value
        def delete(self,*args): self.value=''
        def insert(self,index,value): self.value=str(value)
    values=db.settings()
    inputs={key:(Input(values[key]),kind) for heading,fields in GROUPS for key,title,kind in fields}
    assert not any(key.startswith('ai_') for key in inputs)
    inputs['dsa_target'][0].value='4'
    notices=[]
    app=SimpleNamespace(db=db,timer_minutes=Input(25),notice=notices.append)
    SettingsPage.save(SimpleNamespace(app=app,inputs=inputs))
    assert db.settings()['dsa_target']==4 and notices
    assert {key:db.settings()[key] for key in legacy}==legacy



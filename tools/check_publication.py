"""Read-only publication audit; Git metadata/reports stay in ignored test output.

No staging, commit, remote operation, database access or application launch.
This is a heuristic scan, not a guarantee that every possible secret is absent.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

from PIL import Image, ExifTags


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_SUFFIXES = {'.sqlite', '.sqlite3', '.db', '.exe', '.dll', '.pyd', '.pem', '.key', '.pfx', '.p12', '.log', '.zip'}
TEXT_SUFFIXES = {'.py', '.md', '.txt', '.json', '.toml', '.sql', '.svg', '.spec', '.ps1', '.cmd'}
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.ico'}


def git(*arguments, metadata, empty_excludes, input_bytes=None):
    command = ['git', '-c', f'core.excludesFile={empty_excludes}',
               f'--git-dir={metadata}', f'--work-tree={ROOT}', *arguments]
    result = subprocess.run(command, input=input_bytes, capture_output=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.decode(errors='replace'))
    return result


def run(directory, existing_metadata=None):
    directory = Path(directory).resolve()
    if not directory.is_relative_to(ROOT / '.test-artifacts'):
        raise ValueError('Choose a new directory under .test-artifacts.')
    directory.mkdir(parents=True, exist_ok=False)
    if existing_metadata is None:
        metadata = directory / 'git-metadata'
        subprocess.run(['git', 'init', '--bare', '--quiet', str(metadata)], check=True, capture_output=True)
    else:
        # Reuse prior audit metadata read-only when initialization is forbidden.
        metadata = Path(existing_metadata).resolve()
        if not metadata.is_relative_to(ROOT / '.test-artifacts') or not (metadata / 'HEAD').is_file() or not (metadata / 'config').is_file():
            raise ValueError('Use an existing isolated Git metadata directory under .test-artifacts.')
    empty = directory / 'empty-global-excludes'
    empty.touch()
    actual = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    root_repository = actual.returncode == 0
    if root_repository:
        raise ValueError('A repository now exists. Review its tracked files/history before rerunning this no-repository audit.')
    raw = git('ls-files', '--others', '--exclude-standard', '-z', metadata=metadata, empty_excludes=empty).stdout
    candidates = sorted(p.decode('utf-8') for p in raw.split(b'\0') if p)
    assert candidates and '.gitignore' in candidates and 'LifeOS.spec' in candidates

    excluded_samples = [
        '.venv/Lib/sample.py', '__pycache__/sample.pyc', '.pytest_cache/state', '.test-artifacts/profile/record.json',
        'dist/LifeOS/LifeOS.exe', 'build/package/work/file.txt', 'profile.sqlite3', 'nested/profile.sqlite3-wal',
        'nested/profile.sqlite-journal', 'profile.db', 'profile.db-shm', 'nested/backups/profile.json',
        'exports/meals.csv', 'meals.csv', 'weight.tsv', 'records.xlsx', 'records.xls',
        'progress-photos/photo.jpg', 'logs/session.log', 'session.log.1',
        '.env', '.env.production', 'nested/.env.local', 'credentials-local.json', 'secret.pem', 'id_ed25519',
        'archive.zip', '.vscode/settings.json', 'notes.tmp', 'profile.backup', 'profile.bak',
    ]
    retained_samples = ['main.py', 'LifeOS.spec', 'lifeos/schema.sql', 'lifeos/migration_2.sql',
                        'lifeos/assets/icon-manifest.json', 'lifeos/assets/backgrounds/workout.webp',
                        'lifeos/assets/backgrounds/originals/workout.jpg', 'tests/test_records.py',
                        'docs/screenshots/cmd-dashboard.png', '.env.example']
    samples = excluded_samples + retained_samples
    raw = git('check-ignore', '--no-index', '--stdin', '-z', metadata=metadata, empty_excludes=empty,
              input_bytes=b'\0'.join(p.encode() for p in samples) + b'\0').stdout
    ignored = set(p.decode() for p in raw.split(b'\0') if p)
    assert set(excluded_samples) <= ignored, sorted(set(excluded_samples) - ignored)
    assert not set(retained_samples) & ignored, sorted(set(retained_samples) & ignored)

    patterns = {
        'provider-token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{25,}|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9_-]{24,}|xox[baprs]-[A-Za-z0-9-]{18,}|glpat-[A-Za-z0-9_-]{18,})'),
        'private-key-header': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----'),
        'literal-credential': re.compile(r'''(?i)["']?(?:api[_-]?key|password|passwd|access[_-]?token|client[_-]?secret)["']?\s*[:=]\s*["']([^"'\n]{6,})["']'''),
        'credential-in-url': re.compile(r'https?://[^\s/:@]+:[^\s/@]+@'),
        'machine-profile-path': re.compile(r'(?i)(?:[A-Z]:[\\/]+(?:Users|Documents and Settings)[\\/]|/(?:Users|home)/)[^\s"\'<>]+'),
        'email-address': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
    }
    findings = []
    metadata_findings = []
    link_errors = []
    hashes = {}
    sizes = {}
    images = 0
    text_files = 0
    for name in candidates:
        path = ROOT / name
        if path.is_symlink():
            findings.append(dict(path=name, category='symlink-review', line=0))
            continue
        data = path.read_bytes()
        hashes[name] = hashlib.sha256(data).hexdigest()
        sizes[name] = len(data)
        if path.suffix.lower() in PRIVATE_SUFFIXES or path.name.startswith('.env'):
            findings.append(dict(path=name, category='sensitive-or-generated-file', line=0))
        if len(data) > 10 * 1024**2:
            findings.append(dict(path=name, category='large-file-review', line=0))
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {'.gitignore', '.gitattributes', 'LICENSE'}:
            text_files += 1
            content = data.decode('utf-8-sig')
            for category, pattern in patterns.items():
                for match in pattern.finditer(content):
                    findings.append(dict(path=name, category=category, line=content.count('\n', 0, match.start()) + 1))
            # Public entry docs must not rely on ignored build/test output.
            if name in {'README.md', 'THIRD_PARTY_NOTICES.md'}:
                for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', content):
                    if re.match(r'[a-z]+://|#', target):
                        continue
                    local = (path.parent / unquote(target.split('#')[0])).resolve()
                    if not local.exists() or not local.is_relative_to(ROOT):
                        link_errors.append(dict(path=name, target=target))
                    elif local.is_file() and local.relative_to(ROOT).as_posix() not in candidates:
                        link_errors.append(dict(path=name, target=target, reason='ignored public document link'))
        if path.suffix.lower() in IMAGE_SUFFIXES:
            images += 1
            with Image.open(path) as image:
                for key in image.getexif():
                    tag = ExifTags.TAGS.get(key, str(key))
                    metadata_findings.append(dict(path=name, tag=tag))
                for key in image.info:
                    if key.lower() in {'author', 'comment', 'description', 'exif', 'xml:com.adobe.xmp', 'xmp'}:
                        metadata_findings.append(dict(path=name, tag=key))

    report = dict(result='PASS' if not (findings or metadata_findings or link_errors) else 'REVIEW',
                  root_repository_exists=False, commit_or_remote_operations=False,
                  git_initialized=existing_metadata is None,
                  candidate_files=len(candidates), candidate_size_mib=round(sum(sizes.values())/1024**2, 2),
                  text_files_scanned=text_files, images_metadata_checked=images,
                  ignore_samples_checked=len(samples), findings=findings,
                  image_metadata_review=metadata_findings, public_document_link_errors=link_errors,
                  groups=dict(Counter(p.split('/')[0] if '/' in p else '(root)' for p in candidates)),
                  license_present=any((ROOT/p).is_file() for p in ('LICENSE','LICENSE.md','LICENSE.txt')),
                  notice='Heuristic scan; review copyright-holder confirmation and third-party terms separately.')
    (directory/'audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (directory/'candidate-files.txt').write_text('\n'.join(candidates)+'\n', encoding='utf-8')
    (directory/'candidate-sha256.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path, help='New ignored .test-artifacts subdirectory')
    parser.add_argument('--git-metadata', type=Path, help='Reuse existing ignored audit metadata read-only; do not initialize Git')
    args = parser.parse_args()
    raise SystemExit(0 if run(args.results,args.git_metadata)['result'] == 'PASS' else 1)

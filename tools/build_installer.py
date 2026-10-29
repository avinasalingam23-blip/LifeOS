"""Build an installer from dist/LifeOS without rebuilding or modifying the app."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
import uuid

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from check_packaged import audit, inventory

ROOT = Path(__file__).resolve().parents[1]


def inside(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT) or path == ROOT:
        raise ValueError(f'Generated path is outside the project: {path}')
    return path


def notices(destination):
    destination.mkdir()
    project = tomllib.loads((ROOT/'pyproject.toml').read_text())['project']
    pending = [Requirement(r).name for r in project['dependencies']]
    seen = set()
    report = []
    while pending:
        name = canonicalize_name(pending.pop())
        if name in seen:
            continue
        seen.add(name)
        dist = metadata.distribution(name)
        for value in dist.requires or []:
            requirement = Requirement(value)
            if not requirement.marker or requirement.marker.evaluate({'extra': ''}):
                pending.append(requirement.name)
        report.append(copy_notices(dist, destination))
    # PyInstaller's bootloader accompanies this binary; retain its exception.
    report.append(copy_notices(metadata.distribution('pyinstaller'), destination))
    for label, source in (
        ('Python-LICENSE.txt', Path(sys.base_prefix)/'LICENSE.txt'),
        ('Tcl-license.terms', Path(sys.base_prefix)/'tcl/tcl8.6/license.terms'),
        ('Tk-license.terms', Path(sys.base_prefix)/'tcl/tk8.6/license.terms'),
    ):
        if source.is_file():
            shutil.copyfile(source, destination/label)
        else:
            report.append(dict(name=label, notices=0, review='Original notice not found at the standard runtime location'))
    shutil.copyfile(ROOT/'THIRD_PARTY_NOTICES.md', destination/'LifeOS-THIRD_PARTY_NOTICES.md')
    (destination/'README.txt').write_text(
        'Third-party licenses retain their original holders and terms.\n'
        'These copies supplement the unchanged verified portable package.\n'
        'LifeOS source copyright-holder confirmation and Python-logo policy review remain separate.\n'
        'No project-wide ownership of third-party code, photos or marks is claimed.\n', encoding='utf-8')
    (destination/'dependency-inventory.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def copy_notices(dist, destination):
    name = canonicalize_name(dist.metadata['Name'])
    count = 0
    for relative in dist.files or []:
        if not (any(p.lower() == 'licenses' for p in relative.parts) or
                relative.name.lower().startswith(('license', 'licence', 'copying', 'notice'))):
            continue
        if '..' in relative.parts:
            raise ValueError('Unexpected license path outside its distribution')
        source = Path(dist.locate_file(relative))
        if source.is_file():
            target = destination/name/Path(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            count += 1
    return dict(name=name, version=dist.version, notices=count,
                license=(dist.metadata.get('License-Expression') or dist.metadata.get('License') or 'See upstream notice').splitlines()[0])


def build(compiler):
    compiler = Path(compiler).resolve()
    if not compiler.is_file():
        raise ValueError('Obtain Inno Setup from https://jrsoftware.org/isdl.php first; no compiler is installed automatically.')
    package = ROOT/'dist/LifeOS'
    package_audit = audit(package/'LifeOS.exe')
    original = inventory(package)
    recorded = json.loads((package/'BUILD_INFO.json').read_text())
    assert recorded['exe_sha256'] == package_audit['exe_sha256'], 'Verified executable has changed'
    script = ROOT/'installer/LifeOS.iss'
    text = script.read_text()
    assert not re.search(r'^\[(?:UninstallDelete|InstallDelete|Registry|Dirs|Code)\]', text, re.M|re.I)
    assert 'DefaultDirName={autopf}\\LifeOS' in text and 'PrivilegesRequired=admin' in text
    job = inside(ROOT/'build'/('installer-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]))
    job.mkdir(parents=True)
    notice_directory = job/'notices'
    license_inventory = notices(notice_directory)
    staged = job/'output'
    staged.mkdir()
    version = tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
    engine = subprocess.run([str(compiler), '--version'], capture_output=True, text=True)
    # Inno Setup 7 uses long options. Retain traditional options for 6.x.
    modern = engine.returncode == 0 and '7.' in (engine.stdout+engine.stderr)
    command = [str(compiler)]
    if modern:
        command += ['--quiet', f'--output-dir={staged}', f'--define=PayloadDir={package}',
                    f'--define=NoticesDir={notice_directory}', f'--define=AppVersion={version}']
    else:
        command += ['/Q', f'/O{staged}', f'/DPayloadDir={package}',
                    f'/DNoticesDir={notice_directory}', f'/DAppVersion={version}']
    command.append(str(script))
    print('Compiling LifeOS installer from the unchanged verified package...', flush=True)
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    (job/'compiler.log').write_text(result.stdout+'\n'+result.stderr, encoding='utf-8')
    if result.returncode:
        raise RuntimeError('Inno Setup failed: '+result.stdout[-4000:]+'\n'+result.stderr[-2000:])
    assert inventory(package) == original, 'The portable folder changed during packaging'
    installer = staged/'LifeOS-Setup.exe'
    assert installer.is_file() and installer.stat().st_size > 1_000_000
    report = dict(app_version=version, compiler_version=(engine.stdout+engine.stderr).strip(),
                  built_utc=datetime.now(timezone.utc).isoformat(),
                  installer_sha256=hashlib.sha256(installer.read_bytes()).hexdigest(),
                  executable_sha256=package_audit['exe_sha256'], payload_files=len(original),
                  package_unchanged=True, package_inventory_sha256=hashlib.sha256(json.dumps(original, sort_keys=True).encode()).hexdigest(),
                  script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
                  notices=license_inventory, notice_files=len(inventory(notice_directory)),
                  normal_install='Program Files/LifeOS; administrative installation',
                  user_data='%LOCALAPPDATA%/LifeOS; preserved on uninstall', signed=False)
    (staged/'BUILD_INFO.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (job/'payload-sha256.json').write_text(json.dumps(original, indent=2), encoding='utf-8')
    (staged/'INSTALL.txt').write_text(
        'LifeOS Windows x64 installer\n\n'
        'Run LifeOS-Setup.exe, approve Windows UAC, keep Program Files\\LifeOS,\n'
        'choose whether to create a desktop shortcut, and install.\n'
        'Launch from Start > LifeOS or the optional desktop shortcut.\n'
        'No separate Python installation is required. Close LifeOS before upgrading.\n\n'
        'SQLite, backups and logs stay in %LOCALAPPDATA%\\LifeOS.\n'
        'Uninstall via Windows Settings > Apps > Installed apps > LifeOS.\n'
        'Uninstall removes program files and shortcuts, not your personal data.\n'
        'The installer and application are unsigned; this is a local test build.\n'
        'Another-machine/UAC Program Files verification remains a manual check\n'
        'unless explicitly recorded otherwise in PROJECT_STATUS.md.\n', encoding='utf-8')
    output = inside(ROOT/'dist/installer')
    if output.exists():
        archived = inside(ROOT/'dist/archive'/('installer-'+job.name))
        assert not archived.exists()
        archived.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(inside(output)), str(archived))
    shutil.move(str(inside(staged)), str(output))
    print(json.dumps(dict(result='BUILT', installer=str(output/'LifeOS-Setup.exe'),
                         size_mib=round(installer_size(output)/1024**2, 2),
                         payload_files=report['payload_files'], notice_files=report['notice_files'],
                         missing_notices=[r['name'] for r in license_inventory if not r['notices']],
                         installer_sha256=report['installer_sha256']), indent=2), flush=True)


def installer_size(output):
    return (output/'LifeOS-Setup.exe').stat().st_size


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', required=True, type=Path)
    build(parser.parse_args().compiler)

"""Exercise the exact installer in a new isolated directory using /CURRENTUSER.

Creates/removes only its own test installation, Start Menu group and optional
desktop shortcut. Never opens the normal LifeOS profile. Refuses an existing
LifeOS registration and preserves any pre-existing desktop shortcut.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import time
import uuid
import winreg

from check_packaged import inventory, normal_window, rows

ROOT = Path(__file__).resolve().parents[1]
APP_KEY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{02C71D19-97DA-4094-80F3-5D2348B5975C}_is1'


def registration(hive):
    try:
        with winreg.OpenKey(hive, APP_KEY, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            return {name: winreg.QueryValueEx(key, name)[0] for name in
                    ('DisplayName','InstallLocation','UninstallString','QuietUninstallString','NoModify','NoRepair')}
    except FileNotFoundError:
        return None


def special_folder(number):
    buffer = ctypes.create_unicode_buffer(32768)
    result = ctypes.windll.shell32.SHGetFolderPathW(None, number, None, 0, buffer)
    assert result == 0, result
    return Path(buffer.value)


def shortcut_info(path, env):
    settings = dict(env, LIFEOS_TEST_SHORTCUT=str(path))
    command = "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:LIFEOS_TEST_SHORTCUT); [pscustomobject]@{target=$s.TargetPath;working_directory=$s.WorkingDirectory;arguments=$s.Arguments}|ConvertTo-Json"
    result = subprocess.run(['powershell.exe','-NoProfile','-Command',command], env=settings,
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def same_records(before, after):
    assert set(before) == set(after)
    for table, records in before.items():
        current = {row[0]:row for row in after[table]}
        assert all(current.get(row[0]) == row for row in records), table
        if table != 'tasks':
            assert len(after[table]) == len(records), table


def run(directory):
    directory = Path(directory).resolve()
    assert directory.is_relative_to(ROOT/'.test-artifacts') and directory != ROOT/'.test-artifacts'
    assert not registration(winreg.HKEY_CURRENT_USER), 'An existing LifeOS user installation must be preserved'
    assert not registration(winreg.HKEY_LOCAL_MACHINE), 'An existing LifeOS machine installation must be preserved'
    directory.mkdir(parents=True, exist_ok=False)
    target = directory/'installed application'
    installer = ROOT/'dist/installer/LifeOS-Setup.exe'
    original_package = inventory(ROOT/'dist/LifeOS')
    installer_hash = hashlib.sha256(installer.read_bytes()).hexdigest()
    group_name = 'LifeOS Installer Verification '+uuid.uuid4().hex[:8]
    group = special_folder(2)/group_name
    desktop = special_folder(0x10)/'LifeOS.lnk'
    assert not group.exists()
    original_desktop = desktop.read_bytes() if desktop.exists() else None
    profile_root = directory/'local-app-data'
    env = dict(os.environ)
    for key in ('LIFEOS_DATA_DIR','PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'):
        env.pop(key, None)
    env['LOCALAPPDATA'] = str(profile_root)
    env['MPLCONFIGDIR'] = str(directory/'plot-cache')
    env['PATH'] = os.pathsep.join([str(Path(os.environ['SystemRoot'])/'System32'), os.environ['SystemRoot']])
    profile = profile_root/'LifeOS/lifeos.sqlite3'
    profile.parent.mkdir(parents=True)
    # Use an earlier isolated test profile with real saved rows, never the user's.
    source = ROOT/'.test-artifacts/packaged-verification-03/local-app-data/LifeOS/lifeos.sqlite3'
    assert source.is_relative_to(ROOT/'.test-artifacts') and source.is_file()
    with sqlite3.connect(source.as_uri()+'?mode=ro', uri=True) as old, sqlite3.connect(profile) as new:
        old.backup(new)
    before = rows(profile)
    marker = profile.parent/'user-data-must-survive.txt'
    marker.write_text('Keep the isolated profile and backups after uninstall.\n')
    (profile.parent/'backups').mkdir(exist_ok=True)
    backup_marker = profile.parent/'backups/preserved.txt'
    backup_marker.write_text('Keep this backup.\n')
    user_note = target/'user-created-note.txt'

    def install(cycle, checked):
        print(f'Install cycle {cycle}: desktop shortcut {checked}', flush=True)
        command = [str(installer), '/CURRENTUSER','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',
                   f'/DIR={target}', f'/GROUP={group_name}', '/TASKS='+('desktopicon' if checked else ''),
                   f'/LOG={directory}/install-{cycle}.log']
        result = subprocess.run(command, env=env, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode == 0, ('setup', result.returncode)
        info = registration(winreg.HKEY_CURRENT_USER)
        assert info and info['DisplayName'] == 'LifeOS' and info['NoModify'] == info['NoRepair'] == 1
        assert Path(info['InstallLocation']).resolve() == target.resolve()
        assert not registration(winreg.HKEY_LOCAL_MACHINE)
        for name, digest in original_package.items():
            assert hashlib.sha256((target/name).read_bytes()).hexdigest() == digest, name
        assert len(list((target/'ThirdParty-Notices').rglob('*LICENSE*'))) > 5
        entry = group/'LifeOS.lnk'
        assert entry.is_file()
        link = shortcut_info(entry, env)
        assert Path(link['target']).resolve() == (target/'LifeOS.exe').resolve()
        assert Path(link['working_directory']).resolve() == target.resolve() and not link['arguments']
        if checked:
            assert desktop.is_file()
            assert Path(shortcut_info(desktop, env)['target']).resolve() == (target/'LifeOS.exe').resolve()
        else:
            assert (desktop.read_bytes() if desktop.exists() else None) == original_desktop
        same_records(before, rows(profile))

    def uninstall(cycle, checked):
        info = registration(winreg.HKEY_CURRENT_USER)
        assert info and Path(info['InstallLocation']).resolve() == target.resolve()
        executable = Path(info['UninstallString'].strip('"')).resolve()
        # Validate the exact uninstaller's absolute target before its deletions.
        assert executable.parent == target.resolve() and target.is_relative_to(directory)
        assert executable.name == 'unins000.exe' and executable.is_file()
        result = subprocess.run([str(executable),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',
                                 f'/LOG={directory}/uninstall-{cycle}.log'],
                                env=env, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode == 0, ('uninstall', result.returncode)
        # The uninstall loader can return before its temporary final cleanup
        # marker disappears. Wait for all managed/self-cleanup files, not just
        # LifeOS.exe, while leaving the intentional unmanaged file untouched.
        until = time.monotonic()+15
        while any(path.is_file() for path in target.rglob('*') if path != user_note) and time.monotonic() < until:
            time.sleep(.1)
        assert not (target/'LifeOS.exe').exists()
        assert not registration(winreg.HKEY_CURRENT_USER) and not registration(winreg.HKEY_LOCAL_MACHINE)
        assert not (group/'LifeOS.lnk').exists()
        if checked:
            assert not desktop.exists()
        else:
            assert (desktop.read_bytes() if desktop.exists() else None) == original_desktop
        assert user_note.read_text() == 'Unmanaged files must survive.\n'
        assert marker.is_file() and backup_marker.is_file()
        same_records(before, rows(profile))
        assert not any(path.is_file() for path in target.rglob('*') if path != user_note), 'Managed files remained after uninstall'

    install(1, False)
    user_note.write_text('Unmanaged files must survive.\n')
    smoke = directory/'installed-smoke'
    print('Checking the installed application GUI in both themes', flush=True)
    result = subprocess.run([str(target/'LifeOS.exe'),'--smoke-test','--data-dir',str(smoke)],
                            cwd=directory, env=env, capture_output=True, text=True, timeout=360,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    (directory/'installed-process.txt').write_text(result.stdout+'\n'+result.stderr)
    assert result.returncode == 0, result.stderr
    smoke_result = json.loads((smoke/'smoke-results.json').read_text())
    assert smoke_result['result'] == 'PASS' and smoke_result['frozen'] and smoke_result['themes_checked'] == 2
    assert not smoke_result['network_attempts'] and not (smoke/'callback-errors.txt').exists()
    normal_window(target/'LifeOS.exe', directory, env, directory, 1)
    same_records(before, rows(profile))
    uninstall(1, False)
    print('First uninstall preserved the external database, backups and unmanaged file', flush=True)
    checked = original_desktop is None
    install(2, checked)
    normal_window(target/'LifeOS.exe', directory, env, directory, 2)
    uninstall(2, checked)
    assert inventory(ROOT/'dist/LifeOS') == original_package
    assert hashlib.sha256(installer.read_bytes()).hexdigest() == installer_hash
    report = dict(result='PASS', install_cycles=2, uninstall_cycles=2, original_package_unchanged=True,
                  installed_payload_identical=True, user_registration_added_removed=True,
                  start_menu_shortcut_verified=True, desktop_unchecked_verified=True,
                  desktop_checked_verified=checked, preexisting_desktop_preserved=True,
                  external_records_and_backups_preserved=True, unmanaged_app_file_preserved=True,
                  reinstall_persistence=True, installed_gui=smoke_result, live_profile_opened=False,
                  actual_program_files_and_uac_tested=False, installer_sha256=installer_hash)
    (directory/'installer-results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path)
    run(parser.parse_args().results)

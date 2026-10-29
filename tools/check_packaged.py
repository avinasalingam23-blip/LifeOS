"""Audit and exercise a relocated Windows package without opening the live profile."""
from pathlib import Path
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import time
import types
import psutil
from PIL import ImageGrab
from PyInstaller.archive.readers import CArchiveReader


def inventory(folder):
    return {p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}


def audit(executable):
    folder=executable.parent;files=list(folder.rglob('*'))
    forbidden=[]
    for path in files:
        relative=path.relative_to(folder)
        if any(p.lower() in ('.venv','.git','.test-artifacts','__pycache__','backups') for p in relative.parts):forbidden.append(str(relative))
        if path.is_file() and (path.suffix.lower() in ('.sqlite','.sqlite3','.db','.log','.pem','.key') or path.name.startswith('.env')):forbidden.append(str(relative))
    assert not forbidden,forbidden
    root=folder/'_internal'
    for name in ('schema.sql','migration_2.sql'):assert (root/'lifeos'/name).is_file(),name
    assets=root/'lifeos'/'assets'
    manifest=json.loads((assets/'icon-manifest.json').read_text())
    for name in manifest:
        assert (assets/'python-logo.png' if name=='python-logo' else assets/'icons'/(name+'.png')).is_file(),name
    backgrounds=json.loads((assets/'backgrounds'/'manifest.json').read_text())
    for photo in backgrounds['photos'].values():
        path=assets/'backgrounds'/photo['asset']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==photo['processed_sha256'],str(path)
    assert list((root/'customtkinter').rglob('*.ttf')),'Missing CustomTkinter fonts'
    assert list((root/'matplotlib'/'mpl-data').rglob('*.ttf')),'Missing plot fonts'
    assert (root/'python313.dll').is_file() and (root/'_sqlite3.pyd').is_file()
    archive=CArchiveReader(str(executable)).open_embedded_archive('PYZ.pyz')
    assert 'lifeos.workout_checklist' in archive.toc
    assert 'lifeos.ui.appearance' in archive.toc
    assert 'lifeos.ai' not in archive.toc and 'lifeos.ui.assistant' not in archive.toc
    code=archive.extract('lifeos.ui.fitness')
    workout=next(c for c in code.co_consts if isinstance(c,types.CodeType) and c.co_name=='WorkoutPage')
    assert {'save_target','toggle_target','reset_day','flush'}<=set(workout.co_names)
    assert not {'start','finish_workout','open_session'}&set(workout.co_names),'Old session UI was packaged'
    return dict(files=sum(p.is_file() for p in files),size_mib=round(sum(p.stat().st_size for p in files if p.is_file())/2**20,2),
                icons=len(manifest),photographs=len(backgrounds['photos']),latest_checklist=True,no_personal_files=True,
                exe_sha256=hashlib.sha256(executable.read_bytes()).hexdigest())


def rows(path):
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as conn:
        tables=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {t:conn.execute('SELECT rowid,* FROM "'+t+'" ORDER BY rowid').fetchall() for t in tables}


def normal_window(executable,cwd,env,directory,cycle):
    user32=ctypes.windll.user32
    user32.SetProcessDPIAware()
    user32.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
    user32.IsWindowVisible.argtypes=[wintypes.HWND]
    user32.GetWindow.argtypes=[wintypes.HWND,ctypes.c_uint];user32.GetWindow.restype=wintypes.HWND
    user32.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    user32.PostMessageW.argtypes=[wintypes.HWND,ctypes.c_uint,wintypes.WPARAM,wintypes.LPARAM]
    process=subprocess.Popen([str(executable)],cwd=cwd,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
    handles=[]
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    @callback_type
    def visit(hwnd,parameter):
        pid=wintypes.DWORD();user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        title=ctypes.create_unicode_buffer(300);user32.GetWindowTextW(hwnd,title,300)
        if pid.value==process.pid and user32.IsWindowVisible(hwnd) and title.value.startswith('LifeOS'):handles.append(hwnd)
        return True
    hwnd=None
    try:
        until=time.monotonic()+40
        while time.monotonic()<until and not handles:
            assert process.poll() is None,'The packaged app exited during startup'
            user32.EnumWindows(visit,0);time.sleep(.15)
        assert handles,'No packaged application window appeared'
        def area(window):
            rect=wintypes.RECT();user32.GetWindowRect(window,ctypes.byref(rect));return (rect.right-rect.left)*(rect.bottom-rect.top)
        hwnd=max(handles,key=area);client=user32.GetWindow(hwnd,5) or hwnd
        time.sleep(2)
        ImageGrab.grab(window=client).save(directory/f'normal-{cycle}-dashboard.png')
        # Page actions/themes are already exercised by the frozen smoke above.
        # Ordinary restarts verify default storage/runtime without stealing the
        # user's mouse focus or relying on display-coordinate clicks.
        mapped=[m.path for m in psutil.Process(process.pid).memory_maps()]
        assert any(Path(m).name.lower()=='python313.dll' and Path(m).is_relative_to(executable.parent) for m in mapped),'Python DLL was not loaded from the portable package'
        user32.PostMessageW(hwnd,0x0010,0,0)
        assert process.wait(timeout=30)==0
    finally:
        if process.poll() is None and hwnd:
            user32.PostMessageW(hwnd,0x0010,0,0)
            process.wait(timeout=30)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('executable',type=Path);parser.add_argument('results',type=Path);parser.add_argument('relocation',type=Path);parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();source=args.executable.resolve();directory=args.results.resolve();relocation=args.relocation.resolve()
    directory.mkdir(parents=True,exist_ok=args.resume);relocation.mkdir(parents=True,exist_ok=args.resume)
    assert source.name=='LifeOS.exe'
    report=audit(source)
    package=relocation/'LifeOS'
    if not args.resume:shutil.copytree(source.parent,package)
    executable=package/'LifeOS.exe';cwd=relocation/'unrelated-working-directory';cwd.mkdir(exist_ok=args.resume)
    assert inventory(package)==inventory(source.parent),'Relocated files differ from the tested build'
    before_package=inventory(package)
    env=dict(os.environ)
    for key in ('PYTHONHOME','PYTHONPATH','LIFEOS_DATA_DIR','VIRTUAL_ENV'):env.pop(key,None)
    windows=os.environ['SystemRoot']
    env['PATH']=os.pathsep.join([str(Path(windows)/'System32'),windows])
    env['LOCALAPPDATA']=str(directory/'local-app-data');env['MPLCONFIGDIR']=str(directory/'plot-cache')
    smoke=directory/'frozen-smoke'
    if not args.resume:
        print('Starting relocated executable smoke check',flush=True)
        completed=subprocess.run([str(executable),'--smoke-test','--data-dir',str(smoke)],cwd=cwd,env=env,capture_output=True,text=True,timeout=360,creationflags=subprocess.CREATE_NO_WINDOW)
        (directory/'frozen-process.txt').write_text(completed.stdout+'\n'+completed.stderr,encoding='utf-8')
        assert completed.returncode==0,(completed.returncode,completed.stdout,completed.stderr)
    result=json.loads((smoke/'smoke-results.json').read_text())
    assert result['result']=='PASS' and result['frozen'] and result['themes_checked']==2 and not result['network_attempts']
    assert not (smoke/'callback-errors.txt').exists()
    profile=Path(env['LOCALAPPDATA'])/'LifeOS'/'lifeos.sqlite3';profile.parent.mkdir(parents=True,exist_ok=args.resume)
    if not args.resume:
        with sqlite3.connect((smoke/'gui-smoke.sqlite3').as_uri()+'?mode=ro',uri=True) as original,sqlite3.connect(profile) as target:original.backup(target)
    before=rows(profile)
    print('Frozen smoke PASS; checking two ordinary launches and persistent external data',flush=True)
    for cycle in (1,2):
        normal_window(executable,cwd,env,directory,cycle)
        after=rows(profile)
        for table,records in before.items():
            by_id={r[0]:r for r in after[table]}
            assert all(by_id.get(r[0])==r for r in records),(table,'An existing row changed on restart')
            if table!='tasks':assert len(after[table])==len(records),(table,'Unexpected new record')
        with sqlite3.connect(profile) as conn:
            assert json.loads(conn.execute("SELECT value FROM settings WHERE key='theme'").fetchone()[0])=='CMD / Robotic Command Center'
            doc=json.loads(conn.execute('SELECT values_json FROM fitness_preferences WHERE id=1').fetchone()[0])['weekly_workout_checklist']
            assert any(t['completed'] and t['name']=='Incline push-ups' for t in doc['days']['Monday']['targets'])
    assert inventory(package)==before_package,'The application wrote into the portable folder'
    audit(executable)
    log=profile.with_name('lifeos.log');assert log.is_file() and 'ERROR' not in log.read_text(encoding='utf-8')
    report.update(result='PASS',frozen_smoke=result,relocated=True,unrelated_working_directory=True,
                  normal_launches=2,bundled_python_loaded=True,external_default_profile=True,existing_rows_preserved=True,
                  theme_and_checklist_persisted=True,package_unmodified=True,live_profile_opened=False)
    (directory/'packaged-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)


if __name__=='__main__':main()

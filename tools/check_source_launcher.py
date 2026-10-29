"""Windows-only launch/close verification of the actual source launcher.

Uses a new explicit test profile. Finds only its newly created pythonw process,
captures only that process's window, and sends that exact window WM_CLOSE.
"""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import psutil
from PIL import ImageGrab

def main():
    root=Path(__file__).resolve().parents[1]
    directory=Path(sys.argv[1]).resolve()
    resume=len(sys.argv)>2 and sys.argv[2]=='--resume'
    if directory.exists() and not resume:
        raise ValueError('Use a new isolated test directory.')
    if not directory.is_relative_to(root/'.test-artifacts'):
        raise ValueError('Launcher checks must use a project-local .test-artifacts profile.')
    directory.mkdir(parents=True,exist_ok=resume)
    env={**os.environ,'LIFEOS_DATA_DIR':str(directory)}
    started=0 if resume else time.time()
    if not resume:
        subprocess.run(['cmd.exe','/c',str(root/'Launch LifeOS.cmd')],cwd=root,env=env,
                       creationflags=subprocess.CREATE_NO_WINDOW,check=True)
    process=None
    until=time.monotonic()+25
    candidates={}
    def find_processes():
        for candidate in psutil.process_iter(['name','create_time','cmdline']):
            try:
                if (candidate.info['name'].lower()=='pythonw.exe' and candidate.info['create_time']>=started-1
                    and 'main.py' in candidate.info['cmdline'] and candidate.environ().get('LIFEOS_DATA_DIR')==str(directory)):
                    candidates[candidate.pid]=candidate
            except (psutil.NoSuchProcess,psutil.AccessDenied):
                pass
    user32=ctypes.windll.user32
    user32.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
    user32.IsWindowVisible.argtypes=[wintypes.HWND]
    user32.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    user32.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    user32.GetWindow.argtypes=[wintypes.HWND,wintypes.UINT]
    user32.GetWindow.restype=wintypes.HWND
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    handles=[]
    @callback_type
    def inspect_window(hwnd,lparam):
        nonlocal process
        pid=wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        title=ctypes.create_unicode_buffer(300)
        user32.GetWindowTextW(hwnd,title,300)
        if pid.value in candidates and user32.IsWindowVisible(hwnd) and title.value.startswith('LifeOS'):
            handles.append(hwnd)
            process=candidates[pid.value]
        return True
    while time.monotonic()<until and not handles:
        # Windows venv pythonw may be a redirector with a second pythonw child.
        # Match the actual window-owning process, not the first redirector PID.
        find_processes()
        user32.EnumWindows(inspect_window,0)
        time.sleep(.1)
    if not handles:
        raise AssertionError('No LifeOS source window appeared.')
    time.sleep(2)
    def area(hwnd):
        rect=wintypes.RECT()
        user32.GetWindowRect(hwnd,ctypes.byref(rect))
        return max(0,rect.right-rect.left)*max(0,rect.bottom-rect.top)
    hwnd=max(handles,key=area)
    captured=False
    try:
        # Tk's outer Windows wrapper may not support PrintWindow; its actual
        # client child is the same target used by Tk.winfo_id() in GUI checks.
        client=user32.GetWindow(hwnd,5)  # GW_CHILD
        ImageGrab.grab(window=client or hwnd).save(directory/'launcher-dashboard.png')
        captured=True
    except OSError as error:
        (directory/'capture-note.txt').write_text(str(error),encoding='utf-8')
    finally:
        user32.PostMessageW(hwnd,0x0010,0,0)
    process.wait(timeout=20)
    log=directory/'lifeos.log'
    assert log.exists() and 'ERROR' not in log.read_text(encoding='utf-8'),'Source launch logged an error'
    result=dict(result='PASS',launcher='Launch LifeOS.cmd',source_process=True,graceful_close=True,captured=captured,isolated_profile=str(directory))
    (directory/'launcher-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':
    main()

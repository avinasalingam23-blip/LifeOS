"""LifeOS application entry point; also used by the Windows executable."""
import argparse
import logging
import os
import sys
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description='LifeOS local desktop application')
    parser.add_argument('--data-dir',help='Optional alternate data directory for a separate profile or testing')
    parser.add_argument('--smoke-test',action='store_true',help='Run native GUI checks using a new isolated --data-dir; never uses your normal profile')
    args=parser.parse_args()
    if args.data_dir:
        os.environ['LIFEOS_DATA_DIR']=str(Path(args.data_dir).resolve())
    if args.smoke_test:
        if not args.data_dir:
            parser.error('--smoke-test requires a new, isolated --data-dir')
        from lifeos.smoke import run
        print(run(args.data_dir))
        return 0
    from lifeos.db import data_directory
    directory=data_directory()
    directory.mkdir(parents=True,exist_ok=True)
    from logging.handlers import RotatingFileHandler
    logging.basicConfig(level=logging.INFO,handlers=[RotatingFileHandler(directory/'lifeos.log',maxBytes=1_000_000,backupCount=3,encoding='utf-8')],format='%(asctime)s %(levelname)s %(message)s')
    try:
        from lifeos.ui.app import LifeOS
        app=LifeOS()
        app.mainloop()
    except Exception:
        logging.exception('Application startup failed')
        import tkinter as tk
        from tkinter import messagebox
        root=tk.Tk()
        root.withdraw()
        messagebox.showerror('LifeOS could not start','See '+str(directory/'lifeos.log')+' for details.\n'+str(sys.exc_info()[1]))
        root.destroy()
        return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())

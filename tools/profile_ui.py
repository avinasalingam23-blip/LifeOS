"""Measure real native navigation and wheel events on an isolated profile."""
import cProfile
import io
import json
from pathlib import Path
import pstats
import sqlite3
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def main():
    directory=Path(sys.argv[1]).resolve()
    directory.mkdir(parents=True,exist_ok=False)
    source=Path('.test-artifacts/gui-ui-cleanup-02/gui-smoke.sqlite3').resolve()
    database=directory/'profile.sqlite3'
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as original,sqlite3.connect(database) as target:
        original.backup(target)
    from lifeos.db import Database
    from lifeos.ui.app import LifeOS,PAGES
    from lifeos.ui.collections import PhotoRecordList
    app=LifeOS(Database(database))
    errors=[]
    app.report_callback_exception=lambda exc,value,tb:errors.append(str(value))
    def settle():
        app.update()
        app.update_idletasks()
    def lists(widget):
        found=[]
        for child in widget.winfo_children():
            if isinstance(child,PhotoRecordList) and child.winfo_ismapped(): found.append(child)
            found.extend(lists(child))
        return found
    profile=cProfile.Profile()
    navigation=[];wheels=[]
    try:
        profile.enable()
        for cycle in range(2):
            for page in PAGES:
                start=time.perf_counter();app.show(page);settle()
                navigation.append(dict(page=page,cycle=cycle,ms=round((time.perf_counter()-start)*1000,2)))
                if cycle==0:
                    candidates=lists(app.content)
                    target=candidates[0] if candidates else app.page_frame
                    before=app.wallpaper.render_count
                    frames=[]
                    for i in range(12):
                        start=time.perf_counter()
                        target.event_generate('<MouseWheel>',delta=-120 if i<6 else 120)
                        settle()
                        frames.append(round((time.perf_counter()-start)*1000,2))
                    wheels.append(dict(page=page,mean_ms=round(sum(frames)/len(frames),2),max_ms=max(frames),
                        full_repaints=app.wallpaper.render_count-before))
        profile.disable()
        stream=io.StringIO();pstats.Stats(profile,stream=stream).strip_dirs().sort_stats('cumulative').print_stats(45)
        (directory/'profile.txt').write_text(stream.getvalue(),encoding='utf-8')
        profile.dump_stats(str(directory/'profile.pstats'))
        result=dict(navigation=navigation,wheels=wheels,callback_errors=errors)
        (directory/'metrics.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result))
        assert not errors,errors
    finally:
        app.close()

if __name__=='__main__':main()

"""Navigation-only regression check: every saved row/schema must remain identical."""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def snapshot(path):
    with sqlite3.connect(path) as conn:
        tables=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return dict(schema=conn.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY name').fetchall(),
                    rows={table:conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall() for table in tables},
                    columns={table:[r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')] for table in tables},
                    version=conn.execute('PRAGMA user_version').fetchone()[0])

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('database',type=Path)
    args=parser.parse_args()
    if not args.database.is_file():
        raise ValueError('Select an existing isolated test profile.')
    before=snapshot(args.database)
    from lifeos.db import Database
    from lifeos.ui.app import LifeOS,PAGES
    app=LifeOS(Database(args.database))
    failures=[]
    app.report_callback_exception=lambda exc,value,tb:failures.append(str(value))
    for page in PAGES:
        app.show(page)
        app.update()
        if page=='Workout Planner':
            app.page_frame.sections.set('Workout history')
        elif page=='Diet & Nutrition':
            app.page_frame.sections.set('History & library')
        for name,frame in app.record_frames.items():
            app.tabs.set(name)
            app.tab_changed()
            until=time.monotonic()+.16
            while time.monotonic()<until:
                app.update()
                time.sleep(.01)
            assert frame.tree.winfo_ismapped(),name
    resize_checks=0
    for geometry in ('960x600','1235x635','1024x635'):
        app.geometry(geometry)
        app.update()
        app.wallpaper.render()
        assert app.wallpaper.last_error is None,app.wallpaper.last_error
        resize_checks+=1
    # Switch without pumping events to exercise cancellation of retired-page
    # callbacks, then allow the last page to settle and repaint.
    for page in list(PAGES)*2:
        app.show(page)
    app.update()
    app.wallpaper.render()
    assert app.wallpaper.last_error is None,app.wallpaper.last_error
    assert not failures,failures
    app.close()
    after=snapshot(args.database)
    if before['version']==after['version']:
        expected=dict(before)
        expected['rows']=dict(before['rows'])
        if not any(row[0]=='theme' for row in before['rows']['settings']):
            expected['rows']['settings']=[*before['rows']['settings'],('theme','\"Current Theme\"')]
        assert expected==after,'Navigation changed an existing schema or saved record'
    else:
        assert before['version']==1 and after['version']==2,'Unexpected migration'
        # V2 is additive: every original column/value must be identical. New
        # tables must stay empty when navigating; no sample fitness plan is seeded.
        with sqlite3.connect(args.database) as conn:
            for table,columns in before['columns'].items():
                projection=','.join('"'+c+'"' for c in columns)
                assert conn.execute(f'SELECT {projection} FROM "{table}" ORDER BY rowid').fetchall()==before['rows'][table],table
            for table in set(after['rows'])-set(before['rows']):
                assert after['rows'][table]==[],table
    print(json.dumps(dict(result='PASS',schema_unchanged=before['version']==after['version'],all_saved_rows_unchanged=True,
                          navigation_pages=len(PAGES),resize_checks=resize_checks,rapid_navigation_changes=len(PAGES)*2,
                          callback_errors=failures,profile=str(args.database),schema_version=after['version'],additive_migration=before['version']!=after['version'])))

if __name__=='__main__':
    main()

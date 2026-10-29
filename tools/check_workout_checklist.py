"""Verify the real weekly checklist, legacy preservation, themes and process restart."""
from pathlib import Path
import json
import sqlite3
import subprocess
import sys
import time
from datetime import date
from tkinter import messagebox
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    from lifeos.db import Database
    from lifeos.service import Service
    from lifeos.fitness import FitnessCoach
    from lifeos.workout_checklist import WorkoutChecklist,KEY,progress
    from lifeos.ui.app import LifeOS,PAGES
    from lifeos.ui import appearance
    from PIL import ImageGrab
    directory=Path(sys.argv[1]).resolve();restart='--restart' in sys.argv
    if not restart:directory.mkdir(parents=True,exist_ok=False)
    database=directory/'checklist.sqlite3'
    tables=['workout_routines','workout_days','planned_exercises','workouts','exercise_logs','fitness_sessions','fitness_sets',
            'food_logs','foods','tasks','measurements','paths','problems','water_logs']
    if not restart:
        db=Database(database);service=Service(db);coach=FitnessCoach(service)
        routine=coach.create_template();monday=coach.weekly(routine)[0]
        rid=coach.start(monday['days'][0]['id'],monday['date'])
        for row in coach.session(rid)['exercises']:
            coach.save_set(row['id'],1,reps=0 if row['target_duration'] else 8,duration_min=row['target_duration'])
        coach.finish(rid,'Earlier recorded performance')
        service.save('tasks',dict(title='Preserve my task'))
        service.log_food(service.list('foods')[0]['id'],100,'g',date.today().isoformat(),meal='Lunch')
        before={t:db.query('SELECT * FROM '+t+' ORDER BY rowid') for t in tables}
        (directory/'legacy.json').write_text(json.dumps(before),encoding='utf-8');db.close()
    app=LifeOS(Database(database));errors=[]
    app.report_callback_exception=lambda exc,value,tb:errors.append(str(value))
    def fail(title,message,**kw):raise AssertionError(title+': '+str(message))
    messagebox.showerror=fail;messagebox.askyesno=lambda *a,**k:True
    def pump():app.update();app.update_idletasks()
    def enter(field,value):field.delete(0,'end');field.insert(0,value)
    def capture(name):
        pump();app.wallpaper.render();pump();assert app.wallpaper.last_error is None
        ImageGrab.grab(window=app.winfo_id()).save(directory/name)
    try:
        app.show('Workout Planner');pump();page=app.page_frame
        if restart:
            checkpoint=json.loads((directory/'checkpoint.json').read_text())
            page.select_day('Monday');pump()
            assert page.target_name.get()=='Not submitted yet' and page.target_goal.get()=='Keep this draft'
            assert any(t['id']==checkpoint['checked'] and t['completed'] for t in page.day['targets'])
            assert page.day['muscles']==checkpoint['muscles']
            assert any(t['id']==checkpoint['tuesday'] and t['completed'] for t in page.store.load()['days']['Tuesday']['targets'])
            assert appearance.current()==appearance.COMMAND
            capture('restart-draft-and-checks.png');assert not errors,errors;print('Restart PASS');return
        assert len(page.day_buttons)==7
        for day,button in page.day_buttons.items():button.invoke();pump();assert page.weekday==day
        page.select_day('Monday');pump()
        original_day=app.db.query('SELECT * FROM workout_days')
        page.toggle_muscle('Back');page.toggle_muscle('Abs');pump()
        assert 'Back' in page.day['muscles'] and 'Abs' in page.day['muscles']
        assert app.db.query('SELECT * FROM workout_days')==original_day
        more=page.more_muscles();pump();assert 'Core/abs' in more.picker.selected
        more.picker.toggle('Core/abs');page.apply_muscles(more.picker.selected);more.destroy();pump()
        assert 'Abs' not in page.day['muscles']
        page.toggle_muscle('Abs')
        more=page.more_muscles();pump();more.picker.toggle('Forearms');page.apply_muscles(more.picker.selected);more.destroy();pump()
        # Unsubmitted text survives day switches, without quietly adding a row.
        count=len(page.day['targets'])
        enter(page.target_name,'Push-ups');enter(page.target_goal,'3 \u00d7 15')
        page.select_day('Tuesday');pump();page.select_day('Monday');pump()
        assert page.target_name.get()=='Push-ups' and len(page.day['targets'])==count
        first=page.add_button.invoke();pump();assert page.selected_target()['id']==first
        enter(page.target_name,'Plank');enter(page.target_goal,'60 seconds');second=page.save_target();pump()
        page.target_list.selection_set(second);page.edit_target();enter(page.target_name,'Side plank');enter(page.target_goal,'30 seconds each side');page.add_button.invoke();pump()
        assert page.day['targets'][-1]['name']=='Side plank'
        page.target_list.selection_set(second);page.move_target(-1);pump()
        assert page.day['targets'][-2]['id']==second
        # Checkbox clicks work with no session logger, even on future weekdays.
        page.target_list.select_index(page.target_list.order.index(first));page.target_list.draw()
        box=next(b for b,k in page.target_list.hitboxes if k==('toggle',first))
        page.target_list.event_generate('<Button-1>',x=round((box[0]+box[2])/2),y=round((box[1]+box[3])/2));pump()
        assert next(t for t in page.day['targets'] if t['id']==first)['completed']
        page.target_list.selection_set(first);page.target_list.toggle();pump()
        assert not next(t for t in page.day['targets'] if t['id']==first)['completed']
        page.toggle_target(first);pump()
        before=page.store.load();messagebox.askyesno=lambda *a,**k:False;page.reset_day();assert page.store.load()==before
        messagebox.askyesno=lambda *a,**k:True;page.reset_button.invoke();pump()
        assert progress(page.day)['completed']==0
        assert len(page.day['targets'])==len(before['days']['Monday']['targets'])
        assert page.day['muscles']==before['days']['Monday']['muscles']
        assert page.store.load()['history'][-1]['targets']==before['days']['Monday']['targets']
        page.target_list.selection_set(second);page.remove_target();pump()
        assert all(t['id']!=second for t in page.day['targets'])
        page.toggle_target(first);page.select_day('Tuesday');pump()
        enter(page.target_name,'Pull-ups');enter(page.target_goal,'3 x 8');tuesday=page.save_target();page.toggle_target(tuesday);page.toggle_muscle('Back')
        page.select_day('Monday');pump()
        page.choose_section('Workout history');pump()
        for kind in ('Earlier workouts','Earlier plans','Checklist resets'):
            page.history_kind.set(kind);page.render_history();pump();assert page.history_list.get_children()
            page.history_list.selection_set(page.history_list.get_children()[0]);details=page.history_details();pump();details.destroy();pump()
        page.choose_section('Weekly checklist');pump()
        for i in range(65):page.store.save_target('Monday','Extra target '+str(i),'Any goal text')
        page.render_day();pump();identity=id(page);timings={}
        bindings=str(app.bind_all('<MouseWheel>'))
        for theme,name in ((appearance.COMMAND,'cmd'),(appearance.CURRENT,'current')):
            app.set_theme(theme);pump();assert id(app.page_frame)==identity
            page.target_list.yview('moveto',0);pump();capture(name+'-checklist.png')
            target=page.target_list;photo=target.photo;items=len(target.find_all());repaints=app.wallpaper.render_count;times=[]
            for _ in range(12):
                started=time.perf_counter();target.event_generate('<MouseWheel>',delta=-120);pump();times.append((time.perf_counter()-started)*1000)
            assert target.offset>0 and target.photo is photo and len(target.find_all())<=items+15
            assert app.wallpaper.render_count==repaints
            timings[name]=round(sum(times)/len(times),2)
            app.geometry('960x600');pump();capture(name+'-small.png');app.geometry('1024x635');pump()
        for route in list(PAGES)*3:app.show(route)
        app.show('Workout Planner');pump();assert id(app.page_frame)==identity
        assert str(app.bind_all('<MouseWheel>'))==bindings
        assert not any(hasattr(page,k) for k in ('start','finish_workout','open_session','view_mode'))
        # No changes to any earlier workout, actual set, nutrition, task or schema.
        before=json.loads((directory/'legacy.json').read_text())
        assert {t:app.db.query('SELECT * FROM '+t+' ORDER BY rowid') for t in tables}==before
        assert app.db.one('PRAGMA user_version')['user_version']==2
        assert app.db.query('PRAGMA foreign_key_check')==[]
        app.set_theme(appearance.COMMAND);page.select_day('Monday');pump()
        enter(page.target_name,'Not submitted yet');enter(page.target_goal,'Keep this draft');page.queue_editor()
        checkpoint=dict(checked=first,tuesday=tuesday,muscles=page.day['muscles'])
        (directory/'checkpoint.json').write_text(json.dumps(checkpoint))
        assert not errors,errors
        app.close()  # Flushes the pending draft even before the debounce fires.
        child=subprocess.run([sys.executable,__file__,str(directory),'--restart'],capture_output=True,text=True,timeout=60)
        assert child.returncode==0 and 'Restart PASS' in child.stdout and not child.stderr,(child.stdout,child.stderr)
        result=dict(result='PASS',weekly_days=7,custom_targets=True,edit_delete_reorder=True,checkbox_click_and_keyboard=True,
            autosave=True,reset_cancel_and_confirm=True,history_preserved=True,reset_snapshot=True,
            restart_checks_and_draft=True,themes=2,resize=True,rapid_navigation=24,
            legacy_rows_unchanged=True,schema_version=2,scroll_mean_ms=timings,callback_errors=errors)
        (directory/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
    finally:
        try:
            if app.winfo_exists():app.close()
        except Exception:pass
        appearance.select(appearance.CURRENT)


if __name__=='__main__':main()

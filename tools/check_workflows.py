"""Native workout/day, dated meals, live themes and actual overflow scrolling."""
from pathlib import Path
import json
import hashlib
import subprocess
import sqlite3
import sys
import time
from datetime import date
from tkinter import messagebox
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def main():
    directory=Path(sys.argv[1]).resolve()
    restart='--restart' in sys.argv
    if not restart:directory.mkdir(parents=True,exist_ok=False)
    from lifeos.db import Database
    from lifeos.ui.app import LifeOS,PAGES
    from lifeos.workout_checklist import WorkoutChecklist
    from lifeos.ui import appearance
    from lifeos.ui.scrolling import ScrollFrame
    from PIL import ImageGrab
    database=directory/'workflow.sqlite3'
    def fail(title,message,**kwargs):raise AssertionError(title+': '+str(message))
    messagebox.showerror=fail;messagebox.askyesno=lambda *a,**k:True
    app=LifeOS(Database(database));errors=[]
    app.report_callback_exception=lambda exc,value,tb:errors.append(str(value))
    def pump():
        app.update();app.update_idletasks()
    def capture(name,window=None):
        pump();owner=window or app;owner.wallpaper.render();pump()
        assert owner.wallpaper.last_error is None,owner.wallpaper.last_error
        ImageGrab.grab(window=owner.winfo_id()).save(directory/name)
    def enter(widget,value):widget.delete(0,'end');widget.insert(0,str(value))
    def snapshot():
        tables=[r['name'] for r in app.db.query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {t:app.db.query('SELECT * FROM "'+t+'" ORDER BY rowid'+("" if t!='settings' else "")) for t in tables if t!='settings'}, {k:v for k,v in app.db.settings().items() if k!='theme'}
    def digest():return hashlib.sha256(json.dumps(snapshot(),sort_keys=True).encode()).hexdigest()
    if restart:
        checkpoint=json.loads((directory/'checkpoint.json').read_text())
        try:
            pump()
            assert app.db.settings()['theme']==appearance.COMMAND
            assert digest()==checkpoint['digest']
            assert any(t['id']==checkpoint['checklist_target'] and t['completed'] for t in WorkoutChecklist(app.db).load()['days']['Monday']['targets'])
            assert app.service.meal_day('2026-10-20')['calories']==387.5
            capture('restart-command-theme.png')
            assert not errors,errors
            print('Restart PASS')
        finally:app.close()
        return
    try:
        app.show('Workout Planner');pump();page=app.page_frame
        page.select_day('Monday');page.toggle_muscle('Chest');page.toggle_muscle('Back')
        enter(page.target_name,'Push-ups');enter(page.target_goal,'3 x 15');rid=page.save_target();pump()
        page.toggle_target(rid);assert page.day['targets'][0]['completed']
        page.target_list.selection_set(rid);page.edit_target();enter(page.target_goal,'3 x 20');page.save_target()
        assert page.day['targets'][0]['completed']
        capture('weekly-checklist.png')
        app.show('Diet & Nutrition');pump();nutrition=app.page_frame
        enter(nutrition.day,'2026-10-20');nutrition.refresh_meals()
        ids={}
        for meal in ('Breakfast','Lunch','Snacks','Dinner'):
            food=nutrition.add_food(meal);pump()
            assert food.day.get()=='2026-10-20' and food.meal.get()==meal
            food.food.set(next(k for k,v in food.food_map.items() if v['name']=='Egg, whole, boiled'))
            enter(food.quantity,100);food.unit.set('g');food.save();pump()
            ids[meal]=nutrition.report['meals'][meal]['entries'][0]['id']
        assert nutrition.report['calories']==620
        nutrition.meal_lists['Lunch'].selection_set(str(ids['Lunch']));food=nutrition.edit_food('Lunch');pump()
        enter(food.quantity,50);food.meal.set('Snacks');food.save();pump()
        assert len(nutrition.report['meals']['Snacks']['entries'])==2
        assert not nutrition.report['meals']['Lunch']['entries']
        nutrition.meal_lists['Dinner'].selection_set(str(ids['Dinner']));nutrition.remove_food('Dinner')
        assert nutrition.report['calories']==387.5
        nutrition.shift(1);assert nutrition.report['calories']==0
        nutrition.shift(-1);assert nutrition.report['calories']==387.5
        custom=nutrition.custom_food();pump()
        assert all(custom.inputs[k].get()=='' for k in ('calories','protein','carbs','fat'))
        for key,value in dict(name='Verified test food',source='Package label',calories=100,protein=10,carbs=10,fat=2).items():enter(custom.inputs[key],value)
        custom.save();pump()
        capture('dated-meals-current.png')
        # Move a genuinely overflowing native canvas using an event on a child.
        body=nutrition.body;canvas=body.master;before_y=canvas.yview()
        for _ in range(5):nutrition.meal_labels['Breakfast'].event_generate('<MouseWheel>',delta=-120);pump()
        assert canvas.yview()!=before_y,(canvas.yview(),before_y)
        canvas.yview_moveto(0);pump();before_y=canvas.yview()
        nutrition.meal_lists['Breakfast'].event_generate('<MouseWheel>',delta=-120);pump()
        assert canvas.yview()!=before_y,'Nested record list trapped the parent wheel event'
        # Add enough real saved rows to measure scrolling, rather than empty lists.
        for i in range(80):app.service.save('problems',dict(name='Scrolling record '+str(i),topic='Arrays'))
        app.show('DSA Tracker');pump();view=app.record_frames['Problems'].tree
        repaint=app.wallpaper.render_count;times=[];initial=view.offset
        background_item=view._row_background;background_photo=view.photo
        before_items=len(view.find_all())
        for _ in range(20):
            start=time.perf_counter();view.event_generate('<MouseWheel>',delta=-120);pump();times.append((time.perf_counter()-start)*1000)
        assert view.offset>initial
        assert app.wallpaper.render_count==repaint
        assert view._row_background==background_item and view.photo is background_photo
        assert len(view.find_all())<=before_items+len(view.columns)*2+4,'Record canvas items accumulated during scrolling'
        saved=app.db.backup(directory/'restore-check.sqlite3')
        app.service.save('tasks',dict(title='Temporary restore check'))
        settings_module=__import__('lifeos.ui.settings',fromlist=['filedialog'])
        previous_open=settings_module.filedialog.askopenfilename
        settings_module.filedialog.askopenfilename=lambda **kwargs:str(saved)
        app.show('Settings');pump();app.page_frame.restore();pump()
        settings_module.filedialog.askopenfilename=previous_open
        assert not app.service.list('tasks'), 'Restore left a temporary task behind'
        app.show('Diet & Nutrition');pump()
        assert app.page_frame.report['date']==date.today().isoformat()
        theme_scroll={}
        cache_ids={}
        expected=snapshot()
        for theme in (appearance.COMMAND,appearance.CURRENT):
            app.show('Settings');pump();settings=app.page_frame
            option=settings.inputs['theme'][0];option.set(theme);option.cget('command')(theme);pump()
            for page_name in PAGES:
                app.show(page_name);pump();assert app.wallpaper.last_error is None
                cache_ids.setdefault(page_name,id(app.page_frame));assert cache_ids[page_name]==id(app.page_frame)
                capture(('cmd-' if theme==appearance.COMMAND else 'current-')+page_name.lower().replace(' ','-')+'.png')
                if page_name=='DSA Tracker':
                    target=app.record_frames['Problems'].tree
                    timings=[]
                    for _ in range(5):
                        start=time.perf_counter();target.event_generate('<MouseWheel>',delta=-120);pump();timings.append((time.perf_counter()-start)*1000)
                    theme_scroll[theme]=round(sum(timings)/len(timings),2)
                if theme==appearance.COMMAND:
                    assert app.wallpaper.wallpaper.getpixel((0,0))==(9,11,10)
                else:
                    r,g,b=app.wallpaper.wallpaper.getpixel((200,200));assert r==g==b
            assert snapshot()==expected,'Theme switching changed saved records or inactive preferences'
        app.set_theme(appearance.COMMAND);pump()
        app.show('Workout Planner');pump();page=app.page_frame
        identity=id(page);page.select_day('Monday')
        app.set_theme(appearance.CURRENT);pump();app.set_theme(appearance.COMMAND);pump()
        assert id(page)==identity and any(t['id']==rid and t['completed'] for t in page.day['targets'])
        capture('cmd-workout-checklist.png')
        app.geometry('960x600');pump();capture('cmd-small.png')
        # Global wheel callback count stays bounded across repeat visits.
        bindings=str(app.bind_all('<MouseWheel>'))
        for page_name in list(PAGES)*3:app.show(page_name)
        pump();assert str(app.bind_all('<MouseWheel>'))==bindings
        assert not errors,errors
        (directory/'checkpoint.json').write_text(json.dumps(dict(digest=digest(),checklist_target=rid)),encoding='utf-8')
        app.close()
        restarted=subprocess.run([sys.executable,__file__,str(directory),'--restart'],capture_output=True,text=True,timeout=60)
        assert restarted.returncode==0,(restarted.stdout,restarted.stderr)
        assert 'Restart PASS' in restarted.stdout and not restarted.stderr,(restarted.stdout,restarted.stderr)
        result=dict(result='PASS',weekly_days=7,weekly_checklist=True,direct_completion_checkboxes=True,
            plan_history_preserved=True,dated_meals_edit_remove=True,custom_values_explicit=True,
            themes_navigated=2,theme_pages=8,theme_restart=True,records_preserved=True,
            actual_scroll_mean_ms=round(sum(times)/len(times),2),actual_scroll_max_ms=round(max(times),2),
            full_window_scroll_repaints=0,child_wheel_scrolled=True,theme_scroll_mean_ms=theme_scroll,
            restore_invalidated_cache=True,cached_workout_rethemed=True,rapid_switches=24,callback_errors=errors)
        (directory/'workflow-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
    finally:
        try:
            if app.winfo_exists():app.close()
        except Exception:
            pass
        appearance.select(appearance.CURRENT)

if __name__=='__main__':main()

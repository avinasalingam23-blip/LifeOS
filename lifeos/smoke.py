"""Opt-in native GUI integration check, using only an explicitly isolated profile."""
from __future__ import annotations
import json
import time
import re
import socket
import sys
import tkinter as tk
from datetime import date,timedelta
from pathlib import Path
from tkinter import messagebox
from .db import Database
from .models import ENTITIES,defaults_for

def run(directory):
    from .ui.app import LifeOS,PAGES
    from .ui.records import RecordEditor
    from .ui.nutrition import FoodDialog,RecipeDialog
    directory=Path(directory).resolve()
    directory.mkdir(parents=True,exist_ok=True)
    # Never open a normal profile in this check.
    database=directory/'gui-smoke.sqlite3'
    if database.exists():
        raise ValueError('Use a new, empty smoke-test directory to avoid touching previous records.')
    failures=[]
    original_connect=socket.socket.connect
    network_attempts=[]
    def offline_only(*args,**kwargs):
        network_attempts.append('Unexpected network connection')
        raise AssertionError(network_attempts[-1])
    socket.socket.connect=offline_only
    def fail(title,message,**kwargs):
        failures.append(f'{title}: {message}')
        raise AssertionError(message)
    messagebox.showerror=fail
    app=LifeOS(Database(database))
    def callback_failure(exc,value,tb):
        import traceback
        with (directory/'callback-errors.txt').open('a',encoding='utf-8') as handle:
            handle.write(''.join(traceback.format_exception(exc,value,tb)))
        fail('Tk callback',str(value))
    app.report_callback_exception=callback_failure
    app.update()
    from .ui.icons import NAV_ICONS
    assert set(NAV_ICONS)==set(PAGES)
    for page,nav in app.nav.items():
        assert nav.cget('image').lifeos_name==NAV_ICONS[page],f'Wrong/missing navigation icon: {page}'
        assert nav.cget('text')==page,f'Icon-only or unreadable navigation: {page}'
    def settle():
        # CTkTabview.set defers grid cleanup by 100 ms. Wait for real rendering.
        until=time.monotonic()+.16
        while time.monotonic()<until:
            app.update()
            time.sleep(.01)
    audited_widgets=0
    def audit_widgets(widget):
        nonlocal audited_widgets
        audited_widgets+=1
        forbidden=re.compile(r'\bai\b|ollama|assistant|ai[_-]|qwen',re.I)
        for option in ('text','values','placeholder_text'):
            try:
                value=widget.cget(option)
            except (tk.TclError,ValueError,TypeError,AttributeError,KeyError):
                continue
            assert not forbidden.search(str(value)),(type(widget).__name__,option,value)
        try:
            assert getattr(widget.cget('image'),'lifeos_name','')!='brain'
        except (tk.TclError,ValueError,TypeError,AttributeError,KeyError):
            pass
        if isinstance(widget,tk.Canvas):
            for item in widget.find_all():
                if widget.type(item)=='text':
                    assert not forbidden.search(widget.itemcget(item,'text')),widget.itemcget(item,'text')
        if isinstance(widget,tk.Text):
            assert not forbidden.search(widget.get('1.0','end-1c'))
        for child in widget.winfo_children():
            audit_widgets(child)
    def capture(widget,name):
        from PIL import ImageGrab
        settle()
        widget.winfo_toplevel().wallpaper.render()
        settle()
        widget.winfo_toplevel().wallpaper.render()
        app.update_idletasks()
        assert widget.winfo_toplevel().wallpaper.last_error is None,widget.winfo_toplevel().wallpaper.last_error
        audit_widgets(widget.winfo_toplevel())
        ImageGrab.grab(window=widget.winfo_toplevel().winfo_id()).save(directory/name)
    created={}
    today=date.today().isoformat()
    samples={
        'problems':dict(name='Two sum',platform='LeetCode',topic='Arrays',status='Solved',solved_date=today),
        'solutions':dict(title='Hash-map solution',code='def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen:\n            return [seen[target - n], i]\n        seen[n] = i\n'),
        'paths':dict(name='Systems thinking',goal='Understand feedback loops',target_minutes=90),
        'concepts':dict(name='Feedback loops',understanding=2,notes='Need practice with delays',prerequisites='Stocks and flows'),
        'study_sessions':dict(minutes=35,planned_minutes=30),
        'workout_routines':dict(name='Home strength',split='Full Body'),
        'workout_days':dict(name='Full body A',weekday=date.today().strftime('%A')),
        'planned_exercises':dict(exercise='Goblet squat',weight_kg=12),
        'workouts':dict(name='Home session',status='Completed'),
        'exercise_logs':dict(exercise='Goblet squat',weight_kg=12),
        'foods':dict(name='My verified snack',preparation='As sold',source='Package label',calories=120,protein=10,carbs=12,fat=3,serving_g=100),
        'water_logs':dict(ml=500),
        'measurements':dict(weight_kg=72),
        'tasks':dict(title='Review feedback loop notes',priority='High'),
        'daily_routines':dict(title='Evening review',weekdays=date.today().strftime('%A')),
        'focus_sessions':dict(title='Manual reading session',actual_minutes=20),
    }
    try:
        # Exercise actual form widgets and Save, including all optional data types.
        for table,entity in ENTITIES.items():
            if table=='food_logs':
                continue
            editor=RecordEditor(app,app,table)
            values=defaults_for(table)
            values.update(samples[table])
            for f in entity.fields:
                if f.kind=='ref':
                    values[f.key]=created.get(f.ref)
                value=values.get(f.key)
                widget=editor.inputs[f.key]
                if f.kind=='ref':
                    choice=next((name for name,rid in editor.ref_maps[f.key].items() if rid==value),'— Select —')
                    widget.set(choice)
                elif f.kind=='choice':
                    widget.set(value)
                elif f.kind=='memo':
                    widget.delete('1.0','end')
                    widget.insert('1.0',value or '')
                elif f.kind=='code':
                    widget.text.delete('1.0','end')
                    widget.text.insert('1.0',value or '')
                    widget.highlight()
                else:
                    widget.delete(0,'end')
                    if value is not None:
                        widget.insert(0,str(value))
            app.update()
            editor.save()
            app.update()
            created[table]=app.selected[table]
        code=app.service.get('solutions',created['solutions'])['code']
        assert code==samples['solutions']['code']
        editor=RecordEditor(app,app,'solutions',app.service.get('solutions',created['solutions']))
        assert editor.inputs['code'].caption.cget('image').lifeos_name=='python-logo'
        editor.inputs['code'].copy()
        assert app.clipboard_get()==code
        editor.destroy()
        generic=RecordEditor(app,app,'concepts',app.service.get('concepts',created['concepts']))
        assert generic.inputs['code'].caption.cget('image').lifeos_name=='code-xml'
        generic.destroy()
        # Calculated meal through the actual food form.
        dialog=FoodDialog(app,app)
        dialog.phrase.insert(0,'2 eggs')
        dialog.lookup()
        selected=next(name for name,f in dialog.food_map.items() if f['name']=='Egg, whole, boiled')
        dialog.food.set(selected)
        dialog.preview()
        dialog.save()
        assert app.service.list('food_logs')[0]['calories']==155
        # Build a recipe through the GUI.
        recipe=RecipeDialog(app,app,lambda:None)
        recipe.name.insert(0,'Test rice recipe')
        recipe.yield_g.insert(0,'300')
        ingredient=next(name for name,rid in recipe.food_map.items() if app.service.get('foods',rid)['name']=='Rice, white, dry')
        recipe.food.set(ingredient)
        recipe.grams.insert(0,'100')
        recipe.add_ingredient()
        recipe.save()
        app.service.plan_workout(created['workout_days'],today)
        app.service.generate_tasks()
        # Build every page and tab, exercise filters, sorts and refresh.
        for page in PAGES:
            app.show(page)
            settle()
            audit_widgets(app)
            app.wallpaper.render()
            assert app.wallpaper.last_error is None,app.wallpaper.last_error
            assert app.wallpaper.render_count>0
            assert app.wallpaper.painted_name==app.wallpaper.name
            assert len(app.wallpaper.images)>=1,(page,'Glass container photo compositing is missing')
            assert app.wallpaper.wallpaper.getextrema()[0][0]!=app.wallpaper.wallpaper.getextrema()[0][1],page
            if page=='Dashboard':
                assert len(app.page_frame.cards)==8
                assert app.page_frame.backing is not None
            if page=='Workout Planner':
                app.page_frame.sections.set('Workout history')
            elif page=='Diet & Nutrition':
                app.page_frame.sections.set('History & library')
            for name,frame in app.record_frames.items():
                app.tabs.set(name)
                app.tab_changed()
                settle()
                until=time.monotonic()+3
                while not frame.tree.winfo_ismapped() and time.monotonic()<until:
                    app.update()
                    time.sleep(.02)
                if not frame.tree.winfo_ismapped():
                    from PIL import ImageGrab
                    ImageGrab.grab(window=app.winfo_id()).save(directory/'unmapped-records.png')
                    ancestry=[]
                    node=frame.tree
                    while node is not None:
                        ancestry.append(dict(widget=str(node),mapped=node.winfo_ismapped(),
                            size=[node.winfo_width(),node.winfo_height()],manager=node.winfo_manager()))
                        node=getattr(node,'master',None)
                    (directory/'unmapped-records.json').write_text(json.dumps(ancestry,indent=2),encoding='utf-8')
                assert frame.tree.winfo_ismapped(),f'{page} / {name} table is not visible'
                frame.refresh()
                if frame.entity.columns:
                    frame.sort(frame.entity.columns[0])
                if frame.filter_fields:
                    field=next(iter(frame.filter_fields))
                    frame.filter_field.set(field)
                    frame.change_filter(field)
                    frame.refresh()
                    frame.clear()
            if page=='Analytics':
                for view in ['DSA','Learning','Workouts','Nutrition','Water & Weight','Tasks & Focus']:
                    app.page_frame.view.set(view)
                    app.page_frame.render()
                    app.update()
            if page=='Settings':
                legacy={'ai_url':'inactive old address','ai_model':'','ai_context':0}
                app.db.save_settings(legacy)
                app.page_frame.save()
                assert {key:app.db.settings()[key] for key in legacy}==legacy
                assert not any(key.startswith('ai_') for key in app.page_frame.inputs)
                assert app.page_frame.sections.names==['Appearance / Theme','Daily goals','Nutrition goals','Preferences','Data safety']
                for section in app.page_frame.sections.names:
                    app.page_frame.sections.set(section)
                    settle()
                    audit_widgets(app)
                app.page_frame.sections.set('Daily goals')
            if page=='Workout Planner':
                app.page_frame.sections.set('Weekly checklist')
            elif page=='Diet & Nutrition':
                app.page_frame.sections.set('Meals')
            elif app.record_frames:
                app.tabs.set(next(iter(app.record_frames)))
                app.tab_changed()
            if page!='Dashboard':
                try:
                    from PIL import ImageGrab
                    settle()
                    ImageGrab.grab(window=app.winfo_id()).save(directory/(page.lower().replace(' ','-')+'.png'))
                    app.geometry('960x600')
                    settle()
                    app.wallpaper.render()
                    ImageGrab.grab(window=app.winfo_id()).save(directory/(page.lower().replace(' ','-')+'-small.png'))
                    app.geometry('1024x635')
                except Exception:
                    pass
        # Subject cards open scoped details; advanced fields remain editable.
        from .ui.records import RecordDetails
        app.show('Learning Paths')
        settle()
        subjects=app.record_frames['Subjects']
        subjects.tree.selection_set(str(created['paths']))
        subjects.details()
        settle()
        details=next(w for w in subjects.winfo_children() if isinstance(w,RecordDetails))
        assert details.related['concepts'].scope=={'path_id':created['paths']}
        assert details.related['concepts'].tree.exists(str(created['concepts']))
        details.edit()
        settle()
        editing=next(w for w in details.winfo_children() if isinstance(w,RecordEditor))
        editing.toggle_advanced()
        settle()
        assert all(w.winfo_ismapped() for w in editing.advanced_frames)
        editing.save()
        settle()
        assert not details.winfo_exists()
        # Simple weekly checklist: free text, direct checks, autosave and safe reset.
        from .ui.nutrition import NutritionReviewDialog
        from .workout_checklist import WorkoutChecklist,progress
        app.show('Workout Planner');settle();page=app.page_frame
        assert len(page.day_buttons)==7
        for weekday,control in page.day_buttons.items():
            control.invoke();assert page.weekday==weekday
        page.select_day('Monday')
        page.toggle_muscle('Chest');page.toggle_muscle('Back')
        for field,value in [(page.target_name,'Push-ups'),(page.target_goal,'3 x 15')]:field.delete(0,'end');field.insert(0,value)
        target_id=page.add_button.invoke();settle()
        page.toggle_target(target_id);assert progress(page.day)['completed']>=1
        page.toggle_target(target_id);assert not next(t for t in page.day['targets'] if t['id']==target_id)['completed']
        page.target_list.selection_set(target_id);page.edit_target()
        page.target_name.delete(0,'end');page.target_name.insert(0,'Incline push-ups');page.save_target()
        page.select_day('Tuesday');page.select_day('Monday')
        assert next(t for t in page.day['targets'] if t['id']==target_id)['name']=='Incline push-ups'
        page.toggle_target(target_id)
        previous_confirmation=messagebox.askyesno;messagebox.askyesno=lambda *a,**k:True
        page.reset_day();messagebox.askyesno=previous_confirmation
        assert progress(page.day)['completed']==0
        page.toggle_target(target_id)
        capture(app,'workout-checklist.png')
        page.choose_section('Workout history');page.history_kind.set('Earlier workouts');page.render_history()
        assert page.history_list.get_children()
        page.history_list.selection_set(page.history_list.get_children()[0]);history=page.history_details()
        capture(history,'earlier-workout-history.png');history.destroy()
        assert not any(hasattr(page,key) for key in ('start','finish_workout','open_session'))
        previous=(date.today()-timedelta(days=7)).isoformat()
        body_entry=RecordEditor(app,app,'measurements')
        body_entry.inputs['date'].delete(0,'end')
        body_entry.inputs['date'].insert(0,previous)
        body_entry.inputs['weight_kg'].delete(0,'end')
        body_entry.inputs['weight_kg'].insert(0,'73')
        body_entry.save()
        page.sections.set('Fitness progress')
        page.progress.render()
        app.update()
        review=NutritionReviewDialog(app,app)
        assert review.report['calories']==155
        capture(review,'nutrition-trends.png')
        review.tabs.set('Practical meal ideas')
        assert 'source' in review.ideas.cget('text').lower() or 'USDA' in review.ideas.cget('text')
        capture(review,'meal-ideas.png')
        review.destroy()
        # Open the real calculated progress review through the visible control.
        progress_review=page.progress.review()
        assert '1 completed workouts' in progress_review.output.get('1.0','end')
        assert 'Date range:' in progress_review.output.get('1.0','end')
        capture(progress_review,'progress-review.png')
        progress_review.destroy()
        page.sections.set('Weekly checklist')
        settle()
        app.wallpaper.render()
        from PIL import ImageGrab
        ImageGrab.grab(window=app.winfo_id()).save(directory/'workout-coach.png')
        page.sections.set('Fitness progress')
        settle()
        app.wallpaper.render()
        ImageGrab.grab(window=app.winfo_id()).save(directory/'fitness-progress.png')
        app.show('Learning Paths')
        settle()
        app.wallpaper.set_page('Learning Paths','NLP / Machine Learning')
        settle()
        app.wallpaper.render()
        assert app.wallpaper.name=='research'
        assert app.wallpaper.last_error is None
        try:
            from PIL import ImageGrab
            ImageGrab.grab(window=app.winfo_id()).save(directory/'research.png')
        except Exception:
            pass
        app.timer_title.insert(0,'Smoke focus')
        app.timer_minutes.delete(0,'end')
        app.timer_minutes.insert(0,'1')
        app.start_timer()
        app.pause_timer()
        assert app.service.active_timer()['status']=='Paused'
        app.pause_timer()
        app.timer_action('finish')
        assert app.service.active_timer() is None
        app.show('Dashboard')
        settle()
        app.wallpaper.render()
        board=app.page_frame
        assert board.configured_duration()==float(app.timer_minutes.get())
        if board.missions:
            mission=dict(board.missions[0])
            board.toggle_task(mission)
            assert app.service.get('tasks',mission['id'])['status']!=mission['status']
            board.toggle_task(app.service.get('tasks',mission['id']))
            assert app.service.get('tasks',mission['id'])['status']==mission['status']
        board.keyboard_action='focus-toggle'
        board.key_activate(None)
        assert app.service.active_timer()['status']=='Running'
        board.focus_toggle()
        assert app.service.active_timer()['status']=='Paused'
        board.focus_toggle()
        assert app.service.active_timer()['status']=='Running'
        board.finish_focus()
        assert app.service.active_timer() is None
        app.timer_minutes.delete(0,'end')
        app.timer_minutes.insert(0,str(app.db.settings()['focus_minutes']))
        board.draw()
        for geometry in ('960x600','1235x635','1024x635'):
            app.geometry(geometry)
            settle()
            app.wallpaper.render()
            board=app.page_frame
            for box in board.cards.values():
                x,y,right,bottom=board.rect(box)
                assert x>=0 and y>=0 and right<=board.winfo_width()+1 and bottom<=board.winfo_height()+1
            if geometry=='960x600':
                ImageGrab.grab(window=app.winfo_id()).save(directory/'dashboard-small.png')
        try:
            from PIL import ImageGrab
            app.update()
            ImageGrab.grab(window=app.winfo_id()).save(directory/'dashboard.png')
        except Exception as error:
            # Screenshot availability isn't required to exercise the native widgets.
            (directory/'screenshot-note.txt').write_text(str(error),encoding='utf-8')
        # The same check runs from LifeOS.exe: exercise frozen fonts, images,
        # charts and cached pages in both themes, then leave CMD persisted.
        from .ui import appearance
        for theme,prefix in ((appearance.CURRENT,'current'),(appearance.COMMAND,'cmd')):
            app.set_theme(theme)
            for page_name in PAGES:
                app.show(page_name)
                if page_name=='Workout Planner':
                    app.page_frame.choose_section('Weekly checklist')
                    app.page_frame.select_day('Monday')
                settle()
                if page_name=='Workout Planner':assert app.page_frame.target_list.winfo_ismapped()
                capture(app,prefix+'-'+page_name.lower().replace(' ','-')+'.png')
        app.show('Workout Planner')
        app.page_frame.choose_section('Weekly checklist')
        app.page_frame.select_day('Monday')
        capture(app,'packaged-final-checklist.png')
        assert not failures,failures
        assert not network_attempts,network_attempts
        metrics=dict(screen=[app.winfo_screenwidth(),app.winfo_screenheight()],
                     window=[app.winfo_width(),app.winfo_height()],scaling=app._get_window_scaling())
        assert app.db.query('PRAGMA foreign_key_check')==[]
        app.db.backup(directory/'gui-backup.sqlite3')
        app.close()
        reopened=Database(database)
        assert reopened.one('SELECT COUNT(*) count FROM solutions')['count']==1
        assert reopened.one('SELECT COUNT(*) count FROM paths')['count']==1
        assert reopened.one('SELECT COUNT(*) count FROM fitness_sessions')['count']==0
        assert reopened.one('SELECT COUNT(*) count FROM fitness_sets')['count']==0
        assert any(t['id']==target_id and t['completed'] for t in WorkoutChecklist(reopened).load()['days']['Monday']['targets'])
        assert reopened.settings()['theme']==appearance.COMMAND
        reopened.close()
        result=dict(result='PASS',forms=len(samples),navigation_pages=len(PAGES),analytics_views=6,
                    code_copy=True,restart_persistence=True,recipe_builder=True,food_logger=True,timer=True,
                    navigation_icons=8,photographic_backgrounds=9,
                    reference_dashboard_cards=8,resize_checks=3,failures=failures,display=metrics)
        result.update(weekly_days=7,custom_checklist=True,direct_checkbox_completion=True,reset_preserves_plan=True,
                      themes_checked=2,theme_persisted=True,frozen=bool(getattr(sys,'frozen',False)),
                      nutrition_review=True,page_sizes_checked=2,
                      progress_review=True,inactive_ai_settings_preserved=True,
                      audited_widgets=audited_widgets,removed_entry_points_verified=True,network_attempts=network_attempts)
        (directory/'smoke-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        return result
    except Exception:
        try:
            app.close()
        except Exception:
            pass
        raise
    finally:
        socket.socket.connect=original_connect

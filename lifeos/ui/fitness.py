from .lifecycle import Textbox
from .appearance import menu as themed_menu
from .scrolling import ScrollFrame
"""Workout coaching UI. All calculations and persistence live in FitnessCoach."""
from datetime import date,timedelta
import json
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from matplotlib.figure import Figure
from ..models import ENTITIES,WEEKDAYS
from ..fitness import readiness
from ..exercise_library import EQUIPMENT,CATEGORIES
from .common import button,label,safe,Dialog,TEXT,MUTED,PANEL
from .theme import GlassCard
from .collections import GlassTabs,PhotoRecordList
from .records import RecordsFrame,RecordEditor,RecordsDialog
from .charts import GlassPlot,style_axes
from .workout_view import ChecklistHeader,ChecklistTargets,WeekDayCard,MuscleStrip,CommandButton

class MusclePicker(ctk.CTkFrame):
    def __init__(self,parent,coach,selected=()):
        super().__init__(parent,fg_color='transparent')
        self.coach=coach
        self.selected=list(selected)
        self.grid_columnconfigure(0,weight=1)
        self.search=ctk.CTkEntry(self,placeholder_text='Search muscles or regions…')
        self.search.grid(row=0,column=0,sticky='ew',pady=(0,6))
        self.search.bind('<KeyRelease>',lambda e:self.render())
        self.summary=label(self,', '.join(self.selected) or 'No muscles selected',11,MUTED,anchor='w',wraplength=650)
        self.summary.grid(row=1,column=0,sticky='ew')
        self.choices=ScrollFrame(self,height=100,fg_color='transparent',corner_radius=0)
        self.choices.grid(row=2,column=0,sticky='ew',pady=6)
        for col in range(3):
            self.choices.grid_columnconfigure(col,weight=1)
        self.custom=ctk.CTkEntry(self,placeholder_text='Custom muscle group (optional)',width=230)
        self.custom.grid(row=3,column=0,sticky='w',pady=4)
        button(self,'Add custom',self.add_custom,True,width=110).grid(row=3,column=0,sticky='e')
        self.render()

    def render(self):
        for child in self.choices.winfo_children():
            child.destroy()
        for index,muscle in enumerate(self.coach.muscles(self.search.get())):
            control=button(self.choices,('✓ ' if muscle in self.selected else '')+muscle,lambda m=muscle:self.toggle(m),
                           muscle not in self.selected,width=150,height=28)
            control.grid(row=index//3,column=index%3,sticky='ew',padx=3,pady=3)
        self.summary.configure(text=', '.join(self.selected) or 'No muscles selected')
        self.winfo_toplevel().wallpaper.request()

    def toggle(self,muscle):
        self.selected.remove(muscle) if muscle in self.selected else self.selected.append(muscle)
        self.render()

    def add_custom(self):
        value=self.custom.get().strip()
        if value:
            self.coach.save_preferences(dict(custom_muscles=[*self.coach.preferences()['custom_muscles'],value]))
            self.selected.append(value)
            self.custom.delete(0,'end')
            self.render()

class DayDialog(Dialog):
    def __init__(self,parent,app,routine_id,weekday,day=None,on_save=None):
        super().__init__(parent,'Configure '+weekday,780,670)
        self.app,self.routine_id,self.weekday,self.day,self.on_save=app,routine_id,weekday,day,on_save
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(1,weight=1)
        label(self,weekday+' · muscles & recovery',22).grid(row=0,column=0,sticky='w',padx=22,pady=14)
        body=ScrollFrame(self,fg_color='transparent',corner_radius=0)
        body.grid(row=1,column=0,sticky='nsew',padx=22)
        body.grid_columnconfigure(0,weight=1)
        self.name=ctk.CTkComboBox(body,values=['Push: chest, shoulders & triceps','Pull: back & biceps','Legs & glutes','Upper body','Legs & core','Full body & conditioning','Recovery & mobility'],width=600)
        self.name.set(day['name'] if day else 'Recovery & mobility')
        self.name.grid(row=0,column=0,sticky='ew',pady=8)
        self.recovery=ctk.CTkOptionMenu(body,values=['Training day','Recovery / mobility day'])
        self.recovery.set('Recovery / mobility day' if not day or day['recovery']=='Yes' else 'Training day')
        self.recovery.grid(row=1,column=0,sticky='w',pady=6)
        self.muscles=MusclePicker(body,app.coach,[m.strip() for m in day['muscles'].split(',') if m.strip()] if day else [])
        self.muscles.grid(row=2,column=0,sticky='ew',pady=8)
        label(body,'Why this day / recovery instructions',12,MUTED).grid(row=3,column=0,sticky='w',pady=4)
        self.notes=Textbox(body,height=75)
        self.notes.grid(row=4,column=0,sticky='ew',pady=4)
        self.notes.insert('1.0',day['notes'] if day else 'Choose a comfortable workload and allow recovery between demanding sessions.')
        button(self,'Save day',self.save,width=140).grid(row=2,column=0,sticky='e',padx=22,pady=14)

    def save(self):
        def action():
            self.app.coach.configure_day(self.routine_id,self.weekday,self.name.get(),self.muscles.selected,
                self.recovery.get()!='Training day',self.notes.get('1.0','end-1c'),self.day['id'] if self.day else None)
            if self.on_save:
                self.on_save()
            self.destroy()
        safe(self,action)

class ExercisePicker(Dialog):
    def __init__(self,parent,app,day_id,on_save=None,record=None):
        super().__init__(parent,'Exercise library',900,750)
        self.app,self.day_id,self.on_save,self.record=app,day_id,on_save,record
        self.selected_key=record['library_key'] if record else None
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(1,weight=1)
        label(self,'Choose an exercise',23).grid(row=0,column=0,sticky='w',padx=22,pady=14)
        self.tabs=GlassTabs(self)
        self.tabs.grid(row=1,column=0,sticky='nsew',padx=22,pady=(0,14))
        find=self.tabs.add('Find exercise')
        find.grid_columnconfigure(0,weight=1)
        find.grid_rowconfigure(2,weight=1)
        self.search=ctk.CTkEntry(find,placeholder_text='Search exercise, muscle or equipment…')
        self.search.grid(row=0,column=0,sticky='ew',pady=6)
        self.search.bind('<KeyRelease>',lambda e:self.lookup())
        filters=ctk.CTkFrame(find,fg_color='transparent')
        filters.grid(row=1,column=0,sticky='ew',pady=8)
        day=app.service.get('workout_days',day_id)
        muscles=[m.strip() for m in day['muscles'].split(',') if m.strip()]
        self.muscle=ctk.CTkOptionMenu(filters,values=['Any muscle',*app.coach.muscles()],width=170,command=lambda v:self.lookup())
        self.muscle.set(muscles[0] if muscles and muscles[0] in app.coach.muscles() else 'Any muscle')
        self.muscle.pack(side='left',padx=(0,8))
        self.equipment=ctk.CTkOptionMenu(filters,values=['My equipment','All equipment',*EQUIPMENT],width=160,command=lambda v:self.lookup())
        self.equipment.pack(side='left',padx=4)
        self.category=ctk.CTkOptionMenu(filters,values=['Any category',*CATEGORIES],width=160,command=lambda v:self.lookup())
        self.category.pack(side='left',padx=4)
        self.results=PhotoRecordList(find,('name','muscles','equipment'),on_open=self.configure_selection)
        self.results.grid(row=2,column=0,sticky='nsew',padx=(0,12))
        results_scroll=ctk.CTkScrollbar(find,orientation='vertical',command=self.results.yview)
        results_scroll.grid(row=2,column=0,sticky='nse')
        self.results.configure(yscrollcommand=results_scroll.set)
        for key,title in [('name','Exercise'),('muscles','Primary muscles'),('equipment','Equipment')]:
            self.results.heading(key,text=title)
        self.results.bind('<<TreeviewSelect>>',self.select_result)
        self.detail=label(find,'Select an exercise to see its instructions.',12,MUTED,justify='left',anchor='w',wraplength=760)
        self.detail.grid(row=3,column=0,sticky='ew',pady=10)
        buttons=ctk.CTkFrame(find,fg_color='transparent')
        buttons.grid(row=4,column=0,sticky='ew')
        button(buttons,'Configure selection',self.configure_selection,width=170).pack(side='right')
        button(buttons,'Custom exercise',self.custom_exercise,True,width=145,icon_name='plus').pack(side='left')
        config=self.tabs.add('Sets & instructions')
        config.grid_columnconfigure(0,weight=1)
        config.grid_rowconfigure(0,weight=1)
        self.config_body=ScrollFrame(config,fg_color='transparent',corner_radius=0)
        self.config_body.grid(row=0,column=0,sticky='nsew')
        self.config_body.grid_columnconfigure((0,1),weight=1)
        self.instructions=label(self.config_body,'Choose an exercise first.',12,anchor='w',justify='left',wraplength=740)
        self.instructions.grid(row=0,column=0,columnspan=2,sticky='ew',pady=(8,12))
        self.inputs={}
        for index,(key,title,default) in enumerate([
            ('sets','Target sets',2),('reps','Target reps / set',8),('rest_seconds','Rest (seconds)',60),
            ('weight_kg','External load (kg; 0 = none)',0),('resistance','Band resistance / equipment setting',''),
            ('tempo','Tempo (optional)',''),('duration_min','Target time (minutes; optional)',0),('notes','Plan notes','')]):
            row=1+(index//2)*2
            col=index%2
            label(self.config_body,title,11,MUTED).grid(row=row,column=col,sticky='w',padx=8,pady=(6,2))
            entry=ctk.CTkEntry(self.config_body,height=30)
            entry.insert(0,str(record.get(key,default) if record else default))
            entry.grid(row=row+1,column=col,sticky='ew',padx=8,pady=(0,6))
            self.inputs[key]=entry
        button(config,'Save exercise' if record else 'Add to selected day',self.save,width=175).grid(row=1,column=0,sticky='e',pady=10)
        self.lookup()
        if record and self.selected_key:
            self.show_instructions()
            self.tabs.set('Sets & instructions')

    def lookup(self):
        equipment=self.equipment.get()
        self.matches=self.app.coach.library(self.search.get(),'' if self.muscle.get()=='Any muscle' else self.muscle.get(),
            equipment if equipment not in ('My equipment','All equipment') else '',
            '' if self.category.get()=='Any category' else self.category.get(),available_only=equipment=='My equipment')
        self.results.delete(*self.results.get_children())
        for item in self.matches:
            self.results.insert('','end',iid=item['key'],values=(item['name'],', '.join(item['primary']),', '.join(item['equipment'])))
        self.results.empty_title='No matching exercises'
        self.results.empty_help='Change the muscle or equipment filter.'
        self.results.empty_action='Search another exercise'
        self.results.draw()

    def select_result(self,event=None):
        if self.results.selection():
            self.selected_key=self.results.selection()[0]
            e=self.app.coach.exercise(self.selected_key)
            alternatives=[self.app.coach.exercise(k)['name'] for k in e['alternatives'] if self.app.coach.exercise(k)]
            self.detail.configure(text=e['name']+' · '+e['difficulty']+'\n'+e['instructions']+'\nAlternatives: '+(', '.join(alternatives) or 'Choose a comfortable option from the library.'))

    def show_instructions(self):
        exercise=self.app.coach.exercise(self.selected_key)
        if exercise:
            self.instructions.configure(text=exercise['name']+' · '+', '.join(exercise['primary'])+'\n'+exercise['instructions'])

    def configure_selection(self):
        self.select_result()
        if not self.selected_key:
            messagebox.showinfo('Choose an exercise','Select a library result first.',parent=self)
            return
        self.show_instructions()
        if not self.record and getattr(self,'configured_key',None)!=self.selected_key:
            e=self.app.coach.exercise(self.selected_key)
            duration=5 if e['category']=='Cardio' else 2 if e['category'] in ('Mobility','Stretching') else 0
            defaults=dict(sets=1 if e['difficulty']=='Advanced' or duration else 2,
                          reps=0 if duration else 1 if e['difficulty']=='Advanced' else 6 if e['difficulty']=='Intermediate' else 8,
                          rest_seconds=120 if e['difficulty']=='Advanced' else 60,duration_min=duration)
            for key,value in defaults.items():
                self.inputs[key].delete(0,'end')
                self.inputs[key].insert(0,str(value))
            self.configured_key=self.selected_key
        self.tabs.set('Sets & instructions')

    def save(self):
        def action():
            if not self.selected_key:
                raise ValueError('Select an exercise from the library.')
            self.app.coach.add_exercise(self.day_id,self.selected_key,**{k:w.get() for k,w in self.inputs.items()},record_id=self.record['id'] if self.record else None)
            if self.on_save:
                self.on_save()
            self.destroy()
        safe(self,action)

    def custom_exercise(self):
        CustomExerciseDialog(self,self.app,self.custom_saved)

    def custom_saved(self,key):
        self.selected_key=key
        self.show_instructions()
        self.tabs.set('Sets & instructions')

class CustomExerciseDialog(Dialog):
    def __init__(self,parent,app,on_save):
        super().__init__(parent,'Custom exercise',760,650)
        self.app,self.on_save=app,on_save
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(0,weight=1)
        body=ScrollFrame(self,fg_color='transparent')
        body.grid(row=0,column=0,sticky='nsew',padx=20,pady=16)
        body.grid_columnconfigure(0,weight=1)
        self.name=ctk.CTkEntry(body,placeholder_text='Unique exercise name')
        self.name.grid(row=0,column=0,sticky='ew',pady=8)
        self.muscles=MusclePicker(body,app.coach)
        self.muscles.grid(row=1,column=0,sticky='ew',pady=8)
        self.equipment=ctk.CTkOptionMenu(body,values=list(EQUIPMENT))
        self.equipment.grid(row=2,column=0,sticky='w',pady=6)
        self.category=ctk.CTkOptionMenu(body,values=list(CATEGORIES))
        self.category.grid(row=3,column=0,sticky='w',pady=6)
        self.instructions=Textbox(body,height=80)
        self.instructions.grid(row=4,column=0,sticky='ew',pady=8)
        label(body,'Add clear setup and comfortable-range instructions. This is your custom reference, not verified technique guidance.',11,MUTED,wraplength=650,justify='left').grid(row=5,column=0,sticky='w',pady=8)
        button(self,'Save custom exercise',self.save,width=180).grid(row=1,column=0,sticky='e',padx=20,pady=12)

    def save(self):
        def action():
            key=self.app.coach.custom_exercise(self.name.get(),self.muscles.selected,[self.equipment.get()],self.instructions.get('1.0','end-1c'),self.category.get())
            self.on_save(key)
            self.destroy()
        safe(self,action)

class ReadinessDialog(Dialog):
    def __init__(self,parent,app,day_id,on_date,on_started):
        super().__init__(parent,'Before your workout',700,600)
        self.app,self.day_id,self.on_date,self.on_started=app,day_id,on_date,on_started
        self.grid_columnconfigure(0,weight=1)
        panel=GlassCard(self)
        panel.grid(row=0,column=0,sticky='ew',padx=22,pady=20)
        panel.grid_columnconfigure(1,weight=1)
        label(panel,'How are you feeling?',22).grid(row=0,column=0,columnspan=2,sticky='w',padx=18,pady=16)
        self.inputs={}
        for row,(key,title) in enumerate([('sleep_hours','Sleep (hours, optional)'),('energy','Energy (1–5, optional)'),('soreness','Soreness (0–10, optional)'),('fatigue','Fatigue (0–10, optional)')],1):
            label(panel,title,12,MUTED).grid(row=row,column=0,sticky='w',padx=18,pady=5)
            entry=ctk.CTkEntry(panel,width=160)
            entry.grid(row=row,column=1,sticky='ew',padx=18,pady=5)
            self.inputs[key]=entry
        label(panel,'Pain or concerning symptoms?',12,MUTED).grid(row=5,column=0,sticky='w',padx=18,pady=6)
        self.pain=ctk.CTkOptionMenu(panel,values=['No','Yes'],width=160)
        self.pain.grid(row=5,column=1,sticky='ew',padx=18,pady=6)
        self.notes=ctk.CTkEntry(panel,placeholder_text='Optional recovery notes')
        self.notes.grid(row=6,column=0,columnspan=2,sticky='ew',padx=18,pady=8)
        self.mode=ctk.CTkOptionMenu(panel,values=['Use recovery assessment','Recovery'],width=220)
        self.mode.grid(row=7,column=0,columnspan=2,sticky='w',padx=18,pady=8)
        self.advice=label(self,'Pain or severe fatigue selects recovery. Moderate fatigue reduces planned sets. Nothing is diagnosed.',12,MUTED,wraplength=610,justify='left')
        self.advice.grid(row=1,column=0,sticky='w',padx=24,pady=8)
        footer=ctk.CTkFrame(self,fg_color='transparent')
        footer.grid(row=2,column=0,sticky='ew',padx=22,pady=14)
        button(footer,'Assess recovery',self.assess,True,width=155).pack(side='left')
        button(footer,'Start session',self.start,width=145).pack(side='right')

    def report(self):
        return readiness({**{k:w.get() for k,w in self.inputs.items()},'pain':self.pain.get(),'notes':self.notes.get()})

    def assess(self):
        safe(self,lambda:self.advice.configure(text=self.report()['recommendation']+' · '+self.report()['explanation']))

    def start(self):
        def action():
            report=self.report()
            mode='Recovery' if self.mode.get()=='Recovery' else report['recommendation']
            rid=self.app.coach.start(self.day_id,self.on_date,report,mode)
            self.destroy()
            self.on_started(rid)
        safe(self,action)

class SessionDialog(Dialog):
    def __init__(self,parent,app,rid,on_save=None):
        super().__init__(parent,'Workout session',900,760)
        self.app,self.rid,self.on_save=app,rid,on_save
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(1,weight=1)
        self.title_label=label(self,'Workout session',22,anchor='w')
        self.title_label.grid(row=0,column=0,sticky='ew',padx=22,pady=14)
        self.tabs=GlassTabs(self)
        self.tabs.grid(row=1,column=0,sticky='nsew',padx=22,pady=(0,12))
        work=self.tabs.add('Exercises & sets')
        work.grid_columnconfigure(0,weight=1)
        work.grid_rowconfigure(1,weight=1)
        self.exercise_menu=ctk.CTkOptionMenu(work,values=['No training exercises'],command=lambda v:self.change_exercise(),dynamic_resizing=False)
        self.exercise_menu.grid(row=0,column=0,sticky='ew',pady=(0,8))
        body=ScrollFrame(work,fg_color='transparent',corner_radius=0)
        body.grid(row=1,column=0,sticky='nsew')
        body.grid_columnconfigure((0,1,2,3),weight=1)
        self.instructions=label(body,'',12,anchor='w',justify='left',wraplength=760)
        self.instructions.grid(row=0,column=0,columnspan=4,sticky='ew',pady=8)
        self.inputs={}
        specs=[('set_no','Set number',1),('reps','Actual reps',0),('weight_kg','Load (kg)',0),('rir','Reps in reserve',''),
               ('resistance','Band resistance',''),('variation','Variation',''),('duration_min','Time (minutes)',0),('distance_km','Distance (km)',0)]
        for index,(key,title,value) in enumerate(specs):
            row=1+(index//4)*2
            col=index%4
            label(body,title,11,MUTED).grid(row=row,column=col,sticky='w',padx=5,pady=(6,2))
            entry=ctk.CTkEntry(body,width=130,height=30)
            entry.insert(0,str(value))
            entry.grid(row=row+1,column=col,sticky='ew',padx=5,pady=(0,6))
            self.inputs[key]=entry
        self.set_notes=ctk.CTkEntry(body,placeholder_text='Optional set notes / easier or harder variation')
        self.set_notes.grid(row=5,column=0,columnspan=4,sticky='ew',pady=6)
        controls=ctk.CTkFrame(body,fg_color='transparent')
        controls.grid(row=6,column=0,columnspan=4,sticky='ew',pady=8)
        button(controls,'Save set',self.save_set,width=120).pack(side='left')
        button(controls,'Set options',self.set_options,True,width=120).pack(side='left',padx=8)
        button(controls,'Skip exercise…',self.skip,True,width=145).pack(side='right')
        self.set_list=PhotoRecordList(body,('set_no','reps','weight_kg','variation'),on_open=self.edit_set)
        self.set_list.configure(height=110*self.set_list.scale)
        for key,title in [('set_no','Saved set'),('reps','Reps'),('weight_kg','kg'),('variation','Variation')]:
            self.set_list.heading(key,text=title)
        self.set_list.grid(row=7,column=0,columnspan=4,sticky='ew',pady=8)
        sets_scroll=ctk.CTkScrollbar(body,orientation='vertical',command=self.set_list.yview)
        sets_scroll.grid(row=7,column=3,sticky='nse',pady=8)
        self.set_list.configure(yscrollcommand=sets_scroll.set)
        self.set_list.empty_title='No actual sets logged'
        self.set_list.empty_help='Enter what you performed, then Save set.'
        self.set_list.empty_action='Log actual performance above'
        review=self.tabs.add('Finish & review')
        review.grid_columnconfigure(0,weight=1)
        self.summary=label(review,'',14,anchor='w',justify='left',wraplength=750)
        self.summary.grid(row=0,column=0,sticky='ew',pady=16)
        label(review,'Post-workout review · form, energy, recovery or what to change',12,MUTED).grid(row=1,column=0,sticky='w',pady=8)
        self.review=Textbox(review,height=120)
        self.review.grid(row=2,column=0,sticky='ew',pady=8)
        self.finish_button=button(review,'Finish Workout',self.finish,width=165,icon_name='circle-check')
        self.finish_button.grid(row=3,column=0,sticky='e',pady=14)
        self.session=app.coach.session(rid)
        self.review.insert('1.0',self.session['coaching']['review'])
        self.refresh()
        if not self.session['exercises'] or self.session['coaching']['finished_at']:
            self.tabs.set('Finish & review')

    def refresh(self):
        self.session=self.app.coach.session(self.rid)
        self.title_label.configure(text=self.session['name']+' · '+self.session['date'])
        self.exercise_map={f"{i+1}. {e['exercise']} · {e['completion']}":e for i,e in enumerate(self.session['exercises'])}
        current=getattr(self,'current_id',None)
        selected=next((name for name,e in self.exercise_map.items() if e['id']==current),next(iter(self.exercise_map),'No training exercises'))
        self.exercise_menu.configure(values=list(self.exercise_map) or ['No training exercises'])
        self.exercise_menu.set(selected)
        self.change_exercise()
        s=self.app.coach.session_summary(self.rid)
        self.summary.configure(text=f"{s['status']} · {s['completed_exercises']} / {s['planned_exercises']} exercises performed · {s['skipped_exercises']} skipped\n{s['completed_sets']} / {s['planned_sets']} planned sets · {s['total_reps']} actual repetitions\nRecovery option: {self.session['coaching']['recovery_option']}. Log or skip every exercise before finishing.")
        self.finish_button.configure(state='disabled' if self.session['coaching']['finished_at'] else 'normal',text='Session saved' if self.session['coaching']['finished_at'] else 'Finish Workout')

    def change_exercise(self):
        item=self.exercise_map.get(self.exercise_menu.get())
        self.set_list.delete(*self.set_list.get_children())
        if not item:
            self.instructions.configure(text='Recovery session · Rest and reassess. No demanding exercises were prescribed.')
            self.set_list.draw()
            return
        self.current_id=item['id']
        exercise=self.app.coach.exercise(item['library_key'])
        instructions=exercise['instructions'] if exercise else item['notes'] or 'Use your saved instructions and comfortable technique.'
        self.instructions.configure(text=f"{self.session['muscles'] or 'Recovery / mobility'}\nTarget: {item['target_sets']} sets × {item['target_reps']} reps · Rest {item['rest_seconds']} s · {item['equipment']}\n"+(f"Time target: {item['target_duration']:g} min · " if item['target_duration'] else '')+(f"Tempo: {item['tempo']} · " if item['tempo'] else '')+instructions)
        self.sets=self.app.db.query('SELECT * FROM fitness_sets WHERE exercise_log_id=? ORDER BY set_no',(item['id'],))
        for row in self.sets:
            self.set_list.insert('','end',iid=str(row['id']),values=(row['set_no'],row['reps'],f"{row['weight_kg']:g}",row['variation'] or row['resistance'] or 'Standard'))
        self.set_list.draw()
        self.set_input('set_no',max((r['set_no'] for r in self.sets),default=0)+1)
        self.set_input('reps',0)
        self.set_input('resistance',item['resistance'])

    def set_input(self,key,value):
        self.inputs[key].delete(0,'end')
        self.inputs[key].insert(0,str(value if value is not None else ''))

    def edit_set(self):
        selected=self.set_list.selection()
        if selected:
            row=next(r for r in self.sets if str(r['id'])==selected[0])
            for key in self.inputs:
                self.set_input(key,row[key])
            self.set_notes.delete(0,'end')
            self.set_notes.insert(0,row['notes'])

    def save_set(self):
        def action():
            if not self.exercise_map:
                raise ValueError('This is a rest-only session; use Finish & review.')
            self.app.coach.save_set(self.current_id,**{k:w.get() for k,w in self.inputs.items()},notes=self.set_notes.get())
            self.refresh()
        safe(self,action)

    def skip(self):
        if not self.exercise_map:
            return
        prompt=ctk.CTkInputDialog(text='Why are you skipping this exercise?',title='Skip exercise')
        reason=prompt.get_input()
        if reason:
            def action():
                self.app.coach.skip(self.current_id,reason)
                self.refresh()
            safe(self,action)

    def set_options(self):
        menu=themed_menu(self,tearoff=False,bg='#242424',fg=TEXT,activebackground='#454545')
        menu.add_command(label='Edit selected saved set',command=self.edit_set)
        menu.add_command(label='Delete selected saved set…',command=self.delete_set)
        self.menu=menu
        menu.tk_popup(self.winfo_pointerx(),self.winfo_pointery())

    def delete_set(self):
        selected=self.set_list.selection()
        if not selected:
            messagebox.showinfo('Choose a set','Select a saved set first.',parent=self)
            return
        if messagebox.askyesno('Delete saved set?','Remove this recorded set? If no performed sets remain, the exercise is marked skipped after correction.',parent=self):
            def action():
                self.app.coach.delete_set(int(selected[0]))
                self.refresh()
                if self.on_save:
                    self.on_save()
            safe(self,action)

    def finish(self):
        def action():
            self.app.coach.finish(self.rid,self.review.get('1.0','end-1c'))
            self.refresh()
            if self.on_save:
                self.on_save()
            self.app.notice('Workout saved locally. Review your actual sets and recovery before progressing.')
        safe(self,action)

class FitnessProgress(ctk.CTkFrame):
    def __init__(self,parent,app):
        super().__init__(parent,fg_color='transparent')
        self.app=app
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(2,weight=1)
        controls=ctk.CTkFrame(self,fg_color='transparent')
        controls.grid(row=0,column=0,sticky='ew',pady=(0,8))
        self.period=ctk.CTkOptionMenu(controls,values=['30 days','7 days'],width=105,command=lambda v:self.render())
        self.period.pack(side='left',padx=(0,8))
        self.exercise_map={e['name']:e['key'] for e in app.coach.library()}
        self.exercise=ctk.CTkOptionMenu(controls,values=list(self.exercise_map),width=220,command=lambda v:self.render(),dynamic_resizing=False)
        recorded=app.db.one("SELECT exercise FROM exercise_logs WHERE library_key!='' ORDER BY id DESC LIMIT 1")
        if recorded and recorded['exercise'] in self.exercise_map:
            self.exercise.set(recorded['exercise'])
        self.exercise.pack(side='left',padx=4)
        button(controls,'Body progress',self.body_options,True,width=130,icon_name='activity').pack(side='right')
        button(controls,'Progress review',self.review,True,width=145,icon_name='chart-no-axes-combined').pack(side='right',padx=6)
        self.summary=label(self,'',12,MUTED,anchor='w',justify='left',wraplength=730)
        self.summary.grid(row=1,column=0,sticky='ew',pady=(0,8))
        self.plot=GlassPlot(self,app)
        self.plot.grid(row=2,column=0,sticky='nsew')

    def review(self):
        from .reviews import FitnessReviewDialog
        return FitnessReviewDialog(self,self.app)

    def body_options(self):
        menu=themed_menu(self,tearoff=False,bg='#242424',fg=TEXT,activebackground='#454545')
        menu.add_command(label='Add measurement / recovery notes…',command=lambda:RecordEditor(self,self.app,'measurements',on_save=self.render))
        menu.add_command(label='Review / edit measurements…',command=lambda:RecordsDialog(self,self.app,'measurements'))
        self.menu=menu
        menu.tk_popup(self.winfo_pointerx(),self.winfo_pointery())

    def render(self):
        key=(self.app.db.revision(),self.period.get(),self.exercise.get(),date.today())
        if getattr(self,'_plot_key',None)==key:return
        self._plot_key=key
        end=date.today().isoformat()
        start=(date.today()-timedelta(days=6 if self.period.get()=='7 days' else 29)).isoformat()
        self.body=self.app.coach.body_trend(start,end)
        self.strength=self.app.coach.strength(self.exercise_map[self.exercise.get()],start,end)
        factor=2.2046226218 if self.app.db.settings()['weight_unit']=='lb' else 1
        unit='lb' if factor!=1 else 'kg'
        change='Weight change unknown: log measurements on two dates.' if self.body['change_kg'] is None else f"Calculated weight change: {self.body['change_kg']*factor:+.2f} {unit}."
        self.summary.configure(text=f"{start} to {end} · {change}\n{self.strength['recommendation']}")
        fig=Figure(figsize=(8,5),dpi=100,layout='constrained')
        ax1,ax2=fig.subplots(2,1)
        style_axes(fig,(ax1,ax2))
        points=self.body['weight_points']
        if points:
            ax1.plot([p['date'][5:] for p in points],[p['weight_kg']*factor for p in points],color='#dedede',marker='o')
        else:
            ax1.text(.5,.5,'No actual measurements in this date range',transform=ax1.transAxes,ha='center',color=MUTED)
        ax1.set_title('Measured body weight · daily mean ('+unit+')',fontsize=10)
        groups={}
        for p in self.strength['points']:
            groups.setdefault((p['variation'],p['resistance'],p['weight_kg']),[]).append(p)
        for index,(signature,values) in enumerate(groups.items()):
            name=' / '.join(str(v) for v in signature if v) or 'Standard bodyweight'
            ax2.plot([v['date'][5:] for v in values],[v['best_reps'] for v in values],marker='o',label=name[:35],color=['#dedede','#9f9f9f','#777777'][index%3])
        legacy=self.strength['legacy_aggregate_points']
        if legacy:
            ax2.scatter([p['date'][5:] for p in legacy],[p['reps'] for p in legacy],marker='x',color='#a3a3a3',label='Legacy aggregate (setup unknown)')
        if groups or legacy:
            ax2.legend(facecolor=PANEL,labelcolor=TEXT,fontsize=7)
        else:
            ax2.text(.5,.5,'Log completed sets to see real strength trends',transform=ax2.transAxes,ha='center',color=MUTED)
        ax2.set_title(self.exercise.get()+' · best actual reps in one set',fontsize=10)
        self.plot.show(fig)

class WorkoutPage(ctk.CTkFrame):
    """One weekly checklist; no active workout/session state is required."""
    def __init__(self,parent,app):
        super().__init__(parent,fg_color='transparent')
        from ..workout_checklist import WorkoutChecklist
        self.app=app;self.store=WorkoutChecklist(app.db)
        self.weekday=date.today().strftime('%A');self.editing_id=None;self.editor_job=None
        self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(1,weight=1)
        self.training_header=ChecklistHeader(self)
        self.training_header.grid(row=0,column=0,sticky='ew',pady=(0,8))
        self.sections=GlassTabs(self,command=self.section_changed)
        self.sections.grid(row=1,column=0,sticky='nsew');self.sections.bar.grid_remove()
        week=self.sections.add('Weekly checklist')
        week.grid_columnconfigure(0,weight=1);week.grid_rowconfigure(3,weight=1)
        days=ctk.CTkFrame(week,fg_color='transparent');days.grid(row=0,column=0,sticky='ew',pady=(0,8))
        self.day_buttons={}
        for index,weekday in enumerate(WEEKDAYS):
            days.grid_columnconfigure(index,weight=1,uniform='day')
            control=WeekDayCard(days,weekday,lambda d=weekday:self.select_day(d),compact=True)
            control.grid(row=0,column=index,sticky='ew',padx=(0,4));self.day_buttons[weekday]=control
        self.muscle_strip=MuscleStrip(week,self.toggle_muscle,self.more_muscles)
        self.muscle_strip.grid(row=1,column=0,sticky='ew',pady=(0,8))
        editor=ctk.CTkFrame(week,fg_color='transparent');editor.grid(row=2,column=0,sticky='ew',pady=(0,10))
        editor.grid_columnconfigure((0,1),weight=1)
        label(editor,'Exercise / target name',10,MUTED,anchor='w').grid(row=0,column=0,sticky='w',pady=(0,3))
        label(editor,'Goal (optional)',10,MUTED,anchor='w').grid(row=0,column=1,sticky='w',pady=(0,3))
        self.target_name=ctk.CTkEntry(editor,placeholder_text='Exercise or target name',height=34)
        self.target_name.grid(row=1,column=0,sticky='ew',padx=(0,8))
        self.target_goal=ctk.CTkEntry(editor,placeholder_text='Optional goal, e.g. 3 x 15 or 60 seconds',height=34)
        self.target_goal.grid(row=1,column=1,sticky='ew',padx=(0,8))
        self.add_button=CommandButton(editor,'ADD TARGET',self.save_target,width=110,height=34)
        self.add_button.grid(row=1,column=2)
        for field in (self.target_name,self.target_goal):
            field.bind('<Return>',lambda e:self.save_target())
            field.bind('<KeyRelease>',self.queue_editor)
            field.bind('<FocusOut>',lambda e:self.persist_editor())
        self.target_list=ChecklistTargets(week,('target','goal'),on_open=self.edit_target,on_toggle=self.toggle_target,on_add=lambda:self.target_name.focus_set())
        self.target_list.heading('target',text='YOUR WORKOUT TARGETS');self.target_list.heading('goal',text='OPTIONAL GOAL')
        self.target_list.empty_title='Add a target for '+self.weekday
        self.target_list.empty_help='Type any exercise name and an optional goal above.'
        self.target_list.empty_action='Type a target'
        self.target_list.grid(row=3,column=0,sticky='nsew',padx=(0,12))
        scroll=ctk.CTkScrollbar(week,command=self.target_list.yview,width=9);scroll.grid(row=3,column=0,sticky='nse')
        self.target_list.configure(yscrollcommand=scroll.set)
        actions=ctk.CTkFrame(week,fg_color='transparent');actions.grid(row=4,column=0,sticky='ew',pady=(8,0))
        for title,command,width in [('Rename / edit',self.edit_target,120),('Remove',self.remove_target,80),('Move up',lambda:self.move_target(-1),80),('Move down',lambda:self.move_target(1),95)]:
            button(actions,title,command,True,width=width,height=30).pack(side='left',padx=(0,6))
        self.cancel_button=button(actions,'Cancel edit',self.cancel_edit,True,width=90,height=30)
        self.status=label(self,'',10,MUTED,anchor='w',wraplength=720)
        self.status.grid(row=2,column=0,sticky='ew',pady=(8,0))
        footer=ctk.CTkFrame(self,fg_color='transparent');footer.grid(row=3,column=0,sticky='ew',pady=(8,0))
        self.section_menu=ctk.CTkOptionMenu(footer,values=['Weekly checklist','Workout history','Fitness progress'],width=165,height=30,command=self.choose_section)
        self.section_menu.pack(side='left')
        self.reset_button=CommandButton(footer,'RESET CHECKBOXES',self.reset_day,kind='save',width=160,height=30)
        self.reset_button.pack(side='right')
        self.history=self.sections.add('Workout history');self.history.grid_columnconfigure(0,weight=1);self.history.grid_rowconfigure(2,weight=1)
        label(self.history,'Earlier plans and measured sessions are preserved. Checklist resets save a separate snapshot.',11,MUTED,anchor='w',wraplength=700).grid(row=0,column=0,sticky='ew',pady=8)
        self.history_kind=ctk.CTkOptionMenu(self.history,values=['Earlier workouts','Earlier plans','Checklist resets'],command=lambda v:self.render_history())
        self.history_kind.grid(row=1,column=0,sticky='w',pady=(0,8))
        self.history_list=PhotoRecordList(self.history,('date','name','status'),on_open=self.history_details)
        self.history_list.grid(row=2,column=0,sticky='nsew',padx=(0,12))
        history_scroll=ctk.CTkScrollbar(self.history,command=self.history_list.yview,width=9);history_scroll.grid(row=2,column=0,sticky='nse')
        self.history_list.configure(yscrollcommand=history_scroll.set)
        for key,title in [('date','Date / day'),('name','Saved record'),('status','Status')]:self.history_list.heading(key,text=title)
        self.history_list.empty_title='No records in this view';self.history_list.empty_help='Existing records remain here; reset snapshots appear after resetting checked targets.';self.history_list.empty_action='Select another history view'
        self.history_list.on_add=lambda:self.history_kind.focus_set()
        progress_page=self.sections.add('Fitness progress');progress_page.grid_columnconfigure(0,weight=1);progress_page.grid_rowconfigure(1,weight=1)
        label(progress_page,'Charts use earlier measured sets and body measurements. A checklist tick does not claim reps or load.',11,MUTED,anchor='w',wraplength=720).grid(row=0,column=0,sticky='ew',pady=6)
        self.progress=FitnessProgress(progress_page,app);self.progress.grid(row=1,column=0,sticky='nsew')
        self.document=self.store.load();self.render_day(load_editor=True)

    def queue_editor(self,event=None):
        if self.editor_job:self.after_cancel(self.editor_job)
        self.editor_job=self.after(350,self.persist_editor)

    def persist_editor(self):
        if getattr(self,'_destroying',False):return
        if self.editor_job:self.after_cancel(self.editor_job);self.editor_job=None
        return self.store.editor(self.weekday,self.target_name.get(),self.target_goal.get(),self.editing_id)

    def flush(self):
        self.persist_editor()

    def destroy(self):
        self._destroying=True
        if self.editor_job:self.after_cancel(self.editor_job);self.editor_job=None
        super().destroy()

    def refresh_routines(self):
        # Cached navigation calls this hook after database changes or restore.
        self.flush();self.render_day(load_editor=True)
        if self.sections.get()=='Workout history':self.render_history()

    def select_day(self,weekday):
        self.flush();self.weekday=weekday;self.target_list.offset=0
        self.render_day(load_editor=True)

    def render_day(self,load_editor=False):
        from ..workout_checklist import progress
        self.document=self.store.load();self.day=self.document['days'][self.weekday]
        for weekday,control in self.day_buttons.items():
            day=self.document['days'][weekday];p=progress(day)
            control.active=weekday==self.weekday;control.today=weekday==date.today().strftime('%A')
            control.kind=' / '.join(day['muscles']) or 'YOUR PLAN'
            control.state='COMPLETED' if p['total'] and p['completed']==p['total'] else f"{p['completed']} / {p['total']} DONE" if p['total'] else 'NO TARGETS'
            control.draw()
        self.muscle_strip.selected=self.day['muscles'];self.muscle_strip.draw()
        selection=self.target_list.selection()
        self.target_list.delete(*self.target_list.get_children());self.target_list.details.clear()
        for target in self.day['targets']:
            self.target_list.insert('','end',iid=target['id'],values=(target['name'],target['goal']))
            self.target_list.details[target['id']]=dict(completed=target['completed'])
        if selection and self.target_list.exists(selection[0]):self.target_list.selected=selection[0]
        self.target_list.empty_title='Add a target for '+self.weekday;self.target_list.draw()
        p=progress(self.day)
        self.training_header.weekday=self.weekday;self.training_header.completed=p['completed'];self.training_header.total=p['total'];self.training_header.draw()
        self.status.configure(text=f"{self.weekday}: {p['completed']} / {p['total']} targets completed | Saved automatically | Reset clears checkboxes only.")
        if load_editor:
            draft=self.day.get('editor',{})
            self.editing_id=draft.get('target_id')
            for field,value in [(self.target_name,draft.get('name','')),(self.target_goal,draft.get('goal',''))]:
                field.delete(0,'end')
                if value:field.insert(0,value)
            self.add_button.configure(text='SAVE TARGET' if self.editing_id else 'ADD TARGET')
            self.cancel_button.pack(side='right') if self.editing_id else self.cancel_button.pack_forget()
        self.app.wallpaper.request()

    def save_target(self):
        def action():
            rid=self.store.save_target(self.weekday,self.target_name.get(),self.target_goal.get(),self.editing_id)
            if self.editor_job:self.after_cancel(self.editor_job);self.editor_job=None
            self.editing_id=None;self.render_day(load_editor=True);self.target_list.select_index(self.target_list.order.index(rid));self.target_name.focus_set()
            return rid
        return safe(self,action)

    def selected_target(self):
        selected=self.target_list.selection()
        return next((t for t in self.day['targets'] if selected and t['id']==selected[0]),None)

    def edit_target(self):
        target=self.selected_target()
        if target:
            self.flush();self.editing_id=target['id']
            for field,key in [(self.target_name,'name'),(self.target_goal,'goal')]:field.delete(0,'end');field.insert(0,target[key])
            self.persist_editor();self.add_button.configure(text='SAVE TARGET');self.cancel_button.pack(side='right');self.target_name.focus_set()

    def cancel_edit(self):
        if self.editor_job:self.after_cancel(self.editor_job);self.editor_job=None
        self.editing_id=None;self.target_name.delete(0,'end');self.target_goal.delete(0,'end');self.persist_editor();self.render_day(load_editor=True)

    def remove_target(self):
        target=self.selected_target()
        if target:
            def action():
                self.store.remove(self.weekday,target['id'])
                if self.editing_id==target['id']:self.cancel_edit()
                self.render_day()
            safe(self,action)

    def move_target(self,direction):
        target=self.selected_target()
        if target:
            safe(self,lambda:self.store.move(self.weekday,target['id'],direction));self.render_day()
            self.target_list.select_index(self.target_list.order.index(target['id']))

    def toggle_target(self,rid):
        target=next(t for t in self.day['targets'] if t['id']==rid)
        safe(self,lambda:self.store.complete(self.weekday,rid,not target['completed']));self.render_day()

    def toggle_muscle(self,muscle):
        selected=list(self.day['muscles'])
        groups=['Legs','Quadriceps','Hamstrings','Glutes','Calves'] if muscle=='Legs' else [muscle]
        if any(m in selected for m in groups):selected=[m for m in selected if m not in groups]
        else:selected.append(muscle)
        self.apply_muscles(selected)

    def more_muscles(self):
        selected=['Core/abs' if m=='Abs' else m for m in self.day['muscles']]
        return MuscleSelectionDialog(self,self.app,selected,self.apply_muscles)

    def apply_muscles(self,selected):
        selected=list(dict.fromkeys('Abs' if m=='Core/abs' else m for m in selected))
        safe(self,lambda:self.store.muscles(self.weekday,selected));self.render_day()

    def reset_day(self):
        if messagebox.askyesno('Reset checkboxes?',f"Mark all {self.weekday} targets incomplete for a new training day? The saved plan and muscle selection stay intact. A snapshot of checked targets is kept in Workout history.",parent=self):
            safe(self,lambda:self.store.reset(self.weekday));self.render_day()

    def choose_section(self,name):
        self.flush();self.sections.set(name);self.section_changed()

    def section_changed(self):
        self.section_menu.set(self.sections.get())
        self.reset_button.pack_forget()
        if self.sections.get()=='Weekly checklist':self.reset_button.pack(side='right');self.render_day()
        elif self.sections.get()=='Workout history':self.render_history()
        else:self.progress.render()

    def render_history(self):
        self.history_rows={};kind=self.history_kind.get();self.history_list.delete(*self.history_list.get_children())
        if kind=='Earlier workouts':
            rows=self.app.service.list('workouts')
            for row in rows:
                key=str(row['id']);self.history_rows[key]=row
                self.history_list.insert('','end',iid=key,values=(row['date'],row['name'],row['status']))
        elif kind=='Earlier plans':
            for row in self.app.service.list('workout_days'):
                key=str(row['id']);self.history_rows[key]=row
                self.history_list.insert('','end',iid=key,values=(row['weekday'],row['name'],'Preserved plan'))
        else:
            from ..workout_checklist import progress
            for row in reversed(self.store.load()['history']):
                key=row['id'];self.history_rows[key]=row;p=progress(row)
                self.history_list.insert('','end',iid=key,values=(row['saved_at'][:16],row['weekday'],f"{p['completed']} / {p['total']} checked"))
        self.history_list.draw();self.app.wallpaper.request()

    def history_details(self):
        selection=self.history_list.selection()
        if not selection:return
        row=self.history_rows[selection[0]];kind=self.history_kind.get()
        text=[]
        if kind=='Checklist resets':
            text=[row['weekday']+' | '+row['saved_at'],'Muscles: '+', '.join(row['muscles']),'']
            text += [(' [x] ' if t['completed'] else ' [ ] ')+t['name']+(' - '+t['goal'] if t['goal'] else '') for t in row['targets']]
        else:
            text=[str(k).replace('_',' ').capitalize()+': '+str(v) for k,v in row.items()]
            table='planned_exercises' if kind=='Earlier plans' else 'exercise_logs';field='day_id' if kind=='Earlier plans' else 'workout_id'
            for exercise in self.app.service.list(table,filters={field:row['id']}):
                text+=['','EXERCISE: '+exercise['exercise'],json.dumps(exercise,ensure_ascii=False,indent=2)]
                if table=='exercise_logs':
                    for actual in self.app.db.query('SELECT * FROM fitness_sets WHERE exercise_log_id=? ORDER BY set_no',(exercise['id'],)):
                        text+=['Saved set: '+json.dumps(actual,ensure_ascii=False)]
        dialog=Dialog(self,'Saved workout history',820,650)
        dialog.grid_columnconfigure(0,weight=1);dialog.grid_rowconfigure(1,weight=1)
        label(dialog,'Saved workout history (read only)',20).grid(row=0,column=0,sticky='w',padx=20,pady=15)
        output=Textbox(dialog,wrap='word');output.grid(row=1,column=0,sticky='nsew',padx=20,pady=12)
        output.insert('1.0','\n'.join(text));output.configure(state='disabled')
        button(dialog,'Close',dialog.destroy,True,width=90).grid(row=2,column=0,sticky='e',padx=20,pady=12)
        return dialog

class MuscleSelectionDialog(Dialog):
    def __init__(self,parent,app,selected,on_save):
        super().__init__(parent,'Target muscle groups',760,600)
        self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(1,weight=1)
        label(self,'Target muscle groups',22).grid(row=0,column=0,sticky='w',padx=20,pady=16)
        self.picker=MusclePicker(self,app.coach,selected);self.picker.grid(row=1,column=0,sticky='nsew',padx=20)
        button(self,'Apply selection',lambda:(on_save(self.picker.selected),self.destroy()),width=150).grid(row=2,column=0,sticky='e',padx=20,pady=16)

class PreferencesDialog(Dialog):
    def __init__(self,parent,app,on_save=None):
        super().__init__(parent,'Coach preferences',800,700)
        self.app,self.on_save=app,on_save
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(1,weight=1)
        label(self,'Your coaching preferences',23).grid(row=0,column=0,sticky='w',padx=22,pady=14)
        body=ScrollFrame(self,fg_color='transparent')
        body.grid(row=1,column=0,sticky='nsew',padx=22)
        body.grid_columnconfigure(1,weight=1)
        p=app.coach.preferences()
        self.inputs={}
        specs=[('goal','Your goal',['Maintain fitness','Build strength','Improve conditioning','Weight management']),
               ('experience','Training experience',['Beginner','Intermediate','Experienced']),
               ('diet','Dietary preference',['No preference','Vegetarian','Vegan','Egg-inclusive']),
               ('restrictions','Restrictions (comma-separated food names)',None),('budget','Food budget / notes',None),('meals','Meals per day',None)]
        for row,(key,title,choices) in enumerate(specs):
            label(body,title,12,MUTED).grid(row=row,column=0,sticky='w',padx=8,pady=8)
            if choices:
                widget=ctk.CTkOptionMenu(body,values=choices,width=220)
                widget.set(p[key])
            else:
                widget=ctk.CTkEntry(body,width=250)
                widget.insert(0,str(p[key]))
            widget.grid(row=row,column=1,sticky='ew',padx=8,pady=8)
            self.inputs[key]=widget
        label(body,'Available equipment',14).grid(row=6,column=0,columnspan=2,sticky='w',padx=8,pady=10)
        self.equipment=list(p['equipment'])
        self.equipment_buttons={}
        for index,equipment in enumerate(EQUIPMENT):
            control=button(body,('✓ ' if equipment in self.equipment else '')+equipment,lambda e=equipment:self.toggle(e),equipment not in self.equipment,width=230)
            control.grid(row=7+index//2,column=index%2,sticky='ew',padx=8,pady=5)
            self.equipment_buttons[equipment]=control
        label(body,'Targets remain editable in Settings. No automatic calorie prescription. Restrictions use text matching; verify ingredients and allergens yourself. Budget is a planning note, not verified pricing.',11,MUTED,wraplength=680,justify='left').grid(row=11,column=0,columnspan=2,sticky='w',padx=8,pady=14)
        button(self,'Save preferences',self.save,width=165).grid(row=2,column=0,sticky='e',padx=22,pady=14)

    def toggle(self,equipment):
        if equipment=='Bodyweight':
            return
        self.equipment.remove(equipment) if equipment in self.equipment else self.equipment.append(equipment)
        control=self.equipment_buttons[equipment]
        control.secondary=equipment not in self.equipment
        control.configure(text=('✓ ' if equipment in self.equipment else '')+equipment)

    def save(self):
        def action():
            self.app.coach.save_preferences({**{k:w.get() for k,w in self.inputs.items()},'equipment':self.equipment})
            if self.on_save:
                self.on_save()
            self.destroy()
        safe(self,action)


class WorkoutDayDialog(Dialog):
    """A dated day workspace; saved plans and actual session snapshots stay separate."""
    def __init__(self,parent,app,routine_id,selected,day,on_save=None):
        super().__init__(parent,selected['weekday']+' workout',900,800)
        self.app,self.routine_id,self.selected,self.day,self.on_save=app,routine_id,selected,day,on_save
        self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(1,weight=1)
        label(self,selected['weekday']+' | '+selected['date'],23).grid(row=0,column=0,sticky='w',padx=20,pady=12)
        body=ScrollFrame(self,fg_color='transparent');body.grid(row=1,column=0,sticky='nsew',padx=20)
        body.grid_columnconfigure(0,weight=1)
        header=ctk.CTkFrame(body,fg_color='transparent');header.grid(row=0,column=0,sticky='ew')
        self.name=ctk.CTkEntry(header,width=460);self.name.insert(0,day['name'] if day else selected['weekday']+' workout');self.name.pack(side='left',fill='x',expand=True,padx=(0,12))
        self.rest=ctk.StringVar(value='Yes' if day and day['recovery']=='Yes' else 'No')
        ctk.CTkCheckBox(header,text='Rest Day',variable=self.rest,onvalue='Yes',offvalue='No').pack(side='right')
        self.muscle_panel=ctk.CTkFrame(body,fg_color='transparent')
        self.muscle_panel.grid(row=1,column=0,sticky='ew',pady=8)
        self.muscle_panel.grid_columnconfigure(0,weight=1)
        self.muscle_summary=label(self.muscle_panel,'',12,MUTED,anchor='w',wraplength=600)
        self.muscle_summary.grid(row=0,column=0,sticky='ew')
        button(self.muscle_panel,'Muscle groups',self.toggle_muscles,True,width=140).grid(row=0,column=1,padx=8)
        self.muscles=MusclePicker(self.muscle_panel,app.coach,[m.strip() for m in day['muscles'].split(',') if m.strip()] if day else [])
        self.muscles.grid(row=1,column=0,columnspan=2,sticky='ew',pady=6)
        self.muscles_expanded=not bool(day)
        if not self.muscles_expanded:self.muscles.grid_remove()
        controls=ctk.CTkFrame(body,fg_color='transparent');controls.grid(row=2,column=0,sticky='ew',pady=8)
        button(controls,'Save plan',self.save_plan,width=115).pack(side='left')
        button(controls,'Add exercise',self.add_exercise,True,width=125).pack(side='left',padx=6)
        button(controls,'Edit',self.edit_exercise,True,width=65).pack(side='left',padx=3)
        button(controls,'Remove',self.remove_exercise,True,width=85).pack(side='left',padx=3)
        self.mode=ctk.CTkOptionMenu(controls,values=['Workout plan','Actual session'],width=155,command=lambda v:self.refresh())
        self.mode.pack(side='right')
        self.progress=label(body,'',12,MUTED,anchor='w',justify='left',wraplength=760);self.progress.grid(row=3,column=0,sticky='ew',pady=8)
        self.exercises=PhotoRecordList(body,('exercise','sets','reps','load'),on_open=self.log_exercise,on_toggle=self.toggle_exercise)
        self.exercises.configure(height=200)
        for key,title in [('exercise','Exercise / completion'),('sets','Sets'),('reps','Reps / time'),('load','kg')]:self.exercises.heading(key,text=title)
        self.exercises.grid(row=4,column=0,sticky='ew',padx=(0,12))
        scroll=ctk.CTkScrollbar(body,command=self.exercises.yview);scroll.grid(row=4,column=0,sticky='nse');self.exercises.configure(yscrollcommand=scroll.set)
        self.exercises.empty_title='No exercises for this day';self.exercises.empty_help='Save a plan, add exercises, or select Rest Day.'
        self.exercises.empty_action='Add exercise';self.exercises.on_add=self.add_exercise
        label(body,'Post-workout review (optional)',12,MUTED).grid(row=5,column=0,sticky='w',pady=(10,4))
        self.review=Textbox(body,height=65);self.review.grid(row=6,column=0,sticky='ew')
        footer=ctk.CTkFrame(self,fg_color='transparent');footer.grid(row=2,column=0,sticky='ew',padx=20,pady=14)
        self.start_button=button(footer,'Start Workout',self.start,width=145,icon_name='play');self.start_button.pack(side='left')
        self.finish_button=button(footer,'Finish Workout',self.finish,width=145,icon_name='circle-check');self.finish_button.pack(side='left',padx=8)
        button(footer,'Close',self.destroy,True,width=90).pack(side='right')
        if day and day.get('session'):self.mode.set('Actual session')
        self.refresh()

    def refresh(self):
        self.session=None
        self.muscle_summary.configure(text=', '.join(self.muscles.selected) or 'Choose target muscles, or use Rest Day.')
        if self.day:
            self.day=self.app.service.get('workout_days',self.day['id'])
            saved=self.app.db.one('SELECT workout_id FROM fitness_sessions WHERE day_id=? AND session_date=?',(self.day['id'],self.selected['date']))
            if saved:self.session=self.app.coach.session(saved['workout_id'])
        self.actual=bool(self.session and self.mode.get()=='Actual session')
        self.rows=self.session['exercises'] if self.actual else self.app.coach.planned(self.day['id']) if self.day else []
        self.exercises.delete(*self.exercises.get_children());self.exercises.details.clear()
        for row in self.rows:
            duration=row['target_duration'] if self.actual else row['duration_min']
            self.exercises.insert('','end',iid=str(row['id']),values=(row['exercise'],
                f"{row['sets']} / {row['target_sets']}" if self.actual else row['sets'],
                f"{duration:g} min" if duration else row['target_reps'] if self.actual else row['reps'],f"{row['weight_kg']:g}"))
            self.exercises.details[str(row['id'])]=dict(completed=self.actual and row['completion']=='Completed')
        self.exercises.on_toggle=self.toggle_exercise if self.actual else None
        text='Plan only | Saving this plan does not record performance. Start to log actual sets.'
        if self.session:
            summary=self.app.coach.session_summary(self.session['id'])
            count=summary['planned_exercises'];done=summary['completed_exercises'];skipped=summary['skipped_exercises']
            text=f"{done} / {count} exercises complete | {skipped} skipped | {(done+skipped)/max(1,count):.0%} resolved | {summary['status']}\nSession snapshots preserve history when the plan changes. Check completion after logging actual sets."
        self.progress.configure(text=text)
        finished=self.session and self.session['coaching']['finished_at']
        self.finish_button.configure(state='normal' if self.session and not finished else 'disabled')
        self.start_button.configure(text='Review session' if finished else 'Resume Workout' if self.session else 'Start Workout',
            state='normal' if self.session or self.selected['date']<=date.today().isoformat() else 'disabled')
        self.exercises.draw();self.wallpaper.request()

    def toggle_muscles(self):
        self.muscles_expanded=not self.muscles_expanded
        self.muscles.grid() if self.muscles_expanded else self.muscles.grid_remove()
        self.muscle_summary.configure(text=', '.join(self.muscles.selected) or 'Choose target muscles, or use Rest Day.')
        self.wallpaper.request()

    def save_plan(self):
        def action():
            rid=self.app.coach.configure_day(self.routine_id,self.selected['weekday'],self.name.get(),self.muscles.selected,
                self.rest.get()=='Yes',self.day['notes'] if self.day else 'Rest and comfortable mobility as needed.',self.day['id'] if self.day else None)
            self.day=self.app.service.get('workout_days',rid);self.refresh()
            if self.on_save:self.on_save()
            self.app.notice('Workout plan saved. Existing session history is unchanged.')
        safe(self,action)

    def add_exercise(self):
        if not self.day:
            messagebox.showinfo('Save the day first','Save the workout name, muscles and Rest Day choice before adding exercises.',parent=self);return
        self.mode.set('Workout plan')
        return ExercisePicker(self,self.app,self.day['id'],self.refresh)

    def selected_row(self):
        ids=self.exercises.selection()
        return next((r for r in self.rows if str(r['id'])==ids[0]),None) if ids else None

    def edit_exercise(self):
        if self.actual:
            self.mode.set('Workout plan');self.refresh();return
        row=self.selected_row()
        if row:return ExercisePicker(self,self.app,self.day['id'],self.refresh,row)

    def remove_exercise(self):
        row=self.selected_row()
        if not self.actual and row and messagebox.askyesno('Remove from plan?','Remove this exercise from the plan? Saved workout history is kept.',parent=self):
            self.app.service.delete('planned_exercises',row['id']);self.refresh()

    def start(self):
        if self.session:return self.open_session(self.session['id'])
        if not self.day:return self.save_plan()
        return ReadinessDialog(self,self.app,self.day['id'],self.selected['date'],self.open_session)

    def open_session(self,rid):
        self.mode.set('Actual session');self.refresh()
        dialog=SessionDialog(self,self.app,rid,self.refresh)
        dialog.bind('<Destroy>',lambda e:self.refresh() if e.widget is dialog and self.winfo_exists() else None,add='+')
        return dialog

    def log_exercise(self):
        if not self.actual:return self.edit_exercise()
        row=self.selected_row();dialog=self.open_session(self.session['id'])
        if row:
            key=next(k for k,v in dialog.exercise_map.items() if v['id']==row['id'])
            dialog.exercise_menu.set(key);dialog.change_exercise()
        return dialog

    def toggle_exercise(self,rid):
        if self.session and self.session['coaching']['finished_at']:return
        row=next(r for r in self.rows if str(r['id'])==str(rid))
        if not self.app.db.one('SELECT id FROM fitness_sets WHERE exercise_log_id=?',(row['id'],)):
            self.exercises.selection_set(str(rid));return self.log_exercise()
        safe(self,lambda:self.app.coach.set_exercise_completed(row['id'],row['completion']!='Completed'))
        self.refresh()

    def finish(self):
        def action():
            if not self.session:raise ValueError('Start the workout and log actual sets first.')
            self.app.coach.finish(self.session['id'],self.review.get('1.0','end-1c'));self.refresh()
            if self.on_save:self.on_save()
            self.app.notice('Workout finished and saved locally.')
        safe(self,action)

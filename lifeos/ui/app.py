import logging
import json
from . import appearance
from datetime import date,datetime
from tkinter import messagebox
import customtkinter as ctk
from ..db import Database
from ..service import Service
from ..analytics import Analytics
from .common import BG,PANEL,CARD,ACCENT,BLUE,TEXT,MUTED,button,label,configure_tree,safe
from .records import RecordsFrame
from .dashboard import Dashboard
from .analytics import AnalyticsPage
from .settings import SettingsPage
from .theme import install_theme,GlassCard,BORDER,SURFACE_BLUE,SURFACE_VIOLET
from .icons import NAV_ICONS,ASSETS,icon
from .backgrounds import PhotographicBackground
from .photowidgets import PhotoNavButton
from .collections import GlassTabs

PAGES={
    'Dashboard':(),
    'DSA Tracker':('problems','solutions'),
    'Learning Paths':('paths','concepts','study_sessions'),
    'Workout Planner':('workout_routines','workout_days','planned_exercises','workouts','exercise_logs'),
    'Diet & Nutrition':('food_logs','foods','water_logs','measurements'),
    'Daily Planner':('tasks','daily_routines','focus_sessions'),
    'Analytics':(), 'Settings':(),
}

class LifeOS(ctk.CTk):
    def __init__(self,db=None):
        self.db=db or Database()
        appearance.select(self.db.settings().get('theme',appearance.CURRENT))
        install_theme()
        super().__init__()
        self.appearance=appearance.Appearance(self)
        window_icon=ASSETS/'lifeos-monochrome.ico'
        if window_icon.exists():
            self.iconbitmap(str(window_icon))
        self.title('LifeOS · Your personal command center')
        scaling=self._get_window_scaling()
        available_width=int(self.winfo_screenwidth()/scaling)-45
        available_height=int(self.winfo_screenheight()/scaling)-85
        self.geometry(f'{min(1024,available_width)}x{min(638,available_height)}+18+18')
        self.minsize(min(960,available_width),min(600,available_height))
        self.configure(fg_color=BG)
        self.service=Service(self.db)
        self.analytics=Analytics(self.db)
        from ..fitness import FitnessCoach
        self.coach=FitnessCoach(self.service)
        self.selected={}
        self.current_page=''
        self.reminded=set()
        self.jobs=[]
        self.notice_job=None
        self.record_frames={}
        self.page_cache={}
        configure_tree(self)
        self.wallpaper=PhotographicBackground(self)
        self.grid_columnconfigure(1,weight=1)
        self.grid_rowconfigure(1,weight=1)
        self.sidebar=GlassCard(self,tint='#171717',width=190,corner_radius=0,border_width=0)
        self.sidebar.grid(row=0,column=0,rowspan=3,sticky='nsew')
        self.sidebar.grid_propagate(False)
        label(self.sidebar,'LifeOS',20,TEXT,icon_name='layout-dashboard').pack(anchor='w',padx=22,pady=(28,24))
        self.nav={}
        for page in PAGES:
            nav=PhotoNavButton(self.sidebar,page,lambda p=page:self.show(p),image=icon(NAV_ICONS[page],MUTED,18),width=166,height=31)
            nav.pack(padx=12,pady=3)
            self.nav[page]=nav
        label(self.sidebar,'ON YOUR DEVICE\nPrivate by default',10,MUTED,justify='left',icon_name='shield-check').pack(side='bottom',anchor='w',padx=22,pady=22)
        self.header=ctk.CTkFrame(self,fg_color='transparent')
        self.header.grid(row=0,column=1,sticky='ew',padx=22,pady=(21,8))
        self.page_title=label(self.header,'Dashboard',23)
        self.page_title.pack(side='left')
        self.content=ctk.CTkFrame(self,fg_color='transparent')
        self.content.grid(row=1,column=1,sticky='nsew',padx=(30,20),pady=12)
        self.content.grid_columnconfigure(0,weight=1)
        self.content.grid_rowconfigure(0,weight=1)
        self.bottom=GlassCard(self,tint='#1b1b1b',corner_radius=18)
        self.bottom.grid(row=2,column=1,sticky='ew',padx=20,pady=(5,14))
        self.notice_label=label(self.bottom,'Ready · All changes save locally',10,MUTED,anchor='w',wraplength=960)
        self.notice_label.pack(fill='x',padx=20,pady=(5,2))
        self.focus_toggle=button(self.bottom,'Focus timer',self.toggle_focus,True,width=110,height=26,icon_name='timer')
        self.focus_toggle.pack(anchor='e',padx=14,pady=(0,5))
        timer=ctk.CTkFrame(self.bottom,fg_color='transparent')
        self.timer_bar=timer
        self.focus_expanded=True
        timer.pack(fill='x',padx=20,pady=(2,12))
        self.timer_title=ctk.CTkEntry(timer,placeholder_text='Focus session title',width=180,height=32)
        self.timer_title.pack(side='left',padx=(0,7))
        self.timer_minutes=ctk.CTkEntry(timer,width=65,height=32)
        self.timer_minutes.insert(0,str(self.db.settings()['focus_minutes']))
        self.timer_minutes.pack(side='left',padx=4)
        label(timer,'min',11,MUTED).pack(side='left',padx=(0,7))
        button(timer,'Start',self.start_timer,width=65,height=32).pack(side='left',padx=3)
        self.pause=button(timer,'Pause',self.pause_timer,True,width=75,height=32)
        self.pause.pack(side='left',padx=3)
        self.finish=button(timer,'Finish',lambda:self.timer_action('finish'),True,width=70,height=32)
        self.finish.pack(side='left',padx=3)
        self.timer_label=label(timer,'No active session',12,ACCENT,anchor='e')
        self.timer_label.pack(side='right',padx=8)
        try:
            self.db.automatic_backup()
        except Exception as error:
            logging.exception('Automatic backup failed')
            self.notice('Automatic backup failed: '+str(error))
        self.service.generate_tasks()
        self.show('Dashboard')
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.timer_job=self.after(500,self.tick)

    def show(self,page):
        def action():
            from ..models import ENTITIES
            previous=self.page_cache.get(self.current_page)
            if previous and hasattr(previous['frame'],'flush'):previous['frame'].flush()
            if previous and isinstance(previous['frame'],Dashboard) and previous['frame'].timer_job:
                previous['frame'].after_cancel(previous['frame'].timer_job)
                previous['frame'].timer_job=None
            self.current_page=page
            if page in ('Dashboard','Workout Planner'):
                self.header.grid_remove()
                self.bottom.grid_remove()
            else:
                self.header.grid()
                self.bottom.grid()
            self.set_focus_expanded(page=='Daily Planner')
            for name,nav in self.nav.items():
                nav.configure(fg_color='#444444' if name==page else 'transparent',text_color='#f0f0f0' if name==page else MUTED,
                              border_width=1 if name==page else 0,border_color='#777777',
                              image=icon(NAV_ICONS[name],ACCENT if name==page else MUTED,18))
            self.page_title.configure(text=page,image=icon(NAV_ICONS[page],ACCENT,23))
            for child in self.content.winfo_children():child.grid_remove()
            cached=self.page_cache.get(page)
            if cached:
                self.page_frame=cached['frame']
                self.record_frames=cached['records']
                self.tabs=cached['tabs']
                self.nutrition_summary=cached['nutrition_summary']
                self.page_frame.grid(row=0,column=0,sticky='nsew')
                revision=(self.db.revision(),date.today())
                if cached['revision']!=revision:
                    for records in self.record_frames.values():records.refresh()
                    if hasattr(self.page_frame,'refresh_routines'):self.page_frame.refresh_routines()
                    elif hasattr(self.page_frame,'refresh_meals'):self.page_frame.refresh_meals()
                    elif isinstance(self.page_frame,AnalyticsPage):self.page_frame.render()
                if isinstance(self.page_frame,Dashboard):
                    self.page_frame.refresh_data()
                    self.page_frame.timer_job=self.page_frame.after(1000,self.page_frame.update_timer)
                cached['revision']=revision
                self.wallpaper.set_page(page)
                return
            self.record_frames={}
            self.nutrition_summary=None
            if page=='Dashboard':
                frame=Dashboard(self.content,self)
            elif page=='Analytics':
                frame=AnalyticsPage(self.content,self)
            elif page=='Settings':
                frame=SettingsPage(self.content,self)
            elif page=='Diet & Nutrition':
                from .meals import NutritionPage
                frame=NutritionPage(self.content,self)
            elif page=='Workout Planner':
                from .fitness import WorkoutPage
                frame=WorkoutPage(self.content,self)
            else:
                frame=ctk.CTkFrame(self.content,fg_color='transparent')
                frame.grid_columnconfigure(0,weight=1)
                frame.grid_rowconfigure(1,weight=1)
                if page=='Diet & Nutrition':
                    summary=GlassCard(frame)
                    summary.grid(row=0,column=0,sticky='ew',pady=(0,12))
                    summary.grid_columnconfigure(0,weight=1)
                    self.nutrition_summary=label(summary,'',12,ACCENT,justify='left',anchor='w',wraplength=560)
                    self.nutrition_summary.grid(row=0,column=0,sticky='ew',padx=14,pady=12)
                    from .nutrition import NutritionReviewDialog
                    button(summary,'Nutrition review',lambda:NutritionReviewDialog(self,self),True,width=145,icon_name='chart-no-axes-combined').grid(row=0,column=1,padx=12,pady=10)
                    self.refresh_nutrition()
                elif page=='DSA Tracker':
                    today=date.today().isoformat()
                    d=self.analytics.dashboard()
                    label(frame,f"Today: {d['today']['dsa']['solved']} / {d['goals']['dsa_target']} solved · Last 7 days: {d['week']['dsa']['solved']} solved, {d['week']['dsa']['independent']} independent · {len(d['today']['dsa_revisions'])} due for revision",12,ACCENT,anchor='w').grid(row=0,column=0,sticky='ew',pady=(0,10))
                elif page=='Learning Paths':
                    label(frame,'Your subjects, your pace. Add a subject, track its concepts, then record study sessions. Your history stays on this device.',12,MUTED,anchor='w',wraplength=1100).grid(row=0,column=0,sticky='ew',pady=(0,10))
                tabs=GlassTabs(frame,command=self.tab_changed)
                tabs.grid(row=1,column=0,sticky='nsew')
                self.tabs=tabs
                for table in PAGES[page]:
                    name=ENTITIES[table].title
                    tab=tabs.add(name)
                    tab.grid_columnconfigure(0,weight=1)
                    tab.grid_rowconfigure(0,weight=1)
                    records=RecordsFrame(tab,self,table)
                    records.grid(row=0,column=0,sticky='nsew')
                    self.record_frames[name]=records
            self.page_frame=frame
            frame.grid(row=0,column=0,sticky='nsew')
            self.page_cache[page]=dict(frame=frame,records=self.record_frames,tabs=getattr(self,'tabs',None),
                nutrition_summary=self.nutrition_summary,revision=(self.db.revision(),date.today()))
            self.wallpaper.set_page(page)
        safe(self,action)

    def set_theme(self,name):
        if name not in appearance.OPTIONS:raise ValueError('Choose a supported theme.')
        self.db.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',('theme',json.dumps(name)))
        appearance.select(name)
        settings=self.page_cache.get('Settings')
        if settings:settings['frame'].inputs['theme'][0].set(name)
        self.appearance.apply()
        self.notice('Appearance saved: '+name)

    def clear_page_cache(self):
        for cached in list(self.page_cache.values()):
            cached['frame'].destroy()
        self.page_cache.clear()
        self.record_frames={}
        self.tabs=None
        self.nutrition_summary=None

    def set_focus_expanded(self,expanded):
        self.focus_expanded=expanded
        if expanded:
            self.timer_bar.pack(fill='x',padx=16,pady=(0,10))
        else:
            self.timer_bar.pack_forget()
        self.focus_toggle.configure(text='Hide timer' if expanded else 'Focus timer')

    def toggle_focus(self):
        self.set_focus_expanded(not self.focus_expanded)
        self.wallpaper.request()

    def tab_changed(self):
        if self.record_frames:
            records=self.record_frames.get(self.tabs.get())
            if records:
                name=records.filter_field.get()
                records.change_filter(name)
                records.refresh()
        self.refresh_nutrition()

    def refresh_nutrition(self):
        if self.current_page=='Diet & Nutrition' and hasattr(getattr(self,'page_frame',None),'refresh_meals'):
            self.page_frame.refresh_meals()
            return
        if getattr(self,'nutrition_summary',None) and self.nutrition_summary.winfo_exists():
            day=date.today().isoformat()
            s=self.analytics.summary(day,day)
            n=s['nutrition'];g=self.db.goals_on(day)
            text=f"Today · {n['calories']:,.0f} / {g['calories']:g} kcal · Protein {n['protein']:.1f} / {g['protein']:g} g\nCarbs {n['carbs']:.1f} g · Fat {n['fat']:.1f} g · Water {s['water']['ml']:g} / {g['water_ml']:g} ml"
            if self.db.settings()['nutrition_mode']=='Detailed':
                text+='\nKnown totals · '+' · '.join(f"{key.replace('_',' ')} {n[key]:.1f}"+(f" ({n[key+'_unknown']} entries unknown)" if n[key+'_unknown'] else '') for key in ('fibre','sugar','calcium_mg','iron_mg','sodium_mg','potassium_mg'))
            meals=self.db.query('SELECT meal,SUM(calories) kcal FROM food_logs WHERE date=? GROUP BY meal',(day,))
            text+='\n'+(' · '.join(f"{r['meal']}: {r['kcal']:.0f} kcal" for r in meals) if meals else 'No meals logged today. Add a food entry to begin.')
            self.nutrition_summary.configure(text=text)

    def notice(self,text):
        self.notice_label.configure(text=text)
        self.refresh_nutrition()

    def start_timer(self):
        def action():
            self.service.start_timer(self.timer_title.get(),float(self.timer_minutes.get()))
            self.notice('Focus timer started. It survives closing and reopening LifeOS.')
        safe(self,action)

    def pause_timer(self):
        timer=self.service.active_timer()
        if timer:
            self.timer_action('resume' if timer['status']=='Paused' else 'pause')

    def timer_action(self,action):
        safe(self,lambda:self.service.timer_action(action))
        if self.current_page=='Daily Planner':
            for frame in self.record_frames.values():
                frame.refresh()

    def tick(self):
        try:
            timer=self.service.active_timer()
            self.pause.configure(state='normal' if timer else 'disabled')
            self.finish.configure(state='normal' if timer else 'disabled')
            if timer:
                remaining=self.service.timer_remaining(timer)
                seconds=int(remaining+.99)
                self.timer_label.configure(text=f"{timer['title'][:32]} · {seconds//60:02}:{seconds%60:02} · {timer['status']}")
                self.pause.configure(text='Resume' if timer['status']=='Paused' else 'Pause',
                                     image=icon('play' if timer['status']=='Paused' else 'pause',MUTED,16))
                if remaining<=0:
                    self.timer_action('finish')
                    self.bell()
                    self.notice('Focus complete: '+timer['title'])
            else:
                self.timer_label.configure(text='No active session')
            now=datetime.now()
            if getattr(self,'last_date',date.today())!=date.today():
                self.service.generate_tasks()
                self.reminded.clear()
                if self.current_page=='Dashboard':
                    self.show('Dashboard')
            self.last_date=date.today()
            if self.db.settings()['reminders']=='Yes':
                for routine in self.service.list('daily_routines',filters={'active':'Yes'}):
                    if now.strftime('%A') in routine['weekdays'].split(',') and routine['time']==now.strftime('%H:%M') and routine['id'] not in self.reminded:
                        self.reminded.add(routine['id'])
                        self.bell()
                        self.notice('Routine reminder: '+routine['title'])
        except Exception:
            logging.exception('Timer / reminder tick failed')
        self.timer_job=self.after(1000,self.tick)

    def report_callback_exception(self,exc,value,tb):
        logging.error('UI callback failed',exc_info=(exc,value,tb))
        messagebox.showerror('LifeOS error',str(value),parent=self)

    def close(self):
        try:
            for page in self.page_cache.values():
                if hasattr(page['frame'],'flush'):page['frame'].flush()
        except Exception as error:
            logging.exception('Could not save pending workout text')
            messagebox.showerror('LifeOS could not save',str(error),parent=self)
            return
        if self.service.active_timer():
            # Running sessions retain their deadline; paused sessions retain remaining time.
            self.notice('Active focus session saved.')
        self.wallpaper.close()
        self.after_cancel(self.timer_job)
        for child in list(self.winfo_children()):
            if isinstance(child,ctk.CTkToplevel):
                child.destroy()
        self.db.close()
        # Cancel callbacks owned by this Tcl interpreter, including library DPI
        # and appearance polling, before destroying the last application window.
        for pending in self.tk.call('after','info'):
            # Keep each child widget's registered Tcl command for its normal
            # destroy cleanup; cancelling through the root's after_cancel would
            # delete that command twice when the owning child is destroyed.
            self.tk.call('after','cancel',pending)
        self.destroy()

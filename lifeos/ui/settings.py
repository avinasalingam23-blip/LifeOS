import json
import math
from .appearance import OPTIONS
from tkinter import messagebox,filedialog
import customtkinter as ctk
from .common import BG,PANEL,CARD,TEXT,MUTED,ACCENT,button,label,safe
from .theme import GlassCard
from .collections import GlassTabs

GROUPS=[('Appearance / Theme',[('theme','Theme',list(OPTIONS))]),('Daily goals',[
    ('dsa_target','Problems per day','int'),('study_target','Learning minutes per day','number'),
    ('focus_minutes','Default focus session (minutes)','number')]),
    ('Nutrition goals',[(n,title,'number') for n,title in [('calories','Calories (kcal)'),('protein','Protein (g)'),
        ('carbs','Carbohydrates (g)'),('fat','Fat (g)'),('fibre','Fibre (g)'),('water_ml','Water (ml)')]]),
    ('Display & reminders',[
        ('weight_unit','Weight chart unit',['kg','lb']),('distance_unit','Distance display unit',['km','mi']),
        ('nutrition_mode','Nutrition detail',['Simple','Detailed']),('reminders','In-app routine reminders',['Yes','No'])])]

class SettingsPage(ctk.CTkFrame):
    def __init__(self,parent,app):
        super().__init__(parent,fg_color='transparent')
        self.app,self.inputs=app,{}
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(1,weight=1)
        values=app.db.settings()
        header=ctk.CTkFrame(self,fg_color='transparent')
        header.grid(row=0,column=0,sticky='ew',pady=(0,12))
        label(header,'Preferences for your day',13,MUTED).pack(side='left')
        button(header,'Save settings',self.save,width=135).pack(side='right')
        self.sections=GlassTabs(self)
        self.sections.grid(row=1,column=0,sticky='nsew')
        descriptions={
            'Appearance / Theme':'Changes apply immediately and persist across restarts. Your records stay unchanged.',
            'Daily goals':'Adjust your own goals. Changes apply from today; earlier targets remain in history.',
            'Nutrition goals':'Your editable daily targets. Food totals are estimates from logged portions.',
            'Display & reminders':'Choose display units and in-app reminders. Forms show their entry units.'}
        for heading,fields in GROUPS:
            tab=self.sections.add(heading.replace('Display & reminders','Preferences'))
            tab.grid_columnconfigure(0,weight=1)
            tab.grid_rowconfigure(0,weight=1)
            panel=GlassCard(tab)
            panel.grid(row=0,column=0,sticky='nsew')
            panel.grid_columnconfigure(1,weight=1)
            label(panel,heading,20).grid(row=0,column=0,columnspan=2,sticky='w',padx=20,pady=(18,6))
            label(panel,descriptions[heading],12,MUTED,anchor='w',wraplength=660).grid(row=1,column=0,columnspan=2,sticky='ew',padx=20,pady=(0,12))
            for i,(key,title,kind) in enumerate(fields,2):
                label(panel,title,12,MUTED).grid(row=i,column=0,sticky='w',padx=20,pady=5)
                if isinstance(kind,list):
                    widget=ctk.CTkOptionMenu(panel,values=kind,width=180,height=30)
                    widget.set(str(values[key]))
                    if key=='theme':widget.configure(command=app.set_theme)
                else:
                    widget=ctk.CTkEntry(panel,width=200,height=30)
                    widget.insert(0,str(values[key]))
                widget.grid(row=i,column=1,sticky='ew',padx=20,pady=5)
                self.inputs[key]=(widget,kind)
            panel.grid_rowconfigure(len(fields)+2,weight=1)
        safety=self.sections.add('Data safety')
        safety.grid_columnconfigure(0,weight=1)
        safety.grid_rowconfigure(0,weight=1)
        panel=GlassCard(safety)
        panel.grid(row=0,column=0,sticky='nsew')
        label(panel,'Data safety',20).pack(anchor='w',padx=18,pady=(16,8))
        label(panel,'Database: '+str(app.db.path)+'\n\nAn automatic backup is made on the first launch each day. Restore creates an additional safety backup first.',12,MUTED,justify='left',wraplength=650).pack(anchor='w',padx=18,pady=8)
        bar=ctk.CTkFrame(panel,fg_color='transparent')
        bar.pack(anchor='w',padx=18,pady=(4,18))
        button(bar,'Create backup',self.backup,width=150).pack(side='left',padx=(0,8))
        button(bar,'Restore backup…',self.restore,True,width=155).pack(side='left',padx=4)
        label(panel,'Subject goals: Learning Paths. Training schedules: Workout Planner.\nCustom reminder times: Daily Planner → Daily routines.',12,MUTED,justify='left',wraplength=650).pack(anchor='w',padx=18,pady=16)

    def save(self):
        def action():
            result={}
            for key,(widget,kind) in self.inputs.items():
                value=widget.get().strip()
                if kind in ('number','int'):
                    try:
                        value=float(value)
                    except ValueError:
                        raise ValueError(f'{key.replace("_"," ").capitalize()} must be numeric.') from None
                    if not math.isfinite(value) or value<0:
                        raise ValueError('Goals must be finite, non-negative numbers.')
                    if kind=='int':
                        if not value.is_integer():
                            raise ValueError('Problem target must be a whole number.')
                        value=int(value)
                if isinstance(kind,list) and value not in kind:
                    raise ValueError('Choose a valid display preference.')
                result[key]=value
            if not 0.1<=result['focus_minutes']<=1440:
                raise ValueError('Focus duration must be between 0.1 and 1440 minutes.')
            self.app.db.save_settings(result)
            self.app.timer_minutes.delete(0,'end')
            self.app.timer_minutes.insert(0,str(result['focus_minutes']))
            self.app.notice('Settings saved. New goals take effect today; older goal history is preserved.')
        safe(self,action)

    def backup(self):
        target=filedialog.asksaveasfilename(parent=self,title='Create a new backup file',defaultextension='.sqlite3',
            initialfile='LifeOS-backup.sqlite3',filetypes=[('SQLite backup','*.sqlite3')])
        if target:
            def action():
                path=self.app.db.backup(target)
                self.app.notice('Backup saved: '+str(path))
            safe(self,action)

    def restore(self):
        source=filedialog.askopenfilename(parent=self,title='Choose LifeOS backup',filetypes=[('SQLite backup','*.sqlite3')])
        if source and messagebox.askyesno('Restore LifeOS backup?',
            'This replaces current records with the selected backup. A safety backup of the current database is created first. Continue?',parent=self):
            def action():
                safety=self.app.db.restore(source)
                self.app.selected.clear()
                self.app.clear_page_cache()
                from . import appearance
                appearance.select(self.app.db.settings()['theme'])
                self.app.show('Settings')
                self.app.appearance.apply()
                self.app.notice('Restored. Previous data is backed up at '+str(safety))
            safe(self,action)

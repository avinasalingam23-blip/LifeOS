from .scrolling import ScrollFrame
"""Date-based meals over existing food snapshots and library workflows."""
from datetime import date,timedelta
from tkinter import messagebox
import customtkinter as ctk
from .common import button,label,safe,MUTED
from .theme import GlassCard
from .collections import GlassTabs,PhotoRecordList
from .nutrition import FoodDialog,NutritionReviewDialog
from .records import RecordsFrame,RecordEditor
from ..models import ENTITIES

class NutritionPage(ctk.CTkFrame):
    def __init__(self,parent,app):
        super().__init__(parent,fg_color='transparent')
        self.app=app
        self.last_revision=None
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(2,weight=1)
        bar=ctk.CTkFrame(self,fg_color='transparent');bar.grid(row=0,column=0,sticky='ew',pady=(0,8))
        button(bar,'Previous',lambda:self.shift(-1),True,width=90).pack(side='left')
        self.day=ctk.CTkEntry(bar,width=125);self.day.insert(0,date.today().isoformat());self.day.pack(side='left',padx=6)
        self.day.bind('<Return>',lambda e:self.refresh_meals())
        button(bar,'Show date',self.refresh_meals,True,width=100).pack(side='left')
        button(bar,'Next',lambda:self.shift(1),True,width=70).pack(side='left',padx=6)
        button(bar,'Custom food',self.custom_food,True,width=120).pack(side='right')
        button(bar,'Nutrition review',lambda:NutritionReviewDialog(self,app),True,width=145).pack(side='right',padx=6)
        self.summary=label(self,'',13,anchor='w',justify='left',wraplength=800)
        self.summary.grid(row=1,column=0,sticky='ew',pady=(0,8))
        self.sections=GlassTabs(self);self.sections.grid(row=2,column=0,sticky='nsew')
        meals=self.sections.add('Meals');meals.grid_columnconfigure(0,weight=1);meals.grid_rowconfigure(0,weight=1)
        self.body=ScrollFrame(meals,fg_color='transparent');self.body.grid(row=0,column=0,sticky='nsew')
        self.body.grid_columnconfigure((0,1),weight=1,uniform='meal')
        self.meal_lists={};self.meal_labels={}
        for i,name in enumerate(('Breakfast','Lunch','Snacks','Dinner')):
            card=GlassCard(self.body);card.grid(row=i//2,column=i%2,sticky='nsew',padx=5,pady=6)
            card.grid_columnconfigure(0,weight=1)
            header=ctk.CTkFrame(card,fg_color='transparent');header.grid(row=0,column=0,sticky='ew',padx=12,pady=(10,4))
            label(header,name,18,icon_name='utensils').pack(side='left')
            button(header,'Add food',lambda m=name:self.add_food(m),True,width=95).pack(side='right')
            totals=label(card,'',11,MUTED,anchor='w');totals.grid(row=1,column=0,sticky='ew',padx=12)
            self.meal_labels[name]=totals
            view=PhotoRecordList(card,('name','quantity','calories','protein'),on_open=lambda m=name:self.edit_food(m))
            view.configure(height=150)
            for key,title in [('name','Food'),('quantity','Amount'),('calories','kcal'),('protein','Protein')]:view.heading(key,text=title)
            view.grid(row=2,column=0,sticky='nsew',padx=8,pady=6)
            scroll=ctk.CTkScrollbar(card,command=view.yview);scroll.grid(row=2,column=0,sticky='nse',padx=4)
            view.configure(yscrollcommand=scroll.set)
            view.empty_title='No foods logged';view.empty_help='Add a food and confirm its portion.';view.empty_action='Add food'
            view.on_add=lambda m=name:self.add_food(m)
            view.bind('<Delete>',lambda e,m=name:self.remove_food(m))
            controls=ctk.CTkFrame(card,fg_color='transparent');controls.grid(row=3,column=0,sticky='e',padx=10,pady=(0,8))
            button(controls,'Edit',lambda m=name:self.edit_food(m),True,width=65).pack(side='left',padx=3)
            button(controls,'Remove',lambda m=name:self.remove_food(m),True,width=80).pack(side='left',padx=3)
            self.meal_lists[name]=view
        history=self.sections.add('History & library');history.grid_columnconfigure(0,weight=1);history.grid_rowconfigure(0,weight=1)
        self.record_tabs=GlassTabs(history,command=app.tab_changed);self.record_tabs.grid(row=0,column=0,sticky='nsew')
        app.tabs=self.record_tabs
        for table in ('food_logs','foods','water_logs','measurements'):
            name=ENTITIES[table].title;tab=self.record_tabs.add(name);tab.grid_columnconfigure(0,weight=1);tab.grid_rowconfigure(0,weight=1)
            frame=RecordsFrame(tab,app,table);frame.grid(row=0,column=0,sticky='nsew');app.record_frames[name]=frame
        self.refresh_meals()

    def shift(self,days):
        def action():
            value=(date.fromisoformat(self.day.get())+timedelta(days=days)).isoformat()
            self.day.delete(0,'end');self.day.insert(0,value);self.refresh_meals()
        safe(self,action)

    def refresh_meals(self):
        def action():
            revision=(self.day.get(),self.app.db.revision())
            if revision==self.last_revision:return
            report=self.app.service.meal_day(self.day.get());self.report=report
            goals=self.app.db.goals_on(self.day.get())
            self.summary.configure(text=f"{report['date']} · Logged {report['calories']:,.0f} / {goals['calories']:g} kcal · Protein {report['protein']:.1f} / {goals['protein']:g} g\nSource-labelled estimates from saved portions. Double-click a food to edit; missing meals remain unknown.")
            for name,group in report['meals'].items():
                self.meal_labels[name].configure(text=f"{group['calories']:,.0f} kcal · {group['protein']:.1f} g protein · {len(group['entries'])} entries")
                view=self.meal_lists[name];view.delete(*view.get_children())
                for row in group['entries']:
                    view.insert('','end',iid=str(row['id']),values=(row['name'],f"{row['quantity']:g} {row['unit']}",f"{row['calories']:.0f}",f"{row['protein']:.1f} g"))
                view.draw()
            self.last_revision=revision
        safe(self,action)

    def add_food(self,meal):
        return FoodDialog(self,self.app,on_save=self.refresh_meals,selected_date=self.day.get(),meal_type=meal)

    def selected(self,meal):
        ids=self.meal_lists[meal].selection()
        return self.app.service.get('food_logs',int(ids[0])) if ids else None

    def edit_food(self,meal):
        row=self.selected(meal)
        if row:return FoodDialog(self,self.app,row,self.refresh_meals)

    def remove_food(self,meal):
        row=self.selected(meal)
        if row and messagebox.askyesno('Remove food entry?','Remove this portion from '+row['date']+' / '+row['meal']+'?',parent=self):
            self.app.service.delete('food_logs',row['id']);self.refresh_meals()

    def custom_food(self):
        return RecordEditor(self,self.app,'foods',on_save=self.refresh_meals)

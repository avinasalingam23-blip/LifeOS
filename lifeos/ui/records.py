from __future__ import annotations
from .lifecycle import Textbox
from .appearance import menu as themed_menu
from .scrolling import ScrollFrame
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser
from datetime import date
import customtkinter as ctk
from ..models import ENTITIES, defaults_for
from .common import BG,PANEL,CARD,ACCENT,TEXT,MUTED,button,label,safe,Dialog,CodeEditor
from .theme import GlassCard,BORDER,INPUT
from .icons import icon,tree_icon,ENTITY_ICONS,row_icon
from .collections import PhotoRecordList,GlassTabs
from .presentation import COLUMNS,HEADINGS,PRIMARY,subject_progress,compact_value

class RecordEditor(Dialog):
    def __init__(self,parent,app,table,record=None,on_save=None):
        self.app,self.table,self.record,self.on_save=app,table,record,on_save
        self.entity=ENTITIES[table]
        super().__init__(parent,('Edit ' if record else 'New ')+self.entity.title)
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(1,weight=1)
        label(self,self.entity.title,24).grid(row=0,column=0,sticky='w',padx=24,pady=(20,10))
        self.body=ScrollFrame(self,fg_color=PANEL,corner_radius=18,border_width=1,border_color=BORDER)
        self.body.grid(row=1,column=0,sticky='nsew',padx=20)
        self.body.grid_columnconfigure(0,weight=1)
        self.inputs={}
        self.ref_maps={}
        self.advanced_frames=[]
        basic=set(COLUMNS.get(table,()))|{f.key for f in self.entity.fields if f.required and f.kind=='ref'}
        if table=='foods':basic.update({'name','preparation','source','calories','protein','carbs','fat'})
        basic.update({'solved_date','attempt_date'} if table=='problems' else {'goal','target_minutes','target_period'} if table=='paths' else {'code'} if table=='solutions' else ())
        toggle=button(self.body,'More details',self.toggle_advanced,True,width=155,icon_name='plus')
        toggle.grid(row=len(self.entity.fields)+1,column=0,sticky='w',padx=12,pady=12)
        self.advanced_visible=False
        data=defaults_for(table)
        if table=='foods' and not record:
            # A blank label value is unknown; never prefill invented zero macros.
            for key in ('calories','protein','carbs','fat'): data[key]=None
        if record:
            data.update(record)
        else:
            for f in self.entity.fields:
                if f.kind=='ref':
                    selected=app.selected.get(f.ref)
                    if selected and app.service.get(f.ref,selected):
                        data[f.key]=selected
        for row,f in enumerate(self.entity.fields):
            frame=ctk.CTkFrame(self.body,fg_color='transparent')
            frame.grid(row=row,column=0,sticky='ew',padx=12,pady=6)
            frame.grid_columnconfigure(0,weight=1)
            label(frame,f.label+(' *' if f.required else ''),13,MUTED,anchor='w').grid(row=0,column=0,sticky='ew')
            value=data.get(f.key)
            value='' if value is None else str(value)
            if f.kind=='code':
                widget=CodeEditor(frame,value)
            elif f.kind=='memo':
                widget=Textbox(frame,height=110,fg_color=INPUT,font=('Segoe UI',13),wrap='word')
                widget.insert('1.0',value)
            elif f.kind in ('choice','ref'):
                values=list(f.choices)
                if f.kind=='ref':
                    mapping={app.service.label(f.ref,r):r['id'] for r in app.service.list(f.ref)}
                    self.ref_maps[f.key]=mapping
                    values=['— Select —']+list(mapping)
                    value=next((name for name,rid in mapping.items() if str(rid)==value),'— Select —')
                widget=ctk.CTkOptionMenu(frame,values=values,fg_color=INPUT,button_color=CARD,dynamic_resizing=False)
                widget.set(value if value in values else values[0])
                if table=='workouts' and record and f.key in ('status','routine_id') and app.db.one('SELECT workout_id FROM fitness_sessions WHERE workout_id=?',(record['id'],)):
                    widget.configure(state='disabled')
            else:
                widget=ctk.CTkEntry(frame,fg_color=INPUT,height=36,placeholder_text=f.help)
                widget.insert(0,value)
            widget.grid(row=1,column=0,sticky='ew',pady=(4,0))
            if f.help:
                label(frame,f.help,11,MUTED).grid(row=2,column=0,sticky='w')
            self.inputs[f.key]=widget
            if f.key not in basic:
                self.advanced_frames.append(frame)
                frame.grid_remove()
        if 'language' in self.inputs and 'code' in self.inputs:
            self.inputs['code'].set_language(self.inputs['language'].get())
            self.inputs['language'].configure(command=lambda value:self.inputs['code'].set_language(value))
        footer=ctk.CTkFrame(self,fg_color='transparent')
        footer.grid(row=2,column=0,sticky='ew',padx=20,pady=15)
        button(footer,'Cancel',self.close,True,width=100).pack(side='right',padx=6)
        button(footer,'Save record',self.save,width=130).pack(side='right',padx=6)
        label(footer,'* Required · Changes save only when you click Save',11,MUTED).pack(side='left')
        self.initial=self.values()
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.bind('<Control-s>',lambda e:self.save())

    def toggle_advanced(self):
        self.advanced_visible=not self.advanced_visible
        for frame in self.advanced_frames:
            frame.grid() if self.advanced_visible else frame.grid_remove()
        self.wallpaper.request()

    def values(self):
        result={}
        for f in self.entity.fields:
            widget=self.inputs[f.key]
            value=widget.get('1.0','end-1c') if f.kind=='memo' else widget.get()
            if f.kind=='ref':
                value=self.ref_maps[f.key].get(value)
            result[f.key]=value
        return result

    def save(self):
        def action():
            rid=self.app.service.save(self.table,self.values(),self.record['id'] if self.record else None)
            self.app.selected[self.table]=rid
            if self.on_save:
                self.on_save()
            self.app.notice('Saved locally.')
            self.destroy()
        safe(self,action)

    def close(self):
        if self.values()!=self.initial and not messagebox.askyesno('Discard unsaved edits?','Your changes have not been saved. Discard them?',parent=self):
            return
        self.destroy()

class RecordsFrame(ctk.CTkFrame):
    def __init__(self,parent,app,table,scope=None):
        super().__init__(parent,fg_color='transparent')
        self.app,self.table,self.entity=app,table,ENTITIES[table]
        self.rows=[]
        self.scope=scope or {}
        self.daily_view=True
        self.columns=COLUMNS[table]
        self.advanced_visible=False
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(3,weight=1)
        self.hint=label(self,'',12,MUTED,anchor='w',justify='left',wraplength=740)
        self.hint.grid(row=0,column=0,sticky='ew',pady=(0,6))
        bar=ctk.CTkFrame(self,fg_color='transparent')
        bar.grid(row=1,column=0,sticky='ew',pady=4)
        button(bar,PRIMARY[table],self.add,width=132,icon_name='plus').pack(side='left',padx=(0,12))
        self.search=ctk.CTkEntry(bar,placeholder_text='Search…',width=200,height=34)
        self.search.pack(side='left',fill='x',expand=True,padx=(0,8))
        self.search.bind('<Return>',lambda e:self.refresh())
        self.search.bind('<KeyRelease>',self.search_changed)
        self.search_job=None
        self.more=button(bar,'More',self.show_menu,True,width=75)
        self.more.pack(side='right')
        self.edit_button=button(bar,'Edit',self.edit,True,width=70)
        filters=ctk.CTkFrame(self,fg_color='transparent')
        filters.grid(row=2,column=0,sticky='ew',pady=(8,10))
        self.filters=filters
        label(filters,'Filter',12,MUTED).pack(side='left',padx=(0,8))
        fields=[f for f in self.entity.fields if f.kind in ('choice','ref','date') or f.key in ('topic','platform','exercise')]
        if table=='food_logs':
            from ..models import day,choice
            fields=[day(),choice('meal','Meal',['Breakfast','Lunch','Dinner','Snacks'])]
        self.filter_fields={f.label:f for f in fields}
        self.filter_field=ctk.CTkOptionMenu(filters,values=['All fields']+list(self.filter_fields),width=140,command=self.change_filter,dynamic_resizing=False)
        self.filter_field.pack(side='left',padx=4)
        self.filter_holder=ctk.CTkFrame(filters,fg_color='transparent',width=170,height=34)
        self.filter_holder.pack(side='left',padx=4)
        self.filter_value=None
        self.change_filter('All fields')
        button(filters,'Apply',self.refresh,True,width=65).pack(side='left',padx=4)
        button(filters,'Clear',self.clear,True,width=65).pack(side='left',padx=4)
        filters.grid_remove()
        box=ctk.CTkFrame(self,fg_color='transparent')
        box.grid(row=3,column=0,sticky='nsew',pady=(10,0))
        box.grid_columnconfigure(0,weight=1)
        box.grid_rowconfigure(0,weight=1)
        self.tree=PhotoRecordList(box,self.columns,mode='cards' if table in ('paths','workout_routines') else 'rows',
                                 on_open=self.details,on_toggle=self.toggle_task if table=='tasks' else None,on_add=self.add)
        for key in self.columns:
            field=next((f for f in self.entity.fields if f.key==key),None)
            heading=(field.label.split(' (')[0] if field else key.replace('_',' ').title())
            self.tree.heading(key,text=HEADINGS.get(key,heading),command=lambda k=key:self.sort(k))
        self.tree.grid(row=0,column=0,sticky='nsew',padx=(2,0),pady=(2,0))
        v=ctk.CTkScrollbar(box,orientation='vertical',command=self.tree.yview)
        v.grid(row=0,column=1,sticky='ns')
        self.tree.configure(yscrollcommand=v.set)
        self.tree.empty_title='No '+self.entity.title.lower()+' yet'
        self.tree.empty_help='Start small. Your saved history stays here.'
        self.tree.empty_action=PRIMARY[table]
        self.tree.bind('<<TreeviewSelect>>',self.select)
        self.count=label(self,'',12,MUTED,anchor='w')
        self.count.grid(row=4,column=0,sticky='ew',pady=8)
        self.descending=False
        self.refresh()

    def search_changed(self,event=None):
        if self.search_job:
            self.after_cancel(self.search_job)
        self.search_job=self.after(220,self.run_search)

    def run_search(self):
        self.search_job=None
        self.refresh()

    def destroy(self):
        if self.search_job:
            self.after_cancel(self.search_job)
        super().destroy()

    def toggle_filters(self):
        self.advanced_visible=not self.advanced_visible
        if self.advanced_visible:
            self.filters.grid()
        else:
            self.filters.grid_remove()
        self.winfo_toplevel().wallpaper.request()

    def show_menu(self,event=None):
        menu=themed_menu(self,tearoff=False,bg='#242424',fg=TEXT,activebackground='#454545',activeforeground=TEXT,
                     relief='flat',borderwidth=1,font=('Segoe UI',11))
        if self.tree.selection():
            menu.add_command(label='Open details',command=self.details)
            menu.add_command(label='Edit record',command=self.edit)
            if self.table=='problems':
                menu.add_command(label='Open problem URL',command=self.open_url)
            if self.table=='workout_days':
                menu.add_command(label='Plan scheduled day…',command=self.plan)
            if self.table=='tasks':
                menu.add_command(label='Mark complete',command=self.complete)
            menu.add_command(label='Delete record…',command=self.delete)
            menu.add_separator()
        if self.table=='daily_routines':
            menu.add_command(label='Generate today’s tasks',command=self.generate)
        if self.table=='foods':
            menu.add_command(label='Build weighed recipe…',command=self.recipe)
        if self.table in ('tasks','food_logs'):
            menu.add_command(label=('Show all history' if self.daily_view else 'Show today and overdue' if self.table=='tasks' else 'Show today'),command=self.toggle_history)
        menu.add_command(label='Show / hide filters',command=self.toggle_filters)
        menu.add_command(label='Clear search and filters',command=self.clear)
        menu.add_command(label='Export CSV…',command=self.export)
        menu.add_command(label='Refresh',command=self.refresh)
        self.menu=menu
        menu.tk_popup(self.more.winfo_rootx(),self.more.winfo_rooty()+self.more.winfo_height())

    def toggle_history(self):
        self.daily_view=not self.daily_view
        self.refresh()

    def details(self):
        record=self.selected_row()
        if record:
            if self.table=='workouts' and self.app.db.one('SELECT workout_id FROM fitness_sessions WHERE workout_id=?',(record['id'],)):
                from .fitness import SessionDialog
                SessionDialog(self,self.app,record['id'],self.refresh)
                return
            RecordDetails(self,self.app,self.table,record,self.refresh)

    def toggle_task(self,rid):
        record=self.app.service.get('tasks',int(rid))
        if record:
            record['status']='To do' if record['status']=='Completed' else 'Completed'
            safe(self,lambda:self.app.service.save('tasks',record,record['id']))
            self.refresh()

    def change_filter(self,name):
        for widget in self.filter_holder.winfo_children():
            widget.destroy()
        field=self.filter_fields.get(name)
        self.filter_mapping={}
        if field and field.kind in ('choice','ref'):
            values=['Any']
            if field.kind=='ref':
                self.filter_mapping={self.app.service.label(field.ref,r):r['id'] for r in self.app.service.list(field.ref)}
                values+=list(self.filter_mapping)
            else:
                values+=list(field.choices)
            self.filter_value=ctk.CTkOptionMenu(self.filter_holder,values=values,width=185,dynamic_resizing=False)
        else:
            self.filter_value=ctk.CTkEntry(self.filter_holder,width=185,height=34,placeholder_text='YYYY-MM-DD' if field and field.kind=='date' else 'Filter value')
            self.filter_value.bind('<Return>',lambda e:self.refresh())
        self.filter_value.pack()

    def clear(self):
        self.search.delete(0,'end')
        self.filter_field.set('All fields')
        self.change_filter('All fields')
        self.refresh()

    def refresh(self):
        if not self.winfo_exists():
            return
        filters=dict(self.scope)
        f=self.filter_fields.get(self.filter_field.get())
        value=self.filter_value.get()
        if f and value and value!='Any':
            if f.key not in self.scope:
                filters[f.key]=self.filter_mapping.get(value) if f.kind=='ref' else value
        self.rows=self.app.service.list(self.table,self.search.get().strip(),filters)
        if self.daily_view and not self.search.get().strip() and 'date' not in filters:
            today=date.today().isoformat()
            if self.table=='tasks':
                self.rows=[r for r in self.rows if r['date']==today or (r['date']<today and r['status'] not in ('Completed','Skipped'))]
            elif self.table=='food_logs':
                self.rows=[r for r in self.rows if r['date']==today]
        self.tree.delete(*self.tree.get_children())
        ref_fields={f.key:f.ref for f in self.entity.fields if f.kind=='ref'}
        labels={key:{r['id']:self.app.service.label(table,r).rsplit('  ·',1)[0] for r in self.app.service.list(table)} for key,table in ref_fields.items()}
        self.tree.details={}
        for row in self.rows:
            values=[]
            for key in self.columns:
                value=row.get(key,'')
                if key in labels:
                    value=labels[key].get(value,'—')
                values.append(compact_value(key,value,row))
            name,color=row_icon(self.table,row)
            self.tree.insert('', 'end',iid=str(row['id']),values=values,image=tree_icon(name,color,19,self.winfo_toplevel()),
                             tags=('even',) if len(self.tree.get_children())%2==0 else ())
            if self.table=='paths':
                ratio,progress=subject_progress(self.app.service,row)
                self.tree.details[str(row['id'])]=dict(ratio=ratio,progress=progress,
                    subtitle=f"{row['priority']} priority · {row['status']}",
                    footer='Deadline: '+row['deadline'] if row['deadline'] else 'Open concepts & study →')
            elif self.table=='workout_routines':
                days=self.app.service.list('workout_days',filters={'routine_id':row['id']})
                self.tree.details[str(row['id'])]=dict(subtitle=f"{row['split']} · {row['location']}",
                    progress=f"{row['days_per_week']} training days / week · {len(days)} scheduled",footer='Active routine · Open schedule →' if row['active']=='Yes' else 'Inactive · Open details →')
            elif self.table=='tasks':
                self.tree.details[str(row['id'])]=dict(completed=row['status']=='Completed')
        filtered=bool(self.search.get().strip() or (f and value and value!='Any'))
        self.tree.empty_title='No matching records' if filtered else 'No '+self.entity.title.lower()+' yet'
        self.tree.empty_help='Clear search or filters from More.' if filtered else 'Start small. Your saved history stays here.'
        suffix=' · Click a card to open details.' if self.tree.mode=='cards' else ' · Enter or double-click for details.'
        self.count.configure(text=f'{len(self.rows)} records'+suffix)
        selected=self.app.selected.get(self.table)
        if selected and self.tree.exists(str(selected)):
            self.tree.selection_set(str(selected))
        else:
            self.edit_button.pack_forget()
        self.tree.draw()
        self.refresh_hint()
        owner=self.winfo_toplevel()
        if hasattr(owner,'wallpaper'):
            owner.wallpaper.request()

    def refresh_hint(self):
        text=''
        if self.table=='tasks':
            today=date.today().isoformat()
            tasks=self.app.service.list('tasks',filters={'date':today})
            text=f"Today · {sum(t['status']=='Completed' for t in tasks)} / {len(tasks)} tasks completed · Check a box to finish a task."
        elif self.table=='workout_routines':
            today=date.today().isoformat()
            upcoming=self.app.db.one("SELECT name,date FROM workouts WHERE date>=? AND status='Planned' ORDER BY date,id LIMIT 1",(today,))
            text=f"Up next · {upcoming['name']} · {upcoming['date']}" if upcoming else 'Build your routine, schedule its days, then log your training.'
        elif self.table=='food_logs':
            text='Source-labelled estimates · Open a meal to review its portion and nutrients.'
        elif self.table=='paths':
            text='Your subjects · Open a card to manage concepts and study sessions.'
        elif self.table=='problems':
            text='Your practice history · Notes, revisions and code versions are in problem details.'
        elif self.table=='foods':
            text='Per 100 g · Recipes and CSV export are in More. Unknown micronutrients stay unknown.'
        self.hint.configure(text=text)
        if text:
            self.hint.grid()
        else:
            self.hint.grid_remove()

    def select(self,event=None):
        selection=self.tree.selection()
        if selection:
            self.edit_button.pack(side='right',before=self.more,padx=(0,8))
            self.app.selected[self.table]=int(selection[0])
            if self.app.current_page=='Learning Paths' and self.winfo_toplevel() is self.app:
                record=self.app.service.get(self.table,int(selection[0]))
                if record:
                    subject=record if self.table=='paths' else self.app.service.get('paths',record.get('path_id')) if record.get('path_id') else None
                    if subject:
                        self.app.wallpaper.set_page('Learning Paths',subject['name'])

    def selected_row(self):
        selection=self.tree.selection()
        if not selection:
            messagebox.showinfo('Choose a record','Select a row first.',parent=self)
            return None
        return self.app.service.get(self.table,int(selection[0]))

    def add(self):
        for field in self.entity.fields:
            if field.kind=='ref' and field.key in self.scope:
                self.app.selected[field.ref]=self.scope[field.key]
        if self.table=='food_logs':
            from .nutrition import FoodDialog
            FoodDialog(self,self.app,on_save=self.refresh)
        else:
            RecordEditor(self,self.app,self.table,on_save=self.refresh)

    def edit(self):
        record=self.selected_row()
        if not record:
            return
        if self.table=='exercise_logs' and self.app.db.one('SELECT workout_id FROM fitness_sessions WHERE workout_id=?',(record['workout_id'],)):
            from .fitness import SessionDialog
            dialog=SessionDialog(self,self.app,record['workout_id'],self.refresh)
            dialog.current_id=record['id']
            dialog.refresh()
            return
        if self.table=='food_logs':
            from .nutrition import FoodDialog
            FoodDialog(self,self.app,record,self.refresh)
        elif self.table=='focus_sessions' and record['status'] in ('Running','Paused'):
            messagebox.showinfo('Active session','Use the timer controls above to pause or finish the current session.',parent=self)
        else:
            RecordEditor(self,self.app,self.table,record,self.refresh)

    def delete(self):
        record=self.selected_row()
        if record and messagebox.askyesno('Delete record?',
            'Permanently delete this record? Linked child records (such as solutions, concepts, sessions or exercise logs) are also deleted. Deleting a workout routine preserves completed workout history; deleting a food preserves meal history. Back up first if you may need to recover it.',parent=self):
            safe(self,lambda:self.app.service.delete(self.table,record['id']))
            self.refresh()

    def export(self):
        target=filedialog.asksaveasfilename(parent=self,defaultextension='.csv',initialfile=self.table+'.csv',filetypes=[('CSV','*.csv')])
        if target:
            safe(self,lambda:self.app.service.export_csv(self.table,target,self.rows))
            self.app.notice('CSV export saved.')

    def sort(self,key):
        self.descending=not self.descending
        ids=[str(r['id']) for r in sorted(self.rows,key=lambda r:(r.get(key) is None,r.get(key) if r.get(key) is not None else ''),reverse=self.descending)]
        self.tree.order=ids
        self.tree.draw()

    def open_url(self):
        record=self.selected_row()
        if record:
            if record['url'].startswith(('https://','http://')):
                webbrowser.open(record['url'])
            else:
                messagebox.showinfo('No URL','Edit this problem to add a URL.',parent=self)

    def plan(self):
        record=self.selected_row()
        if not record:
            return
        dialog=ctk.CTkInputDialog(text='Plan this workout on (YYYY-MM-DD):',title='Plan scheduled day')
        value=dialog.get_input()
        if value:
            def action():
                self.app.service.plan_workout(record['id'],value)
                self.app.notice('Workout and exercise snapshot created. Open Workout history to complete it.')
            safe(self,action)

    def generate(self):
        count=self.app.service.generate_tasks()
        self.app.notice(f'{count} tasks generated for today.')

    def complete(self):
        record=self.selected_row()
        if record:
            record['status']='Completed'
            safe(self,lambda:self.app.service.save('tasks',record,record['id']))
            self.refresh()

    def recipe(self):
        from .nutrition import RecipeDialog
        RecipeDialog(self,self.app,self.refresh)

class RecordDetails(Dialog):
    """Complete saved fields and related history, away from the everyday list."""
    def __init__(self,parent,app,table,record,on_save=None):
        self.app,self.table,self.record,self.on_save=app,table,record,on_save
        super().__init__(parent,'Record details',860,720)
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(1,weight=1)
        heading=ctk.CTkFrame(self,fg_color='transparent')
        heading.grid(row=0,column=0,sticky='ew',padx=22,pady=18)
        label(heading,record.get('name') or record.get('title') or ENTITIES[table].title,22,anchor='w',wraplength=530).pack(side='left',fill='x',expand=True)
        button(heading,'Edit',self.edit,True,width=80).pack(side='right')
        self.sections=GlassTabs(self)
        self.sections.grid(row=1,column=0,sticky='nsew',padx=22,pady=(0,20))
        overview=self.sections.add('Details')
        overview.grid_columnconfigure(0,weight=1)
        overview.grid_rowconfigure(0,weight=1)
        body=ScrollFrame(overview,fg_color=PANEL,corner_radius=12)
        body.grid(row=0,column=0,sticky='nsew')
        body.grid_columnconfigure(0,weight=1)
        fields=ENTITIES[table].fields
        if table=='food_logs':
            from ..models import Field
            fields=[Field(k,HEADINGS.get(k,k.replace('_',' ').title())) for k in record if k!='id']
        for row,field in enumerate(fields):
            value=record.get(field.key)
            if field.kind=='ref' and value:
                related=app.service.get(field.ref,value)
                value=app.service.label(field.ref,related) if related else 'Deleted record'
            label(body,field.label,11,MUTED,anchor='w').grid(row=row*2,column=0,sticky='ew',padx=16,pady=(12,2))
            if field.kind=='code':
                code=CodeEditor(body,str(value or ''))
                code.grid(row=row*2+1,column=0,sticky='ew',padx=16,pady=6)
                code.set_language(record.get('language','Other'))
            else:
                label(body,str(value) if value is not None and value!='' else 'Not recorded',13,anchor='w',justify='left',wraplength=680).grid(row=row*2+1,column=0,sticky='ew',padx=16,pady=(0,8))
        related=[]
        if table=='paths':
            ratio,progress=subject_progress(app.service,record)
            label(heading,progress,11,MUTED).pack(side='right',padx=12)
            related=[('concepts',{'path_id':record['id']}),('study_sessions',{'path_id':record['id']})]
            self.wallpaper.set_page('Learning Paths',record['name'])
        elif table=='problems':
            related=[('solutions',{'problem_id':record['id']})]
        elif table=='workout_routines':
            related=[('workout_days',{'routine_id':record['id']})]
        elif table=='workout_days':
            related=[('planned_exercises',{'day_id':record['id']})]
        elif table=='workouts':
            related=[('exercise_logs',{'workout_id':record['id']})]
        self.related={}
        for child,scope in related:
            for key,rid in scope.items():
                field=next(f for f in ENTITIES[child].fields if f.key==key)
                app.selected[field.ref]=rid
            section=self.sections.add(ENTITIES[child].title)
            section.grid_columnconfigure(0,weight=1)
            section.grid_rowconfigure(0,weight=1)
            view=RecordsFrame(section,app,child,scope=scope)
            view.grid(row=0,column=0,sticky='nsew')
            self.related[child]=view
        if table=='paths':
            self.sections.set('Concepts')

    def edit(self):
        if self.table=='food_logs':
            from .nutrition import FoodDialog
            FoodDialog(self,self.app,self.record,self.saved)
        elif self.table=='focus_sessions' and self.record['status'] in ('Running','Paused'):
            messagebox.showinfo('Active session','Use the focus timer to finish this session.',parent=self)
        else:
            RecordEditor(self,self.app,self.table,self.record,self.saved)

    def saved(self):
        if self.on_save:
            self.on_save()
        # Let the saving child finish its callback before closing this parent.
        self.after_idle(self.destroy)

class RecordsDialog(Dialog):
    def __init__(self,parent,app,table):
        super().__init__(parent,ENTITIES[table].title,850,700)
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(1,weight=1)
        label(self,ENTITIES[table].title,23).grid(row=0,column=0,sticky='w',padx=22,pady=16)
        self.records=RecordsFrame(self,app,table)
        self.records.grid(row=1,column=0,sticky='nsew',padx=22,pady=(0,18))

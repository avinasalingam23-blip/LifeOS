from datetime import date,timedelta
from tkinter import messagebox
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg,NavigationToolbar2Tk
from PIL import ImageTk
from .common import PANEL,CARD,ACCENT,BLUE,TEXT,MUTED,button,label,safe
from .theme import GlassCard,BORDER,MINT,VIOLET

class AnalyticsPage(ctk.CTkFrame):
    def __init__(self,parent,app):
        super().__init__(parent,fg_color='transparent')
        self.app=app
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(3,weight=1)
        bar=ctk.CTkFrame(self,fg_color='transparent')
        bar.grid(row=0,column=0,sticky='ew',pady=(0,8))
        self.view=ctk.CTkOptionMenu(bar,values=['DSA','Learning','Workouts','Nutrition','Water & Weight','Tasks & Focus'],command=lambda v:self.render(),width=185)
        self.view.pack(side='left',padx=(0,12))
        self.range=ctk.CTkOptionMenu(bar,values=['Last 30 days','Last 7 days','Last 90 days'],width=145,command=self.set_range)
        self.range.pack(side='left',padx=4)
        button(bar,'Dates',self.toggle_dates,True,width=80,icon_name='calendar-check').pack(side='left',padx=6)
        button(bar,'Chart tools',self.toggle_tools,True,width=115,icon_name='chart-no-axes-combined').pack(side='right')
        self.dates=ctk.CTkFrame(self,fg_color='transparent')
        self.dates.grid(row=1,column=0,sticky='ew',pady=6)
        label(self.dates,'From',11,MUTED).pack(side='left',padx=(0,6))
        self.start=ctk.CTkEntry(self.dates,width=125)
        self.start.insert(0,(date.today()-timedelta(days=29)).isoformat())
        self.start.pack(side='left',padx=(0,5))
        label(self.dates,'to',12,MUTED).pack(side='left',padx=3)
        self.end=ctk.CTkEntry(self.dates,width=125)
        self.end.insert(0,date.today().isoformat())
        self.end.pack(side='left',padx=5)
        button(self.dates,'Apply dates',self.render,width=125,icon_name='filter').pack(side='left',padx=10)
        self.dates.grid_remove()
        self.show_tools=False
        self.summary=label(self,'',12,MUTED,justify='left',anchor='w',wraplength=1050)
        self.summary.grid(row=2,column=0,sticky='ew',pady=8)
        self.plot=GlassCard(self,fg_color=PANEL)
        self.plot.grid(row=3,column=0,sticky='nsew')
        self.fig=None
        self.canvas=None
        self.render()

    def set_range(self,value):
        count=int(value.split()[1])
        self.start.delete(0,'end')
        self.start.insert(0,(date.today()-timedelta(days=count-1)).isoformat())
        self.end.delete(0,'end')
        self.end.insert(0,date.today().isoformat())
        self.render()

    def toggle_dates(self):
        self.dates.grid_remove() if self.dates.winfo_ismapped() else self.dates.grid()

    def toggle_tools(self):
        self.show_tools=not self.show_tools
        if self.show_tools:
            self.toolbar.pack(fill='x')
        else:
            self.toolbar.pack_forget()
        self.app.wallpaper.request()

    def render(self):
        safe(self,self._render)

    def _render(self):
        start,end=self.start.get(),self.end.get()
        key=(start,end,self.view.get(),self.app.db.revision())
        if getattr(self,'_plot_key',None)==key:return
        self._plot_key=key
        summary=self.app.analytics.summary(start,end)
        daily=self.app.analytics.daily(start,end)
        groups=self.app.analytics.breakdowns(start,end)
        self.clear_plot()
        self.fig=Figure(figsize=(11,6),dpi=100,facecolor=PANEL,layout='constrained')
        self.fig.patch.set_alpha(0)
        ax1,ax2=self.fig.subplots(2,1)
        for ax in (ax1,ax2):
            ax.set_prop_cycle(color=['#dddddd','#a9a9a9','#7c7c7c','#f2f2f2','#969696'])
            ax.set_facecolor(PANEL)
            ax.patch.set_alpha(0)
            ax.tick_params(colors=MUTED,labelsize=8)
            ax.grid(axis='y',color=BORDER,alpha=.45)
            ax.set_axisbelow(True)
            for spine in ax.spines.values():
                spine.set_color(BORDER)
            ax.title.set_color(TEXT)
            ax.xaxis.label.set_color(MUTED)
            ax.yaxis.label.set_color(MUTED)
        dates=[r['date'][5:] for r in daily]
        x=list(range(len(daily)))
        view=self.view.get()
        if view=='DSA':
            ax1.bar(x,[r['dsa']['solved'] for r in daily],color=ACCENT,label='Solved')
            ax1.plot(x,[r['goals']['dsa_target'] for r in daily],color=BLUE,label='Target on that date')
            ax1.set_title('Daily solves and historical targets')
            self.date_axis(ax1,x,dates)
            ax1.legend(facecolor=CARD,labelcolor=TEXT,fontsize=8)
            topics=groups['topics']
            ax2.barh([r['name'] for r in topics],[r['count'] for r in topics],color=BLUE)
            ax2.set_title('Solved problems by topic')
            d=summary['dsa']
            difficulty=', '.join(f"{r['name']}: {r['count']}" for r in groups['difficulty']) or 'No solves'
            self.summary.configure(text=f"Solved: {d['solved']} · Independent: {d['independent']} · With hints: {d['hinted']} · Copied: {d['copied']}\nDifficulty — {difficulty}. Due revisions now: {len(summary['dsa_revisions'])}.")
        elif view=='Learning':
            subjects=groups['subjects']
            ax1.barh([r['name'] for r in subjects],[r['actual'] for r in subjects],color=ACCENT,label='Actual')
            ax1.set_title('Actual learning minutes by subject')
            counts=summary['concept_status']
            ax2.bar([r['status'] for r in counts],[r['count'] for r in counts],color=BLUE)
            ax2.set_title('Current concept understanding (all saved concepts)')
            self.summary.configure(text=f"Study: {summary['study']['actual']:g} min actual / {summary['study']['planned']:g} min planned in range. Concepts due as of {end}: {len(summary['concept_revisions'])}.\nSubject targets are editable in Learning Paths; concept status is self-assessed.")
        elif view=='Workouts':
            completed={r['date']:r['count'] for r in groups['workouts']}
            ax1.bar(x,[completed.get(r['date'],0) for r in daily],color=ACCENT)
            self.date_axis(ax1,x,dates)
            ax1.set_title('Completed workouts per day')
            names=sorted({r['exercise'] for r in groups['strength']})
            for name in names:
                rows=[r for r in groups['strength'] if r['exercise']==name]
                ax2.plot([r['date'][5:] for r in rows],[r['weight'] for r in rows],marker='o',label=name)
            ax2.set_title('Maximum weight per exercise / day (kg)')
            if names:
                ax2.legend(facecolor=CARD,labelcolor=TEXT,fontsize=7,loc='upper left')
            records='; '.join(f"{r['exercise']}: {r['weight']:g} kg, {r['distance']:g} km" for r in groups['records']) or 'No completed exercise records yet'
            w=summary['workouts']
            self.summary.configure(text=f"{w['completed']} completed / {w['total']-w['recovery']} planned or logged training sessions · {w['recovery']} recovery days.\nPersonal records within range — {records}")
        elif view=='Nutrition':
            ax1.bar(x,[r['nutrition']['calories'] or 0 for r in daily],color=ACCENT,label='Logged kcal')
            ax1.plot(x,[r['goals']['calories'] for r in daily],color=BLUE,label='Historical goal')
            self.date_axis(ax1,x,dates)
            ax1.set_title('Calories vs target')
            ax1.legend(facecolor=CARD,labelcolor=TEXT,fontsize=8)
            for n,color in [('protein',ACCENT),('carbs',BLUE),('fat','#8b8b8b')]:
                ax2.plot(x,[r['nutrition'][n] or 0 for r in daily],color=color,label=n+' logged (g)')
                ax2.plot(x,[r['goals'][n] for r in daily],color=color,linestyle=':',alpha=.65,label=n+' goal')
            self.date_axis(ax2,x,dates)
            ax2.set_title('Macronutrients and dated goals')
            ax2.legend(facecolor=CARD,labelcolor=TEXT,fontsize=7,ncol=3)
            food=summary['nutrition']
            self.summary.configure(text=f"{food['entries']} entries · {food['calories']:,.0f} kcal · Protein {food['protein']:.1f} g · Carbs {food['carbs']:.1f} g · Fat {food['fat']:.1f} g\nSource-labelled food estimates; unlogged food is unknown. Detailed micronutrient totals are in Diet & Nutrition.")
        elif view=='Water & Weight':
            ax1.bar(x,[r['water'] for r in daily],color=ACCENT,label='Water ml')
            ax1.plot(x,[r['goals']['water_ml'] for r in daily],color=BLUE,label='Historical goal')
            self.date_axis(ax1,x,dates)
            ax1.set_title('Water intake (ml)')
            ax1.legend(facecolor=CARD,labelcolor=TEXT,fontsize=8)
            rows=groups['weight']
            pounds=self.app.db.settings()['weight_unit']=='lb'
            factor=2.2046226218 if pounds else 1
            ax2.plot([r['date'][5:] for r in rows],[r['weight']*factor for r in rows],color=BLUE,marker='o')
            ax2.set_title('Body weight ('+('lb' if pounds else 'kg')+')')
            self.summary.configure(text=f"Water logged in range: {summary['water']['ml']:g} ml · {len(rows)} weigh-in days.\nMultiple weigh-ins on one day are averaged. Canonical measurement entry is in kg / cm; charts honor the preferred display unit.")
        else:
            ax1.bar(x,[r['tasks']['total'] for r in daily],color=BLUE,label='Tasks planned')
            ax1.bar(x,[r['tasks']['completed'] for r in daily],color=ACCENT,label='Completed')
            self.date_axis(ax1,x,dates)
            ax1.set_title('Task completion')
            ax1.legend(facecolor=CARD,labelcolor=TEXT,fontsize=8)
            ax2.plot(x,[r['focus']['actual'] for r in daily],color=ACCENT,label='Actual focus minutes')
            ax2.plot(x,[r['focus']['planned'] for r in daily],color=BLUE,label='Planned focus minutes')
            self.date_axis(ax2,x,dates)
            ax2.set_title('Focus time')
            ax2.legend(facecolor=CARD,labelcolor=TEXT,fontsize=8)
            t=summary['tasks'];f=summary['focus']
            self.summary.configure(text=f"Tasks: {t['completed']} / {t['total']} completed · Time: {t['actual']:g} actual / {t['planned']:g} planned minutes\nFocus: {f['total']} finished or interrupted sessions · {f['actual']:g} actual / {f['planned']:g} planned minutes. Active timers are excluded.")
        for ax in (ax1,ax2):
            if not ax.has_data():
                ax.text(.5,.5,'No records in this view yet',transform=ax.transAxes,ha='center',va='center',color=MUTED)
        canvas=FigureCanvasTkAgg(self.fig,master=self.plot)
        self.canvas=canvas
        self.app.appearance.figure(self.fig)
        canvas.draw()
        native=canvas.get_tk_widget()
        def refresh_chart_glass():
            if not native.winfo_exists() or native.winfo_width()<2:
                return
            key=self.app.wallpaper.key(native)
            if getattr(native,'lifeos_chart_key',None)==key:return
            native.lifeos_chart_key=key
            image=self.app.wallpaper.sample(native)
            native.glass_photo=ImageTk.PhotoImage(image,master=self.app)
            native.delete('chart-glass')
            item=native.create_image(0,0,image=native.glass_photo,anchor='nw',tags='chart-glass')
            native.tag_lower(item)
        native.refresh_glass=refresh_chart_glass
        native.pack(fill='both',expand=True,padx=12,pady=12)
        toolbar=NavigationToolbar2Tk(canvas,self.plot,pack_toolbar=False)
        self.toolbar=toolbar
        toolbar.configure(background=PANEL)
        if self.show_tools:
            toolbar.pack(fill='x')

    @staticmethod
    def date_axis(ax,x,labels):
        step=max(1,len(x)//12)
        ax.set_xticks(x[::step],labels[::step],rotation=25,ha='right')

    def destroy(self):
        self.clear_plot()
        super().destroy()

    def clear_plot(self):
        if self.canvas:
            widget=self.canvas.get_tk_widget()
            for key in ('_idle_draw_id','_event_loop_id'):
                job=getattr(self.canvas,key,None)
                if job:
                    widget.after_cancel(job)
                    setattr(self.canvas,key,None)
            # Figure.clear otherwise calls update() on an already destroyed toolbar.
            self.canvas.toolbar=None
        if self.fig:
            self.fig.clear()
        for child in self.plot.winfo_children():
            child.destroy()
        self.canvas=None
        self.fig=None

"""Reference-driven dashboard: actual saved data on fully translucent glass."""
from datetime import date,datetime,timedelta
import math
from PIL import ImageTk
from .glass import GlassSurface,composite_glass
from .theme import TEXT,MUTED
from . import appearance
from .common import safe

class Dashboard(GlassSurface):
    def __init__(self,parent,app):
        super().__init__(parent,app)
        self.cards={}
        self.timer_job=None
        self.refresh_data()
        self.timer_job=self.after(500,self.update_timer)

    def refresh_data(self):
        today=date.today().isoformat()
        self.data=self.app.analytics.dashboard()
        self.missions=self.app.db.query("SELECT * FROM tasks WHERE date=? OR (date<? AND status NOT IN ('Completed','Skipped')) ORDER BY CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END,id LIMIT 4",(today,today))
        self.routines=[r for r in self.app.service.list('daily_routines',filters={'active':'Yes'}) if date.today().strftime('%A') in r['weekdays'].split(',')]
        self.routines.sort(key=lambda r:r['time'])
        start=(date.today()-timedelta(days=6)).isoformat()
        self.days=self.app.analytics.daily(start,today)
        self.meals=self.app.db.query('SELECT DISTINCT meal FROM food_logs WHERE date=?',(today,))
        self.subjects=[]
        for path in self.data['paths'][:2]:
            since=today if path['target_period']=='Daily' else start
            actual=self.app.db.one('SELECT COALESCE(SUM(minutes),0) n FROM study_sessions WHERE path_id=? AND date BETWEEN ? AND ?',(path['id'],since,today))['n']
            concepts=self.app.db.one("SELECT COUNT(*) n,COALESCE(SUM(status='Understood'),0) understood FROM concepts WHERE path_id=?",(path['id'],))
            ratio=actual/path['target_minutes'] if path['target_minutes'] else concepts['understood']/max(1,concepts['n'])
            self.subjects.append((path['name'],actual,path['target_minutes'],ratio))
        studied={r['date'] for r in self.app.db.query('SELECT DISTINCT date FROM study_sessions WHERE minutes>0')}
        cursor=date.today()
        if cursor.isoformat() not in studied:
            cursor-=timedelta(days=1)
        self.streak=0
        while cursor.isoformat() in studied:
            self.streak+=1
            cursor-=timedelta(days=1)
        self.active_routines=self.app.service.list('workout_routines',filters={'active':'Yes'})
        self.training_days=self.app.db.one("SELECT COUNT(DISTINCT date) n FROM workouts WHERE date BETWEEN ? AND ? AND status='Completed'",(start,today))['n']
        self.recent_activity=self.app.db.query("""SELECT date,event,title FROM (
            SELECT date,'TASK COMPLETED' event,title,id FROM tasks WHERE status='Completed'
            UNION ALL SELECT date,'WORKOUT '||UPPER(status),name,id FROM workouts WHERE status IN ('Completed','Recovery')
            UNION ALL SELECT s.date,'STUDY LOGGED',p.name,s.id FROM study_sessions s JOIN paths p ON p.id=s.path_id
            ) ORDER BY date DESC,id DESC LIMIT 4""")
        self.draw()

    def layout(self):
        width,height=max(1,self.winfo_width()),max(1,self.winfo_height())
        self.s=min(width/800,height/580)
        self.ox=max(0,(width-800*self.s)/2)
        self.oy=8*self.s
        col=800/3-10
        gap=15
        self.cards={
            'mission':(0,112,col,160),'focus':(col+gap,112,col,160),
            'schedule':(2*(col+gap),112,col,202),
            'learning':(0,287,col,145),'fitness':(col+gap,287,col,114),
            'nutrition':(col+gap,416,col,145),'analytics':(2*(col+gap),329,col,232),
            'dsa':(0,447,col,114),
        }

    def draw(self):
        if not hasattr(self,'data') or self.winfo_width()<20:
            return
        if appearance.current()==appearance.COMMAND:
            return self.draw_command()
        self.layout()
        self.delete('all')
        self.actions={}
        wp=self.app.wallpaper
        key=(self.winfo_width(),self.winfo_height(),wp.name,wp.last_size,appearance.epoch,
             self.winfo_rootx()-self.app.winfo_rootx(),self.winfo_rooty()-self.app.winfo_rooty())
        if self._backing_key!=key:
            self.backing=wp.crop(self)
            for box in self.cards.values():
                self.backing=composite_glass(self.backing,self.rect(box),radius=round(8*self.s),blur=round(4*self.s))
            self.photo=ImageTk.PhotoImage(self.backing,master=self.app)
            self._backing_key=key
        self.create_image(0,0,image=self.photo,anchor='nw')
        hour=datetime.now().hour
        greeting='Good morning.' if hour<12 else 'Good afternoon.' if hour<18 else 'Good evening.'
        self.text(0,36,greeting,38,family='Georgia')
        self.text(0,72,'Your day, organized in one place.',16,MUTED)
        self.text(752,40,date.today().strftime('%A, %B %d'),13,MUTED,anchor='e')
        self.draw_mission()
        self.draw_focus()
        self.draw_schedule()
        self.draw_learning()
        self.draw_fitness()
        self.draw_nutrition()
        self.draw_analytics()
        self.draw_dsa()
        if self.keyboard_action in self.actions:
            self.create_rectangle(*self.actions[self.keyboard_action]['box'],outline='#eeeeee',dash=(2,3))

    def draw_command(self):
        """Terminal composition inspired by the supplied image, using saved facts."""
        self.layout()
        self.cards={'completion':(0,92,190,112),'dsa':(202,92,190,112),
            'fitness':(404,92,190,112),'nutrition':(606,92,194,112),
            'mission':(0,217,542,166),'focus':(555,217,245,166),
            'schedule':(0,396,542,169),'learning':(555,396,245,169)}
        self.delete('all');self.actions={}
        key=(self.winfo_width(),self.winfo_height(),self.app.wallpaper.last_size,appearance.epoch)
        if getattr(self,'_command_key',None)!=key:
            self._command_key=key
            backing=self.app.wallpaper.crop(self)
            for box in self.cards.values():backing=composite_glass(backing,self.rect(box),radius=2)
            self.command_photo=ImageTk.PhotoImage(backing,master=self.app)
        self.create_image(0,0,image=self.command_photo,anchor='nw')
        green=appearance.palette()['accent'];amber=appearance.palette()['amber']
        self.text(0,21,'LIFEOS_TERMINAL // COMMAND CENTER',21,green,bold=True)
        self.text(0,45,'PERSONAL OPERATING SYSTEM',12)
        self.text(0,65,'LOCAL DATA | OFFLINE READY',11,MUTED)
        self.text(798,24,'TIME: '+datetime.now().strftime('%H:%M:%S'),11,MUTED,anchor='e')
        self.text(798,47,date.today().isoformat(),11,MUTED,anchor='e')
        a,b,c,d=self.rect((0,78,800,0));self.create_line(a,b,c,d,fill=green)
        def heading(key,title,page):
            x,y,w,h=self.cards[key]
            self.text(x+12,y+19,'[ '+title+' ]',12)
            self.action(key+'-open',(x,y,w,30),lambda:self.app.show(page))
            return x,y,w,h
        x,y,w,h=heading('completion','DAILY COMPLETION','Daily Planner')
        tasks=self.data['today']['tasks'];ratio=tasks['completed']/tasks['total'] if tasks['total'] else 0
        self.text(x+w/2,y+51,f'{ratio:.0%}' if tasks['total'] else '--',27,green,bold=True,anchor='center')
        self.progress(x+12,y+74,w-24,ratio)
        self.text(x+12,y+96,f"{tasks['completed']} / {tasks['total']} TASKS COMPLETE",11)
        x,y,w,h=heading('dsa','DSA PERFORMANCE','DSA Tracker')
        self.text(x+12,y+47,f"{self.data['week']['dsa']['solved']} PROBLEMS / 7 DAYS",12,green)
        values=[v['dsa']['solved'] for v in self.days]
        for i,value in enumerate(values):
            left,top,right,bottom=self.rect((x+13+i*24,y+68,17,10))
            self.create_rectangle(left,top,right,bottom,outline=green,fill=green if value else '')
            self.text(x+20+i*24,y+94,date.fromisoformat(self.days[i]['date']).strftime('%a')[0],10,MUTED,anchor='center')
        x,y,w,h=heading('fitness','FITNESS STATUS','Workout Planner')
        self.text(x+12,y+49,f'{self.training_days} TRAINING DAYS',18,green,bold=True)
        self.text(x+12,y+76,'LAST 7 SAVED DAYS',11,MUTED)
        self.button('workout-open',(x+12,y+87,w-24,18),'OPEN WORKOUT',lambda:self.app.show('Workout Planner'))
        x,y,w,h=heading('nutrition','NUTRITION STATUS','Diet & Nutrition')
        food=self.data['today']['nutrition']
        self.text(x+12,y+47,f"{food['calories']:,.0f} KCAL LOGGED",14,green)
        self.text(x+12,y+70,f"{food['protein']:.1f} g PROTEIN",12)
        self.text(x+12,y+94,f'{len(self.meals)} / 4 MEALS LOGGED',11,MUTED)
        x,y,w,h=heading('mission',"TODAY'S EXECUTION QUEUE",'Daily Planner')
        for i,task in enumerate(self.missions):
            yy=y+49+i*27;status='DONE' if task['status']=='Completed' else 'ACTIVE' if task['status']=='In progress' else 'PENDING'
            tint=amber if status=='ACTIVE' else green if status=='DONE' else MUTED
            self.text(x+12,yy,'['+status+']',12,tint)
            self.text(x+104,yy,task['title'][:35],12,tint)
            self.action('task-'+str(task['id']),(x+8,yy-12,w-16,25),lambda t=task:self.toggle_task(t))
        if not self.missions:
            self.text(x+12,y+59,'NO TASKS QUEUED',14,MUTED)
            self.button('new-task',(x+12,y+99,180,27),'OPEN DAILY PLANNER',lambda:self.app.show('Daily Planner'))
        x,y,w,h=heading('focus','SESSION TELEMETRY','Daily Planner')
        timer=self.app.service.active_timer()
        remaining=self.app.service.timer_remaining(timer) if timer else self.configured_duration()*60
        seconds=math.ceil(remaining)
        self.text(x+12,y+54,f'{seconds//60:02}:{seconds%60:02}',29,green)
        self.text(x+12,y+80,'FOCUS: '+(timer['status'].upper() if timer else 'IDLE'),11,MUTED)
        self.text(x+12,y+102,f"WATER: {self.data['today']['water']['ml']:g} ml LOGGED",11,MUTED)
        self.button('focus-toggle',(x+12,y+123,130,26),'START' if not timer else 'RESUME' if timer['status']=='Paused' else 'PAUSE',self.focus_toggle)
        if timer:self.button('focus-finish',(x+151,y+123,80,26),'FINISH',self.finish_focus)
        x,y,w,h=heading('schedule','RECENT ACTIVITY LOG','Analytics')
        for i,row in enumerate(self.recent_activity):
            self.text(x+12,y+48+i*23,'['+row['date'][5:]+'] '+row['event']+': '+row['title'][:28],11)
        if not self.recent_activity:self.text(x+12,y+57,'NO SAVED ACTIVITY YET',12,MUTED)
        self.button('analytics-open',(x+12,y+135,210,23),'OPEN ACTIVITY ANALYTICS',lambda:self.app.show('Analytics'))
        x,y,w,h=heading('learning','LEARNING PROGRESS','Learning Paths')
        for i,(name,actual,target,ratio) in enumerate(self.subjects):
            self.text(x+12,y+48+i*39,name[:24],11)
            self.progress(x+12,y+62+i*39,w-24,ratio)
        if not self.subjects:self.text(x+12,y+54,'NO SUBJECTS RECORDED',11,MUTED)
        self.text(x+12,y+132,f'STUDY STREAK: {self.streak} DAYS',11,green)
        if self.keyboard_action in self.actions:
            self.create_rectangle(*self.actions[self.keyboard_action]['box'],outline=green,dash=(2,3))

    def heading(self,key,title,page):
        x,y,w,h=self.cards[key]
        self.text(x+14,y+23,title,14,bold=True)
        self.text(x+w-15,y+23,'···',13,MUTED,anchor='e')
        self.action(key+'-open',(x+w-40,y+5,35,30),lambda:self.app.show(page))
        return x,y,w,h

    def draw_mission(self):
        x,y,w,h=self.heading('mission',"Today's Mission",'Daily Planner')
        if not self.missions:
            self.text(x+14,y+59,'Make space for what matters.',12,MUTED,width=w-30)
            d=self.data['today']['dsa'];g=self.data['goals']
            self.text(x+14,y+88,f"DSA progress: {d['solved']} / {g['dsa_target']}",12)
            self.button('new-task',(x+14,y+118,119,26),'Plan your day',lambda:self.app.show('Daily Planner'))
        for i,task in enumerate(self.missions):
            yy=y+54+i*27
            left,top,right,bottom=self.rect((x+14,yy-7,12,12))
            done=task['status']=='Completed'
            self.create_rectangle(left,top,right,bottom,outline='#c8c8c8',fill='#c8c8c8' if done else '')
            if done:
                self.create_line(left+2*self.s,top+6*self.s,left+5*self.s,top+9*self.s,right-2*self.s,top+3*self.s,fill='#242424',width=max(1,round(self.s)))
            self.text(x+34,yy,task['title'][:32]+('…' if len(task['title'])>32 else ''),12)
            self.action('task-'+str(task['id']),(x+10,yy-12,w-23,25),lambda t=task:self.toggle_task(t))

    def draw_focus(self):
        x,y,w,h=self.heading('focus','Focus Session','Daily Planner')
        timer=self.app.service.active_timer()
        minutes=self.configured_duration()
        remaining=self.app.service.timer_remaining(timer) if timer else minutes*60
        seconds=math.ceil(remaining)
        self.text(x+14,y+80,f'{seconds//60:02}:{seconds%60:02}',43,family='Georgia')
        cx,cy=x+w-54,y+86
        radius=35
        completed=1-remaining/(timer['planned_minutes']*60) if timer else 0
        for i in range(60):
            angle=math.radians(i*6-90)
            a=(self.ox+(cx+math.cos(angle)*(radius-5))*self.s,self.oy+(cy+math.sin(angle)*(radius-5))*self.s)
            b=(self.ox+(cx+math.cos(angle)*radius)*self.s,self.oy+(cy+math.sin(angle)*radius)*self.s)
            self.create_line(*a,*b,fill='#eeeeee' if i<completed*60 else '#8b8b8b',width=max(1,round(self.s)))
        title='Start Focus' if not timer else 'Resume' if timer['status']=='Paused' else 'Pause'
        self.button('focus-toggle',(x+14,y+117,115,28),title,self.focus_toggle)
        if timer:
            self.button('focus-finish',(x+145,y+117,72,28),'Finish',self.finish_focus)

    def draw_schedule(self):
        x,y,w,h=self.heading('schedule',"Today's Schedule",'Daily Planner')
        rows=[(r['time'],r['title']) for r in self.routines[:3]]
        if not rows:
            rows=[('Today',t['title']) for t in self.missions[:3] if t['status']!='Completed']
        for i,(when,title) in enumerate(rows):
            yy=y+62+i*45
            self.text(x+14,yy,when+' — '+title[:25]+('…' if len(title)>25 else ''),12,width=w-28)
            if i<len(rows)-1:
                a,b,c,d=self.rect((x+14,yy+22,w-28,0))
                self.create_line(a,b,c,d,fill='#686868',width=1)
        if not rows:
            self.text(x+14,y+65,'No schedule entries for today.',12,MUTED,width=w-30)
            self.text(x+14,y+101,'Set routine times in Daily Planner.',12,MUTED,width=w-30)
        self.action('schedule-all',(x+8,y+39,w-16,h-45),lambda:self.app.show('Daily Planner'))

    def draw_learning(self):
        x,y,w,h=self.heading('learning','Learning Progress','Learning Paths')
        if not self.subjects:
            self.text(x+14,y+61,'Your next subject starts here.',12,MUTED,width=w-30)
            self.button('create-subject',(x+14,y+93,155,27),'Open learning paths',lambda:self.app.show('Learning Paths'))
        for i,(name,actual,target,ratio) in enumerate(self.subjects):
            yy=y+54+i*34
            self.text(x+14,yy,name[:31],12)
            self.progress(x+14,yy+13,w-29,ratio)
        if self.subjects:
            self.text(x+14,y+127,f'Daily learning streak: {self.streak} '+('day' if self.streak==1 else 'days'),11)
        self.action('learning-all',(x+8,y+37,w-16,h-43),lambda:self.app.show('Learning Paths'))

    def draw_fitness(self):
        x,y,w,h=self.heading('fitness','Workout','Workout Planner')
        workouts=self.data['workouts']
        name=workouts[0]['name'] if workouts else 'No workout planned'
        self.text(x+14,y+54,"Today's workout: "+name[:21],12,width=w-28)
        denominator=self.active_routines[0]['days_per_week'] if len(self.active_routines)==1 else None
        actual=f'{self.training_days} / {denominator} days' if denominator else f'{self.training_days} training days'
        self.text(x+14,y+83,'Last 7 days: '+actual,12)
        self.action('fitness-all',(x+8,y+36,w-16,h-42),lambda:self.app.show('Workout Planner'))

    def draw_nutrition(self):
        x,y,w,h=self.heading('nutrition','Nutrition','Diet & Nutrition')
        n=self.data['today']['nutrition'];g=self.data['goals']
        rows=[('Meals logged',f'{len(self.meals)} / 4',len(self.meals)/4),
              ('Protein',f"{n['protein']:.0f} g / {g['protein']:g} g",n['protein']/g['protein'] if g['protein'] else 0),
              ('Calories',f"{n['calories']:,.0f} / {g['calories']:,.0f} kcal",n['calories']/g['calories'] if g['calories'] else 0)]
        for i,(title,value,ratio) in enumerate(rows):
            yy=y+48+i*32
            self.text(x+14,yy,title+':',11)
            self.text(x+w-14,yy,value,11,anchor='e')
            self.progress(x+14,yy+13,w-28,ratio)
        self.action('nutrition-all',(x+8,y+34,w-16,h-40),lambda:self.app.show('Diet & Nutrition'))

    def draw_analytics(self):
        x,y,w,h=self.heading('analytics','Daily Analytics','Analytics')
        self.text(x+14,y+43,'Focus minutes · last 7 days',11,MUTED)
        left,top=x+18,y+69
        cw,ch=w-36,128
        values=[day['focus']['actual'] for day in self.days]
        maximum=max(1,max(values))
        for i in range(4):
            a,b,c,d=self.rect((left,top+ch*i/3,cw,0))
            self.create_line(a,b,c,d,fill='#666666',dash=(2,4))
        points=[]
        for i,value in enumerate(values):
            px=left+i*cw/6
            py=top+ch-value/maximum*(ch-8)
            points.extend([self.ox+px*self.s,self.oy+py*self.s])
            if value:
                r=2.5*self.s
                self.create_oval(points[-2]-r,points[-1]-r,points[-2]+r,points[-1]+r,outline='#eeeeee',fill='#d0d0d0')
        if any(values):
            self.create_line(*points,fill='#dedede',width=max(1,round(1.5*self.s)),smooth=True)
        else:
            self.text(x+w/2,y+125,'No focus sessions yet',12,MUTED,anchor='center')
        for i in (0,2,4,6):
            self.text(left+i*cw/6,top+ch+16,date.fromisoformat(self.days[i]['date']).strftime('%a'),10,MUTED,anchor='center')
        self.action('analytics-all',(x+8,y+36,w-16,h-42),lambda:self.app.show('Analytics'))

    def draw_dsa(self):
        x,y,w,h=self.heading('dsa','DSA Activity','DSA Tracker')
        d=self.data['week']['dsa']
        self.text(x+14,y+49,f"{d['solved']} solved · {d['independent']} independent",12)
        values=[day['dsa']['solved'] for day in self.days]
        for i,value in enumerate(values):
            bx=x+17+i*(w-32)/7
            bh=max(1,value/max(1,max(values))*24)
            a,b,c,dd=self.rect((bx,y+88-bh,(w-65)/7,bh))
            self.create_rectangle(a,b,c,dd,fill='#c2c2c2' if value else '#696969',outline='')
        due=len(self.data['today']['dsa_revisions'])
        self.text(x+14,y+101,f'{due} due for revision',10,MUTED)
        self.action('dsa-all',(x+8,y+35,w-16,h-40),lambda:self.app.show('DSA Tracker'))

    def toggle_task(self,task):
        def action():
            updated=dict(task)
            updated['status']='To do' if updated['status']=='Completed' else 'Completed'
            self.app.service.save('tasks',updated,updated['id'])
            self.refresh_data()
        safe(self,action)

    def focus_toggle(self):
        def action():
            timer=self.app.service.active_timer()
            if timer:
                self.app.service.timer_action('resume' if timer['status']=='Paused' else 'pause')
            else:
                title=self.app.timer_title.get().strip() or 'Focus session'
                self.app.service.start_timer(title,self.configured_duration())
            self.draw()
        safe(self,action)

    def configured_duration(self):
        try:
            value=float(self.app.timer_minutes.get())
            if not math.isfinite(value) or value<=0:
                raise ValueError()
            return value
        except ValueError:
            return float(self.app.db.settings()['focus_minutes'])

    def finish_focus(self):
        self.app.timer_action('finish')
        self.refresh_data()

    def update_timer(self):
        if not self.winfo_ismapped():
            self.timer_job=None
            return
        self.draw()
        self.timer_job=self.after(1000,self.update_timer)

    def destroy(self):
        if self.timer_job:
            self.after_cancel(self.timer_job)
        super().destroy()

"""Reference workout controls over the existing native photo/theme system."""
from datetime import date
import tkinter as tk
from PIL import ImageTk
from . import appearance
from .photowidgets import PhotoWidget,PhotoButton
from .collections import PhotoRecordList
from .glass import composite_glass


def week_completion(week):
    """Finished dated sessions, including recorded recovery; never plan flags."""
    completed=sum(bool(day['days']) and all(d.get('session') and d['session']['finished_at'] for d in day['days']) for day in week)
    return completed,len(week)


def workout_totals(planned,session=None):
    rows=session['exercises'] if session else planned
    actual=bool(session)
    count=len(rows)
    completed=sum(r.get('completion')=='Completed' for r in rows) if actual else 0
    skipped=sum(r.get('completion')=='Skipped' for r in rows) if actual else 0
    total_sets=sum(r['target_sets'] if actual else r['sets'] for r in rows)
    seconds=0
    for r in rows:
        duration=r['target_duration'] if actual else r['duration_min']
        sets=r['target_sets'] if actual else r['sets']
        reps=r['target_reps'] if actual else r['reps']
        seconds+=duration*60 if duration else sets*(reps*3+r['rest_seconds'])
    return dict(planned=count,completed=completed,skipped=skipped,sets=total_sets,
                ratio=completed/count if count else 0,minutes=seconds/60)


class WorkoutSurface(PhotoWidget):
    def background(self,panel=False):
        wallpaper=getattr(self.owner,'wallpaper',None)
        key=(wallpaper.key(self) if wallpaper else (self.winfo_width(),self.winfo_height(),appearance.epoch),panel)
        if getattr(self,'_surface_key',None)!=key:
            self._surface_key=key
            base=self.backdrop()
            self.glass_image=composite_glass(base,(0,0,base.width,base.height),radius=5) if panel else base
            self.photo=ImageTk.PhotoImage(self.glass_image,master=self.owner)
        self.delete('all')
        self.create_image(0,0,image=self.photo,anchor='nw')

    def text(self,x,y,text,size=11,color=None,bold=False,anchor='w',width=0):
        return self.create_text(x*self.scale,y*self.scale,text=text,anchor=anchor,fill=color or appearance.palette()['text'],
            font=appearance.font(('Segoe UI',-round(size*self.scale),'bold' if bold else 'normal'),terminal=True),
            width=width*self.scale)

    def segments(self,x,y,width,ratio):
        p=appearance.palette()
        for i in range(24):
            left=x+i*width/24
            self.create_rectangle(left*self.scale,y*self.scale,(left+width/24-2)*self.scale,(y+8)*self.scale,
                outline=p['border'],fill=p['accent'] if i<round(ratio*24) else p['secondary'])


class TrainingHeader(WorkoutSurface):
    def __init__(self,parent):
        self.completed=0;self.total=7;self.weekday=date.today().strftime('%A')
        super().__init__(parent,height=70)
        self.configure(height=round(70*self.scale))

    def draw(self):
        if not self.winfo_exists() or self.winfo_width()<3:return
        self.background();p=appearance.palette();width=self.winfo_width()/self.scale
        self.text(0,20,'WORKOUT // TRAINING CONTROL',21,p['accent'],True)
        self.text(0,47,'CURRENT DATE: '+date.today().strftime('%b %d, %Y').upper()+' // VIEW: '+self.weekday.upper(),9,p['muted'])
        self.text(0,63,'LOCAL DATA / OFFLINE READY',8,p['muted'])
        right=width-205
        self.text(right,12,'WEEKLY WORKOUT COMPLETION',9,p['muted'])
        ratio=self.completed/max(1,self.total)
        self.text(right,31,f'{ratio:.0%}  ({self.completed}/{self.total} DAYS)',10)
        self.segments(right,45,200,ratio)


class ChecklistHeader(WorkoutSurface):
    def __init__(self,parent):
        self.weekday=date.today().strftime('%A');self.completed=0;self.total=0
        super().__init__(parent,height=66)
        self.configure(height=round(66*self.scale))

    def draw(self):
        if self.winfo_width()<3:return
        self.background();p=appearance.palette();w=self.winfo_width()/self.scale
        self.text(0,21,'WORKOUT // WEEKLY CHECKLIST',21,p['accent'],True)
        self.text(0,49,self.weekday.upper()+' / YOUR SAVED PLAN',10,p['muted'])
        right=w-200
        self.text(right,15,f'{self.completed} / {self.total} targets completed',10)
        self.segments(right,32,195,self.completed/self.total if self.total else 0)
        self.text(right,52,'CHANGES SAVE AUTOMATICALLY',8,p['muted'])


class WeekDayCard(PhotoButton):
    def __init__(self,parent,weekday,command,compact=False):
        self.weekday=weekday;self.state='UNASSIGNED';self.kind='NO PLAN';self.active=False;self.today=False
        self.compact=compact
        super().__init__(parent,weekday,command,width=80,height=66 if compact else 86,secondary=True)

    def draw(self):
        if not hasattr(self,'scale') or self.winfo_width()<3 or self.winfo_height()<3:return
        self.delete('all');self.paint_background()
        p=appearance.palette();s=self.scale;w,h=self.winfo_width(),self.winfo_height()
        border=p['accent'] if self.active or self.state=='COMPLETED' else p['amber'] if self.state=='PENDING' else p['border']
        self.create_rectangle(1,8*s,w-2,h-2,fill=p['secondary'] if self.active or self.hover else '',outline=border,width=2 if self.active else 1)
        color=p['accent'] if self.active or self.state=='COMPLETED' else p['muted'] if self.kind=='REST' else p['text']
        family='Consolas' if appearance.current()==appearance.COMMAND else 'Segoe UI'
        if self.today:
            self.create_rectangle(w*.15,0,w*.85,14*s,fill=p['accent'],outline='')
            self.create_text(w/2,7*s,text='TODAY',fill=p['bg'],font=(family,-round(8*s),'bold'))
        self.create_text(w/2,(28 if self.compact else 31)*s,text=self.weekday[:3].upper(),fill=color,font=(family,-round((20 if self.compact else 23)*s),'bold'))
        self.create_text(w/2,(44 if self.compact else 56)*s,text=self.kind[:15].upper(),fill=color,font=(family,-round(9*s)))
        self.create_text(w/2,(57 if self.compact else 71)*s,text=self.state,fill=color,font=(family,-round(9*s)))


class ChecklistTargets(PhotoRecordList):
    def select_index(self,index):
        if self.order:
            self.selection_set(self.order[index])
            top=(42+index*54)*self.scale;bottom=top+54*self.scale
            if top<self.offset+42*self.scale:self.offset=max(0,top-42*self.scale)
            elif bottom>self.offset+self.winfo_height():self.offset=bottom-self.winfo_height()
            self.draw()
        return 'break'


class CommandButton(PhotoButton):
    def __init__(self,parent,text,command,kind='normal',**kwargs):
        self.kind=kind
        super().__init__(parent,text,command,**kwargs)

    def draw(self):
        if not hasattr(self,'values') or self.winfo_width()<3:return
        self.delete('all');self.paint_background();p=appearance.palette();s=self.scale
        disabled=self.values['state']=='disabled'
        color=p['muted'] if disabled else p['amber'] if self.kind=='save' else p['accent']
        fill=p['accent'] if self.kind=='finish' and not disabled else p['secondary'] if self.hover else ''
        self.create_rectangle(1,1,self.winfo_width()-2,self.winfo_height()-2,outline=p['border'] if disabled else color,fill=fill)
        self.create_text(self.winfo_width()/2,self.winfo_height()/2,text=self.values['text'],
            fill=p['bg'] if self.kind=='finish' and not disabled else color,
            font=appearance.font(('Segoe UI',-round(10*s),'bold'),terminal=True))


class MuscleStrip(WorkoutSurface):
    def __init__(self,parent,on_toggle,on_more):
        self.selected=[];self.on_toggle=on_toggle;self.on_more=on_more;self.boxes=[]
        super().__init__(parent,takefocus=True,height=58)
        self.configure(height=round(58*self.scale))
        self.bind('<Button-1>',self.click)
        self.bind('<Return>',lambda e:self.on_more())
        self.bind('<space>',lambda e:self.on_more())
        self.bind('<Motion>',lambda e:self.configure(cursor='hand2' if any(a<=e.x<=c and b<=e.y<=d for (a,b,c,d),m in self.boxes) else ''))

    def draw(self):
        if self.winfo_width()<3:return
        self.background();p=appearance.palette();self.boxes=[];s=self.scale
        self.text(0,10,'TARGET MUSCLE GROUPS // SELECTION',10)
        # Common groups fit the reference row; More opens the complete searchable library.
        choices=[('Chest','Chest'),('Back','Back'),('Shoulders','Shoulders'),('Biceps','Biceps'),
                 ('Triceps','Triceps'),('Legs','Legs'),('Abs','Abs'),('Forearms','Forearms')]
        width=self.winfo_width()/s
        self.text(width-3,10,'SEARCH / MORE +',9,p['accent'],anchor='e')
        self.boxes.append((((width-112)*s,0,width*s,22*s),None))
        unit=(self.winfo_width()/s-7*6)/sum(len(t)+5 for t,m in choices)
        left=0
        for title,muscle in choices:
            width=(len(title)+5)*unit
            active=any(m in self.selected for m in ('Legs','Quadriceps','Hamstrings','Glutes','Calves')) if muscle=='Legs' else muscle in self.selected
            box=(left*s,26*s,(left+width)*s,50*s)
            self.create_rectangle(*box,fill=p['secondary'] if active else '',outline=p['accent'] if active else p['border'])
            display=('x ' if active else '  ')+title
            self.text(left+width/2,38,display,10,p['accent'] if active else p['text'],anchor='center')
            self.boxes.append((box,muscle));left+=width+6

    def click(self,event):
        for (a,b,c,d),muscle in self.boxes:
            if a<=event.x<=c and b<=event.y<=d:
                self.focus_set()
                return self.on_more() if muscle is None else self.on_toggle(muscle)


class WorkoutSummary(WorkoutSurface):
    def __init__(self,parent):
        self.totals=workout_totals([]);self.status='NOT STARTED'
        super().__init__(parent,width=180,height=240)
        self.configure(width=round(180*self.scale))

    def draw(self):
        if self.winfo_width()<3:return
        self.background(True);p=appearance.palette();w=self.winfo_width()/self.scale;t=self.totals
        self.text(w/2,20,'[ WORKOUT SUMMARY ]',10,anchor='center')
        for y,title,value in [(52,'PLANNED EXERCISES',str(t['planned'])),(80,'COMPLETED',f"{t['completed']} / {t['planned']}")]:
            self.text(12,y,title,9,p['muted']);self.text(w-12,y,value,10,anchor='e')
        self.text(12,108,'WORKOUT PROGRESS',9,p['muted']);self.text(w-12,108,f"{t['ratio']:.0%}",10,p['accent'],anchor='e')
        self.segments(12,124,w-24,t['ratio'])
        self.text(12,159,'TOTAL SETS',9,p['muted']);self.text(w-12,159,str(t['sets']),10,anchor='e')
        self.text(12,187,'EST. DURATION',9,p['muted']);self.text(w-12,187,f"~{t['minutes']:.0f} min",10,anchor='e')
        self.create_line(12*self.scale,207*self.scale,(w-12)*self.scale,207*self.scale,fill=p['border'])
        self.text(12,225,self.status.upper(),9,p['accent'],width=w-24)
        if self.winfo_height()/self.scale>270:
            self.text(12,260,'DURATION IS AN ESTIMATE.\nPROGRESS USES LOGGED SETS.',8,p['muted'],width=w-24)


class WorkoutExerciseList(PhotoRecordList):
    """Compact reference queue; reuse bounded rendering, real selection and wheel routing."""
    def __init__(self,parent,on_open,on_toggle,on_add,on_actions):
        self.on_actions=on_actions
        super().__init__(parent,('exercise','muscles','sets','reps','load','duration'),on_open=on_open,on_toggle=on_toggle,on_add=on_add)

    def click(self,event):
        key=self.hit(event.x,event.y)
        if key and key[0]=='actions':
            self.selection_set(key[1]);return self.on_actions()
        return super().click(event)

    def draw_rows(self,width,height):
        s=self.scale;p=appearance.palette();pad=8*s;header=28*s;rowheight=33*s
        available=width-2*pad
        # First cell is completion, last is a real exercise action menu.
        fractions=(.055,.255,.17,.065,.075,.17,.12,.09)
        total=sum(fractions);widths=[available*f/total for f in fractions]
        headings=('STAT','EXERCISE NAME','TARGET MUSCLE','SETS','REPS','WEIGHT/LOAD','DURATION','')
        left=pad
        for title,cw in zip(headings,widths):
            self.text(left+3*s,header/2,title,8,p['muted'],cw-4*s)
            left+=cw
        self.create_line(pad,header,width-pad,header,fill=p['border'])
        self.extent=max(height,header+len(self.order)*rowheight+6*s)
        self.offset=max(0,min(self.offset,self.extent-height))
        for index,iid in enumerate(self.order):
            top=header+index*rowheight-self.offset
            if top<header or top>=height:continue
            mid=top+rowheight/2;info=self.details.get(iid,{})
            color=p['accent'] if info.get('completed') else p['amber'] if iid==self.selected else p['text']
            if iid==self.selected:self.create_rectangle(pad,top,width-pad,top+rowheight,fill=p['secondary'],outline=p['border'])
            self.hitboxes.append(((pad,top,width-pad,top+rowheight),('row',iid)))
            left=pad;r=5*s;center=left+widths[0]/2
            self.create_rectangle(center-r,mid-r,center+r,mid+r,outline=color,fill=p['accent'] if info.get('completed') else '')
            if info.get('completed'):self.text(center,mid,'x',9,p['bg'],anchor='center')
            elif info.get('skipped'):self.text(center,mid,'/',9,p['amber'],anchor='center')
            self.hitboxes.append(((left,top,left+widths[0],top+rowheight),('toggle',iid)))
            left+=widths[0]
            for value,cw in zip(self.data[iid],widths[1:-1]):
                self.text(left+4*s,mid,value,10,color,cw-7*s);left+=cw
            self.text(left+widths[-1]/2,mid,'...',11,color,anchor='center')
            self.hitboxes.append(((left,top,width-pad,top+rowheight),('actions',iid)))
            self.create_line(pad,top+rowheight,width-pad,top+rowheight,fill=p['border'])

    def select_index(self,index):
        if self.order:
            self.selection_set(self.order[index])
            y=(28+index*33)*self.scale;height=self.winfo_height()
            if y<self.offset+28*self.scale:self.offset=max(0,y-28*self.scale)
            elif y+33*self.scale>self.offset+height:self.offset=y+33*self.scale-height
            self.draw()
        return 'break'

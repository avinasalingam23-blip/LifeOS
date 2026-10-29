"""Offline, cached icons from bundled SVG-derived masks; no icon fonts or network.

Lucide 0.468.0: 24px view box / rounded 2-unit stroke. Three exercise
pictograms use the same grid. Python's official mark keeps its outline in grayscale;
record rows display a separate adjacent trademark marker.
"""
from functools import lru_cache
from pathlib import Path
from PIL import Image,ImageTk,ImageOps
import customtkinter as ctk
from .theme import BLUE,VIOLET,MINT,TEXT,MUTED,BORDER

ASSETS=Path(__file__).resolve().parents[1]/'assets'
NAV_ICONS={
    'Dashboard':'layout-dashboard','DSA Tracker':'code-xml','Learning Paths':'book-open',
    'Workout Planner':'dumbbell','Diet & Nutrition':'apple','Daily Planner':'calendar-check',
    'Analytics':'chart-no-axes-combined','Settings':'settings',
}
ENTITY_ICONS={
    'problems':'code-xml','solutions':'file-code-2','paths':'book-open','concepts':'graduation-cap',
    'study_sessions':'notebook-pen','workout_routines':'dumbbell','workout_days':'calendar-check',
    'planned_exercises':'activity','workouts':'dumbbell','exercise_logs':'activity',
    'foods':'apple','food_logs':'utensils','water_logs':'droplets','measurements':'activity',
    'tasks':'list-checks','daily_routines':'calendar-check','focus_sessions':'timer',
}
TITLE_ICONS={
    'Problems':'code-xml','Solution versions':'file-code-2','Subjects':'book-open','Concepts':'graduation-cap',
    'Study sessions':'notebook-pen','Routines':'dumbbell','Weekly schedule':'calendar-check',
    'Planned exercises':'activity','Workout history':'dumbbell','Exercise history':'activity',
    'Food library':'apple','Food diary':'utensils','Water':'droplets','Body measurements':'activity',
    'Daily tasks':'list-checks','Daily routines':'calendar-check','Focus history':'timer',
    'Daily goals':'circle-check','Nutrition goals':'apple','Display & reminders':'calendar-check',
    'Data safety':'shield-check','Food logger':'utensils',
    'Build a weighed recipe':'cooking-pot',
    'Your next moves':'list-checks','Practice rhythm':'code-xml',
    'Keep your curiosity moving':'book-open','Move. Recover. Repeat.':'dumbbell',
    **NAV_ICONS,
}

@lru_cache(maxsize=256)
def raster(name,color=TEXT):
    if name=='python-logo':
        source=Image.open(ASSETS/'python-logo.png').convert('RGBA')
        monochrome=ImageOps.grayscale(source).convert('RGBA')
        monochrome.putalpha(source.getchannel('A'))
        return monochrome
    source=Image.open(ASSETS/'icons'/(name+'.png')).convert('RGBA')
    tinted=Image.new('RGBA',source.size,color)
    tinted.putalpha(source.getchannel('A'))
    return tinted

@lru_cache(maxsize=256)
def icon(name,color=TEXT,size=18):
    result=ctk.CTkImage(light_image=raster(name,color),dark_image=raster(name,color),size=(size,size))
    result.lifeos_name=name
    return result

@lru_cache(maxsize=256)
def tree_icon(name,color=MUTED,size=19,master=None):
    result=ImageTk.PhotoImage(raster(name,color).resize((size,size),Image.Resampling.LANCZOS),master=master)
    result.lifeos_name=name
    return result

class IconBadge(ctk.CTkFrame):
    def __init__(self,parent,name,color=BLUE,size=34,**kwargs):
        tint='#333333' if color==BLUE else '#313131' if color==VIOLET else '#373737' if color==MINT else '#343434'
        super().__init__(parent,width=size,height=size,fg_color=tint,border_width=1,border_color=BORDER,corner_radius=11,**kwargs)
        self.pack_propagate(False)
        self.grid_propagate(False)
        ctk.CTkLabel(self,text='',image=icon(name,color,19)).place(relx=.5,rely=.5,anchor='center')

def action_icon(text):
    text=text.lower().replace('↗','').replace('→','').replace('+','').strip()
    mapping=[('copy','copy'),('save','save'),('cancel','x'),('close','x'),('delete','trash-2'),
        ('remove','trash-2'),('export','download'),('refresh','refresh-cw'),('open url','external-link'),
        ('plan scheduled','calendar-plus'),('generate','calendar-plus'),('mark complete','check-check'),
        ('done','check'),('build recipe','cooking-pot'),('add','plus'),('apply','filter'),('clear','x'),
        ('pause','pause'),('resume','play'),('start','play'),('finish','square'),
        ('create backup','database-backup'),('restore','archive-restore'),
        ('find food','search'),('update charts','chart-no-axes-combined'),('edit','pencil'),
        ('explore learning','book-open'),('review','book-open'),('workout planner','dumbbell'),
        ('daily planner','calendar-check'),('open','arrow-up-right')]
    return next((name for prefix,name in mapping if text.startswith(prefix)),None)

def row_icon(table,row):
    if table=='solutions' and row.get('language')=='Python':
        return 'python-logo',TEXT
    if table in ('tasks','workouts') and row.get('status')=='Completed':
        return 'circle-check',MINT
    if table=='workouts' and row.get('status')=='Recovery':
        return 'moon',VIOLET
    if table in ('planned_exercises','exercise_logs'):
        text=row.get('exercise','').lower().replace('-',' ').replace('_',' ')
        if any(term in text for term in ('running','run','jog','treadmill')):
            return 'running',MINT
        if any(term in text for term in ('pull up','pullup','chin up')):
            return 'pull-up',VIOLET
        if any(term in text for term in ('push up','pushup')):
            return 'push-up',BLUE
        return 'dumbbell',MUTED
    return ENTITY_ICONS[table],BLUE if table in ('problems','focus_sessions') else MUTED

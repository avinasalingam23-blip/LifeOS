"""Monochrome glass surfaces for reliable native Tk rendering.

Tk cannot blur pixels behind individual widgets. Matching photo samples and
33% graphite overlays provide glass across whole surfaces, with photo-aware
text and navigation. No OS hooks or window-alpha extensions are required.
"""
import math
import tkinter as tk
import customtkinter as ctk

BG='#0b0b0b'
PANEL='#1c1c1c'
CARD='#282828'
# Legacy exported names preserve the existing view API; all values are grey.
SURFACE_BLUE='#202020'
SURFACE_VIOLET='#1f1f1f'
BORDER='#505050'
HIGHLIGHT='#676767'
ACCENT='#d8d8d8'
BLUE='#c2c2c2'
MINT='#bbbbbb'
VIOLET='#a3a3a3'
TEXT='#f2f2f2'
MUTED='#d8d8d8'
INPUT='#141414'

def install_theme():
    # Set library-managed DPI awareness before Tk caches virtual screen metrics.
    # CTk's normal scaling initialization happens after tkinter.Tk is created.
    ctk.ScalingTracker.activate_high_dpi_awareness()
    ctk.set_appearance_mode('dark')
    ctk.set_default_color_theme('blue')
    theme=ctk.ThemeManager.theme
    updates={
        'CTk':dict(fg_color=BG),
        'CTkToplevel':dict(fg_color=BG),
        'CTkFrame':dict(fg_color=PANEL,top_fg_color=CARD,border_color=BORDER,corner_radius=16,border_width=0),
        'CTkButton':dict(fg_color='#424242',hover_color='#565656',border_color='#717171',border_width=1,
                         corner_radius=11,text_color=TEXT,text_color_disabled='#878787'),
        'CTkEntry':dict(fg_color=INPUT,border_color=BORDER,border_width=1,corner_radius=10,text_color=TEXT,placeholder_text_color='#a4a4a4'),
        'CTkOptionMenu':dict(fg_color=CARD,button_color='#393939',button_hover_color='#4d4d4d',corner_radius=10,text_color=TEXT),
        'CTkDropdownMenu':dict(fg_color=CARD,hover_color='#464646',text_color=TEXT),
        'CTkSegmentedButton':dict(fg_color='#181818',selected_color='#4a4a4a',selected_hover_color='#595959',
            unselected_color='#181818',unselected_hover_color='#323232',text_color=TEXT,corner_radius=10,border_width=4),
        'CTkTextbox':dict(fg_color=INPUT,border_width=1,border_color=BORDER,corner_radius=12,text_color=TEXT,
                          scrollbar_button_color='#505050',scrollbar_button_hover_color='#727272'),
        'CTkScrollbar':dict(button_color='#4c4c4c',button_hover_color='#727272',corner_radius=8),
        'CTkProgressBar':dict(fg_color='#383838',progress_color=BLUE,corner_radius=6,border_width=0),
        'CTkLabel':dict(text_color=TEXT),
        'CTkCheckBox':dict(fg_color=ACCENT,hover_color=CARD,border_color=BORDER,text_color=TEXT,checkmark_color=INPUT),
        'CTkComboBox':dict(fg_color=INPUT,border_color=BORDER,button_color=CARD,button_hover_color=BORDER,text_color=TEXT),
        'CTkFont':dict(family='Segoe UI',size=13,weight='normal'),
    }
    for name,values in updates.items():
        if name in theme:
            theme[name].update(values)

class GlassCard(ctk.CTkFrame):
    """A consistent, bordered glass surface; all content remains native widgets."""
    def __init__(self,parent,tint=None,**kwargs):
        kwargs.setdefault('fg_color',tint or PANEL)
        kwargs.setdefault('corner_radius',20)
        kwargs.setdefault('border_width',1)
        kwargs.setdefault('border_color',BORDER)
        super().__init__(parent,**kwargs)
        # The shared compositor draws the silver edge, including rounded corners.

def blend(a,b,amount):
    av=[int(a[i:i+2],16) for i in (1,3,5)]
    bv=[int(b[i:i+2],16) for i in (1,3,5)]
    return '#'+''.join(f'{round(x+(y-x)*amount):02x}' for x,y in zip(av,bv))

class DayOverview(tk.Canvas):
    """Resizable ambient hero with an actual, labelled daily-goal progress ring."""
    def __init__(self,parent,progress,subtitle,**kwargs):
        super().__init__(parent,height=166,background=BG,highlightthickness=0,**kwargs)
        self.progress=max(0,min(1,progress))
        self.subtitle=subtitle
        self.bind('<Configure>',self.draw)

    def draw(self,event=None):
        self.delete('all')
        w,h=self.winfo_width(),self.winfo_height()
        wallpaper=getattr(self.winfo_toplevel(),'wallpaper',None)
        if wallpaper:
            self.photograph=wallpaper.canvas_image(self,opacity=.42)
            self.create_image(0,0,image=self.photograph,anchor='nw')
        else:
            self.create_rectangle(0,0,w,h,fill=PANEL,outline='')
        self.create_line(18,1,w-18,1,fill=HIGHLIGHT)
        self.create_text(24,27,text='YOUR SPACE. YOUR PACE.',anchor='w',fill=ACCENT,font=('Segoe UI',-11,'bold'))
        self.create_text(24,65,text='Your life. In focus.',anchor='w',fill=TEXT,font=('Segoe UI',-38,'bold'))
        self.create_text(24,105,text=self.subtitle,anchor='w',fill=MUTED,font=('Segoe UI',-14))
        self.create_text(24,135,text='Local & private  ·  A little progress, every day.',anchor='w',fill='#c8c8c8',font=('Segoe UI',-12))
        radius=49
        cx,cy=w-93,h/2
        self.create_oval(cx-radius,cy-radius,cx+radius,cy+radius,outline='#474747',width=7)
        if self.progress:
            self.create_arc(cx-radius,cy-radius,cx+radius,cy+radius,start=90,extent=-360*self.progress,
                            style='arc',outline='#bfbfbf',width=7)
        self.create_text(cx,cy-4,text=f'{self.progress:.0%}',fill=TEXT,font=('Segoe UI',-30,'bold'))
        self.create_text(cx,cy+22,text='DAILY GOALS',fill=MUTED,font=('Segoe UI',-10))

class ActivityStrip(tk.Canvas):
    def __init__(self,parent,values,**kwargs):
        super().__init__(parent,height=64,background=PANEL,highlightthickness=0,**kwargs)
        self.values=values
        self.bind('<Configure>',self.draw)

    def draw(self,event=None):
        self.delete('all')
        w=self.winfo_width()
        maximum=max(1,max((value for name,value in self.values),default=1))
        gap=w/max(1,len(self.values))
        for i,(name,value) in enumerate(self.values):
            x=gap*i+gap*.25
            bar_w=gap*.5
            self.create_rectangle(x,5,x+bar_w,43,fill='#2c2c2c',outline='')
            if value:
                height=32*value/maximum
                self.create_rectangle(x,43-height,x+bar_w,43,fill=BLUE,outline='')
            self.create_text(x+bar_w/2,55,text=name,fill=MUTED,font=('Segoe UI',-11))

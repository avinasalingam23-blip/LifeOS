"""Reusable, genuinely image-composited glass surfaces for native Tk.

The photo is sampled across the entire card, including its center. Text and
controls are drawn on that surface, avoiding opaque label/Frame backplates.
"""
import tkinter as tk
from PIL import Image,ImageDraw,ImageFilter,ImageTk
from .theme import TEXT,MUTED
from . import appearance

GLASS_OPACITY=.33
GLASS_BLUR=5
GLASS_TINT='#242424'

def composite_glass(background,box,opacity=GLASS_OPACITY,radius=9,blur=GLASS_BLUR):
    """Composite a complete frosted card; retain 67% of the sampled photograph."""
    if not .25<=opacity<=.40:
        raise ValueError('Glass opacity must be between 25% and 40%.')
    x,y,right,bottom=[round(value) for value in box]
    if right<=x or bottom<=y:
        return background
    if appearance.current()==appearance.COMMAND:
        result=background.copy()
        ImageDraw.Draw(result).rounded_rectangle((x,y,right-1,bottom-1),radius=2,
            fill=appearance.palette()['panel'],outline=appearance.palette()['border'])
        return result
    crop=background.crop((x,y,right,bottom))
    frost=crop.filter(ImageFilter.GaussianBlur(blur))
    frost=Image.blend(frost,Image.new('RGB',crop.size,GLASS_TINT),opacity)
    # Broad, barely visible top highlight; no solid fill conceals the center.
    highlight=Image.new('L',frost.size)
    hd=ImageDraw.Draw(highlight)
    for row in range(frost.height):
        hd.line((0,row,frost.width,row),fill=round(8*(1-row/max(1,frost.height))))
    frost=Image.composite(Image.new('RGB',frost.size,'#ffffff'),frost,highlight)
    mask=Image.new('L',frost.size)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,frost.width-1,frost.height-1),radius=radius,fill=255)
    shadow=Image.new('L',background.size)
    ImageDraw.Draw(shadow).rounded_rectangle((x+2,y+4,right+2,bottom+4),radius=radius,fill=42)
    shadow=shadow.filter(ImageFilter.GaussianBlur(6))
    result=Image.composite(Image.new('RGB',background.size,'#000000'),background,shadow)
    result.paste(frost,(x,y),mask)
    ImageDraw.Draw(result).rounded_rectangle((x,y,right-1,bottom-1),radius=radius,outline='#858585',width=1)
    return result

class GlassSurface(appearance.CanvasColors,tk.Canvas):
    """Accessible, resizable canvas controls over a shared composited photograph."""
    def __init__(self,parent,app,**kwargs):
        super().__init__(parent,background='#0b0b0b',highlightthickness=0,takefocus=True,**kwargs)
        self.app=app
        self.actions={}
        self.hovered=None
        self.keyboard_action=None
        self._backing_key=None
        self.backing=None
        self.s=1
        self.ox=0
        self.oy=0
        self.bind('<Configure>',lambda e:self.draw())
        self.bind('<Motion>',self.motion)
        self.bind('<Leave>',lambda e:self.leave())
        self.bind('<Button-1>',self.activate)
        self.bind('<Tab>',self.tab)
        self.bind('<Shift-Tab>',lambda e:self.tab(e,-1))
        self.bind('<Return>',self.key_activate)
        self.bind('<space>',self.key_activate)

    def rect(self,box):
        x,y,w,h=box
        return (self.ox+x*self.s,self.oy+y*self.s,self.ox+(x+w)*self.s,self.oy+(y+h)*self.s)

    def text(self,x,y,text,size=13,color=TEXT,bold=False,anchor='w',width=None,family='Segoe UI',**kwargs):
        if width:
            kwargs['width']=round(width*self.s)
        self.create_text(self.ox+x*self.s+.6,self.oy+y*self.s+.8,text=text,anchor=anchor,
            fill='#080808',font=(family,-max(9,round(size*self.s)),'bold' if bold else 'normal'),**kwargs)
        return self.create_text(self.ox+x*self.s,self.oy+y*self.s,text=text,anchor=anchor,
            fill=color,font=(family,-max(9,round(size*self.s)),'bold' if bold else 'normal'),**kwargs)

    def action(self,key,box,callback):
        self.actions[key]={'box':self.rect(box),'callback':callback}

    def button(self,key,box,text,callback):
        self.action(key,box,callback)
        color='#e3e3e3' if key in (self.hovered,self.keyboard_action) else '#a5a5a5'
        x,y,right,bottom=self.rect(box)
        # A border and a restrained highlight leave the underlying photo visible.
        r=min(5*self.s,(bottom-y)/2)
        self.create_polygon(x+r,y,right-r,y,right,y,right,y+r,right,bottom-r,right,bottom,right-r,bottom,
            x+r,bottom,x,bottom,x,bottom-r,x,y+r,x,y,fill='',outline=color,width=1,smooth=True,splinesteps=16)
        self.text(box[0]+box[2]/2,box[1]+box[3]/2,text,12,anchor='center')

    def progress(self,x,y,width,ratio):
        x1,y1,x2,y2=self.rect((x,y,width,3))
        self.create_line(x1,y1,x2,y1,fill='#777777',width=max(2,round(3*self.s)),capstyle='round')
        if ratio>0:
            self.create_line(x1,y1,x1+(x2-x1)*min(1,ratio),y1,fill='#dedede',width=max(2,round(3*self.s)),capstyle='round')

    def hit(self,x,y):
        for key,action in reversed(list(self.actions.items())):
            left,top,right,bottom=action['box']
            if left<=x<=right and top<=y<=bottom:
                return key
        return None

    def motion(self,event):
        key=self.hit(event.x,event.y)
        self.configure(cursor='hand2' if key else '')
        if key!=self.hovered:
            self.hovered=key
            self.draw()

    def leave(self):
        self.hovered=None
        self.draw()

    def activate(self,event):
        key=self.hit(event.x,event.y)
        if key:
            self.focus_set()
            self.actions[key]['callback']()

    def tab(self,event,direction=1):
        keys=list(self.actions)
        if not keys:
            return None
        if self.keyboard_action not in keys:
            self.keyboard_action=keys[0]
        else:
            index=keys.index(self.keyboard_action)+direction
            if not 0<=index<len(keys):
                self.keyboard_action=None
                (self.tk_focusNext() if direction>0 else self.tk_focusPrev()).focus_set()
                self.draw()
                return 'break'
            self.keyboard_action=keys[index]
        self.draw()
        return 'break'

    def key_activate(self,event):
        if self.keyboard_action in self.actions:
            self.actions[self.keyboard_action]['callback']()
        return 'break'

    def refresh_glass(self):
        if self.winfo_exists() and self.winfo_ismapped():
            self.draw()

    def draw(self):
        """Implemented by the consuming view; shared interactions remain here."""

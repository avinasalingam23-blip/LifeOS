"""Central runtime palettes and in-place widget styling; no page reconstruction."""
import tkinter as tk
import tkinter.font as tkfont
import weakref
from PIL import Image,ImageColor

CURRENT='Current Theme'
COMMAND='CMD / Robotic Command Center'
OPTIONS=(CURRENT,COMMAND)
PALETTES={CURRENT:dict(bg='#0b0b0b',panel='#1c1c1c',secondary='#282828',accent='#d8d8d8',
    amber='#a3a3a3',text='#f2f2f2',muted='#d8d8d8',border='#505050'),
    COMMAND:dict(bg='#090B0A',panel='#111713',secondary='#151D18',accent='#70F0A1',
    amber='#D6A85D',text='#E7EEE9',muted='#91A096',border='#2A3B30')}
_name=CURRENT
epoch=0

def select(name):
    global _name,epoch
    if name not in OPTIONS:raise ValueError('Choose a supported appearance theme.')
    if name!=_name:_name=name;epoch+=1

def current():return _name
def palette():return PALETTES[_name]
def color(value):
    if isinstance(value,(tuple,list)):return [color(v) for v in value]
    if _name==CURRENT or not isinstance(value,str) or not value.startswith('#') or len(value)!=7:return value
    if value.upper() in {v.upper() for v in PALETTES[COMMAND].values()}:return value
    try:r,g,b=ImageColor.getrgb(value)
    except ValueError:return value
    if r!=g or g!=b:return value
    p=palette()
    exact={'#0b0b0b':'bg','#080808':'bg','#1c1c1c':'panel','#141414':'panel','#242424':'secondary',
        '#282828':'secondary','#505050':'border','#d8d8d8':'muted','#f2f2f2':'text',
        '#dedede':'accent','#dddddd':'accent','#bbbbbb':'accent','#a3a3a3':'amber'}
    if value.lower() in exact:return p[exact[value.lower()]]
    return p['bg' if r<20 else 'panel' if r<36 else 'secondary' if r<74 else 'border' if r<128 else 'muted' if r<200 else 'text']

def font(value,terminal=False):
    if _name==CURRENT:return value
    if isinstance(value,tkfont.Font):
        value=(value.cget('family'),value.cget('size'),value.cget('weight'))
    if not isinstance(value,(tuple,list)) or len(value)<2:return value
    family,size,*style=value
    if terminal or family!='Segoe UI' or abs(size)<=13 or 'bold' in style:
        return ('Consolas',size,*style)
    return value

def icon_image(source):
    if _name==CURRENT:return source
    result=Image.new('RGBA',source.size,palette()['accent'])
    result.putalpha(source.getchannel('A'))
    return result

class CanvasColors:
    def _create(self,itemType,args,kw):
        for key in ('fill','outline','activefill','activeoutline','disabledfill'):
            if key in kw:kw[key]=color(kw[key])
        if 'font' in kw and not isinstance(kw['font'],tkfont.Font):
            kw['font']=font(kw['font'],terminal=True)
        return super()._create(itemType,args,kw)

def menu(parent,**kwargs):
    if current()==COMMAND:kwargs.setdefault('font',('Consolas',11))
    return tk.Menu(parent,**{k:color(v) for k,v in kwargs.items()})

class Appearance:
    def __init__(self,app):
        self.app=app
        self.original=weakref.WeakKeyDictionary()
        self.styled=weakref.WeakKeyDictionary()
        self.figures=weakref.WeakKeyDictionary()
        self.text_tags=weakref.WeakKeyDictionary()

    def widget(self,widget):
        if self.styled.get(widget)==epoch:return
        import customtkinter as ctk
        if isinstance(widget,tk.Canvas) and hasattr(widget,'values'):
            self.styled[widget]=epoch
            if hasattr(widget,'measure'):widget.measure()
            return  # Photo controls resolve their original colors at draw time.
        original=self.original.get(widget)
        if original is None:
            original={}
            candidates=('fg_color','bg_color','text_color','text_color_disabled','placeholder_text_color',
                'border_color','hover_color','button_color','button_hover_color','checkmark_color',
                'progress_color','scrollbar_button_color','scrollbar_button_hover_color',
                'selected_color','selected_hover_color','unselected_color','unselected_hover_color','corner_radius')
            if isinstance(widget,(ctk.CTkBaseClass,ctk.CTk,ctk.CTkToplevel)):
                for key in candidates:
                    try:original[key]=widget.cget(key)
                    except (ValueError,tk.TclError,AttributeError):pass
                try:
                    f=widget.cget('font')
                    original['font']=(f.cget('family'),f.cget('size'),f.cget('weight')) if isinstance(f,ctk.CTkFont) else f
                except (ValueError,tk.TclError,AttributeError):pass
            elif isinstance(widget,(tk.Text,tk.Entry,tk.Menu)):
                for key in ('background','foreground','insertbackground','selectbackground','activebackground','activeforeground'):
                    try:original[key]=widget.cget(key)
                    except tk.TclError:pass
                if isinstance(widget,tk.Menu):
                    f=widget.cget('font')
                    original['font']=(f.cget('family'),f.cget('size'),f.cget('weight')) if isinstance(f,ctk.CTkFont) else f
            self.original[widget]=original
        self.styled[widget]=epoch
        updates={key:font(value) if key=='font' else 2 if key=='corner_radius' and current()==COMMAND else color(value) for key,value in original.items()}
        for key,value in updates.items():
            try:
                if widget.cget(key)!=value:widget.configure(**{key:value})
            except (ValueError,tk.TclError,AttributeError):pass
        if isinstance(widget,tk.Text):
            tags=self.text_tags.setdefault(widget,{})
            for tag in widget.tag_names():
                if tag not in tags:tags[tag]=widget.tag_cget(tag,'foreground')
                if tags[tag]:widget.tag_configure(tag,foreground=color(tags[tag]))

    def figure(self,figure):
        """Remember original artist colors and recolor an existing plot in place."""
        if not figure:return
        from matplotlib.colors import to_hex
        originals=self.figures.setdefault(figure,weakref.WeakKeyDictionary())
        for artist in figure.findobj():
            if hasattr(artist,'get_fontfamily'):
                saved=originals.setdefault(artist,{})
                saved.setdefault('fontfamily',artist.get_fontfamily())
                artist.set_fontfamily('Consolas' if current()==COMMAND else saved['fontfamily'])
            for prop in ('color','facecolor','edgecolor'):
                getter=getattr(artist,'get_'+prop,None);setter=getattr(artist,'set_'+prop,None)
                if not getter or not setter:continue
                key=prop
                saved=originals.setdefault(artist,{})
                if key not in saved:
                    try:saved[key]=getter()
                    except (TypeError,ValueError):continue
                value=saved[key]
                try:
                    canonical=to_hex(value,keep_alpha=True)
                    resolved=color(canonical[:7])+canonical[7:]
                    setter(value if current()==CURRENT else resolved)
                except (ValueError,TypeError,IndexError):pass

    def apply(self):
        def walk(widget):
            self.widget(widget)
            figure=getattr(widget,'figure',None) or getattr(widget,'fig',None)
            if figure:
                self.figure(figure)
                canvas=getattr(widget,'canvas',None)
                if canvas and hasattr(canvas,'draw_idle'):canvas.draw_idle()
            for child in widget.winfo_children():walk(child)
        walk(self.app)
        def repaint(window):
            if hasattr(window,'wallpaper'):
                window.wallpaper.last_size=None
                window.wallpaper.render()
                window.wallpaper.request()
            for child in window.winfo_children():
                if isinstance(child,tk.Toplevel):repaint(child)
        repaint(self.app)

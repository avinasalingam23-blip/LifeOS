"""Local photographic wallpaper and precomposed glass for native Tk containers.

Tk has no per-widget alpha. Matching crops of the same wallpaper, darkened and
blended with graphite, provide a consistent glass approximation. Native input
widgets, text, scrollbars and all application actions remain unchanged.
"""
from functools import lru_cache
from pathlib import Path
import logging
import re
import tkinter as tk
import weakref
from . import appearance
from PIL import Image,ImageDraw,ImageFilter,ImageOps,ImageTk
import customtkinter as ctk

DIRECTORY=Path(__file__).resolve().parents[1]/'assets'/'backgrounds'
PAGE_PHOTOS={'Dashboard':'dashboard','DSA Tracker':'dsa','Learning Paths':'learning',
    'Workout Planner':'workout','Diet & Nutrition':'nutrition','Daily Planner':'planner',
    'Analytics':'analytics','Settings':'settings'}

@lru_cache(maxsize=9)
def load_photo(name):
    if name not in {*PAGE_PHOTOS.values(),'research'}:
        raise ValueError('Unknown photographic background.')
    with Image.open(DIRECTORY/(name+'.webp')) as source:
        # Enforce achromatic output even if a future asset is accidentally colored.
        return source.convert('L').convert('RGB')

def learning_photo(subject):
    words=subject.casefold().replace('_',' ').replace('-',' ')
    return 'research' if re.search(r'\b(nlp|ml|machine learning|natural language processing|deep learning)\b',words) else 'learning'

def contrast_ratio(foreground,background):
    def luminance(color):
        rgb=[int(color[i:i+2],16)/255 for i in (1,3,5)]
        linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
        return sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))
    a,b=sorted((luminance(foreground),luminance(background)))
    return (b+.05)/(a+.05)

class PhotographicBackground:
    def __init__(self,root):
        self.root=root
        self.name='dashboard'
        self.job=None
        self.closed=False
        self.last_error=None
        self.render_count=0
        self.painted_name=None
        self.images=weakref.WeakKeyDictionary()
        self.surfaces=weakref.WeakSet()
        self.last_size=None
        self.wallpaper=None
        self.soft_wallpaper=None
        self.canvas=tk.Canvas(root,highlightthickness=0,borderwidth=0,background='#0b0b0b')
        self.canvas.place(x=0,y=0,relwidth=1,relheight=1)
        # Lower the widget, rather than Canvas.lower() which operates on items.
        self.canvas.tk.call('lower',self.canvas._w)
        root.bind('<Configure>',self.request,add='+')
        root.bind('<Map>',self.request,add='+')
        self.scroll_job=None
        self.scroll_frames=weakref.WeakSet()

    def set_page(self,page,subject=''):
        name=learning_photo(subject) if page=='Learning Paths' else PAGE_PHOTOS[page]
        if name!=self.name:
            self.name=name
            self.last_size=None
        # Update the outer wallpaper synchronously, even while new page widgets
        # are still settling their geometry. This avoids a previous-page flash.
        self.prepare()
        self.paint_root()
        self.request()

    def request(self,event=None):
        if self.closed:
            return
        if event is not None and event.type.name=='Configure' and event.widget is not self.root:
            return
        if self.job:
            self.root.after_cancel(self.job)
        # Coalesce the pending layout events, but paint before the next idle
        # display cycle rather than leaving native fallback fills visible for 100ms.
        self.job=self.root.after_idle(self.render)

    def key(self,widget):
        return (widget.winfo_width(),widget.winfo_height(),widget.winfo_rootx()-self.root.winfo_rootx(),
            widget.winfo_rooty()-self.root.winfo_rooty(),self.name,self.last_size,appearance.epoch)

    def request_scroll(self,frame):
        self.scroll_frames.add(frame)
        if self.scroll_job:self.root.after_cancel(self.scroll_job)
        self.scroll_job=self.root.after(80,self.paint_scrolled)

    def paint_scrolled(self):
        self.scroll_job=None
        for frame in list(self.scroll_frames):
            if frame.winfo_exists() and frame.winfo_ismapped():self.walk(frame)
        self.scroll_frames.clear()

    def prepare(self):
        dimensions=(max(1,self.root.winfo_width()),max(1,self.root.winfo_height()))
        size=(*dimensions,appearance.epoch)
        if self.last_size==size and self.wallpaper is not None:return
        if appearance.current()==appearance.COMMAND:
            self.wallpaper=Image.new('RGB',dimensions,appearance.palette()['bg'])
            self.soft_wallpaper=self.wallpaper
        else:
            photo=ImageOps.fit(load_photo(self.name),dimensions,method=Image.Resampling.LANCZOS)
            curve=[round(255*(value/255)**1.35) for value in range(256)]
            photo=photo.point(curve*3)
            vignette=Image.radial_gradient('L').resize(dimensions,Image.Resampling.BILINEAR).point([round(value*.20) for value in range(256)])
            photo=Image.composite(Image.new('RGB',dimensions,'#080808'),photo,vignette)
            self.wallpaper=Image.blend(photo,Image.new('RGB',dimensions,'#080808'),.50)
            self.soft_wallpaper=self.wallpaper.filter(ImageFilter.GaussianBlur(10))
        self.last_size=size

    def crop(self,widget,opacity=0,color='#1c1c1c',blur=False):
        self.prepare()
        width,height=max(1,widget.winfo_width()),max(1,widget.winfo_height())
        x=widget.winfo_rootx()-self.root.winfo_rootx()
        y=widget.winfo_rooty()-self.root.winfo_rooty()
        image=(self.soft_wallpaper if blur else self.wallpaper).crop((x,y,x+width,y+height))
        if opacity:
            image=Image.blend(image,Image.new('RGB',image.size,appearance.color(color)),opacity)
        return image

    def canvas_image(self,canvas,opacity=.35):
        return ImageTk.PhotoImage(self.crop(canvas,opacity=opacity),master=self.root)

    def sample(self,widget):
        """Exact parent pixels, including frost and rounded edges, without seams."""
        ancestor=widget.master
        while ancestor is not None and ancestor is not self.root:
            surface=getattr(ancestor,'glass_image',None)
            if surface is not None:
                x=widget.winfo_rootx()-ancestor.winfo_rootx()
                y=widget.winfo_rooty()-ancestor.winfo_rooty()
                width,height=max(1,widget.winfo_width()),max(1,widget.winfo_height())
                box=(x,y,x+width,y+height)
                if 0<=x and 0<=y and box[2]<=surface.width and box[3]<=surface.height:
                    return surface.crop(box)
                # During geometry changes a child may briefly exceed the cached
                # parent. Pillow pads out-of-bounds crops with black; use the
                # photograph for the uncovered region instead of introducing lines.
                result=self.crop(widget)
                left,top=max(0,x),max(0,y)
                right,bottom=min(surface.width,x+width),min(surface.height,y+height)
                if right>left and bottom>top:
                    result.paste(surface.crop((left,top,right,bottom)),(left-x,top-y))
                return result
            ancestor=getattr(ancestor,'master',None)
        return self.crop(widget)

    def render(self):
        if self.job:
            self.root.after_cancel(self.job)
        self.job=None
        if self.closed or not self.root.winfo_exists():
            return
        try:
            self.prepare()
            self.paint_root()
            self.walk(self.root)
            self.last_error=None
            self.render_count+=1
        except (tk.TclError,RuntimeError):
            if not self.closed:
                self.last_error='Wallpaper could not be rendered.'
                logging.exception(self.last_error)
        except Exception as error:
            self.last_error=str(error)
            logging.exception('Photographic background failed; native controls remain available')

    def walk(self,parent):
        for widget in parent.winfo_children():
            # Independent dialogs keep the same readable monochrome theme.
            if isinstance(widget,tk.Toplevel):
                continue
            if not widget.winfo_ismapped():continue
            controller=getattr(self.root,'appearance',getattr(getattr(self.root,'app',None),'appearance',None))
            if controller:controller.widget(widget)
            if isinstance(widget,ctk.CTkFrame) and widget.winfo_ismapped():
                self.paint_frame(widget)
            if isinstance(widget,ctk.CTkScrollableFrame) and widget.winfo_ismapped():
                self.paint_scroll_frame(widget)
            if type(widget) is tk.Canvas and widget is not self.canvas and not hasattr(widget,'refresh_glass') and not getattr(widget,'lifeos_backdrop',False) and widget.winfo_ismapped():
                self.paint_canvas(widget)
            if isinstance(widget,tk.Canvas) and hasattr(widget,'refresh_glass'):
                self.surfaces.add(widget)
                widget.refresh_glass()
            if isinstance(widget,(ctk.CTkEntry,ctk.CTkOptionMenu,ctk.CTkTextbox,ctk.CTkButton,ctk.CTkScrollbar)) and widget.winfo_ismapped():
                self.paint_control_corners(widget)
            self.walk(widget)

    def paint_root(self):
        key=(id(self.wallpaper),appearance.epoch)
        if getattr(self,'root_key',None)==key:return
        self.root_key=key
        self.root_image=ImageTk.PhotoImage(self.wallpaper,master=self.root)
        self.canvas.delete('wallpaper')
        self.canvas.create_image(0,0,image=self.root_image,anchor='nw',tags='wallpaper')
        self.painted_name=self.name

    def paint_frame(self,frame):
        key=(*self.key(frame),str(frame.cget('fg_color')),frame.cget('border_width'))
        if getattr(frame,'lifeos_paint_key',None)==key:return
        # CTkFrame exposes its drawable as a child Canvas. Work only on container
        # canvases; input controls and ttk tables retain their native behavior.
        # CTkFrame.winfo_children intentionally hides its own drawable. Ask Tk
        # for the native children so no private CTk attributes are required.
        canvas=next((w for w in tk.Misc.winfo_children(frame) if type(w).__name__=='CTkCanvas'),None)
        if canvas is None or canvas.winfo_width()<2 or canvas.winfo_height()<2:
            return
        foreground=frame.cget('fg_color')
        if isinstance(foreground,(list,tuple)):
            foreground=foreground[-1]
        transparent=foreground=='transparent'
        glass=type(frame).__name__=='GlassCard'
        image=self.sample(frame) if transparent else self.crop(frame,opacity=.33,color='#242424',blur=True)
        if not transparent:
            base=self.sample(frame)
            mask=Image.new('L',image.size)
            scale=getattr(frame,'_get_widget_scaling',lambda:1)()
            radius=max(0,int(frame.cget('corner_radius')*scale))
            ImageDraw.Draw(mask).rounded_rectangle((0,0,image.width-1,image.height-1),radius=radius,fill=255)
            base.paste(image,(0,0),mask)
            image=base
            if glass or frame.cget('border_width'):
                ImageDraw.Draw(image).rounded_rectangle((1,1,image.width-2,image.height-2),radius=radius,outline=appearance.color('#515151'),width=1)
        frame.glass_image=image
        frame.lifeos_paint_key=key
        photo=ImageTk.PhotoImage(image,master=self.root)
        self.images[canvas]=photo
        canvas.delete('lifeos-wallpaper')
        canvas.create_image(0,0,image=photo,anchor='nw',tags='lifeos-wallpaper')

    def paint_control_corners(self,widget):
        key=self.key(widget)
        if getattr(widget,'lifeos_corner_key',None)==key:return
        widget.lifeos_corner_key=key
        """Replace only native fake-transparent corners; keep native editing."""
        canvas=next((w for w in tk.Misc.winfo_children(widget) if type(w).__name__=='CTkCanvas'),None)
        if canvas is None or canvas.winfo_width()<3 or canvas.winfo_height()<3:
            return
        background=self.sample(widget).crop((0,0,canvas.winfo_width(),canvas.winfo_height())).convert('RGBA')
        scale=getattr(widget,'_get_widget_scaling',lambda:1)()
        try:
            radius=max(0,round(widget.cget('corner_radius')*scale))
        except (ValueError,tk.TclError):
            radius=0
        mask=Image.new('L',background.size,255)
        ImageDraw.Draw(mask).rounded_rectangle((0,0,background.width-1,background.height-1),radius=radius,fill=0)
        background.putalpha(mask)
        photo=ImageTk.PhotoImage(background,master=self.root)
        self.images[canvas]=photo
        canvas.delete('lifeos-corners')
        canvas.create_image(0,0,image=photo,anchor='nw',tags='lifeos-corners')

    def paint_scroll_frame(self,frame):
        key=self.key(frame)
        existing=getattr(frame,'lifeos_background',None)
        if getattr(frame,'lifeos_scroll_key',None)==key and existing and existing.winfo_exists():return
        frame.lifeos_scroll_key=key
        # CTkScrollableFrame is a native Frame inside a scrollable Canvas. Its
        # public children can carry a lowered photo; no private CTk hooks needed.
        canvas=getattr(frame,'lifeos_background',None)
        # Search/filter lists can clear every child while keeping the scroll
        # frame itself. Recreate its backdrop if that refresh destroyed it.
        if canvas is None or not canvas.winfo_exists():
            canvas=tk.Canvas(frame,borderwidth=0,highlightthickness=0)
            canvas.lifeos_backdrop=True
            canvas.place(x=0,y=0,relwidth=1,relheight=1)
            canvas.tk.call('lower',canvas._w)
            frame.lifeos_background=canvas
        frame.glass_image=self.sample(frame)
        photo=ImageTk.PhotoImage(frame.glass_image,master=self.root)
        self.images[canvas]=photo
        canvas.delete('lifeos-scroll')
        canvas.create_image(0,0,image=photo,anchor='nw',tags='lifeos-scroll')

    def paint_canvas(self,canvas):
        key=self.key(canvas)
        if getattr(canvas,'lifeos_canvas_key',None)==key:return
        canvas.lifeos_canvas_key=key
        image=self.sample(canvas)
        photo=ImageTk.PhotoImage(image,master=self.root)
        self.images[canvas]=photo
        canvas.delete('lifeos-native')
        item=canvas.create_image(canvas.canvasx(0),canvas.canvasy(0),image=photo,anchor='nw',tags='lifeos-native')
        canvas.tag_lower(item)

    def close(self):
        if self.scroll_job:
            self.root.after_cancel(self.scroll_job)
            self.scroll_job=None
        self.closed=True
        if self.job:
            self.root.after_cancel(self.job)
            self.job=None
        self.images.clear()

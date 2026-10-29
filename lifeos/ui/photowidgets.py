"""Photo-aware labels and sidebar controls; no opaque text backplates."""
import tkinter as tk
import tkinter.font as tkfont
from PIL import Image,ImageDraw,ImageTk
from . import appearance

class PhotoWidget(appearance.CanvasColors,tk.Canvas):
    def __init__(self,parent,**kwargs):
        super().__init__(parent,highlightthickness=0,borderwidth=0,background='#171717',**kwargs)
        self.owner=self.winfo_toplevel()
        self.scale=getattr(self.owner,'_get_window_scaling',lambda:1)()
        self.bind('<Configure>',lambda e=None:self.draw())

    def padding(self,kwargs):
        for key in ('padx','pady','ipadx','ipady'):
            if key in kwargs:
                value=kwargs[key]
                kwargs[key]=tuple(round(n*self.scale) for n in value) if isinstance(value,tuple) else round(value*self.scale)
        return kwargs

    def pack(self,**kwargs):
        super().pack(**self.padding(kwargs))

    def grid(self,**kwargs):
        super().grid(**self.padding(kwargs))

    def backdrop(self):
        width,height=max(1,self.winfo_width()),max(1,self.winfo_height())
        wp=getattr(self.owner,'wallpaper',None)
        if not wp:
            return Image.new('RGB',(width,height),'#1c1c1c')
        return wp.sample(self)

    def paint_background(self,image=None):
        self.photo=ImageTk.PhotoImage(image if image is not None else self.backdrop(),master=self.owner)
        self.create_image(0,0,image=self.photo,anchor='nw')

    def refresh_glass(self):
        wp=getattr(self.owner,'wallpaper',None)
        key=wp.key(self) if wp else None
        if getattr(self,'_refresh_key',False)==key:return
        self._refresh_key=key
        self.draw()

class PhotoLabel(PhotoWidget):
    def __init__(self,parent,text='',font=('Segoe UI',13),text_color='#f2f2f2',image=None,
                 anchor='center',justify='center',wraplength=0,padx=0,pady=0,**kwargs):
        self.values=dict(text=text,font=font,text_color=text_color,image=image,anchor=anchor,
                         justify=justify,wraplength=wraplength,padx=padx,pady=pady)
        super().__init__(parent)
        self.measure()

    def cget(self,key):
        return self.values[key] if key in self.values else super().cget(key)

    def configure(self,cnf=None,**kwargs):
        if not hasattr(self,'values'):
            return super().configure(cnf,**kwargs)
        changed=False
        for key in list(kwargs):
            if key in self.values:
                self.values[key]=kwargs.pop(key)
                changed=True
        if kwargs or cnf:
            super().configure(cnf,**kwargs)
        if changed:
            self.measure()
            self.draw()

    config=configure

    def display_text(self):
        text=self.values['text']
        if appearance.current()==appearance.COMMAND:
            if text=='LifeOS':return 'LIFEOS'
            if text.startswith('ON YOUR DEVICE'):return 'LOCAL DATA: READY\nMODE: OFFLINE'
            if self.values['font'][1]>=18:return '[ '+text+' ]'
        return text

    def measure(self):
        family,size,*rest=self.values['font']
        self._font_epoch=appearance.epoch
        selected=appearance.font((family,-max(1,round(size*self.scale)),*rest),terminal=size>=18 or size<=13)
        self.font=tkfont.Font(self,font=selected)
        item=self.create_text(0,0,text=self.display_text(),font=self.font,anchor='nw',
            width=round(self.values['wraplength']*self.scale) if self.values['wraplength'] else 0)
        box=self.bbox(item) or (0,0,0,self.font.metrics('linespace'))
        self.delete(item)
        image=self.values['image']
        iw,ih=image.cget('size') if image else (0,0)
        self.image_size=(round(iw*self.scale),round(ih*self.scale))
        self.text_size=(max(0,box[2]-box[0]),max(0,box[3]-box[1]))
        width=self.text_size[0]+self.image_size[0]+(8*self.scale if image and self.values['text'] else 0)+2*self.values['padx']*self.scale
        if self.values['wraplength']:
            width=min(width,280*self.scale)
        height=max(self.text_size[1],self.image_size[1])+2*self.values['pady']*self.scale
        super().configure(width=max(1,round(width)),height=max(1,round(height)))

    def draw(self):
        if not hasattr(self,'text_size') or not self.winfo_exists() or self.winfo_width()<2:
            return
        if getattr(self,'_font_epoch',None)!=appearance.epoch:self.measure()
        self.delete('all')
        self.paint_background()
        width,height=self.winfo_width(),self.winfo_height()
        iw,ih=self.image_size
        wrap=min(round(self.values['wraplength']*self.scale),max(1,width-iw-round((2*self.values['padx']+8 if iw else 2*self.values['padx'])*self.scale))) if self.values['wraplength'] else 0
        if wrap:
            item=self.create_text(0,0,text=self.display_text(),font=self.font,anchor='nw',width=wrap)
            box=self.bbox(item) or (0,0,0,self.font.metrics('linespace'))
            self.delete(item)
            self.text_size=(box[2]-box[0],box[3]-box[1])
            desired=round(max(self.text_size[1],ih)+2*self.values['pady']*self.scale)
            if abs(self.winfo_reqheight()-desired)>1:
                super().configure(height=desired)
        total=self.text_size[0]+iw+(8*self.scale if iw and self.values['text'] else 0)
        anchor=self.values['anchor']
        left=self.values['padx']*self.scale if 'w' in anchor else width-total-self.values['padx']*self.scale if 'e' in anchor else (width-total)/2
        if self.values['image']:
            source=self.values['image'].cget('dark_image') or self.values['image'].cget('light_image')
            self.mark=ImageTk.PhotoImage(appearance.icon_image(source).resize((max(1,iw),max(1,ih)),Image.Resampling.LANCZOS),master=self.owner)
            self.create_image(left,height/2,image=self.mark,anchor='w')
            left+=iw+(8*self.scale if self.values['text'] else 0)
        options=dict(text=self.display_text(),font=self.font,anchor='w',justify=self.values['justify'],
            width=wrap)
        self.create_text(left+.6,height/2+.8,fill='#080808',**options)
        self.create_text(left,height/2,fill=self.values['text_color'],**options)

class PhotoNavButton(PhotoWidget):
    def __init__(self,parent,text,command,image,width=166,height=31,**kwargs):
        self.values=dict(text=text,image=image,fg_color='transparent',text_color='#d8d8d8',border_width=0,border_color='#777777')
        self.command=command
        self.hover=False
        super().__init__(parent,takefocus=True,cursor='hand2')
        super().configure(width=round(width*self.scale),height=round(height*self.scale))
        self.bind('<Button-1>',lambda e:self.command())
        self.bind('<Return>',lambda e:self.command())
        self.bind('<space>',lambda e:self.command())
        self.bind('<Enter>',lambda e:self.set_hover(True))
        self.bind('<Leave>',lambda e:self.set_hover(False))
        self.bind('<FocusIn>',lambda e:self.set_hover(True))
        self.bind('<FocusOut>',lambda e:self.set_hover(False))

    def set_hover(self,value):
        self.hover=value
        self.draw()

    def cget(self,key):
        return self.values[key] if key in self.values else super().cget(key)

    def configure(self,cnf=None,**kwargs):
        if not hasattr(self,'values'):
            return super().configure(cnf,**kwargs)
        for key in list(kwargs):
            if key in self.values:
                self.values[key]=kwargs.pop(key)
        if kwargs or cnf:
            super().configure(cnf,**kwargs)
        self.draw()

    config=configure

    def draw(self):
        if not self.winfo_exists() or self.winfo_width()<3 or self.winfo_height()<3:
            return
        self.delete('all')
        image=self.backdrop()
        selected=self.values['fg_color']!='transparent'
        if appearance.current()==appearance.COMMAND:
            palette=appearance.palette()
            ImageDraw.Draw(image).rectangle((1,1,image.width-2,image.height-2),
                fill=palette['secondary'] if selected or self.hover else palette['bg'],
                outline=palette['accent'] if selected else palette['border'] if self.hover else palette['bg'])
            self.paint_background(image)
            color=palette['accent'] if selected else palette['text']
            self.create_text(9*self.scale,self.winfo_height()/2,text='[>]' if selected else '[ ]',
                anchor='w',fill=color,font=('Consolas',-round(12*self.scale)))
            self.create_text(36*self.scale,self.winfo_height()/2,text=self.values['text'],
                anchor='w',fill=color,font=('Consolas',-round(12*self.scale)))
            return
        if selected or self.hover:
            overlay=Image.blend(image,Image.new('RGB',image.size,appearance.color('#bdbdbd')),.20 if selected else .10)
            mask=Image.new('L',image.size)
            ImageDraw.Draw(mask).rounded_rectangle((0,0,image.width-1,image.height-1),radius=round(6*self.scale),fill=255)
            image.paste(overlay,(0,0),mask)
            if selected:
                ImageDraw.Draw(image).rounded_rectangle((0,0,image.width-1,image.height-1),radius=round(6*self.scale),outline=appearance.color('#858585'),width=1)
        self.paint_background(image)
        if selected:
            self.create_line(1,self.winfo_height()*.22,1,self.winfo_height()*.78,fill='#eeeeee',width=max(2,round(2*self.scale)),capstyle='round')
        mark=self.values['image']
        source=mark.cget('dark_image') or mark.cget('light_image')
        size=round(16*self.scale)
        self.mark=ImageTk.PhotoImage(appearance.icon_image(source).resize((size,size),Image.Resampling.LANCZOS),master=self.owner)
        self.create_image(11*self.scale,self.winfo_height()/2,image=self.mark,anchor='w')
        self.create_text(36*self.scale,self.winfo_height()/2,text=self.values['text'],anchor='w',fill=self.values['text_color'],font=('Segoe UI',-round(13*self.scale)))

class PhotoButton(PhotoWidget):
    """A keyboard-operable action with real photo-visible rounded corners."""
    def __init__(self,parent,text,command,image=None,width=120,height=34,secondary=False,**kwargs):
        self.values=dict(text=text,image=image,state='normal',width=width,height=height,
                         text_color='#f2f2f2',fg_color='transparent',border_width=1)
        self.command=command
        self.secondary=secondary
        self.hover=False
        super().__init__(parent,takefocus=True,cursor='hand2')
        self.configure(width=width,height=height)
        self.bind('<Button-1>',lambda e:self.invoke())
        self.bind('<Return>',lambda e:self.invoke())
        self.bind('<space>',lambda e:self.invoke())
        for event,value in (('<Enter>',True),('<Leave>',False),('<FocusIn>',True),('<FocusOut>',False)):
            self.bind(event,lambda e,v=value:self.highlight(v))

    def highlight(self,value):
        self.hover=value
        self.draw()

    def invoke(self):
        if self.values['state']!='disabled':
            return self.command()

    def cget(self,key):
        return self.values[key] if key in self.values else super().cget(key)

    def configure(self,cnf=None,**kwargs):
        if not hasattr(self,'values'):
            return super().configure(cnf,**kwargs)
        for key in list(kwargs):
            if key in self.values:
                self.values[key]=kwargs.pop(key)
        kwargs.update(width=round(self.values['width']*self.scale),height=round(self.values['height']*self.scale))
        super().configure(cnf,**kwargs)
        self.draw()

    config=configure

    def draw(self):
        if not hasattr(self,'scale') or not self.winfo_exists():
            return
        self.delete('all')
        image=self.backdrop()
        disabled=self.values['state']=='disabled'
        opacity=.07 if disabled else .24 if self.hover else .12 if self.secondary else .24
        layer=Image.blend(image,Image.new('RGB',image.size,appearance.color('#cccccc')),opacity)
        mask=Image.new('L',image.size)
        rect=(1,1,max(1,image.width-2),max(1,image.height-2))
        radius=round((2 if appearance.current()==appearance.COMMAND else 8)*self.scale)
        ImageDraw.Draw(mask).rounded_rectangle(rect,radius=radius,fill=255)
        image.paste(layer,(0,0),mask)
        ImageDraw.Draw(image).rounded_rectangle(rect,radius=radius,outline=appearance.color('#555555' if disabled else '#8a8a8a' if self.hover else '#666666'),width=1)
        self.paint_background(image)
        color='#909090' if disabled else self.values['text_color']
        text=self.values['text']
        font=tkfont.Font(self,font=appearance.font(('Segoe UI',-round(12*self.scale)),terminal=True))
        mark=self.values['image']
        size=round(15*self.scale) if mark else 0
        text_width=max((font.measure(line) for line in text.splitlines()),default=0)
        left=(self.winfo_width()-text_width-size-(7*self.scale if mark and text else 0))/2
        if mark:
            source=mark.cget('dark_image') or mark.cget('light_image')
            self.mark=ImageTk.PhotoImage(appearance.icon_image(source).resize((size,size),Image.Resampling.LANCZOS),master=self.owner)
            self.create_image(left,self.winfo_height()/2,image=self.mark,anchor='w')
            left+=size+(7*self.scale if text else 0)
        self.create_text(left,self.winfo_height()/2,text=text,anchor='w',fill=color,font=font,justify='center')

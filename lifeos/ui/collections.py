"""Shared photo-backed navigation and collections, without opaque table fields."""
import math
import tkinter as tk
import tkinter.font as tkfont
import customtkinter as ctk
from PIL import Image,ImageDraw,ImageTk
from .photowidgets import PhotoWidget,PhotoButton
from .glass import composite_glass
from .theme import TEXT,MUTED
from . import appearance

class GlassTabs(ctk.CTkFrame):
    """A small keyboard-operable section bar using the shared photo surface."""
    def __init__(self,parent,command=None,**kwargs):
        super().__init__(parent,fg_color='transparent')
        self.command=command
        self.names=[]
        self.pages={}
        self.buttons={}
        self.current=''
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(1,weight=1)
        self.bar=ctk.CTkFrame(self,fg_color='transparent',height=36)
        self.bar.grid(row=0,column=0,sticky='ew',pady=(0,12))

    def add(self,name):
        self.names.append(name)
        index=len(self.names)-1
        self.bar.grid_columnconfigure(index,weight=1)
        control=PhotoButton(self.bar,name,lambda n=name:self.choose(n),secondary=True,width=100,height=32)
        control.grid(row=0,column=index,sticky='ew',padx=(0,6))
        self.buttons[name]=control
        frame=ctk.CTkFrame(self,fg_color='transparent')
        self.pages[name]=frame
        if not self.current:
            self.set(name)
        return frame

    def get(self):
        return self.current

    def set(self,name):
        if name not in self.pages:
            raise ValueError('Unknown section.')
        for key,page in self.pages.items():
            if key==name:
                page.grid(row=1,column=0,sticky='nsew')
            else:
                page.grid_remove()
            self.buttons[key].secondary=key!=name
            self.buttons[key].draw()
        self.current=name
        owner=self.winfo_toplevel()
        if hasattr(owner,'wallpaper'):
            owner.wallpaper.request()

    def choose(self,name):
        self.set(name)
        if self.command:
            self.command()

class PhotoRecordList(PhotoWidget):
    """A scrollable real-record view with selection, sorting and keyboard use.

    A deliberately small Treeview-compatible interface keeps the record controller
    and integration checks independent of the presentation (rows or cards).
    """
    def __init__(self,parent,columns,mode='rows',on_open=None,on_toggle=None,on_add=None):
        self.columns=tuple(columns)
        self.mode=mode
        self.on_open,self.on_toggle,self.on_add=on_open,on_toggle,on_add
        self.data={}
        self.order=[]
        self.selected=''
        self.headings={}
        self.details={}
        self.offset=0
        self.extent=1
        self.yscrollcommand=None
        self.hitboxes=[]
        self.icon_images={}
        self.empty_title='Nothing here yet'
        self.empty_help='Add a record to get started.'
        self.empty_action='Add record'
        super().__init__(parent,takefocus=True,height=240)
        self.bind('<Button-1>',self.click)
        self.bind('<Double-1>',lambda e:self.open())
        self.bind('<Return>',lambda e:self.open())
        self.bind('<space>',self.toggle)
        self.bind('<Up>',lambda e:self.step(-1))
        self.bind('<Down>',lambda e:self.step(1))
        self.bind('<Home>',lambda e:self.select_index(0))
        self.bind('<End>',lambda e:self.select_index(len(self.order)-1))
        self.bind('<MouseWheel>',self.wheel)
        self.bind('<FocusIn>',lambda e:self.draw())
        self.bind('<FocusOut>',lambda e:self.draw())
        self.bind('<Motion>',lambda e:self.configure(cursor='hand2' if self.hit(e.x,e.y) else ''))

    def heading(self,key,text=None,command=None):
        self.headings[key]=(text or key,command)

    def column(self,*args,**kwargs):
        pass

    def tag_configure(self,*args,**kwargs):
        pass

    def configure(self,cnf=None,**kwargs):
        if 'yscrollcommand' in kwargs:
            self.yscrollcommand=kwargs.pop('yscrollcommand')
        kwargs.pop('xscrollcommand',None)
        super().configure(cnf,**kwargs)

    config=configure

    def insert(self,parent,index,iid,values=(),image=None,tags=()):
        iid=str(iid)
        self.data[iid]=tuple(values)
        self.order.append(iid)
        if image:
            self.icon_images[iid]=image
        return iid

    def get_children(self,*args):
        return tuple(self.order)

    def exists(self,iid):
        return str(iid) in self.data

    def delete(self,*ids):
        for iid in ids:
            iid=str(iid)
            self.data.pop(iid,None)
            self.icon_images.pop(iid,None)
            if iid in self.order:
                self.order.remove(iid)
        if self.selected not in self.data:
            self.selected=''

    def selection(self):
        return (self.selected,) if self.selected in self.data else ()

    def selection_set(self,iid):
        if isinstance(iid,(tuple,list)):
            iid=iid[0] if iid else ''
        self.selected=str(iid) if str(iid) in self.data else ''
        self.event_generate('<<TreeviewSelect>>')
        self.draw()

    def move(self,iid,parent,index):
        self.order.remove(str(iid))
        self.order.insert(index,str(iid))
        self.draw()

    def yview(self,*args):
        height=max(1,self.winfo_height())
        if args:
            before=self.offset
            if args[0]=='moveto':
                self.offset=float(args[1])*self.extent
            elif args[0]=='scroll':
                self.offset+=int(args[1])*(height*.8 if args[2]=='pages' else 40*self.scale)
            self.offset=max(0,min(self.offset,self.extent-height))
            if self.offset!=before:self.draw()
        return (self.offset/max(1,self.extent),min(1,(self.offset+height)/max(1,self.extent)))

    def wheel(self,event):
        value=getattr(self,'wheel_remainder',0)+event.delta/120
        units=int(value);self.wheel_remainder=value-units
        if not units:return 'break'
        before=self.offset
        self.yview('scroll',-units,'units')
        return 'break' if self.offset!=before else None

    def hit(self,x,y):
        return next((key for box,key in reversed(self.hitboxes) if box[0]<=x<=box[2] and box[1]<=y<=box[3]),None)

    def click(self,event):
        self.focus_set()
        key=self.hit(event.x,event.y)
        if not key:
            return
        if key[0]=='sort':
            command=self.headings[key[1]][1]
            if command:
                command()
        elif key[0]=='add':
            if self.on_add:
                self.on_add()
        else:
            self.selection_set(key[1])
            if key[0]=='toggle':
                self.toggle()
            elif self.mode=='cards':
                self.open()

    def open(self):
        if self.selection() and self.on_open:
            self.on_open()

    def toggle(self,event=None):
        if self.selection() and self.on_toggle:
            self.on_toggle(self.selected)
        elif self.mode=='cards':
            self.open()
        return 'break'

    def step(self,delta):
        index=self.order.index(self.selected) if self.selected in self.order else (-1 if delta>0 else len(self.order))
        return self.select_index(max(0,min(len(self.order)-1,index+delta)))

    def select_index(self,index):
        if self.order:
            self.selection_set(self.order[index])
            if self.mode=='cards':
                y=(index//self.card_columns)*self.card_height
            else:
                y=index*54*self.scale
            height=self.winfo_height()
            if y<self.offset:
                self.offset=y
            elif y+70*self.scale>self.offset+height:
                self.offset=y+70*self.scale-height
            self.draw()
        return 'break'

    def text(self,x,y,text,size=12,color=TEXT,width=0,bold=False,anchor='w'):
        key=(size,bold,self.scale,appearance.current())
        if not hasattr(self,'_fonts'):self._fonts={}
        if key not in self._fonts:self._fonts[key]=tkfont.Font(self,font=appearance.font(('Segoe UI',-round(size*self.scale),'bold' if bold else 'normal'),terminal=True))
        font=self._fonts[key]
        if width and font.measure(str(text))>width:
            original=str(text);low,high=0,len(original)
            while low<high:
                middle=(low+high+1)//2
                if font.measure(original[:middle]+'…')<=width:low=middle
                else:high=middle-1
            text=original[:low]+'…'
        return self.create_text(x,y,text=text,font=font,fill=color,anchor=anchor)

    def draw(self):
        if not hasattr(self,'scale') or not self.winfo_exists():
            return
        background=getattr(self,'_row_background',None)
        background_exists=bool(background and self.type(background))
        if self.mode=='rows' and background_exists:
            # Scrolling changes the rows, not the fixed photographic surface.
            # Keep its native image/item alive instead of transferring the same
            # full-size bitmap and invalidating the whole canvas every notch.
            self.addtag_all('redraw')
            self.dtag(background,'redraw')
            tk.Canvas.delete(self,'redraw')
        else:
            tk.Canvas.delete(self,'all')
        self.hitboxes=[]
        width,height=self.winfo_width(),self.winfo_height()
        if width<3 or height<3:
            return
        wp=getattr(self.owner,'wallpaper',None)
        key=wp.key(self) if wp else (width,height,appearance.epoch)
        if getattr(self,'_surface_key',None)!=key:
            self._surface_key=key
            self._base=wp.crop(self) if wp else self.backdrop()
            self._surface=composite_glass(self._base,(0,0,width,height),radius=round(12*self.scale))
        base=self._base
        self.glass_image=self._surface
        if self.mode=='rows':
            if getattr(self,'_row_surface',None) is not self.glass_image or not background_exists:
                self._row_surface=self.glass_image
                self.photo=ImageTk.PhotoImage(self.glass_image,master=self.owner)
                if background_exists:
                    self.itemconfigure(background,image=self.photo)
                else:
                    self._row_background=self.create_image(0,0,image=self.photo,anchor='nw')
        else:
            self.paint_background(self.glass_image)
        if self.mode=='cards':
            self.draw_cards(width,height,base)
        else:
            self.draw_rows(width,height)
        if not self.order:
            self.text(width/2,height*.38,self.empty_title,17,anchor='center',width=width-40*self.scale)
            self.text(width/2,height*.38+32*self.scale,self.empty_help,12,MUTED,anchor='center',width=width-40*self.scale)
            self.text(width/2,height*.38+78*self.scale,'+ '+self.empty_action,13,anchor='center')
            self.hitboxes.append(((width*.2,height*.38+55*self.scale,width*.8,height*.38+100*self.scale),('add',)))
        if self.yscrollcommand:
            self.yscrollcommand(*self.yview())

    def draw_rows(self,width,height):
        scale=self.scale
        pad=18*scale
        header=42*scale
        rowheight=54*scale
        count=max(1,len(self.columns))
        # First column gets the largest share of available width.
        first=.43 if count>=3 else .65
        available=width-2*pad
        widths=[available*first]+[available*(1-first)/max(1,count-1)]*(count-1)
        if count==1:
            widths=[available]
        left=pad
        for key,colwidth in zip(self.columns,widths):
            title=self.headings.get(key,(key,None))[0]
            self.text(left+8*scale,22*scale,title,11,MUTED,colwidth-12*scale,bold=True)
            self.hitboxes.append(((left,0,left+colwidth,header),('sort',key)))
            left+=colwidth
        self.create_line(pad,header,width-pad,header,fill='#686868')
        self.extent=max(height,header+len(self.order)*rowheight+12*scale)
        self.offset=max(0,min(self.offset,self.extent-height))
        for index,iid in enumerate(self.order):
            top=header+index*rowheight-self.offset
            if top+rowheight<=header or top>=height:
                continue
            if top<header:
                continue
            mid=top+rowheight/2
            selected=iid==self.selected
            if selected:
                self.create_rectangle(pad,top+3*scale,width-pad,top+rowheight-3*scale,outline='#a3a3a3',width=1)
            self.hitboxes.append(((pad,top,width-pad,top+rowheight),('row',iid)))
            left=pad
            for position,(key,colwidth,value) in enumerate(zip(self.columns,widths,self.data[iid])):
                shift=8*scale
                if position==0:
                    trademark=None
                    if self.on_toggle:
                        r=7*scale
                        self.create_rectangle(left+shift,mid-r,left+shift+2*r,mid+r,outline='#bdbdbd')
                        if self.details.get(iid,{}).get('completed'):
                            self.text(left+shift+r,mid,'✓',12,anchor='center')
                        self.hitboxes.append(((left,top,left+33*scale,top+rowheight),('toggle',iid)))
                    elif iid in self.icon_images:
                        image=self.icon_images[iid]
                        self.create_image(left+shift,mid,image=image,anchor='w')
                        if getattr(image,'lifeos_name',None)=='python-logo':
                            # Keep the mark separate from the unchanged logo pixels.
                            trademark=self.text(left+shift+image.width()+2*scale,
                                mid-6*scale,'\u2122',10,TEXT)
                    shift=34*scale
                    if trademark is not None:
                        shift=max(shift,self.bbox(trademark)[2]-left+6*scale)
                self.text(left+shift,mid,value,12,TEXT,colwidth-shift-10*scale)
                left+=colwidth
            self.create_line(pad,top+rowheight,width-pad,top+rowheight,fill='#4f4f4f')

    def draw_cards(self,width,height,base):
        scale=self.scale
        gap=14*scale
        self.card_columns=max(1,min(3,int((width-gap)/(225*scale))))
        self.card_height=164*scale
        cw=(width-(self.card_columns+1)*gap)/self.card_columns
        self.extent=max(height,math.ceil(len(self.order)/self.card_columns)*self.card_height+gap)
        self.offset=max(0,min(self.offset,self.extent-height))
        backing=base.copy()
        boxes=[]
        for index,iid in enumerate(self.order):
            left=gap+(index%self.card_columns)*(cw+gap)
            top=gap+(index//self.card_columns)*self.card_height-self.offset
            if top+150*scale<0 or top>height:
                continue
            box=(left,top,left+cw,top+150*scale)
            backing=composite_glass(backing,box,radius=round(10*scale))
            boxes.append((iid,box))
        self.glass_image=backing
        tk.Canvas.delete(self,'all')
        self.paint_background(backing)
        for iid,(left,top,right,bottom) in boxes:
            details=self.details.get(iid,{})
            self.hitboxes.append(((left,top,right,bottom),('card',iid)))
            if iid==self.selected:
                self.create_rectangle(left+4,top+4,right-4,bottom-4,outline='#c2c2c2')
            self.text(left+16*scale,top+29*scale,self.data[iid][0],16,width=cw-32*scale,bold=True)
            self.text(left+16*scale,top+59*scale,details.get('subtitle',''),11,MUTED,cw-32*scale)
            ratio=details.get('ratio')
            if ratio is not None:
                a,b=left+16*scale,right-16*scale
                self.create_line(a,top+90*scale,b,top+90*scale,fill='#666666',width=3*scale)
                if ratio>0:
                    self.create_line(a,top+90*scale,a+(b-a)*ratio,top+90*scale,fill='#dddddd',width=3*scale)
                self.text(a,top+110*scale,details.get('progress',''),11,MUTED,cw-32*scale)
            else:
                self.text(left+16*scale,top+91*scale,details.get('progress',''),12,width=cw-32*scale)
            self.text(left+16*scale,top+134*scale,details.get('footer','Open details →'),11,MUTED,cw-32*scale)

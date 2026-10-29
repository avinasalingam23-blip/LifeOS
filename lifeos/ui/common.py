import tkinter as tk
from tkinter import messagebox, ttk
import customtkinter as ctk
from pygments import lex
from pygments.lexers import PythonLexer
from .theme import BG,PANEL,CARD,ACCENT,BLUE,TEXT,MUTED,BORDER,INPUT,GlassCard
from .icons import icon,action_icon,TITLE_ICONS
from .photowidgets import PhotoLabel,PhotoButton

def button(parent,text,command,secondary=False,**kwargs):
    name=kwargs.pop('icon_name',None) or action_icon(text)
    text=text.replace('↗','').replace('→','').replace('✦','').strip()
    if text.startswith('+ '):
        text=text[2:]
    if name:
        kwargs.setdefault('image',icon(name,MUTED if secondary else TEXT,16))
        kwargs.setdefault('compound','left')
        kwargs.setdefault('border_spacing',8)
    kwargs.setdefault('height',34)
    kwargs.setdefault('corner_radius',11)
    kwargs.setdefault('border_width',1)
    kwargs.setdefault('border_color',BORDER if secondary else '#747474')
    image=kwargs.pop('image',None)
    width,height=kwargs.pop('width',120),kwargs.pop('height',34)
    return PhotoButton(parent,text,command,image=image,width=width,height=height,secondary=secondary)

def label(parent,text,size=14,color=TEXT,**kwargs):
    name=kwargs.pop('icon_name',None) or (TITLE_ICONS.get(text) if size>=18 else None)
    if name:
        kwargs.setdefault('image',icon(name,color,21 if size>=18 else 16))
        kwargs.setdefault('padx',6)
    return PhotoLabel(parent,text=text,font=('Segoe UI',size),text_color=color,**kwargs)

def configure_tree(root):
    style=ttk.Style(root)
    style.theme_use('clam')
    style.configure('Treeview',background=PANEL,foreground=TEXT,fieldbackground=PANEL,rowheight=35,
                    borderwidth=0,bordercolor=PANEL,lightcolor=PANEL,darkcolor=PANEL,relief='flat',font=('Segoe UI',10))
    style.layout('Treeview',[('Treeview.treearea',{'sticky':'nswe'})])
    style.configure('Treeview.Heading',background=CARD,foreground='#dddddd',relief='flat',font=('Segoe UI',10,'bold'),padding=10)
    style.map('Treeview',background=[('selected','#484848')],foreground=[('selected','#ffffff')])
    style.map('Treeview.Heading',background=[('active','#383838')])
    style.configure('TScrollbar',background=CARD,troughcolor=BG,arrowcolor=MUTED)

def safe(parent,action):
    try:
        return action()
    except Exception as error:
        import logging
        logging.exception('LifeOS action failed')
        messagebox.showerror('LifeOS · unable to complete',str(error),parent=parent)
        return None

class CodeEditor(GlassCard):
    def __init__(self,parent,value='',**kwargs):
        super().__init__(parent,fg_color=INPUT,**kwargs)
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(1,weight=1)
        bar=ctk.CTkFrame(self,fg_color='transparent')
        bar.grid(row=0,column=0,sticky='ew')
        self.caption=label(bar,'Code · Ctrl+Z to undo',11,MUTED,icon_name='code-xml')
        self.caption.pack(side='left',padx=8)
        button(bar,'Copy',self.copy,True,width=70).pack(side='right',padx=5,pady=4)
        self.text=tk.Text(self,background=INPUT,foreground=TEXT,insertbackground=ACCENT,
                          font=('Consolas',11),undo=True,wrap='none',height=15,padx=12,pady=10,
                          relief='flat',selectbackground='#484848',tabs=('4c',))
        self.text.grid(row=1,column=0,sticky='nsew')
        v=ctk.CTkScrollbar(self,orientation='vertical',command=self.text.yview)
        v.grid(row=1,column=1,sticky='ns')
        h=ctk.CTkScrollbar(self,orientation='horizontal',command=self.text.xview)
        h.grid(row=2,column=0,sticky='ew')
        self.text.configure(yscrollcommand=v.set,xscrollcommand=h.set)
        self.text.insert('1.0',value or '')
        for tag,color in [('Token.Keyword',BLUE),('Token.Literal.String','#bdbdbd'),('Token.Comment','#828282'),
                          ('Token.Literal.Number','#aeaeae'),('Token.Name.Function',ACCENT),('Token.Operator','#c6c6c6')]:
            self.text.tag_configure(tag,foreground=color)
        self.pending=None
        self.text.bind('<KeyRelease>',self.schedule)
        self.text.bind('<Tab>',self.indent)
        self.highlight()

    def indent(self,event):
        self.text.insert('insert','    ')
        return 'break'

    def schedule(self,event=None):
        if self.pending:
            self.after_cancel(self.pending)
        self.pending=self.after(180,self.highlight)

    def highlight(self):
        self.pending=None
        source=self.get()
        # Large solutions stay editable without repeatedly lexing megabytes.
        if len(source)>150000:
            return
        for tag in self.text.tag_names():
            if tag.startswith('Token.'):
                self.text.tag_remove(tag,'1.0','end')
        offset=0
        for token,value in lex(source,PythonLexer()):
            tag=str(token)
            while tag not in self.text.tag_names() and '.' in tag:
                tag=tag.rsplit('.',1)[0]
            if tag.startswith('Token.'):
                self.text.tag_add(tag,f'1.0+{offset}c',f'1.0+{offset+len(value)}c')
            offset+=len(value)

    def copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.get())
        self.update()

    def get(self):
        return self.text.get('1.0','end-1c')

    def set_language(self,language):
        self.caption.configure(text='Python · syntax highlighting · Ctrl+Z to undo' if language=='Python' else language+' · multiline editor · Ctrl+Z to undo',
                               image=icon('python-logo' if language=='Python' else 'code-xml',MUTED,16))

    def destroy(self):
        if self.pending:
            self.after_cancel(self.pending)
        super().destroy()

class Dialog(ctk.CTkToplevel):
    def __init__(self,parent,title,width=820,height=760):
        super().__init__(parent)
        self.title('LifeOS · '+title)
        self.geometry(f'{width}x{height}')
        self.minsize(620,480)
        self.configure(fg_color=BG)
        scaling=self._get_window_scaling()
        available_width=int(self.winfo_screenwidth()/scaling)-50
        available_height=int(self.winfo_screenheight()/scaling)-90
        self.geometry(f'{min(width,available_width)}x{min(height,available_height)}+30+30')
        self.minsize(min(620,available_width),min(440,available_height))
        self.transient(parent.winfo_toplevel())
        from .backgrounds import PhotographicBackground
        self.wallpaper=PhotographicBackground(self)
        owner=parent.winfo_toplevel()
        page=getattr(owner,'current_page','Dashboard')
        self.current_page=page
        self.wallpaper.set_page(page)
        self.activate_job=self.after(100,self._activate)

    def destroy(self):
        if getattr(self,'activate_job',None):
            self.after_cancel(self.activate_job)
            self.activate_job=None
        if hasattr(self,'wallpaper'):
            self.wallpaper.close()
        super().destroy()

    def _activate(self):
        self.activate_job=None
        if self.winfo_exists():
            self.grab_set()
            self.focus_force()

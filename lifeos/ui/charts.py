"""Small photo-backed Matplotlib host shared by fitness and nutrition views."""
import customtkinter as ctk
from PIL import ImageTk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from .theme import PANEL,TEXT,MUTED,BORDER,GlassCard
from . import appearance

def style_axes(figure,axes):
    figure.patch.set_alpha(0)
    for ax in axes:
        ax.patch.set_alpha(0)
        ax.tick_params(colors=MUTED,labelsize=8)
        ax.grid(axis='y',color=BORDER,alpha=.5)
        ax.title.set_color(TEXT)
        ax.xaxis.label.set_color(MUTED)
        ax.yaxis.label.set_color(MUTED)
        for spine in ax.spines.values():
            spine.set_color(BORDER)

class GlassPlot(GlassCard):
    def __init__(self,parent,app):
        super().__init__(parent)
        self.app=app
        self.canvas=None
        self.figure=None

    def show(self,figure):
        self.clear()
        self.figure=figure
        self.canvas=FigureCanvasTkAgg(figure,master=self)
        self.app.appearance.figure(figure)
        self.canvas.draw()
        native=self.canvas.get_tk_widget()
        def refresh():
            if native.winfo_exists() and native.winfo_width()>1:
                wp=getattr(self.winfo_toplevel(),'wallpaper',self.app.wallpaper)
                key=wp.key(native)
                if getattr(native,'lifeos_chart_key',None)==key:return
                native.lifeos_chart_key=key
                native.glass_image=wp.sample(native)
                native.photo=ImageTk.PhotoImage(native.glass_image,master=native)
                native.delete('glass-chart')
                item=native.create_image(0,0,image=native.photo,anchor='nw',tags='glass-chart')
                native.tag_lower(item)
        native.refresh_glass=refresh
        native.pack(fill='both',expand=True,padx=12,pady=12)
        self.winfo_toplevel().wallpaper.request()

    def clear(self):
        if self.canvas:
            widget=self.canvas.get_tk_widget()
            for key in ('_idle_draw_id','_event_loop_id'):
                job=getattr(self.canvas,key,None)
                if job:
                    widget.after_cancel(job)
                    setattr(self.canvas,key,None)
            widget.destroy()
            self.canvas=None
        if self.figure:
            self.figure.clear()
            self.figure=None

    def destroy(self):
        self.clear()
        super().destroy()

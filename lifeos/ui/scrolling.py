"""One wheel router per window; scroll frames never install global callbacks."""
import tkinter as tk
import customtkinter as ctk

class ScrollFrame(ctk.CTkScrollableFrame):
    def bind_all(self,*args,**kwargs):
        # CTk 6 installs five global bindings for each instance and does not
        # remove them on destruction. Use the window router below instead.
        return None

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.master.lifeos_scroll_owner=self
        owner=self.winfo_toplevel()
        if not getattr(owner,'lifeos_wheel_router',False):
            owner.lifeos_wheel_router=True
            owner.bind('<MouseWheel>',route_wheel,add='+')
        self.wheel_remainder=0

def route_wheel(event):
    widget=event.widget
    # Native editors and record canvases already consume their own wheel event.
    if isinstance(widget,(tk.Text,tk.Entry,tk.Spinbox)):return
    node=widget
    while node is not None:
        frame=node if isinstance(node,ScrollFrame) else getattr(node,'lifeos_scroll_owner',None)
        if frame:
            frame.wheel_remainder+=event.delta/120
            units=int(frame.wheel_remainder)
            if not units:return 'break'
            frame.wheel_remainder-=units
            canvas=frame.master
            view=canvas.xview if event.state&1 else canvas.yview
            before=view()
            view('scroll',-units*24,'units')
            if view()!=before:
                owner=frame.winfo_toplevel()
                if hasattr(owner,'wallpaper'):owner.wallpaper.request_scroll(frame)
                return 'break'
            # At a nested viewport boundary, offer the event to its enclosing
            # scroll frame instead of trapping the wheel over a child control.
            node=canvas.master
            continue
        node=getattr(node,'master',None)

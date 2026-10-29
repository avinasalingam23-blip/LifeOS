"""Owned callback cleanup for library widgets with recurring polling timers."""
import customtkinter as ctk

class Textbox(ctk.CTkTextbox):
    """CTk 6 textboxes poll scrollbar state but do not cancel that on destroy."""
    def __init__(self,*args,**kwargs):
        self.pending_callbacks=set()
        super().__init__(*args,**kwargs)

    def after(self,ms,func=None,*args):
        if func is None:return super().after(ms)
        holder={}
        def run():
            self.pending_callbacks.discard(holder['id'])
            return func(*args)
        job=super().after(ms,run)
        holder['id']=job
        self.pending_callbacks.add(job)
        return job

    def after_cancel(self,job):
        self.pending_callbacks.discard(job)
        return super().after_cancel(job)

    def destroy(self):
        for job in tuple(self.pending_callbacks):self.after_cancel(job)
        super().destroy()

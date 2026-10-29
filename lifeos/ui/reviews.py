from .lifecycle import Textbox
"""Read-only progress reviews calculated from saved fitness records."""
import customtkinter as ctk
from .common import Dialog,button,label,PANEL,MUTED
from .theme import BORDER


class FitnessReviewDialog(Dialog):
    def __init__(self,parent,app):
        super().__init__(parent,'Progress review',850,700)
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(2,weight=1)
        label(self,'Progress review',25).grid(row=0,column=0,sticky='w',padx=22,pady=(18,6))
        label(self,'Calculated from saved workouts, measurements and food entries. Missing records remain unknown.',
            12,MUTED,wraplength=760,justify='left').grid(row=1,column=0,sticky='ew',padx=22,pady=6)
        self.output=Textbox(self,fg_color=PANEL,border_color=BORDER,corner_radius=18,
            font=('Segoe UI',14),wrap='word')
        self.output.grid(row=2,column=0,sticky='nsew',padx=22,pady=8)
        self.output.insert('1.0',app.coach.review_text(routine_id=app.selected.get('workout_routines')))
        self.output.configure(state='disabled')
        footer=ctk.CTkFrame(self,fg_color='transparent')
        footer.grid(row=3,column=0,sticky='ew',padx=22,pady=(4,18))
        button(footer,'Copy review',self.copy,True,width=135).pack(side='left')
        button(footer,'Close',self.destroy,True,width=90).pack(side='right')

    def copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.output.get('1.0','end-1c'))

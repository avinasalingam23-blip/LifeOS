"""Opt-in rendering diagnostic for nested native scrolling surfaces."""
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import customtkinter as ctk
from PIL import ImageGrab
from lifeos.db import Database
from lifeos.ui.app import LifeOS
from lifeos.ui.fitness import DayDialog

directory=Path(sys.argv[1])
directory.mkdir(parents=True,exist_ok=True)
app=LifeOS(Database(directory/'diagnostic.sqlite3'))
app.coach.save_preferences(dict(equipment=['Bodyweight','Resistance band']))
rid=app.coach.create_template()
app.show('Workout Planner')
day=app.coach.weekly(rid)[0]['days'][0]
dialog=DayDialog(app,app,rid,'Monday',day)
end=time.monotonic()+2
while time.monotonic()<end:
    app.update()
    time.sleep(.02)
dialog.wallpaper.render()
app.update()
ImageGrab.grab(window=dialog.winfo_id()).save(directory/'dialog.png')
details=[]
def walk(widget):
    if isinstance(widget,ctk.CTkScrollableFrame):
        image=getattr(widget,'glass_image',None)
        canvas=getattr(widget,'lifeos_background',None)
        details.append(dict(name=str(widget),size=[widget.winfo_width(),widget.winfo_height()],
            at=[widget.winfo_rootx()-dialog.winfo_rootx(),widget.winfo_rooty()-dialog.winfo_rooty()],
            image_size=image.size if image else None,canvas=str(canvas),canvas_size=[canvas.winfo_width(),canvas.winfo_height()] if canvas else None,
            canvas_mapped=canvas.winfo_ismapped() if canvas else None))
        if image:
            image.save(directory/f'surface-{len(details)}.png')
    for child in widget.winfo_children():
        walk(child)
walk(dialog)
(directory/'geometry.json').write_text(json.dumps(details,indent=2))
print(json.dumps(details,indent=2))
dialog.destroy()
app.close()

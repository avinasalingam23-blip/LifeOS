from datetime import date,timedelta
from types import SimpleNamespace
from PIL import Image
from lifeos.models import ENTITIES
from lifeos.ui.presentation import COLUMNS,subject_progress
from lifeos.ui.backgrounds import PhotographicBackground

def test_compact_columns_preserve_full_record_metadata():
    assert set(COLUMNS)==set(ENTITIES)
    assert all(1<=len(columns)<=4 for columns in COLUMNS.values())
    assert COLUMNS['problems']==('name','topic','difficulty','status')
    assert 'approach' in {f.key for f in ENTITIES['problems'].fields}
    assert 'code' in {f.key for f in ENTITIES['concepts'].fields}

def test_subject_card_progress_has_explicit_scope_and_never_invents_completion(service):
    today=date.today()
    rid=service.save('paths',dict(name='Learning topic',target_minutes=100,target_period='Weekly'))
    service.save('study_sessions',dict(path_id=rid,date=(today-timedelta(days=7)).isoformat(),minutes=80))
    service.save('study_sessions',dict(path_id=rid,date=today.isoformat(),minutes=25))
    ratio,text=subject_progress(service,service.get('paths',rid),today)
    assert ratio==.25 and '25 / 100' in text and 'last 7 days' in text
    assert service.get('paths',rid)['status']=='Not started'

def test_photo_labels_sample_exact_frosted_parent_pixels_without_a_new_overlay():
    # A real regression for the seams: descendants must crop the already-painted
    # parent rather than blending a differently tinted wallpaper independently.
    photo=Image.new('RGB',(100,80),'#777777')
    photo.putpixel((30,25),(95,95,95))
    root=SimpleNamespace()
    parent=SimpleNamespace(glass_image=photo,master=root,winfo_rootx=lambda:100,winfo_rooty=lambda:50)
    child=SimpleNamespace(master=parent,winfo_rootx=lambda:120,winfo_rooty=lambda:65,winfo_width=lambda:40,winfo_height=lambda:30)
    wallpaper=PhotographicBackground.__new__(PhotographicBackground)
    wallpaper.root=root
    sample=wallpaper.sample(child)
    assert sample.size==(40,30)
    assert sample.getpixel((10,10))==(95,95,95)
    assert sample.getpixel((0,0))==(119,119,119)

"""Offline asset and semantic-icon checks; no desktop or network required."""
import hashlib
import json
from PIL import Image
from lifeos.ui.icons import ASSETS,NAV_ICONS,ENTITY_ICONS,TITLE_ICONS,row_icon,action_icon,raster

def test_every_ui_icon_has_a_bundled_readable_alpha_asset():
    manifest=json.loads((ASSETS/'icon-manifest.json').read_text(encoding='utf-8'))
    expected=set(NAV_ICONS.values())|set(ENTITY_ICONS.values())|set(TITLE_ICONS.values())
    assert len(NAV_ICONS)==8
    for name in expected:
        assert name in manifest
        image=Image.open(ASSETS/'icons'/(name+'.png'))
        assert image.size==(96,96)
        assert image.mode=='RGBA'
        assert image.getchannel('A').getextrema()==(0,255)
    assert (ASSETS/'LUCIDE-LICENSE.txt').is_file()

def test_bundled_vectors_match_recorded_provenance():
    manifest=json.loads((ASSETS/'icon-manifest.json').read_text(encoding='utf-8'))
    for name,item in manifest.items():
        source=ASSETS/'python-logo.ico' if name=='python-logo' else ASSETS/'icons'/(name+'.svg')
        assert hashlib.sha256(source.read_bytes()).hexdigest()==item['sha256']

def test_contextual_icons_do_not_mislabel_general_code_as_python():
    assert row_icon('problems',{'name':'Graphs'})[0]=='code-xml'
    assert row_icon('solutions',{'language':'Python'})[0]=='python-logo'
    assert row_icon('solutions',{'language':'Java'})[0]=='file-code-2'
    assert row_icon('tasks',{'status':'Completed'})[0]=='circle-check'
    assert row_icon('workouts',{'status':'Recovery'})[0]=='moon'
    for exercise,expected in [('Running','running'),('Pull-ups','pull-up'),('Push ups','push-up'),('Squat','dumbbell')]:
        assert row_icon('exercise_logs',{'exercise':exercise})[0]==expected

def test_tint_preserves_shape_and_official_python_mark():
    original=raster('dumbbell','#ffffff')
    tinted=raster('dumbbell','#8ba9ff')
    assert original.getchannel('A').tobytes()==tinted.getchannel('A').tobytes()
    python=raster('python-logo','#ffffff')
    assert len(python.getcolors(python.width*python.height))>2
    assert action_icon('Export CSV')=='download'
    assert action_icon('Pause')=='pause'
    assert action_icon('Resume')=='play'

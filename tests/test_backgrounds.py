import hashlib
import json
import re
import pytest
from pathlib import Path
from PIL import Image,ImageChops,ImageStat
from lifeos.ui.backgrounds import DIRECTORY,PAGE_PHOTOS,PhotographicBackground,load_photo,learning_photo,contrast_ratio
from lifeos.ui import theme
from lifeos.ui.icons import raster

def test_all_pages_have_unique_offline_subjects_and_provenance():
    manifest=json.loads((DIRECTORY/'manifest.json').read_text(encoding='utf-8'))
    assert len(PAGE_PHOTOS)==8 and len(set(PAGE_PHOTOS.values()))==8
    assert set(PAGE_PHOTOS.values())|{'research'}==set(manifest['photos'])
    for name,record in manifest['photos'].items():
        asset=DIRECTORY/record['asset']
        assert hashlib.sha256(asset.read_bytes()).hexdigest()==record['processed_sha256']
        assert (DIRECTORY/record['original']).exists()
        assert record['source_url'].startswith('https://images.unsplash.com/')
        assert asset.stat().st_size<250_000
        photo=load_photo(name)
        assert photo.size==(1600,1000)
        r,g,b=photo.split()
        assert ImageChops.difference(r,g).getbbox() is None
        assert ImageChops.difference(g,b).getbbox() is None
        assert 20<ImageStat.Stat(photo).mean[0]<180

def test_neutral_ui_colors_and_reading_contrast():
    for value in vars(theme).values():
        if isinstance(value,str) and re.fullmatch(r'#[0-9a-fA-F]{6}',value):
            assert value[1:3]==value[3:5]==value[5:7],value
    assert contrast_ratio(theme.TEXT,theme.PANEL)>=7
    assert contrast_ratio(theme.MUTED,theme.CARD)>=7
    assert contrast_ratio(theme.TEXT,'#333333')>=7
    for name in ('book-open','dumbbell','python-logo'):
        image=raster(name)
        r,g,b,a=image.split()
        assert ImageChops.difference(r,g).getbbox() is None
        assert ImageChops.difference(g,b).getbbox() is None

def test_research_variant_does_not_require_or_create_a_subject():
    assert learning_photo('NLP / Machine Learning')=='research'
    assert learning_photo('Introduction to ML')=='research'
    assert learning_photo('Natural Language Processing')=='research'
    assert learning_photo('Compiler design')=='learning'
    assert learning_photo('HTML and CSS')=='learning'

def test_ui_has_no_unintentional_saturated_color_literals():
    directory=Path(theme.__file__).parent
    for file in directory.glob('*.py'):
        if file.name=='appearance.py':continue  # Explicit selectable terminal palette.
        for value in re.findall(r'#[0-9a-fA-F]{6}',file.read_text(encoding='utf-8')):
            assert value[1:3].lower()==value[3:5].lower()==value[5:7].lower(),(file.name,value)


@pytest.mark.parametrize('x,y,width,height',[(-3,-2,12,10),(7,4,12,10),(0,0,4,3)])
def test_resize_sampling_uses_photo_instead_of_black_padding(x,y,width,height):
    from types import SimpleNamespace
    root=object()
    parent=SimpleNamespace(master=root,glass_image=Image.new('RGB',(10,8),'#606060'),
        winfo_rootx=lambda:0,winfo_rooty=lambda:0)
    child=SimpleNamespace(master=parent,winfo_rootx=lambda:x,winfo_rooty=lambda:y,
        winfo_width=lambda:width,winfo_height=lambda:height)
    background=SimpleNamespace(root=root,crop=lambda widget:Image.new('RGB',(width,height),'#303030'))
    result=PhotographicBackground.sample(background,child)
    assert result.size==(width,height)
    for px in range(width):
        for py in range(height):
            expected=96 if 0<=x+px<10 and 0<=y+py<8 else 48
            assert result.getpixel((px,py))==(expected,)*3

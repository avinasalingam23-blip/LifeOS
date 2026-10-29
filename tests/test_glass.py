import pytest
from PIL import Image,ImageDraw,ImageStat
from lifeos.ui.glass import composite_glass,GLASS_OPACITY

def test_card_center_preserves_the_photo_not_just_the_border():
    background=Image.new('RGB',(240,160))
    draw=ImageDraw.Draw(background)
    for x in range(240):
        level=round(x*200/239)
        draw.line((x,0,x,160),fill=(level,level,level))
    result=composite_glass(background,(10,10,230,150),blur=0)
    # Variation must remain across the center, far away from all card borders.
    center=result.crop((60,45,180,115))
    original=background.crop((60,45,180,115))
    assert ImageStat.Stat(center).stddev[0]>ImageStat.Stat(original).stddev[0]*.60
    value=result.getpixel((120,80))[0]
    expected=background.getpixel((120,80))[0]*(1-GLASS_OPACITY)+36*GLASS_OPACITY
    assert abs(value-expected)<9
    assert value>60  # An opaque charcoal card would be around 36.

def test_every_valid_glass_opacity_retains_most_background_luminance():
    dark=Image.new('RGB',(100,100),'#202020')
    light=Image.new('RGB',(100,100),'#aaaaaa')
    for opacity in (.25,.33,.40):
        a=composite_glass(dark,(5,5,95,95),opacity=opacity).getpixel((50,50))[0]
        b=composite_glass(light,(5,5,95,95),opacity=opacity).getpixel((50,50))[0]
        assert b-a>75
    with pytest.raises(ValueError):
        composite_glass(dark,(5,5,95,95),opacity=.95)

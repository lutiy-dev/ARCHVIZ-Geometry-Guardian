"""Deterministic synthetic demo assets for ARCHVIZ Production VARIANT 02."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

W,H=768,512

def _save_mask(path, draw_fn=None, blur=0):
    im=Image.new('L',(W,H),0)
    if draw_fn:
        d=ImageDraw.Draw(im); draw_fn(d)
    if blur: im=im.filter(ImageFilter.GaussianBlur(blur))
    im.save(path)

def ensure_assets(input_root):
    root=Path(input_root); root.mkdir(parents=True,exist_ok=True)
    d=root/'archviz_demo_v02'; d.mkdir(parents=True,exist_ok=True)
    # Synthetic scene: sky, facade blocks, ground, greenery and people markers.
    im=Image.new('RGB',(W,H),(34,46,63)); dr=ImageDraw.Draw(im)
    dr.rectangle((0,300,W,H), fill=(91,78,62))
    dr.rectangle((110,120,350,330), fill=(143,117,87))
    dr.rectangle((410,150,690,330), fill=(132,105,79))
    for x in (145,210,275,445,515,585): dr.rectangle((x,180,x+34,230), fill=(28,34,42))
    dr.ellipse((40,210,150,360), fill=(54,83,47)); dr.ellipse((650,220,750,365), fill=(49,79,43))
    dr.ellipse((360,300,372,332), fill=(180,165,145)); dr.rectangle((364,326,368,365), fill=(90,75,65))
    im.save(root/'archviz_demo_v02_original.png'); im.save(d/'original.png')
    _save_mask(d/'empty.png')
    _save_mask(d/'building_protect.png', lambda x:x.rectangle((95,105,705,345),fill=255))
    _save_mask(d/'facade_edit.png', lambda x:(x.rectangle((110,120,350,330),fill=255),x.rectangle((410,150,690,330),fill=255)))
    _save_mask(d/'facade_protect.png', lambda x:(x.rectangle((140,175,315,235),fill=255),x.rectangle((440,175,625,235),fill=255)))
    _save_mask(d/'facade_composite.png', lambda x:(x.rectangle((105,115,355,335),fill=255),x.rectangle((405,145,695,335),fill=255)), blur=6)
    _save_mask(d/'road_edit.png', lambda x:x.rectangle((0,300,W,H),fill=255))
    _save_mask(d/'road_composite.png', lambda x:x.rectangle((0,292,W,H),fill=255), blur=6)
    _save_mask(d/'greenery_edit.png', lambda x:(x.ellipse((35,205,155,370),fill=255),x.ellipse((640,215,755,375),fill=255)))
    _save_mask(d/'greenery_composite.png', lambda x:(x.ellipse((25,195,165,380),fill=255),x.ellipse((630,205,765,385),fill=255)), blur=6)
    _save_mask(d/'people_edit.png', lambda x:x.rectangle((352,292,382,372),fill=255))
    _save_mask(d/'people_influence.png', lambda x:x.ellipse((330,275,405,395),fill=255), blur=4)
    _save_mask(d/'people_composite.png', lambda x:x.ellipse((338,282,397,388),fill=255), blur=5)
    return [str(p) for p in [root/'archviz_demo_v02_original.png']+sorted(d.glob('*.png'))]

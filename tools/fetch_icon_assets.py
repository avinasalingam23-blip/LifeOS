"""Development-only asset fetch/render. The installed application never uses network for icons."""
import hashlib
import json
import math
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image,ImageDraw
from fontTools.pens.basePen import BasePen
from fontTools.svgLib.path import parse_path

ROOT=Path(__file__).resolve().parents[1]/'lifeos'/'assets'
VERSION='0.468.0'
ICONS=['layout-dashboard','code-xml','book-open','dumbbell','apple','calendar-check',
       'chart-no-axes-combined','settings','plus','pencil','trash-2','download','refresh-cw','external-link',
       'calendar-plus','check-check','check','cooking-pot','filter','x','save','copy','play','pause',
       'square','shield-check','droplets','timer','search','database-backup','archive-restore',
       'arrow-up-right','arrow-left','notebook-pen','graduation-cap','utensils','footprints','activity',
       'moon','list-checks','circle-check','file-code-2','circle-help','armchair']

class PathPen(BasePen):
    def __init__(self,draw,scale,color,width):
        super().__init__(None)
        self.draw,self.scale,self.color,self.width=draw,scale,color,width
        self.points=[]
    def point(self,p):
        return tuple(v*self.scale for v in p)
    def flush(self,closed=False):
        if len(self.points)>1:
            points=self.points+([self.points[0]] if closed else [])
            self.draw.line(points,fill=self.color,width=self.width,joint='curve')
            r=self.width/2
            for x,y in (points[0],points[-1]):
                self.draw.ellipse((x-r,y-r,x+r,y+r),fill=self.color)
        self.points=[]
    def _moveTo(self,p):
        self.flush()
        self.points=[self.point(p)]
    def _lineTo(self,p):
        self.points.append(self.point(p))
    def _curveToOne(self,p1,p2,p3):
        p0=self.points[-1]
        a,b,c=self.point(p1),self.point(p2),self.point(p3)
        for i in range(1,25):
            t=i/24
            self.points.append(tuple((1-t)**3*p0[j]+3*(1-t)**2*t*a[j]+3*(1-t)*t*t*b[j]+t**3*c[j] for j in (0,1)))
    def _closePath(self):
        self.flush(True)
    def _endPath(self):
        self.flush()

def render(svg,target):
    # Render at 8x before downsampling: consistent 2-unit rounded strokes at 24x24.
    size=192
    scale=size/24
    image=Image.new('RGBA',(size,size))
    draw=ImageDraw.Draw(image)
    color=(255,255,255,255)
    width=round(2*scale)
    root=ET.fromstring(svg)
    for element in root:
        tag=element.tag.rsplit('}',1)[-1]
        a=element.attrib
        if tag=='path':
            pen=PathPen(draw,scale,color,width)
            parse_path(a['d'],pen)
            pen.flush()
        elif tag in ('line','polyline','polygon'):
            if tag=='line':
                points=[(float(a['x1'])*scale,float(a['y1'])*scale),(float(a['x2'])*scale,float(a['y2'])*scale)]
            else:
                nums=[float(n) for n in a['points'].replace(',',' ').split()]
                points=[(nums[i]*scale,nums[i+1]*scale) for i in range(0,len(nums),2)]
                if tag=='polygon':
                    points.append(points[0])
            draw.line(points,fill=color,width=width,joint='curve')
            for x,y in (points[0],points[-1]):
                r=width/2
                draw.ellipse((x-r,y-r,x+r,y+r),fill=color)
        elif tag=='rect':
            x,y=float(a.get('x',0))*scale,float(a.get('y',0))*scale
            w,h=float(a['width'])*scale,float(a['height'])*scale
            draw.rounded_rectangle((x,y,x+w,y+h),radius=float(a.get('rx',0))*scale,outline=color,width=width)
        elif tag in ('circle','ellipse'):
            x,y=float(a['cx'])*scale,float(a['cy'])*scale
            rx=float(a['r'] if tag=='circle' else a['rx'])*scale
            ry=float(a['r'] if tag=='circle' else a['ry'])*scale
            draw.ellipse((x-rx,y-ry,x+rx,y+ry),outline=color,width=width)
        else:
            raise ValueError(f'Unsupported SVG primitive: {tag}')
    image.resize((96,96),Image.Resampling.LANCZOS).save(target)

def fetch(url,path):
    if path.exists() and path.stat().st_size:
        return path.read_bytes()
    data=urllib.request.urlopen(url,timeout=30).read()
    path.write_bytes(data)
    return data

def main():
    directory=ROOT/'icons'
    directory.mkdir(parents=True,exist_ok=True)
    manifest={}
    base=f'https://raw.githubusercontent.com/lucide-icons/lucide/{VERSION}'
    for name in ICONS:
        url=f'{base}/icons/{name}.svg'
        data=fetch(url,directory/(name+'.svg'))
        render(data,directory/(name+'.png'))
        manifest[name]=dict(source=url,sha256=hashlib.sha256(data).hexdigest())
    fetch(base+'/LICENSE',ROOT/'LUCIDE-LICENSE.txt')
    original={
        'pull-up':'<path d="M3 3h18M7 3v5l5 4 5-4V3M12 12v5l-4 5M12 17l4 5"/><circle cx="12" cy="8" r="2"/>',
        'push-up':'<path d="M2 22h20M4 17l8-5 5 3v6M4 17l-1 4M12 12l4-1"/><circle cx="19" cy="9" r="2"/>',
        'running':'<circle cx="16" cy="4" r="2"/><path d="M13 8l-4 4-5-1M13 8l3 6 5 1M13 8l-2 7 4 3-2 4M11 15l-5 5H2"/>',
    }
    for name,geometry in original.items():
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{geometry}</svg>'
        (directory/(name+'.svg')).write_text(svg,encoding='utf-8')
        render(svg,directory/(name+'.png'))
        manifest[name]=dict(source='LifeOS original 24px / 2-unit rounded-stroke exercise pictogram',sha256=hashlib.sha256(svg.encode()).hexdigest())
    url='https://www.python.org/static/favicon.ico'
    python=fetch(url,ROOT/'python-logo.ico')
    # The official site favicon is the real, unmodified two-snake Python mark.
    Image.open(ROOT/'python-logo.ico').convert('RGBA').save(ROOT/'python-logo.png')
    manifest['python-logo']=dict(source=url,sha256=hashlib.sha256(python).hexdigest(),
        usage='Official Python logo, used only for Python solution editing. https://www.python.org/psf/trademarks/')
    app_icon=Image.new('RGBA',(256,256))
    draw=ImageDraw.Draw(app_icon)
    draw.rounded_rectangle((2,2,254,254),radius=54,fill='#20263b',outline='#58698d',width=3)
    mark=Image.open(directory/'layout-dashboard.png').convert('RGBA').resize((160,160),Image.Resampling.LANCZOS)
    colored=Image.new('RGBA',mark.size,'#a9baff')
    colored.putalpha(mark.getchannel('A'))
    app_icon.alpha_composite(colored,(48,48))
    app_icon.save(ROOT/'lifeos-icon.png')
    app_icon.save(ROOT/'lifeos.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    (ROOT/'icon-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(f'Fetched and rendered {len(ICONS)} pinned Lucide icons and the official Python logo.')

if __name__=='__main__':
    main()

"""Development-only download/grade step for locally bundled Unsplash photography.

Explicitly requested grayscale processing uses Pillow already installed by the
app. No personal records are read; the running app never invokes this script.
"""
import hashlib
import io
import json
import urllib.request
from datetime import date
from pathlib import Path
from PIL import Image,ImageOps

ROOT=Path(__file__).resolve().parents[1]/'lifeos'/'assets'/'backgrounds'
PHOTOS={
    'dashboard':('photo-1497215728101-856f4ea42174','Minimalist productivity workspace'),
    'dsa':('photo-1555066931-4365d14bab8c','Developer desk and code on a monitor'),
    'learning':('photo-1456513080510-7bf3a84b82f8','Books, notebook and laptop study workspace'),
    'research':('photo-1434030216411-0b793f4b4173','Research notes and computer workspace for NLP / ML'),
    'workout':('photo-1534438327276-14e5300c3a48','Gym equipment and training space'),
    'nutrition':('photo-1512621776951-a57141f2eefd','Balanced meal with vegetables and healthy food'),
    'planner':('photo-1506784365847-bbad939e9335','Calendar, notebook and pen'),
    'analytics':('photo-1551288049-bebda4e38f71','Computer display with charts and data'),
    'settings':('photo-1550684848-fac1c5b4e853','Subtle abstract material texture'),
}

def grade(image):
    image=ImageOps.exif_transpose(image)
    image=ImageOps.fit(image.convert('L'),(1600,1000),method=Image.Resampling.LANCZOS)
    image=ImageOps.autocontrast(image,cutoff=1)
    # One shared low-key, film-like curve; keep highlights and subjects visible.
    return image.point([round(8+196*(v/255)**1.08) for v in range(256)])

def main():
    original=ROOT/'originals'
    original.mkdir(parents=True,exist_ok=True)
    manifest={'license':'Unsplash License','license_url':'https://unsplash.com/license',
        'license_checked':date.today().isoformat(),
        'usage':'Bundled, transformed application backgrounds. Not sold as stock images or used to replicate a photo service.',
        'processing':'EXIF orientation; grayscale; 1600x1000 cover crop; 1% autocontrast; identical low-key tone curve (8..204); WebP quality 84. Runtime dark overlay is separate.',
        'photos':{}}
    for name,(identifier,subject) in PHOTOS.items():
        url=f'https://images.unsplash.com/{identifier}?auto=format&fit=crop&w=1800&q=88&fm=jpg'
        source=original/(name+'.jpg')
        if not source.exists():
            request=urllib.request.Request(url,headers={'User-Agent':'LifeOS-asset-preparation/1.0'})
            with urllib.request.urlopen(request,timeout=40) as response:
                data=response.read(10_000_000)
            Image.open(io.BytesIO(data)).verify()
            source.write_bytes(data)
        with Image.open(source) as image:
            graded=grade(image)
        target=ROOT/(name+'.webp')
        graded.save(target,'WEBP',quality=84,method=6)
        manifest['photos'][name]={'subject':subject,'source_url':url,'source_id':identifier,
            'original_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'processed_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
            'dimensions':list(graded.size),'original':'originals/'+source.name,'asset':target.name}
        print(name,round(target.stat().st_size/1024),'KiB',flush=True)
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (ROOT/'LICENSE.txt').write_text('Photography source: Unsplash\nLicense: https://unsplash.com/license\n\nThe Unsplash License permits downloading, modifying and using these photographs in this application, including local redistribution as application assets. Photos are not offered as an independent stock-photo collection. Source identifiers, download URLs and integrity hashes are recorded in manifest.json. Unmodified source downloads are preserved under originals/ for future regrading. No photo downloads occur at runtime.\n',encoding='utf-8')

if __name__=='__main__':
    main()

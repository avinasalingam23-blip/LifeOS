# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import json
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH)
datas = collect_data_files('customtkinter')
datas += [(str(root / 'lifeos' / 'schema.sql'), 'lifeos')]
datas += [(str(root / 'lifeos' / 'migration_2.sql'), 'lifeos')]
# Explicit licensed runtime assets only: never collect a project/profile tree.
assets = root / 'lifeos' / 'assets'
for name in ('lifeos.ico', 'lifeos-monochrome.ico', 'lifeos-icon.png',
             'python-logo.ico', 'python-logo.png', 'icon-manifest.json', 'LUCIDE-LICENSE.txt'):
    datas.append((str(assets / name), 'lifeos/assets'))
for name in json.loads((assets / 'icon-manifest.json').read_text(encoding='utf-8')):
    if name != 'python-logo':
        for extension in ('.png', '.svg'):
            datas.append((str(assets / 'icons' / (name + extension)), 'lifeos/assets/icons'))
backgrounds = assets / 'backgrounds'
manifest = json.loads((backgrounds / 'manifest.json').read_text(encoding='utf-8'))
for photo in manifest['photos'].values():
    datas.append((str(backgrounds / photo['asset']), 'lifeos/assets/backgrounds'))
for name in ('manifest.json', 'LICENSE.txt'):
    datas.append((str(backgrounds / name), 'lifeos/assets/backgrounds'))
a = Analysis(
    [str(root / 'main.py')],
    pathex=[str(root)], binaries=[], datas=datas,
    hiddenimports=['matplotlib.backends.backend_tkagg'],
    hookspath=[], hooksconfig={'matplotlib': {'backends': ['TkAgg']}},
    runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name='LifeOS', icon=str(assets / 'lifeos-monochrome.ico'),debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='LifeOS')

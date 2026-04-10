# -*- mode: python ; coding: utf-8 -*-

import os
onefile_mode = os.getenv("MN_ONEFILE") == "1"

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('Assets', 'Assets'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data)

if onefile_mode:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='TrayPilot',
        debug=False,
        strip=False,
        upx=True,
        console=False,
        icon=['Assets/app.ico'],
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        [],
        [],
        name='TrayPilot',
        debug=False,
        strip=False,
        upx=True,
        console=False,
        icon=['Assets/app.ico'],
        exclude_binaries=True,
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        name='TrayPilot'
    )


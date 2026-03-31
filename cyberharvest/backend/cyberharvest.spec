# -*- mode: python ; coding: utf-8 -*-
import os, sys
from PyInstaller.utils.hooks import collect_all

project_root = os.path.abspath(os.path.join(SPECPATH, '../..'))

datas = [
    (os.path.join(project_root, 'apps'), 'project/apps'),
    (os.path.join(project_root, 'core'), 'project/core'),
    (os.path.join(project_root, 'config'), 'project/config'),
    (os.path.join(project_root, 'ai_brain'), 'project/ai_brain'),
]

hiddenimports = [
    'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
    'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
    'uvicorn.lifespan', 'uvicorn.lifespan.on',
    'fastapi', 'pydantic', 'starlette',
    'apps.douyin.client', 'apps.douyin.features.search',
    'apps.douyin.features.collectors.video',
    'apps.douyin.neo4j_exporter',
    'core.adb_manager', 'core.device_controller',
    'config.settings',
]

a = Analysis(
    ['server.py'],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'scipy', 'pandas', 'numpy', 'pyarrow',
        'PIL', 'pytesseract', 'IPython', 'jupyter', 'notebook',
        'sklearn', 'tensorflow', 'torch', 'cv2',
        'tkinter', 'wx', 'PyQt5', 'PyQt6',
        'easyocr', 'test', 'tests',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas,
    name='cyberharvest-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    onefile=True,
)

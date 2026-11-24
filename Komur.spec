# -*- mode: python ; coding: utf-8 -*-
# Windows: tek dosya Komur.exe (Python veya kurulum gerektirmez).
# Derleme: pyinstaller --noconfirm Komur.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

_ROOT = Path(SPECPATH)
hiddenimports = sorted(
    p.stem for p in _ROOT.glob('*.py')
    if p.stem not in ('cat', 'generate_sounds', 'preview')
)
hiddenimports += collect_submodules('tkinter')

a = Analysis(
    [str(_ROOT / 'cat.py')],
    pathex=[str(_ROOT)],
    binaries=[],
    datas=[(str(_ROOT / 'assets'), 'assets'), (str(_ROOT / 'plugins'), 'plugins')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'transformers', 'pytest', 'matplotlib', 'pandas', 'faster_whisper', 'ctranslate2', 'onnxruntime'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Komur',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    version='version_info.txt',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

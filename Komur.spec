# -*- mode: python ; coding: utf-8 -*-
# Windows: tek dosya Komur.exe (Python veya kurulum gerektirmez).
# Derleme: pyinstaller --noconfirm Komur.spec
from pathlib import Path

_ROOT = Path(SPECPATH)
hiddenimports = sorted(
    p.stem for p in _ROOT.glob('*.py')
    if p.stem not in ('cat', 'generate_sounds', 'preview')
)
hiddenimports += [
    'tkinter', 'tkinter.ttk', 'tkinter.font', 'tkinter.simpledialog',
    'tkinter.messagebox', 'tkinter.filedialog',
]

# Yalnız Windows çalışma anında gereken sesler + .ico + 64px simge (.icns ve 805KB master PNG hariç)
_ASSET_EXTS = {'.wav', '.mp3'}
_ASSET_KEEP = {'komur.ico', 'komur_icon_64.png'}
_asset_datas = [
    (str(p), 'assets')
    for p in sorted((_ROOT / 'assets').iterdir())
    if p.is_file() and (p.suffix.lower() in _ASSET_EXTS or p.name in _ASSET_KEEP)
]

a = Analysis(
    [str(_ROOT / 'cat.py')],
    pathex=[str(_ROOT)],
    binaries=[],
    datas=_asset_datas + [(str(_ROOT / 'plugins'), 'plugins')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 'transformers', 'pytest', 'matplotlib', 'pandas',
        'faster_whisper', 'ctranslate2', 'onnxruntime',
        'unittest', 'pydoc', 'doctest', 'pdb', 'idlelib', 'turtle', 'turtledemo',
        'tkinter.test', 'tkinter.tix', 'ensurepip', 'venv', 'xmlrpc', 'curses',
    ],
    noarchive=False,
    optimize=0,
)
a.datas = [
    d for d in a.datas
    if not any(part in d[0].replace('\\', '/') for part in ('/demos/', '/tzdata/'))
]
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
    icon=str(_ROOT / 'assets' / 'komur.ico'),
    version='version_info.txt',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

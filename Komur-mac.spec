# -*- mode: python ; coding: utf-8 -*-
# macOS: çift tıklanan Kömür.app paketi (kurulum yok). Derleme: .venv/bin/pyinstaller Komur-mac.spec
from pathlib import Path

# Proje modüllerinin çoğu çalışma anında içe aktarılır; kullanılmayan/Windows-özel olanları hariç tut.
_ROOT = Path(SPECPATH)
_SKIP_MODS = {'cat', 'generate_sounds', 'preview'}
hiddenimports = sorted(p.stem for p in _ROOT.glob('*.py') if p.stem not in _SKIP_MODS)
hiddenimports += [
    'tkinter', 'tkinter.ttk', 'tkinter.font', 'tkinter.simpledialog',
    'tkinter.messagebox', 'tkinter.filedialog',
]

# Yalnız çalışma anında kullanılan sesler + 64px simge (1.4MB .icns ve 805KB master PNG kopyalanmaz)
_ASSET_EXTS = {'.wav', '.mp3'}
_ASSET_KEEP = {'komur_icon_64.png'}
_asset_datas = [
    (str(p), 'assets')
    for p in sorted((_ROOT / 'assets').iterdir())
    if p.is_file() and (p.suffix.lower() in _ASSET_EXTS or p.name in _ASSET_KEEP)
]

a = Analysis(
    [str(_ROOT / 'cat.py')],
    datas=_asset_datas + [(str(_ROOT / 'plugins'), 'plugins')],
    hiddenimports=hiddenimports,
    excludes=[
        'pytest', 'numpy', 'matplotlib', 'pandas', 'PIL',
        'unittest', 'pydoc', 'doctest', 'pdb', 'idlelib', 'turtle', 'turtledemo',
        'tkinter.test', 'tkinter.tix', 'ensurepip', 'venv', 'xmlrpc', 'curses',
    ],
)
# Tcl/Tk paketinden gereksiz demo ve yerel olmayan çeviri yığınlarını temizle
a.datas = [
    d for d in a.datas
    if not any(part in d[0].replace('\\', '/') for part in ('/demos/', '/tzdata/', '/encoding/'))
    or any(keep in d[0].replace('\\', '/') for keep in ('utf-8', 'ascii', 'cp1254', 'iso8859-9', 'macRoman'))
]
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='Kömür',
    console=False, argv_emulation=False,
    icon=str(_ROOT / 'assets' / 'komur.icns'),
)
coll = COLLECT(exe, a.binaries, a.datas, name='Kömür')
app = BUNDLE(
    coll,
    name='Kömür.app',
    icon=str(_ROOT / 'assets' / 'komur.icns'),
    bundle_identifier='com.sushikiddo.komur',
    info_plist={
        'CFBundleShortVersionString': '2.4.0',
        'CFBundleVersion': '2.4.0',
        'LSApplicationCategoryType': 'public.app-category.entertainment',
        'LSMinimumSystemVersion': '13.0',
        'LSUIElement': True,            # Dock'ta simge yok; kedi masaüstünde yaşar
        'NSHighResolutionCapable': True,
        'NSAppleEventsUsageDescription': 'Kömür, istediğin uygulamaları kapatmak ve sesi ayarlamak için kullanır.',
    },
)

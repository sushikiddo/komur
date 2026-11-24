# -*- mode: python ; coding: utf-8 -*-
# macOS: çift tıklanan Kömür.app paketi (kurulum yok). Derleme: .venv/bin/pyinstaller Komur-mac.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

# Proje modüllerinin çoğu çalışma anında içe aktarılır; hepsini pakete dahil et.
_ROOT = Path(SPECPATH)
hiddenimports = sorted(p.stem for p in _ROOT.glob('*.py') if p.stem not in ('cat', 'generate_sounds', 'preview'))
hiddenimports += collect_submodules('tkinter')

a = Analysis(
    [str(_ROOT / 'cat.py')],
    datas=[(str(_ROOT / 'assets'), 'assets'), (str(_ROOT / 'plugins'), 'plugins')],
    hiddenimports=hiddenimports,
    excludes=['pytest', 'numpy', 'matplotlib', 'pandas', 'PIL'],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Kömür', console=False, argv_emulation=False)
coll = COLLECT(exe, a.binaries, a.datas, name='Kömür')
app = BUNDLE(
    coll,
    name='Kömür.app',
    bundle_identifier='com.sushikiddo.komur',
    info_plist={
        'CFBundleShortVersionString': '2.3.0',
        'LSUIElement': True,            # Dock'ta simge yok; kedi masaüstünde yaşar
        'NSHighResolutionCapable': True,
        'NSAppleEventsUsageDescription': 'Kömür, istediğin uygulamaları kapatmak ve sesi ayarlamak için kullanır.',
    },
)

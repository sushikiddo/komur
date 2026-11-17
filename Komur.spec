# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

hiddenimports = ['sounds', 'physics_particles', 'effect_orchestrator', 'needs', 'skins', 'settings', 'autostart', 'tray', 'behavior', 'renderer', 'plugin_loader', 'intents', 'ai_backends', 'window_utils', 'companion', 'panel', 'settings_ui', 'awareness', 'focus', 'updater', 'update_ui', 'version', 'desktop_physics', 'procedural_anim', 'acoustic_engine', 'persona_dreams', 'gamification_productivity', 'context_hud']
hiddenimports += collect_submodules('tkinter')
hiddenimports += ['faster_whisper', 'sounddevice', 'ctranslate2', 'tokenizers', 'onnxruntime']


a = Analysis(
    ['cat.py'],
    pathex=[],
    binaries=collect_dynamic_libs('ctranslate2'),
    datas=[('assets', 'assets'), ('plugins', 'plugins')] + collect_data_files('faster_whisper'),
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'transformers', 'pytest', 'matplotlib', 'pandas'],
    noarchive=False,
    optimize=0,
)
# Speech recognition deliberately uses CPU int8; optional GPU/ASIO runtimes are unnecessary.
a.binaries = [entry for entry in a.binaries if not any(name in entry[0].lower() for name in ('asio', 'cudnn'))]
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

"""Master v2.0 integration tests verifying all 5 slices wired into DesktopCat,
settings, voice, and panel.
"""
from __future__ import annotations

import os
import sys
import threading
import types
import tkinter as tk
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cat
import panel
import settings
import voice


@pytest.fixture(scope="module")
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def desktop_app(tmp_path, monkeypatch, tk_root):
    """Create an isolated DesktopCat instance without touching user profile or OS tray."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(cat, "Tray", lambda tooltip="": types.SimpleNamespace(
        available=False, poll_show=lambda: False, poll_quit=lambda: False, close=lambda: None
    ))

    class FakeShortcut:
        def __init__(self):
            self.requested = threading.Event()
            self.boss_requested = threading.Event()
            self.registered = True

        def close(self):
            pass

    monkeypatch.setattr(cat, "PanelShortcut", FakeShortcut)

    win = tk.Toplevel(tk_root)
    win.withdraw()
    app = cat.DesktopCat(root=win)
    yield app
    if not app.closed:
        app.close()


def test_settings_v2_defaults():
    expected = {
        "persona": "asil_tembel",
        "retro_mode": False,
        "age_days": 7.0,
        "boss_key_mode": True,
        "meow_subtitles": True,
        "lofi_ambience": False,
        "affection_xp": 0,
        "affection_level": 1,
        "rubber_duck_mode": False,
    }
    for key, val in expected.items():
        assert key in settings.DEFAULTS
        assert settings.DEFAULTS[key] == val


def test_desktop_cat_initializes_all_v2_subsystems(desktop_app):
    for attr in (
        "physics",
        "acoustic",
        "hardware_mind",
        "dream_engine",
        "dev_bridge",
        "meow_translator",
        "rubber_duck",
        "affection",
        "fish_pond",
        "basket",
        "boss_key",
        "health_guard",
    ):
        assert getattr(desktop_app, attr) is not None, f"{attr} should be initialized"

    assert desktop_app.acoustic.purr is not None
    assert desktop_app.acoustic.keyboard is not None
    assert desktop_app.acoustic.lofi is not None
    assert desktop_app.acoustic.tts is not None
    assert desktop_app.acoustic.mic is not None


def test_main_loop_targets_60fps(desktop_app, monkeypatch):
    scheduled = []
    orig_after = desktop_app.root.after

    def spy_after(ms, func=None, *args):
        scheduled.append(ms)
        return orig_after(ms, func, *args) if func is not None else None

    monkeypatch.setattr(desktop_app.root, "after", spy_after)
    desktop_app._loop()
    assert 16 in scheduled


def test_slice1_retro_costumes_growth_and_companion_social(desktop_app, monkeypatch):
    # Retro mode toggle + new costumes draw cleanly
    assert desktop_app.toggle_retro_mode() is True
    assert desktop_app.settings.get("retro_mode") is True
    assert desktop_app.renderer.retro_enabled is True

    for costume in ("witch_hat", "winter_set", "cyberpunk_collar", "headphones"):
        desktop_app.settings.set("accessory", costume)
        desktop_app.renderer.accessory = costume
        desktop_app.renderer.draw(desktop_app.brain, 1.2)
        assert desktop_app.renderer.item_count > 10

    # Growth stage sync
    desktop_app.settings.set("age_days", 1.5)
    desktop_app._loop()
    assert desktop_app.brain.age_days == 1.5

    # Companions social step via step_companions with primary_cat
    called = []

    def fake_step_companions(companions, dt, pointer, primary_cat=None):
        called.append((list(companions), primary_cat))
        return ["mutual_groom"]

    monkeypatch.setattr(cat, "step_companions", fake_step_companions)
    fake_mate = types.SimpleNamespace(destroy=lambda: None, set_opacity=lambda v: None)
    desktop_app.companions = [fake_mate]
    desktop_app._loop()
    assert called and called[0][1] is desktop_app


def test_slice2_physics_props_and_menu(desktop_app):
    assert desktop_app.toggle_box_prop() is True
    assert any(p.kind == "box" for p in desktop_app.physics.props)
    assert desktop_app.toggle_laser() is True
    assert desktop_app.physics.chasing_laser is True

    desktop_app._step_v2_subsystems(0.016, (120, 140), 100.0)
    assert desktop_app.toggle_laser() is False
    assert desktop_app.toggle_box_prop() is False

    # Verify v2.0 submenu exists on right-click menu
    end_idx = desktop_app.menu.index("end")
    labels = [desktop_app.menu.entrycget(i, "label") for i in range(end_idx + 1)
              if desktop_app.menu.type(i) in ("command", "cascade")]
    assert "v2.0 Özellikler" in labels


def test_slice3_acoustic_and_voice_tts_hook(desktop_app, monkeypatch):
    # Keyboard reactive audio hook
    calls = []
    monkeypatch.setattr(cat.sound, "play", lambda name, enabled=True: calls.append(name))
    for _ in range(5):
        desktop_app._on_key_press(None)
    assert "chirp" in calls

    # Lofi toggle
    desktop_app.acoustic.lofi.start = MagicMock(return_value=True)
    desktop_app.acoustic.lofi.stop = MagicMock()
    assert desktop_app.toggle_lofi_ambience() is True
    assert desktop_app.settings.get("lofi_ambience") is True

    # VoiceService NaturalTurkishTTS hook + SAPI fallback preservation
    import acoustic_engine

    class FakeTTS:
        def __init__(self, speech_rate=0, sapi_fallback=None, **kwargs):
            self.sapi_fallback = sapi_fallback

        def speak_sync(self, text):
            return "edge-tts"

        def stop(self):
            pass

    monkeypatch.setattr(acoustic_engine, "NaturalTurkishTTS", FakeTTS)
    svc = voice.VoiceService()
    assert svc.speak("Merhaba Kömür") is True

    # Disabled natural_tts falls back to SAPI (and returns False when no Turkish token)
    monkeypatch.setattr(voice, "_turkish_voice_token", lambda: None)
    svc_off = voice.VoiceService(natural_tts=False)
    assert svc_off.speak("Merhaba") is False


def test_slice4_persona_dreams_rubber_duck_and_translator(desktop_app):
    assert desktop_app.toggle_rubber_duck() is True
    assert desktop_app.rubber_duck.active is True
    assert desktop_app.settings.get("rubber_duck_mode") is True

    reply = desktop_app.rubber_duck.process_message("bu kod neden çalışmıyor")
    assert reply["active"] is True and reply["question"]

    assert desktop_app.toggle_rubber_duck() is False
    assert desktop_app.rubber_duck.active is False

    dream = desktop_app.dream_engine.generate_dream(is_sleeping=True, force=True)
    assert dream and dream["dream_text"]

    subtitle = desktop_app.meow_translator.translate_meow("meow", state="idle")
    assert subtitle.startswith("Altyazı:")


def test_slice5_affection_basket_fish_boss_key_and_panel(desktop_app, monkeypatch):
    # Affection XP via commands and fish pond
    start_xp = desktop_app.affection.xp
    desktop_app.command("pet")
    desktop_app.command("feed")
    assert desktop_app.affection.xp == start_xp + 25
    assert f"({desktop_app.affection.xp} XP)" in desktop_app.affection_var.get()

    task = desktop_app.fish_pond.add_task("v2 entegrasyonunu tamamla")
    res = desktop_app.fish_pond.complete_task(task["id"])
    assert res["ok"] is True and res["caught"] is True
    assert desktop_app.affection.xp == start_xp + 50

    # CatBasketDropTarget file/URL drop
    drop_results = desktop_app._on_file_drop(["https://example.com/komur"])
    assert len(drop_results) == 1
    assert drop_results[0]["kind"] == "link"

    # Boss key via Ctrl+Shift+H when boss_key_mode=True
    desktop_app.settings.set("boss_key_mode", True)
    desktop_app.shortcut.boss_requested.set()
    desktop_app._poll_hotkey()
    assert desktop_app.boss_key.active is True
    assert desktop_app.hidden is True
    assert desktop_app.muted is True

    # Second toggle restores
    desktop_app.shortcut.boss_requested.set()
    desktop_app._poll_hotkey()
    assert desktop_app.boss_key.active is False
    assert desktop_app.hidden is False

    # Ctrl+Shift+K always opens the panel; Ctrl+Shift+H is ignored when boss_key_mode=False
    opened = []
    monkeypatch.setattr(desktop_app, "show_panel", lambda: opened.append(True))
    desktop_app.settings.set("boss_key_mode", False)
    desktop_app.shortcut.boss_requested.set()
    desktop_app._poll_hotkey()
    assert desktop_app.boss_key.active is False
    desktop_app.shortcut.requested.set()
    desktop_app._poll_hotkey()
    assert opened == [True]

    # Panel UI renders and callbacks work
    panel.show_panel(desktop_app)
    assert desktop_app.panel is not None and desktop_app.panel.winfo_exists()
    panel.on_accessory_change(desktop_app, "cyberpunk_collar")
    assert desktop_app.settings.get("accessory") == "cyberpunk_collar"
    panel.on_persona_change(desktop_app, "bilge_yazilimci")
    assert desktop_app.settings.get("persona") == "bilge_yazilimci"
    desktop_app.retro_var.set(True)
    panel.on_retro_change(desktop_app)
    assert desktop_app.settings.get("retro_mode") is True

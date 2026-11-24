"""Master v2.0 integration tests verifying all 5 slices wired into DesktopCat,
settings and panel.
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
        "meow_translator",
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
    assert desktop_app.toybox.has("box")
    assert desktop_app.toggle_laser() is True
    assert desktop_app.physics.chasing_laser is True

    desktop_app._step_v2_subsystems(0.016, (120, 140), 100.0)
    assert desktop_app.toggle_laser() is False
    assert desktop_app.toggle_box_prop() is False
    assert not desktop_app.toybox.has("box")

    # Verify v2.0 submenu exists on right-click menu
    end_idx = desktop_app.menu.index("end")
    labels = [desktop_app.menu.entrycget(i, "label") for i in range(end_idx + 1)
              if desktop_app.menu.type(i) in ("command", "cascade")]
    assert "v2.0 Özellikler" in labels




def test_slice4_persona_dreams_and_translator(desktop_app):
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
    if desktop_app.shortcut is None:      # global kısayol yalnız Windows'ta kaydedilir; yoklama mantığını yine sına
        desktop_app.shortcut = cat.PanelShortcut()
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
    panel.on_persona_change(desktop_app, "hiperaktif_yavru")
    assert desktop_app.settings.get("persona") == "hiperaktif_yavru"
    desktop_app.retro_var.set(True)
    panel.on_retro_change(desktop_app)
    assert desktop_app.settings.get("retro_mode") is True


def test_hud_cards_reach_v22_features(desktop_app, monkeypatch):
    """Sağ tık HUD'u yeni özelliklere gerçekten ulaşır (eski tk.Menu yalnız yedek)."""
    hud = desktop_app.context_hud
    assert hud is not None
    assert "clipboard" not in hud.action_buttons
    for key in ("yarn", "bowl", "post", "weather", "chat"):
        assert key in hud.action_buttons
    hud.action_buttons["yarn"].invoke()
    assert desktop_app.toybox.has("yarn")
    hud.action_buttons["yarn"].invoke()
    assert not desktop_app.toybox.has("yarn")
    asked = []
    monkeypatch.setattr(desktop_app, "choose_weather_city", lambda: asked.append("weather"))
    hud.action_buttons["weather"].invoke()
    assert asked == ["weather"]

import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from commands import CommandEngine
from behavior import Bounds, CatBrain
from pc_actions import PCActions, PendingAction
from settings import Settings


def test_dangerous_actions_wait_for_confirmation():
    calls = []
    actions = PCActions(runner=lambda *a: calls.append(a), resolver=lambda n: None,
                        startfile=lambda n: calls.append(n))
    for name, args in [("shutdown", {}), ("restart", {}), ("empty_recycle_bin", {}),
                       ("run_command", {"command": "echo test"}),
                       ("open_app", {"name": "unknown.bat"})]:
        assert isinstance(actions.execute(name, args), PendingAction)
    assert calls == []


def test_folder_action_cannot_launch_script(tmp_path):
    script = tmp_path / "script.bat"
    script.write_text("echo test")
    calls = []
    actions = PCActions(startfile=calls.append)
    actions.execute("open_folder", {"path_or_known": str(script)})
    assert not calls




def test_ball_gravity_pounce_and_sleep_recovery():
    brain = CatBrain(Bounds(0, 0, 800, 600), width=143, height=154, seed=1)
    brain.command("play")
    pounces = []
    for i in range(150):
        brain.step(.033)
        assert 0 <= brain.ball_x <= brain.width
        assert 0 <= brain.ball_y <= brain.height
        pounces.append(brain.pounce)
    assert max(pounces) > .8
    brain.energy = 10
    brain.command("sleep")
    for i in range(100):
        brain.step(.1)
    assert brain.energy > 29 and brain.state == "sleep"
    brain.command("wake")
    assert brain.state == "stretch"






def test_full_app_bubble_chat_and_all_poses(monkeypatch, tmp_path):
    import cat
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(cat.DesktopCat, "_register_hotkey", lambda self: None)
    monkeypatch.setattr(cat, "Tray", lambda **kwargs: SimpleNamespace(
        poll_show=lambda: False, poll_quit=lambda: False, close=lambda: None))
    monkeypatch.setattr(cat.Settings, "load", lambda: Settings({"sound": False}))
    app = cat.DesktopCat()
    try:
        assert (app.w, app.h) == (143, 154)
        text = "Türkçe uzun mesaj: " + "Kömür burada, işlerini birlikte yapabiliriz. " * 7
        app.say(text, 20)
        app._loop()
        app.root.update_idletasks()
        assert app.bubble.visible and app.bubble.text == text.strip()
        bbox = app.bubble.canvas.bbox("all")
        assert bbox is not None
        for state in ("wander", "sit", "look", "groom", "stretch", "sleep", "yawn", "play", "follow", "hiss", "knead", "sneeze", "chirp"):
            app.brain.state = state
            app.renderer.draw(app.brain, 1.2)
            assert app.renderer.item_count > 10
        app.assistant.show()
        assert app.assistant.compact_visible
        assert app.assistant.window is None
        app.assistant.show_history()
        app.assistant.entry.insert(0, "saat kaç")
        app.assistant.send()
        deadline = time.monotonic() + 5
        while app.assistant.busy and time.monotonic() < deadline:
            app.assistant.tick(time.monotonic())
            time.sleep(.01)
        assert not app.assistant.busy
        assert "Kömür:" in app.assistant.history.get("1.0", "end")
        assert app.assistant.commands.transcript
        app.assistant.request_behavior("roll")
        app.assistant.tick(time.monotonic())
        assert app.brain.state == "roll"
        app.assistant.request_behavior("bored")
        app.assistant.tick(time.monotonic())
        assert app.brain.state == "bored"
        app.assistant.request_behavior("yawn")
        app.assistant.tick(time.monotonic())
        assert app.brain.state == "yawn"
    finally:
        app.close()

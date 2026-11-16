import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai import CatAI
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


def test_api_uses_standard_messages_and_no_preview_fallback():
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(content=[{"type": "text", "text": "Merhaba!"}], stop_reason="end_turn")
    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    ai = CatAI(Settings({"ai_backend": "api", "ai_api_key": "test"}).get,
               PCActions(), lambda: "test", client_factory=lambda **kwargs: client)
    assert ai.respond("selam").reply == "Merhaba!"
    assert "fallbacks" not in calls[0] and "betas" not in calls[0]


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


def test_api_disconnect_after_action_does_not_repeat_via_fallback():
    calls = []
    def create(**kwargs):
        if calls:
            raise OSError("disconnected")
        return SimpleNamespace(content=[{"type": "tool_use", "id": "one", "name": "open_app",
                                         "input": {"name": "notepad"}}], stop_reason="tool_use")
    actions = PCActions(resolver=lambda name: ("exec", ["notepad.exe"]), popen=calls.append)
    ai = CatAI(Settings({"ai_backend": "api", "ai_api_key": "test"}).get, actions,
               lambda: "test", client_factory=lambda **kw: SimpleNamespace(messages=SimpleNamespace(create=create)))
    result = ai.respond("Bana bir yazı düzenleyici hazırlar mısın?")
    assert len(calls) == 1
    assert result.actions_done and result.error


def test_cli_error_result_falls_back_without_claiming_ai_connection():
    import subprocess
    ai = CatAI(Settings({"ai_backend": "cli"}).get, PCActions(), lambda: "test",
               which=lambda name: "claude.exe", cli_runner=lambda *a: subprocess.CompletedProcess(
                   [], 1, '{"is_error":true,"result":"session limit"}', ""))
    result = ai.respond("selam")
    assert result.backend != "Claude Code CLI"
    assert "session limit" in result.error


def test_full_app_bubble_chat_and_all_poses(monkeypatch, tmp_path):
    import cat
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(cat.DesktopCat, "_register_hotkey", lambda self: None)
    monkeypatch.setattr(cat, "Tray", lambda **kwargs: SimpleNamespace(
        poll_show=lambda: False, poll_quit=lambda: False, close=lambda: None))
    monkeypatch.setattr(cat.Settings, "load", lambda: Settings({"sound": False, "ai_backend": "offline"}))
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
        assert app.assistant.ai.transcript
        app.assistant.request_behavior("roll")
        app.assistant.tick(time.monotonic())
        assert app.brain.state == "roll"
        app.assistant.request_behavior("bored")
        app.assistant.tick(time.monotonic())
        assert app.brain.state == "bored"
        app.assistant.request_behavior("yawn")
        app.assistant.tick(time.monotonic())
        assert app.brain.state == "yawn"
        app.assistant.api_key.set("private-test-key")
        assert app.assistant.save_options()
        assert app.assistant.get_option("ai_openai_key") == "private-test-key"
        saved = (tmp_path / "Komur" / "settings.json").read_text(encoding="utf-8")
        assert "private-test-key" not in saved
        assert not app.assistant.api_key.get()
    finally:
        app.close()

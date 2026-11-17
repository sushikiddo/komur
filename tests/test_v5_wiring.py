import time

from test_v3_integration import app_factory  # noqa: F401  (gc.collect'li fixture)


def test_focus_chat_command_starts_stops_without_ai(app_factory):
    app = app_factory()
    ui = app.assistant
    sent = []
    ui.submit = lambda *a, **k: sent.append(a)
    assert ui.send_text("25 dakika odaklan")
    assert app.focus.phase == "work" and not sent
    assert "Pomodoro" in ui.chat_log[-1][1]
    assert ui.send_text("pomodoro bitir")
    assert app.focus.phase == "idle" and not sent


def test_focus_tick_shows_message_and_settles(app_factory):
    app = app_factory()
    app.start_focus(1, 1)
    app._tick_focus(time.monotonic())
    assert app.message == "Odak zamani! Ben kosede uyuyorum, sen calis."
    assert app.brain._sleep_requested
    app._tick_focus(time.monotonic() + 61)
    assert app.focus.phase == "break" and "Mola" in app.message


def test_wake_default_off_and_start_stop(app_factory):
    app = app_factory()
    ui = app.assistant
    assert app.settings.get("wake_word") is False
    calls = []
    ui.voice.start_wake_listener = lambda cb, **k: calls.append(("start", cb))
    ui.voice.stop_wake_listener = lambda: calls.append(("stop",))
    ui.start_wake()
    deadline = time.monotonic() + 3
    while not calls and time.monotonic() < deadline:
        time.sleep(.01)
    assert calls[0][0] == "start"
    ui.stop_wake()
    assert calls[-1] == ("stop",)


def test_on_wake_opens_chat_and_listens_once(app_factory):
    app = app_factory()
    ui = app.assistant
    app.settings.set("wake_word", True)
    started = []
    ui.submit = lambda *a, **k: started.append(a)
    ui.on_wake()
    assert ui.compact_visible and ui.listening and len(started) == 1
    ui.on_wake()
    assert len(started) == 1


def test_wake_error_is_shown_not_raised(app_factory):
    app = app_factory()
    ui = app.assistant
    app.settings.set("wake_word", True)
    ui.voice.wake_error = "Mikrofon bulunamadı."
    ui._poll_wake_errors()
    assert ("Ses", "Mikrofon bulunamadı.") in ui.chat_log


def test_habit_suggestion_throttled_and_gated(app_factory):
    app = app_factory()
    ui = app.assistant
    ui.ai.habit_suggestion = lambda: "Spotify açayım mı?"
    app.activity_reactions.current = "gaming"
    ui._habit_check = float("-inf")
    ui.tick(1000.0)
    assert app.message != "Spotify açayım mı?"
    app.activity_reactions.current = None
    app.brain._change("sit")
    ui._habit_check = float("-inf")
    ui.tick(2000.0)
    assert app.message == "Spotify açayım mı?"
    app.message = ""
    ui.tick(2100.0)
    assert app.message == ""


def test_accessory_activity_settings(app_factory):
    app = app_factory()
    ui = app.assistant
    ui.set_accessory("Şapka")
    assert app.settings.get("accessory") == "hat"
    ui.set_accessory("Yok")
    assert app.settings.get("accessory") is None
    ui.set_activity_level("Hareketli")
    assert app.settings.get("activity_level") == "hareketli" and app.brain.activity == "hareketli"

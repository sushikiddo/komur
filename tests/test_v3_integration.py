import gc
import json
import queue
import threading
import time
from types import SimpleNamespace

import pytest
from commands import CommandResult, CommandEngine
from pc_actions import PCActions, PendingAction
from memory_store import MemoryStore
from settings import Settings


@pytest.fixture
def app_factory(monkeypatch, tmp_path):
    import cat
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(cat.DesktopCat, "_register_hotkey", lambda self: None)
    monkeypatch.setattr(cat, "Tray", lambda **kw: SimpleNamespace(
        poll_show=lambda: False, poll_quit=lambda: False, close=lambda: None))
    monkeypatch.setattr(cat.Settings, "load", lambda: Settings({"sound": False, "ai_backend": "offline"}))
    apps = []
    def create():
        # Collect Tk objects of closed apps here, on the main thread; otherwise a
        # worker thread's GC may run tkinter Variable.__del__ and deadlock Tk.
        gc.collect()
        instance = cat.DesktopCat()
        apps.append(instance)
        return instance
    yield create
    for instance in apps:
        if not instance.closed:
            instance.close()
    apps.clear()
    gc.collect()


def finish(app, seconds=5):
    deadline = time.monotonic() + seconds
    while app.assistant.busy and time.monotonic() < deadline:
        app.assistant.tick(time.monotonic())
        time.sleep(.01)
    assert not app.assistant.busy


def test_compact_is_default_history_is_explicit_and_restart_remembers(app_factory):
    app = app_factory()
    ui = app.assistant
    app._on_speak_click()
    app.root.update_idletasks()
    assert ui.compact_visible and ui.window is None
    assert ui.compact.window.winfo_width() == ui.compact.WIDTH
    ui.compact.entry.insert(0, "bunu hatırla: Adım Özgür")
    ui.compact.send()
    finish(app)
    assert "Özgür" in ui.memory.context()
    assert "Özgür" in ui.compact.messages.get("1.0", "end")
    ui.show_history()
    app.root.update_idletasks()
    assert not ui.compact_visible
    assert "Özgür" in ui.history.get("1.0", "end")
    ui.actions.execute("set_timer", {"minutes": 1, "label": "Mola"})
    app.close()
    app2 = app_factory()
    assert "Özgür" in app2.assistant.memory.context()
    assert app2.assistant.chat_log
    assert app2.assistant.actions.timers[0]["label"] == "Mola"
    assert app2.assistant.memory.messages(query="özgür")


def test_confirmation_keeps_turn_locked_and_executes_once(app_factory, monkeypatch):
    import assistant_ui
    app = app_factory()
    ui = app.assistant
    calls = []
    def approve(*args, **kwargs):
        assert ui.busy
        assert not ui.send_text("not defterini aç")
        return True
    monkeypatch.setattr(assistant_ui.messagebox, "askyesno", approve)
    monkeypatch.setattr(ui.commands, "confirm", lambda pending: calls.append(pending.name) or "Onaylandı")
    ui.set_busy(True)
    ui.events.put(("reply", CommandResult("Onay bekliyor", needs_confirmation=[PendingAction("shutdown", {}, "Test onayı")])) )
    ui.tick(time.monotonic())
    finish(app)
    assert calls == ["shutdown"]






def test_recurring_reminder_restores_and_can_be_cancelled(app_factory):
    app = app_factory()
    app.assistant.recurring_reminder(30, 'Mola')
    reminder_id = app.assistant.memory.pending_reminders()[0]['id']
    app.close()
    restored = app_factory()
    assert any(timer.get('memory_id') == reminder_id for timer in restored.assistant.actions.timers)
    restored.assistant.cancel_reminder(reminder_id)
    assert not restored.assistant.memory.pending_reminders()
    assert not restored.assistant.actions.timers










def test_clear_history_locked_and_reminder_cancellation_persists(app_factory, monkeypatch):
    import assistant_ui
    app = app_factory()
    ui = app.assistant
    ui.show_history()
    ui.memory.remember("Örnek not")
    ui.actions.execute("set_timer", {"minutes": 3, "label": "Örnek hatırlatma"})
    def approve(*args, **kwargs):
        assert ui.busy
        assert not ui.send_text("saat kaç")
        return True
    monkeypatch.setattr(assistant_ui.messagebox, "askyesno", approve)
    ui.clear_history()
    assert not ui.memory.notes() and not ui.memory.messages()
    assert ui.memory.pending_reminders()
    ui.set_busy(True)
    ui.history_enabled.set(False)
    ui.set_history_enabled()
    ui.append("Sen", "Bu yeni mesaj kaydedilmemeli")
    assert not ui.memory.messages()
    ui.set_busy(False)
    ui.clear_reminders()
    assert not ui.actions.timers and not ui.memory.pending_reminders()

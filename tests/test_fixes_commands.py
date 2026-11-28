import queue
import sqlite3
import types

import pytest

import assistant_ui
from assistant_ui import AssistantUI
from intents import parse_intent


def name(text):
    result = parse_intent(text)
    return result[0] if result else None


# -- 1/2: restart / shutdown only target the computer
def test_app_restart_is_not_computer_restart():
    assert name("Spotify'ı yeniden başlat") != "restart"
    assert name("chrome yeniden başlat") != "restart"


@pytest.mark.parametrize("text", ["yeniden başlat", "restart", "bilgisayarı yeniden başlat", "pc'yi yeniden başlat"])
def test_computer_restart_still_works(text):
    assert name(text) == "restart"


def test_restart_keeps_delay():
    assert parse_intent("bilgisayarı 5 dakika sonra yeniden başlat")[1]["minutes"] == 5


def test_app_close_on_computer_is_not_shutdown():
    intent = parse_intent("bilgisayarda chrome'u kapat")
    assert intent[0] == "close_app" and intent[1]["name"] == "chrome"


@pytest.mark.parametrize("text", ["bilgisayarı kapat", "pc'yi kapat", "kapat bilgisayarı"])
def test_computer_shutdown_still_works(text):
    assert name(text) == "shutdown"


def test_shutdown_keeps_delay():
    assert parse_intent("bilgisayarı 10 dakika sonra kapat") == ("shutdown", {"minutes": 10}, "")


# -- 3: command prefixes need word boundaries
@pytest.mark.parametrize("text", ["cmdline ls", "powershellx dir", "cmdx ls"])
def test_command_prefix_needs_boundary(text):
    assert name(text) != "run_command"


@pytest.mark.parametrize("text,cmd", [("cmd ls", "ls"), ("cmd'de dir", "dir"), ("cmd: ls -la", "ls -la"),
                                      ("powershell Get-Date", "Get-Date"), ("komut çalıştır ls", "ls")])
def test_command_prefix_still_works(text, cmd):
    assert parse_intent(text) == ("run_command", {"command": cmd}, "")


# -- 4: timer label before the time
def test_timer_label_before_time():
    assert parse_intent("çay demle diye 5 dakika sonra hatırlat")[1] == {"minutes": 5.0, "label": "çay demle"}


def test_timer_label_uppercase_icin():
    assert parse_intent("ÇAY DEMLE İÇİN 5 dakika sonra hatırlat")[1]["label"] == "ÇAY DEMLE"


def test_timer_label_after_time_and_default():
    assert parse_intent("5 dakika sonra çay demle diye hatırlat")[1]["label"] == "çay demle"
    assert parse_intent("10 dakika sonra hatırlat")[1]["label"] == "Süre doldu!"


# -- 5/6: UI robustness
class _Ui:
    def __init__(self):
        self.busy = True
        self.busy_log = []
        self.closed = False
        self.compact_visible = False
        self.behavior_requests = queue.Queue()
        self.events = queue.Queue()
        self.updates = None
        self.memory = None
        self._habit_check = 0
        self.log = []
        self.submitted = []
        self.app = types.SimpleNamespace(
            settings={}, brain=types.SimpleNamespace(state="idle"), message_until=0,
            say=lambda *a: None, say_unsolicited=lambda *a: None, command=lambda *a: None)
        self.actions = types.SimpleNamespace(timers=[])
        self.commands = types.SimpleNamespace(habit_suggestion=lambda: None)

    def set_busy(self, value):
        self.busy = value
        self.busy_log.append(value)

    def append(self, speaker, text):
        self.log.append((speaker, text))

    def submit(self, *a, **k):
        self.submitted.append(a)


def _reply(n=1):
    pending = [types.SimpleNamespace(description=f"p{i}") for i in range(n)]
    return types.SimpleNamespace(reply="tamam", needs_confirmation=pending, remaining_actions=None)


def test_approval_exception_unlocks_input(caplog):
    ui = _Ui()
    ui.approve_action = lambda pending: (_ for _ in ()).throw(RuntimeError("dialog failed"))
    ui.events.put(("reply", _reply()))
    AssistantUI.tick(ui, 100)
    assert ui.busy is False
    assert "Approval flow failed" in caplog.text


def test_reminder_db_error_does_not_abort_tick(caplog):
    ui = _Ui()
    ui.busy = False

    def boom(_id):
        raise sqlite3.OperationalError("database is locked")

    ui.memory = types.SimpleNamespace(complete_reminder=boom)
    ui.actions.timers = [{"due": 0, "label": "su ic", "memory_id": 7}]
    ui.events.put(("reply", types.SimpleNamespace(reply="x", needs_confirmation=[], remaining_actions=None)))
    AssistantUI.tick(ui, 100)  # must not raise; rest of tick (event handling) still runs
    assert ("Kömür", "x") in ui.log
    assert any(t["memory_id"] == 7 for t in ui.actions.timers)  # reminder kept for retry
    assert "Could not complete reminder" in caplog.text

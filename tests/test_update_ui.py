import time

import update_ui
import updater


class FakeSettings(dict):
    def set(self, key, value):
        self[key] = value


class FakeApp:
    def __init__(self, **settings):
        self.settings = FakeSettings(settings)
        self.said, self.closed = [], False

    def say(self, text, seconds):
        self.said.append(text)

    def close(self):
        self.closed = True


INFO = updater.UpdateInfo("9.9.9", "notlar", "https://github.com/x.exe", "https://github.com/x.exe.sha256", 1024)


def drain(flow, seconds=2):
    deadline = time.monotonic() + seconds
    while flow.busy and time.monotonic() < deadline:
        time.sleep(.01)
    flow.poll(now=0)


def test_manual_check_announces_new_version(monkeypatch):
    monkeypatch.setattr(updater, "check_latest", lambda: INFO)
    app = FakeApp()
    flow = update_ui.UpdateFlow(app, started=0)
    flow.check()
    drain(flow)
    assert flow.info is INFO and "9.9.9" in app.said[-1] and "9.9.9" in flow.status
    assert app.settings["update_last_check"] > 0  # set only after success


def test_silent_startup_check_respects_setting_and_daily_limit(monkeypatch):
    calls = []
    monkeypatch.setattr(updater, "check_latest", lambda: calls.append(1))
    flow = update_ui.UpdateFlow(FakeApp(update_check=False), started=0)
    flow.poll(now=update_ui.STARTUP_DELAY + 1)
    assert not calls and not flow.busy
    flow = update_ui.UpdateFlow(FakeApp(update_last_check=time.time()), started=0)
    flow.poll(now=update_ui.STARTUP_DELAY + 1)
    assert not calls


def test_silent_failure_stays_quiet(monkeypatch):
    def boom():
        raise OSError("offline")
    monkeypatch.setattr(updater, "check_latest", boom)
    app = FakeApp()
    flow = update_ui.UpdateFlow(app, started=0)
    flow.check(silent=True)
    drain(flow)
    assert not app.said and "hatası" in flow.status


def test_install_requires_confirmation_then_launches_and_closes(monkeypatch, tmp_path):
    launched = []
    monkeypatch.setattr(updater, "download_verified", lambda info, dest: tmp_path / "setup.exe")
    monkeypatch.setattr(updater, "launch_installer", launched.append)
    app = FakeApp()
    flow = update_ui.UpdateFlow(app, started=0)
    flow.info = INFO
    monkeypatch.setattr(update_ui.messagebox, "askyesno", lambda *a: False)
    flow.install()
    assert not flow.busy and not launched
    monkeypatch.setattr(update_ui.messagebox, "askyesno", lambda *a: True)
    flow.install()
    drain(flow)
    assert launched == [tmp_path / "setup.exe"] and app.closed


def test_failed_check_does_not_suppress_next_days_check(monkeypatch):
    def boom():
        raise OSError("offline")
    monkeypatch.setattr(updater, "check_latest", boom)
    app = FakeApp()
    flow = update_ui.UpdateFlow(app, started=0)
    flow.check(silent=True)
    drain(flow)
    assert "update_last_check" not in app.settings

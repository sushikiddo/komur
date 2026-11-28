import plistlib
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import acoustic_engine
import audio
import autostart
import pc_actions
import steam_actions


def _engine(tmp_path):
    eng = acoustic_engine.LofiAmbiencePlayer() if hasattr(acoustic_engine, "LofiAmbiencePlayer") else None
    return eng


def _find_engine_class():
    for name in dir(acoustic_engine):
        obj = getattr(acoustic_engine, name)
        if isinstance(obj, type) and hasattr(obj, "_afplay_loop"):
            return obj
    raise RuntimeError("engine class not found")


def test_afplay_loop_backs_off_and_stops_on_fast_failures(tmp_path):
    cls = _find_engine_class()
    eng = cls()
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"x")
    eng._playing = True
    eng._afplay_gen = 1
    proc = MagicMock()
    proc.wait.return_value = 1
    with patch.object(acoustic_engine.subprocess, "Popen", return_value=proc) as popen, \
            patch.object(acoustic_engine.time, "sleep"):
        eng._afplay_loop("/usr/bin/afplay", str(wav), 1)
    assert popen.call_count == 3
    assert eng._playing is False
    assert not wav.exists()


def test_afplay_loop_exits_when_generation_changes(tmp_path):
    cls = _find_engine_class()
    eng = cls()
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"x")
    eng._playing = True
    eng._afplay_gen = 2   # stop()+start() happened; this loop is generation 1
    with patch.object(acoustic_engine.subprocess, "Popen") as popen:
        eng._afplay_loop("/usr/bin/afplay", str(wav), 1)
    popen.assert_not_called()


def test_play_wav_bytes_caps_concurrency_and_cleans_up(tmp_path):
    made = []
    proc = MagicMock()
    proc.wait.side_effect = subprocess.TimeoutExpired("afplay", 6)
    real_ntf = audio.tempfile.NamedTemporaryFile

    def ntf(*a, **k):
        f = real_ntf(*a, dir=str(tmp_path), **k)
        made.append(f.name)
        return f

    with patch.object(audio, "AFPLAY", "/usr/bin/afplay"), \
            patch.object(audio.tempfile, "NamedTemporaryFile", ntf), \
            patch.object(audio.subprocess, "Popen", return_value=proc):
        audio.play_wav_bytes(b"RIFF")
    proc.kill.assert_called_once()
    assert made and not Path(made[0]).exists()
    # all slots taken -> dropped silently
    held = [audio._AFPLAY_SLOTS.acquire(blocking=False) for _ in range(3)]
    try:
        with patch.object(audio, "AFPLAY", "/usr/bin/afplay"), \
                patch.object(audio.subprocess, "Popen") as popen:
            audio.play_wav_bytes(b"RIFF")
        popen.assert_not_called()
    finally:
        for ok in held:
            if ok:
                audio._AFPLAY_SLOTS.release()


def test_mac_set_volume_reports_failure():
    runner = lambda argv, t=0: SimpleNamespace(returncode=1, stdout="", stderr="boom")
    with patch.object(pc_actions, "IS_MAC", True):
        pc = pc_actions.PCActions(runner=runner)
        assert "ayarlanamadı" in pc.set_volume(30)
        ok = pc_actions.PCActions(runner=lambda a, t=0: SimpleNamespace(returncode=0, stdout="", stderr=""))
        assert "%30" in ok.set_volume(30)


def test_default_run_prepends_homebrew_path_on_mac():
    captured = {}

    class FakeProc:
        pid = 1

        def wait(self, timeout=None):
            return 0

    def fake_popen(argv, **kw):
        captured.update(kw)
        return FakeProc()

    with patch.object(pc_actions, "IS_WINDOWS", False), patch.object(pc_actions.sys, "platform", "darwin"), \
            patch.object(pc_actions.subprocess, "Popen", fake_popen):
        pc_actions._default_run(["/bin/zsh", "-c", "true"], 5)
    assert captured["env"]["PATH"].startswith("/opt/homebrew/bin")
    assert captured["start_new_session"] is True


def test_default_run_does_not_block_on_backgrounded_child():
    if sys.platform == "win32":
        pytest.skip("posix only")
    start = time.monotonic()
    proc = pc_actions._default_run(["/bin/sh", "-c", "sleep 5 & echo hi"], 20)
    assert time.monotonic() - start < 4
    assert proc.stdout.strip() == "hi"


def test_mac_force_close_uses_cfbundleexecutable(tmp_path):
    app = tmp_path / "Visual Studio Code.app" / "Contents"
    app.mkdir(parents=True)
    with (app / "Info.plist").open("wb") as fh:
        plistlib.dump({"CFBundleExecutable": "Electron"}, fh)
    assert pc_actions._mac_executable_name(str(app.parent), "Visual Studio Code") == "Electron"
    calls = []

    def runner(argv, t=0):
        calls.append(argv)
        return SimpleNamespace(returncode=0 if argv[1:2] == ["-x"] and argv[2] == "Electron" else 1,
                               stdout="", stderr="")

    with patch.object(pc_actions, "IS_MAC", True), \
            patch.object(pc_actions, "_mac_app_bundle_path", return_value=str(app.parent)):
        pc = pc_actions.PCActions(runner=runner, resolver=lambda n: ("exec", ["open", "-a", "Visual Studio Code"]))
        assert "zorla kapatıldı" in pc._close_mac_app("vscode", True)
    assert ["pkill", "-x", "Electron"] in calls


def test_steam_mac_root_and_pgrep(tmp_path):
    with patch.object(steam_actions.sys, "platform", "darwin"), \
            patch.object(steam_actions.Path, "home", return_value=tmp_path):
        roots = steam_actions.steam_roots()
        assert tmp_path / "Library" / "Application Support" / "Steam" in roots
        seen = []

        def runner(argv, t=0):
            seen.append(argv)
            return SimpleNamespace(returncode=0, stdout="123", stderr="")

        assert steam_actions.process_running(730, runner) is True
    assert seen[0][0] == "pgrep"


def test_autostart_requires_existing_executable_and_resyncs(tmp_path):
    plist = tmp_path / "x.plist"
    with patch.object(autostart, "_MAC", True), patch.object(autostart, "mac_plist_path", return_value=plist):
        assert autostart.is_enabled() is False
        with plist.open("wb") as fh:
            plistlib.dump({"ProgramArguments": ["/nonexistent/komur"]}, fh)
        assert autostart.is_enabled() is False
        exe = tmp_path / "Komur"
        exe.write_text("x")
        with patch.object(autostart.sys, "frozen", True, create=True), \
                patch.object(autostart.sys, "executable", str(exe)):
            assert autostart.is_enabled() is True
            with plist.open("rb") as fh:
                assert plistlib.load(fh)["ProgramArguments"] == [str(exe)]


def test_activity_poll_samples_appkit_on_calling_thread():
    import activity_reactions as ar
    names = []
    with patch.object(ar.sys, "platform", "darwin"), \
            patch.object(ar, "_mac_running_app_names", side_effect=lambda: names.append(threading.current_thread()) or set()), \
            patch.object(ar, "get_foreground_info", side_effect=lambda: names.append(threading.current_thread()) or {}), \
            patch.object(ar, "_is_fullscreen", side_effect=lambda: names.append(threading.current_thread()) or False), \
            patch.object(ar, "idle_seconds", return_value=0.0), \
            patch.object(ar, "mic_in_use_apps", return_value=set()):
        mon = ar.ActivityReactions(media_client=SimpleNamespace(query=lambda: [], close=lambda: None)) \
            if hasattr(ar, "ActivityReactions") else None
        if mon is None:
            pytest.skip("monitor class not found")
        mon.poll(now=100.0)
        mon._worker.join(3)
    assert names and all(t is threading.main_thread() or t is threading.current_thread() for t in names)

import json
import os

from dev_bridge import DevBridge


def _repo(tmp_path):
    (tmp_path / ".git" / "logs").mkdir(parents=True)
    head = tmp_path / ".git" / "logs" / "HEAD"
    head.write_text("0 a1 U <u@x> 100 +0000\tcommit: ilk\n", encoding="utf-8")
    cache = tmp_path / ".pytest_cache" / "v" / "cache"
    cache.mkdir(parents=True)
    return head, cache / "lastfailed"


def _write(path, data, stamp):
    path.write_text(json.dumps(data), encoding="utf-8")
    os.utime(path, (stamp, stamp))


def test_commit_and_test_transitions(tmp_path):
    head, lastfailed = _repo(tmp_path)
    _write(lastfailed, {}, 1000)
    bridge = DevBridge(tmp_path)
    assert bridge.poll() == []                         # açılış durumu tepki üretmez

    with head.open("a", encoding="utf-8") as f:
        f.write("a1 b2 U <u@x> 200 +0000\tcommit: yeni\n")
    assert [e["command"] for e in bridge.poll()] == ["dance"]
    assert bridge.poll() == []

    _write(lastfailed, {"t::a": True, "t::b": True}, 2000)
    [event] = bridge.poll()
    assert event["command"] == "hiss" and "2 test" in event["message"]

    _write(lastfailed, {}, 3000)
    assert [e["command"] for e in bridge.poll()] == ["chirp"]


def test_no_repo_is_silent(tmp_path):
    bridge = DevBridge(tmp_path)
    assert bridge.root is None and bridge.poll() == []
    assert bridge.set_repo(tmp_path) is False

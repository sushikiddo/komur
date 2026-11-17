import hashlib
import io
import json

import pytest

import updater
from updater import UpdateError, UpdateInfo


@pytest.fixture(autouse=True)
def _installed_version(monkeypatch):
    # Fixtures below describe a v1.2.0 release; pin the "installed" version so the
    # tests do not depend on the app's current APP_VERSION.
    monkeypatch.setattr(updater, "APP_VERSION", "1.1.0")

EXE = "https://github.com/sushikiddo/komur/releases/download/v1.2.0/Komur-Setup-1.2.0-x64.exe"
SHA = EXE + ".sha256"


def release(tag="v1.2.0", **kw):
    d = {"tag_name": tag, "draft": False, "prerelease": False, "body": "x" * 900,
         "assets": [{"name": "Komur-Setup-1.2.0-x64.exe", "browser_download_url": EXE, "size": 5},
                    {"name": "Komur-Setup-1.2.0-x64.exe.sha256", "browser_download_url": SHA, "size": 90}]}
    d.update(kw)
    return d


def fetch_of(d):
    return lambda url: json.dumps(d).encode()


def test_check_newer_and_notes_truncated():
    info = updater.check_latest(fetch_of(release()))
    assert info.version == "1.2.0" and len(info.notes) == 500 and info.installer_url == EXE


def test_check_same_older_draft_prerelease_missing_asset():
    assert updater.check_latest(fetch_of(release("v1.1.0"))) is None
    assert updater.check_latest(fetch_of(release("v1.0.9"))) is None
    assert updater.check_latest(fetch_of(release(draft=True))) is None
    assert updater.check_latest(fetch_of(release(prerelease=True))) is None
    assert updater.check_latest(fetch_of(release(assets=release()["assets"][:1]))) is None
    assert updater.check_latest(fetch_of(release("banana"))) is None


def test_check_network_error_and_bad_host():
    def boom(url):
        raise OSError("down")
    assert updater.check_latest(boom) is None
    bad = release()
    bad["assets"][0]["browser_download_url"] = "https://evil.example/x.exe"
    assert updater.check_latest(fetch_of(bad)) is None


def test_numeric_compare():
    assert updater._is_newer(updater.parse_version("1.10.0"), updater.parse_version("1.9.0"))
    assert not updater._is_newer(updater.parse_version("1.1"), updater.parse_version("1.1.0"))


def test_should_check():
    assert updater.should_check(None, 1000)
    assert not updater.should_check(1000, 1000 + 3600)
    assert updater.should_check(1000, 1000 + 86400)
    assert updater.should_check(5000, 1000)  # saat geri alindi


class Resp(io.BytesIO):
    def __init__(self, data, url, length=None):
        super().__init__(data)
        self._url = url
        self.headers = {"Content-Length": str(len(data) if length is None else length)}

    def geturl(self):
        return self._url


def make_open(payload, sha_text, exe_url=EXE, length=None):
    def op(url, headers, timeout):
        if url == SHA:
            return Resp(sha_text.encode(), SHA)
        return Resp(payload, exe_url, length)
    return op


INFO = UpdateInfo("1.2.0", "", EXE, SHA, 5)


def test_download_ok(tmp_path):
    data = b"hello-installer"
    h = hashlib.sha256(data).hexdigest()
    seen = []
    p = updater.download_verified(INFO, tmp_path, lambda a, b: seen.append(a),
                                  make_open(data, f"{h}  Komur-Setup-1.2.0-x64.exe\n"))
    assert p.read_bytes() == data and seen and not list(tmp_path.glob("*.part"))


def test_download_hash_mismatch_deletes(tmp_path):
    with pytest.raises(UpdateError, match="dogrulanamadi"):
        updater.download_verified(INFO, tmp_path, None, make_open(b"abc", "0" * 64))
    assert list(tmp_path.iterdir()) == []


def test_download_rejects_redirect_and_http_and_size(tmp_path):
    h = hashlib.sha256(b"abc").hexdigest()
    with pytest.raises(UpdateError):
        updater.download_verified(INFO, tmp_path, None,
                                  make_open(b"abc", h, exe_url="https://evil.example/a.exe"))
    with pytest.raises(UpdateError):
        updater.download_verified(UpdateInfo("1.2.0", "", "http://github.com/a", SHA, 1), tmp_path)
    with pytest.raises(UpdateError):
        updater.download_verified(INFO, tmp_path, None,
                                  make_open(b"abc", h, length=updater.MAX_INSTALLER_BYTES + 1))
    assert list(tmp_path.iterdir()) == []


def test_launch_installer(tmp_path):
    f = tmp_path / "s.exe"
    f.write_bytes(b"x")
    calls = []
    updater.launch_installer(f, popen=lambda *a, **k: calls.append(a))
    assert calls == [([str(f)],)]  # /SILENT yok
    with pytest.raises(UpdateError):
        updater.launch_installer(tmp_path / "yok.exe", popen=lambda *a, **k: None)

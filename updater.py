"""GitHub Releases uzerinden guncelleme denetimi (GUI'den bagimsiz).

Yalnizca sabit GET istekleri yapilir; kullanici verisi gonderilmez. Hicbir sey
otomatik indirilmez veya kurulmaz: cagiran, kullanici onayindan sonra
download_verified ve launch_installer'i ayri ayri cagirir.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from version import APP_VERSION

REPO = "sushikiddo/komur"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
ALLOWED_HOSTS = {"github.com", "objects.githubusercontent.com",
                 "release-assets.githubusercontent.com"}
MAX_INSTALLER_BYTES = 300 * 1024 * 1024
MAX_JSON_BYTES = 2 * 1024 * 1024
TIMEOUT = 10
CHECK_INTERVAL = 24 * 3600
NOTES_LIMIT = 500


class UpdateError(Exception):
    """Kullaniciya gosterilebilir Turkce hata mesaji tasir."""


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    notes: str
    installer_url: str
    sha256_url: str
    size: int


def parse_version(text: str) -> tuple[int, ...] | None:
    m = re.fullmatch(r"v?(\d+(?:\.\d+){0,3})", (text or "").strip())
    if not m:
        return None
    return tuple(int(p) for p in m.group(1).split("."))


def _is_newer(a: tuple[int, ...], b: tuple[int, ...]) -> bool:
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def _host_ok(url: str, hosts=ALLOWED_HOSTS) -> bool:
    p = urlparse(url)
    return p.scheme == "https" and (p.hostname or "").lower() in hosts


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _host_ok(newurl):
            raise UpdateError("Yonlendirme izin verilmeyen bir adrese gidiyor.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _default_open(url: str, headers: dict, timeout: float):
    opener = urllib.request.build_opener(_CheckedRedirect)
    return opener.open(urllib.request.Request(url, headers=headers), timeout=timeout)


def _default_fetch(url: str) -> bytes:
    headers = {"User-Agent": "Komur-Updater", "Accept": "application/vnd.github+json"}
    with _default_open(url, headers, TIMEOUT) as r:
        return r.read(MAX_JSON_BYTES + 1)


def check_latest(fetch: Callable[[str], bytes] | None = None) -> UpdateInfo | None:
    """Daha yeni surum varsa UpdateInfo, yoksa/hata varsa None doner."""
    try:
        data = json.loads((fetch or _default_fetch)(LATEST_URL))
        if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
            return None
        ver = parse_version(str(data.get("tag_name", "")))
        cur = parse_version(APP_VERSION)
        if ver is None or cur is None or not _is_newer(ver, cur):
            return None
        vs = ".".join(map(str, ver))
        name = f"Komur-Setup-{vs}-x64.exe"
        assets = {a.get("name"): a for a in data.get("assets") or [] if isinstance(a, dict)}
        exe, sha = assets.get(name), assets.get(name + ".sha256")
        if not exe or not sha:
            return None
        exe_url, sha_url = exe.get("browser_download_url"), sha.get("browser_download_url")
        if not (isinstance(exe_url, str) and isinstance(sha_url, str)
                and _host_ok(exe_url) and _host_ok(sha_url)):
            return None
        size = exe.get("size")
        notes = str(data.get("body") or "")[:NOTES_LIMIT]
        return UpdateInfo(vs, notes, exe_url, sha_url, size if isinstance(size, int) else 0)
    except (OSError, ValueError, UpdateError):
        return None


def should_check(last_check_ts: float | None, now: float) -> bool:
    if not last_check_ts or last_check_ts > now:
        return True
    return now - last_check_ts >= CHECK_INTERVAL


def _parse_sha256(text: str, filename: str) -> str:
    for line in text.splitlines():
        m = re.match(r"^\s*([0-9a-fA-F]{64})\b\s*\*?(.*)$", line)
        if m:
            other = m.group(2).strip()
            if not other or other == filename:
                return m.group(1).lower()
    raise UpdateError("Ozet (sha256) dosyasi okunamadi.")


def download_verified(info: UpdateInfo, dest_dir, progress: Callable[[int, int], None] | None = None,
                      open_url: Callable | None = None) -> Path:
    opener = open_url or _default_open
    headers = {"User-Agent": "Komur-Updater"}
    for url in (info.installer_url, info.sha256_url):
        if not _host_ok(url):
            raise UpdateError("Indirme adresi guvenilir degil.")

    def opened(url):
        r = opener(url, headers, 30)
        final_url = r.geturl() if hasattr(r, "geturl") else url
        if not _host_ok(final_url):
            r.close()
            raise UpdateError("Indirme izin verilmeyen bir adrese yonlendirildi.")
        return r

    try:
        with opened(info.sha256_url) as r:
            expected = _parse_sha256(r.read(4096).decode("utf-8", "replace"),
                                     f"Komur-Setup-{info.version}-x64.exe")
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        final = dest / f"Komur-Setup-{info.version}-x64.exe"
        tmp = final.with_name(final.name + ".part")
        digest = hashlib.sha256()
        received = 0
        try:
            with opened(info.installer_url) as r, tmp.open("wb") as out:
                total = int(r.headers.get("Content-Length") or 0) if getattr(r, "headers", None) else 0
                if total > MAX_INSTALLER_BYTES:
                    raise UpdateError("Kurulum dosyasi beklenenden buyuk.")
                while True:
                    block = r.read(256 * 1024)
                    if not block:
                        break
                    received += len(block)
                    if received > MAX_INSTALLER_BYTES:
                        raise UpdateError("Kurulum dosyasi beklenenden buyuk.")
                    digest.update(block)
                    out.write(block)
                    if progress:
                        progress(received, total)
            if digest.hexdigest() != expected:
                raise UpdateError("Indirilen dosya dogrulanamadi (ozet uyusmuyor); silindi.")
            os.replace(tmp, final)
            return final
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    except UpdateError:
        raise
    except OSError as exc:
        raise UpdateError(f"Guncelleme indirilemedi: {exc}") from exc


def launch_installer(path, popen: Callable = subprocess.Popen) -> None:
    """Normal Inno Setup sihirbazini baslatir (sessiz degil); cagiran uygulama kapanmalidir."""
    p = Path(path)
    if not p.is_file():
        raise UpdateError("Kurulum dosyasi bulunamadi.")
    popen([str(p)], close_fds=True)

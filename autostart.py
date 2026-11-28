"""Oturum açılınca başlatma: Windows'ta kullanıcı Run kayıt defteri anahtarı, macOS'ta LaunchAgent.

Windows: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\\Komur.
macOS:   ~/Library/LaunchAgents/com.sushikiddo.komur.plist (bir sonraki oturum açılışında devreye girer).
Başka platformlarda etkisizdir. Arayüze asla hata fırlatmaz.
"""
from __future__ import annotations
import logging
import os
import plistlib
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Komur"
MAC_LABEL = "com.sushikiddo.komur"

_WINDOWS = sys.platform == "win32"
_MAC = sys.platform == "darwin"
try:
    import winreg  # type: ignore
except Exception:  # pragma: no cover - non-Windows
    winreg = None
    _WINDOWS = False


def available():
    return (_WINDOWS and winreg is not None) or _MAC


def _argv():
    # When frozen (PyInstaller) sys.executable is the app itself; otherwise run
    # this script through the interpreter.
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, os.path.abspath(sys.argv[0])]


def _command():
    return " ".join(f'"{part}"' for part in _argv())


def mac_plist_path():
    return Path.home() / "Library" / "LaunchAgents" / f"{MAC_LABEL}.plist"


def _mac_enabled():
    path = mac_plist_path()
    try:
        with path.open("rb") as handle:
            data = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException, ValueError):
        return False
    args = data.get("ProgramArguments") if isinstance(data, dict) else None
    if not args or not isinstance(args, list):
        return False
    if getattr(sys, "frozen", False) and args != _argv():
        # Paket taşınmış/güncellenmiş: kaydı mevcut çalıştırılabilire eşitle.
        try:
            _set_mac(True)
            return True
        except OSError:
            logging.exception("Could not re-sync autostart plist")
    return os.path.exists(str(args[0]))


def is_enabled():
    if _MAC:
        return _mac_enabled()
    if not available():
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value)
    except OSError:
        return False


def _set_mac(enabled):
    path = mac_plist_path()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as handle:
            plistlib.dump({"Label": MAC_LABEL, "ProgramArguments": _argv(), "RunAtLoad": True,
                           "ProcessType": "Interactive"}, handle)
        return True
    path.unlink(missing_ok=True)
    return False


def set_enabled(enabled):
    """Add or remove the startup entry. Returns the resulting state (best effort)."""
    if not available():
        return False
    try:
        if _MAC:
            return _set_mac(enabled)
        if enabled:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _command())
            return True
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
        return False
    except OSError:
        logging.exception("Could not update autostart entry")
        return is_enabled()

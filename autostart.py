"""Launch-with-Windows via the per-user Run registry key (winreg, stdlib).

Writes HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\\Komur pointing at
the current executable. No-op and safe off Windows. Never raises into the UI.
"""
from __future__ import annotations
import logging
import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Komur"

_WINDOWS = sys.platform == "win32"
try:
    import winreg  # type: ignore
except Exception:  # pragma: no cover - non-Windows
    winreg = None
    _WINDOWS = False


def available():
    return _WINDOWS and winreg is not None


def _command():
    # When frozen (PyInstaller) sys.executable is the app itself; otherwise run
    # this script through the interpreter.
    exe = sys.executable
    if getattr(sys, "frozen", False):
        return f'"{exe}"'
    import os
    script = os.path.abspath(sys.argv[0])
    return f'"{exe}" "{script}"'


def is_enabled():
    if not available():
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value)
    except OSError:
        return False


def set_enabled(enabled):
    """Add or remove the Run entry. Returns the resulting state (best effort)."""
    if not available():
        return False
    try:
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

"""Read-only, local application health checks for the settings UI."""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
from urllib.error import URLError
from urllib.request import urlopen

from local_models import MODEL_PROFILES
from settings import config_dir

OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"


def _ram_gb():
    """Return installed physical memory on Windows, or None elsewhere/on failure."""
    if os.name != "nt":
        return None

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    try:
        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return status.ullTotalPhys / (1024 ** 3)
    except (AttributeError, OSError, TypeError):
        return None


def _ollama_installed():
    if shutil.which("ollama"):
        return True
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(["sc.exe", "query", "Ollama"], capture_output=True,
                                text=True, timeout=1, check=False,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return result.returncode == 0 and "SERVICE_NAME" in result.stdout.upper()
    except (OSError, subprocess.TimeoutExpired):
        return False


def _ollama_tags():
    """Return installed model names if the local Ollama endpoint answers quickly."""
    try:
        with urlopen(OLLAMA_TAGS_URL, timeout=1) as response:
            payload = json.loads(response.read(1024 * 1024).decode("utf-8"))
        models = payload.get("models", []) if isinstance(payload, dict) else []
        return [str(item.get("name", "")) for item in models
                if isinstance(item, dict) and item.get("name")]
    except (OSError, ValueError, TypeError, URLError):
        return None


def _existing_path(path):
    path = Path(path)
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def health_report(voice=None):
    """Return concise Turkish health lines without changing local machine state."""
    lines = []
    ram = _ram_gb()
    if ram is None:
        lines.append("Bellek: ölçülemedi; model önerisi için sistem bilgisi kullanılamıyor.")
    else:
        lines.append(f"Bellek: {ram:.1f} GB RAM.")
        suitable = [profile["label"] for profile in MODEL_PROFILES.values()
                    if ram >= profile["min_ram_gb"]]
        if suitable:
            lines.append("Yerel model önerisi: " + suitable[-1] + ".")
        else:
            light = min(MODEL_PROFILES.values(), key=lambda profile: profile["min_ram_gb"])
            lines.append("Yerel model önerisi: " + light["label"] + "; yanıtlar yavaş olabilir.")

    installed = _ollama_installed()
    tags = _ollama_tags()
    if tags is not None:
        lines.append("Ollama: çalışıyor; " + (f"{len(tags)} yerel model bulundu." if tags else "model listesi boş."))
    elif installed:
        lines.append("Ollama: kurulu, ancak yerel hizmet yanıt vermiyor.")
    else:
        lines.append("Ollama: kurulu görünmüyor; yerel hizmet yanıt vermiyor.")

    try:
        usage = shutil.disk_usage(_existing_path(config_dir()))
        lines.append(f"Disk: {usage.free / (1024 ** 3):.1f} GB boş alan.")
    except (OSError, ValueError):
        lines.append("Disk: boş alan bilgisi alınamadı.")

    if voice is not None:
        try:
            status = voice.status()
            if isinstance(status, dict):
                for key in ("stt_message", "tts_message", "microphone_message"):
                    message = status.get(key)
                    if message:
                        lines.append("Ses: " + str(message))
        except Exception:
            lines.append("Ses: durum bilgisi alınamadı.")
    return lines

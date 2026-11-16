"""Start the installed local Ollama service; never download or call a cloud AI."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request


def service_ready():
    try:
        # Ignore proxy environment settings for this fixed loopback endpoint.
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                "http://127.0.0.1:11434/api/tags", timeout=1) as response:
            return isinstance(json.loads(response.read(262144)), dict)
    except (OSError, ValueError):
        return False


def ensure_local_service():
    if service_ready():
        return
    executable = shutil.which("ollama")
    if not executable:
        candidate = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Ollama/ollama.exe"
        if candidate.is_file():
            executable = str(candidate)
    if not executable:
        raise RuntimeError("Yerel AI için Ollama kurulu değil. KULLANIM-AI.md dosyasını aç.")
    environment = os.environ.copy()
    environment.update(OLLAMA_HOST="127.0.0.1:11434", OLLAMA_NO_CLOUD="1",
                       OLLAMA_CONTEXT_LENGTH="8192", OLLAMA_KEEP_ALIVE="60s")
    subprocess.Popen([executable, "serve"], env=environment, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=0x08000000 if os.name == "nt" else 0)
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if service_ready():
            return
        time.sleep(.2)
    raise RuntimeError("Ollama başlayamadı. Yerel AI bağlantısını kontrol et.")

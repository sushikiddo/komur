"""Optional, consent-based Ollama setup wizard for the Windows distribution.

This file is also usable as a small CLI library by the installer build. It never
installs software or downloads a model until the user presses the matching button.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable

APP_NAME = "Komur"
MODEL = "qwen2.5:7b"
MODEL_BYTES_ESTIMATE = 6 * 1024**3
from local_models import MODEL_PROFILES
VOICE_REPOSITORY = "Systran/faster-whisper-small"
VOICE_REVISION = "536b0662742c02347bc0e980a01041f333bce120"
VOICE_MODEL_SHA256 = "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671"
VOICE_FILES = {"config.json": 2370, "tokenizer.json": 2203239,
               "vocabulary.txt": 459861, "model.bin": 483546902}
OLLAMA_INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"


def validate_manifest(manifest: Iterable[dict]) -> list[tuple[str, str]]:
    """Validate bundled-file manifest; return (source, relative target) pairs.

    Manifest entries may use `source` plus `target`; paths are relative to the
    distribution root and target paths may never escape the install directory.
    """
    result = []
    seen = set()
    for item in manifest:
        source, target = item.get("source"), item.get("target")
        if not isinstance(source, str) or not isinstance(target, str):
            raise ValueError("Manifest entries require string source and target")
        src = PurePosixPath(source.replace("\\", "/"))
        dst = PurePosixPath(target.replace("\\", "/"))
        if src.is_absolute() or ".." in src.parts or dst.is_absolute() or ".." in dst.parts:
            raise ValueError("Manifest paths must stay inside their root")
        key = str(dst).casefold()
        if key in seen:
            raise ValueError(f"Duplicate target: {target}")
        seen.add(key)
        result.append((str(src), str(dst)))
    return result


def stage_files(source_root: Path, install_root: Path, manifest: Iterable[dict]) -> list[Path]:
    """Copy declared files without overwriting existing files or escaping target."""
    pairs = validate_manifest(manifest)
    source_root, install_root = source_root.resolve(), install_root.resolve()
    copied = []
    for source, relative in pairs:
        src = (source_root / source).resolve()
        dst = (install_root / Path(relative)).resolve()
        if not src.is_relative_to(source_root):
            raise ValueError("Source escaped distribution root")
        if not dst.is_relative_to(install_root):
            raise ValueError("Target escaped installation directory")
        if not src.is_file():
            raise FileNotFoundError(src)
        if dst.exists():
            raise FileExistsError(f"Refusing to overwrite existing file: {dst}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


def environment_report() -> dict:
    """Hardware/storage preflight. Conservative estimates; does not reserve space."""
    system = platform.system()
    machine = platform.machine().lower()
    supported_arch = machine in ("amd64", "x86_64")
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    try:
        free = shutil.disk_usage(local).free
    except OSError:
        free = 0
    try:
        import ctypes
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("memory_load", ctypes.c_ulong),
                        ("total_phys", ctypes.c_ulonglong), ("avail_phys", ctypes.c_ulonglong),
                        ("total_page", ctypes.c_ulonglong), ("avail_page", ctypes.c_ulonglong),
                        ("total_virtual", ctypes.c_ulonglong), ("avail_virtual", ctypes.c_ulonglong),
                        ("avail_extended", ctypes.c_ulonglong)]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        ram = status.total_phys
    except Exception:
        ram = 0
    try:
        windows_10_or_later = system == "Windows" and sys.getwindowsversion().major >= 10
    except AttributeError:
        windows_10_or_later = system == "Windows"
    return {"windows": windows_10_or_later, "supported_arch": supported_arch,
            "free_bytes": free, "ram_bytes": ram,
            "ai_ready_storage": free >= MODEL_BYTES_ESTIMATE,
            "ai_hardware_note": "Qwen 7B needs several GB of disk and works best with 8 GB+ RAM."}


def recommended_model_for_ram(ram_gb: float) -> str:
    return "qwen3:4b" if ram_gb < 12 else "qwen2.5:7b"


def meets_ram_recommendation(ram_gb: float, minimum_gb: float) -> bool:
    # Windows may report an 8 GB DIMM as about 7.8 GiB; allow a small reporting margin.
    return ram_gb + 0.5 >= minimum_gb


def verify_authenticode(path: Path) -> tuple[bool, str]:
    """Accept only a valid Windows Authenticode signature with Ollama in publisher."""
    if os.name != "nt":
        return False, "Ollama setup requires Windows Authenticode verification."
    command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
               "$s=Get-AuthenticodeSignature -LiteralPath $args[0]; "
               "if ($s.Status -eq 'Valid' -and $s.SignerCertificate.Subject -match 'Ollama') "
               "{ 'OK|' + $s.SignerCertificate.Subject } else { 'BAD|' + $s.Status + '|' + $s.SignerCertificate.Subject }"]
    result = subprocess.run(command + [str(path)], capture_output=True, text=True, timeout=30)
    line = (result.stdout or "").strip().splitlines()
    if result.returncode == 0 and line and line[-1].startswith("OK|"):
        return True, line[-1][3:]
    return False, (line[-1] if line else result.stderr.strip() or "No valid Ollama signature found.")


def download_verified_ollama(progress: Callable[[int, int], None] | None = None) -> Path:
    """Download official HTTPS bootstrapper to a temporary file and verify signer."""
    request = urllib.request.Request(OLLAMA_INSTALLER_URL, headers={"User-Agent": "KomurSetup/1"})
    with urllib.request.urlopen(request, timeout=40) as response:
        if not response.geturl().lower().startswith("https://"):
            raise RuntimeError("Ollama installer download did not remain on HTTPS")
        total = int(response.headers.get("Content-Length") or 0)
        fd, filename = tempfile.mkstemp(prefix="Komur-Ollama-", suffix=".exe")
        os.close(fd)
        path = Path(filename)
        received = 0
        try:
            with path.open("wb") as out:
                while True:
                    block = response.read(1024 * 256)
                    if not block:
                        break
                    out.write(block)
                    received += len(block)
                    if progress:
                        progress(received, total)
            valid, detail = verify_authenticode(path)
            if not valid:
                raise RuntimeError(f"Ollama installer signature check failed: {detail}")
            return path
        except Exception:
            path.unlink(missing_ok=True)
            raise


def ollama_executable() -> Path | None:
    found = shutil.which("ollama")
    if found:
        return Path(found)
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    for candidate in (local / "Programs/Ollama/ollama.exe", Path("C:/Program Files/Ollama/ollama.exe")):
        if candidate.is_file():
            return candidate
    return None


def pull_model(executable: Path, progress: Callable[[str], None]) -> None:
    """Pull the configured model with live Ollama status output."""
    pull_model_profile(executable, MODEL, progress)


def pull_model_profile(executable: Path, model: str, progress: Callable[[str], None]) -> None:
    proc = subprocess.Popen([str(executable), "pull", model], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    assert proc.stdout is not None
    for line in proc.stdout:
        progress(line.rstrip())
    if proc.wait() != 0:
        raise RuntimeError("Ollama could not download the model. Check the connection and try again.")


def save_local_model_choice(model: str, settings_path: Path | None = None) -> None:
    """Set only local AI routing keys while preserving all existing settings."""
    path = settings_path or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Komur" / "settings.json"
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RuntimeError("Existing settings could not be read; they were left unchanged.") from exc
        if not isinstance(data, dict):
            raise RuntimeError("Existing settings are not a JSON object; they were left unchanged.")
    data["ai_local_model"] = model
    data["ai_backend"] = "local"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="settings-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.replace(temp_name, path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise


def download_voice_model(progress: Callable[[str, int, int], None] | None = None,
                         cancelled: threading.Event | None = None,
                         model_dir: Path | None = None) -> Path:
    """Download a pinned Whisper snapshot, verify its complete manifest, then publish."""
    cancelled = cancelled or threading.Event()
    base = Path(model_dir) if model_dir else Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Komur/models/faster-whisper-small"
    existing_model = base / "model.bin"
    if existing_model.is_file():
        digest = hashlib.sha256()
        with existing_model.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() == VOICE_MODEL_SHA256 and all((base / name).is_file() for name in VOICE_FILES):
            return base
    base.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=base.name + ".download-", dir=base.parent))
    total_all = sum(VOICE_FILES.values())
    received_all = 0
    try:
        for filename, expected_size in VOICE_FILES.items():
            if cancelled.is_set():
                raise InterruptedError("Ses modeli indirmesi iptal edildi.")
            url = f"https://huggingface.co/{VOICE_REPOSITORY}/resolve/{VOICE_REVISION}/{filename}?download=true"
            req = urllib.request.Request(url, headers={"User-Agent": "KomurSetup/1"})
            with urllib.request.urlopen(req, timeout=40) as response:
                if not response.geturl().lower().startswith("https://"):
                    raise RuntimeError("Ses modeli aktarımı HTTPS dışında yönlendirildi.")
                destination = stage / filename
                got_file = 0
                with destination.open("wb") as out:
                    while True:
                        if cancelled.is_set():
                            raise InterruptedError("Ses modeli indirmesi iptal edildi.")
                        data = response.read(256 * 1024)
                        if not data:
                            break
                        out.write(data)
                        got_file += len(data)
                        received_all += len(data)
                        if progress:
                            progress(filename, received_all, total_all)
                if got_file != expected_size:
                    raise RuntimeError(f"Dosya boyutu doğrulanamadı: {filename}")
                if filename == "model.bin":
                    digest = hashlib.sha256()
                    with destination.open("rb") as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(chunk)
                    if digest.hexdigest() != VOICE_MODEL_SHA256:
                        raise RuntimeError("Ses modeli SHA-256 doğrulaması başarısız oldu.")
        if base.exists():
            raise FileExistsError(f"Model hedefi zaten var; mevcut dosyalar korunuyor: {base}")
        stage.replace(base)
        return base
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise




def launch_wizard() -> None:
    """Localized UI with serialized setup jobs and a direct offline launch path."""
    import tkinter as tk
    from tkinter import messagebox, ttk

    root = tk.Tk()
    root.title("K\u00f6m\u00fcr - Kurulum Yard\u0131mc\u0131s\u0131")
    root.geometry("790x650")
    root.minsize(700, 590)
    report = environment_report()
    ram_gb = report["ram_bytes"] / 1024**3
    model_keys = list(MODEL_PROFILES)
    recommended = recommended_model_for_ram(ram_gb)
    if recommended not in model_keys:
        recommended = model_keys[0]
    model_var = tk.StringVar(value=recommended)
    text = tk.StringVar(value=(
        "Temel/çevrimdışı özellikler bu indirmeler olmadan kullanılabilir. Yerel sohbet isteğe bağlıdır; Ollama ve model yalnızca siz istediğinizde indirilir.\n\n"
        f"Windows 10+ x64: {'uygun' if report['windows'] and report['supported_arch'] else 'gereklidir'}\n"
        f"Boş disk alanı: {report['free_bytes'] / 1024**3:.1f} GB. RAM: {ram_gb:.1f} GB."
    ))
    ttk.Label(root, text="Kömür Kurulum Yardımcısı", font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=20, pady=(18, 8))
    ttk.Label(root, textvariable=text, wraplength=740, justify="left").pack(fill="x", padx=20, pady=8)
    model_row = ttk.Frame(root)
    model_row.pack(fill="x", padx=20, pady=4)
    ttk.Label(model_row, text="Yerel model:").pack(side="left")
    model_picker = ttk.Combobox(model_row, textvariable=model_var, values=model_keys, state="readonly", width=22)
    model_picker.pack(side="left", padx=8)
    model_note = tk.StringVar()
    ttk.Label(model_row, textvariable=model_note).pack(side="left", padx=8)
    ttk.Label(root, text=(
        "Türkçe seslendirme için Windows Türkçe sesi (Tolga/OneCore veya SAPI) gerekir. Ses modeli Windows konuşma sesini kurmaz. "
        "Tolga yoksa Ayarlar > Saat ve Dil > Dil ve Bölge > Türkçe > Dil seçenekleri > Konuşma yolundan Türkçe konuşma bileşenini yükleyin."
    ), wraplength=740, justify="left").pack(fill="x", padx=20, pady=(8, 4))
    bar = ttk.Progressbar(root, mode="determinate", maximum=100)
    bar.pack(fill="x", padx=20, pady=8)
    status = tk.StringVar(value="")
    ttk.Label(root, textvariable=status, wraplength=740).pack(fill="x", padx=20)

    model_buttons = ttk.Frame(root)
    model_buttons.pack(fill="x", padx=20, pady=(12, 4))
    voice_buttons = ttk.Frame(root)
    voice_buttons.pack(fill="x", padx=20, pady=4)
    launch_buttons = ttk.Frame(root)
    launch_buttons.pack(fill="x", padx=20, pady=(12, 16))
    ollama_button = ttk.Button(model_buttons, text="Ollama'yı indir ve kur")
    ollama_button.pack(side="left")
    model_button = ttk.Button(model_buttons, text="Seçili modeli indir")
    model_button.pack(side="left", padx=8)
    voice_button = ttk.Button(voice_buttons, text="Ses tanımayı kur")
    voice_button.pack(side="left")
    cancel_button = ttk.Button(voice_buttons, text="Ses indirmesini iptal et")
    cancel_button.pack(side="left", padx=8)
    language_button = ttk.Button(voice_buttons, text="Windows dil ayarlarını aç",
                                 command=lambda: os.startfile("ms-settings:regionlanguage"))
    language_button.pack(side="left", padx=8)
    launch_button = ttk.Button(launch_buttons, text="Temel / çevrimdışı modu başlat")
    launch_button.pack(side="left")
    ttk.Button(launch_buttons, text="Kömür'ü aç", command=lambda: start_app()).pack(side="left", padx=8)
    ttk.Button(launch_buttons, text="Kapat", command=lambda: close()).pack(side="right")

    voice_cancel = threading.Event()
    alive = threading.Event()
    alive.set()
    busy = {"value": False}
    actions = [ollama_button, model_button, voice_button, language_button, launch_button]

    def safe_after(callback):
        if alive.is_set():
            try:
                root.after(0, callback)
            except tk.TclError:
                pass

    def close():
        alive.clear()
        voice_cancel.set()
        root.destroy()

    def start_app():
        app = Path(sys.executable).with_name("Komur.exe") if getattr(sys, "frozen", False) else Path(__file__).with_name("Komur.exe")
        if not app.is_file():
            messagebox.showerror("Kömür bulunamadı", f"Program dosyası bulunamadı:\n{app}")
            return
        subprocess.Popen([str(app)], close_fds=True)
        close()

    def start_job(fn, *, voice=False):
        if busy["value"]:
            return False
        busy["value"] = True
        for button in actions:
            button.state(["disabled"])
        model_picker.state(["disabled"])
        bar.stop()
        bar.configure(mode="determinate", maximum=100, value=0)
        cancel_button.state(["!disabled"] if voice else ["disabled"])
        if voice:
            voice_cancel.clear()

        def finish():
            busy["value"] = False
            for button in actions:
                button.state(["!disabled"])
            model_picker.state(["!disabled"])
            cancel_button.state(["disabled"])

        def run():
            try:
                fn()
            except InterruptedError as exc:
                message = str(exc)
                safe_after(lambda message=message: status.set(message))
            except Exception as exc:
                error = str(exc)
                safe_after(lambda error=error: (status.set(error), messagebox.showerror("Kurulum tamamlanamadı", error)))
            finally:
                safe_after(finish)
        threading.Thread(target=run, daemon=True).start()
        return True

    def select_profile():
        key = model_var.get()
        profile = MODEL_PROFILES[key]
        suitable = meets_ram_recommendation(ram_gb, profile["min_ram_gb"])
        recommendation = "Önerilen" if suitable else "Yavaş olabilir; temel mod kullanılabilir"
        model_note.set(f"{profile['label']} - yaklaşık {profile['download_gb']:g} GB - {recommendation}")
        return key, profile

    def install_ollama_job():
        safe_after(lambda: status.set("Ollama yükleyicisi HTTPS üzerinden indiriliyor; imza denetleniyor..."))
        installer = download_verified_ollama(lambda got, total: safe_after(lambda: bar.configure(value=got * 100 / total if total else 0)))
        safe_after(lambda: status.set("İmza doğrulandı. Ollama yükleyicisi açılıyor; adımları tamamlayın."))
        subprocess.Popen([str(installer)], close_fds=True)
        safe_after(lambda: status.set("Yükleyici açıldı. Tamamlanınca seçili modeli indirin."))

    def install_model():
        executable = ollama_executable()
        if not executable:
            messagebox.showinfo("Ollama gerekli", "Önce Ollama'yı indirip kurun.")
            return
        key, profile = select_profile()
        required = int((profile["download_gb"] + 0.5) * 1024**3)
        local = Path(os.environ.get("LOCALAPPDATA", Path.home()))
        if shutil.disk_usage(local).free < required and not messagebox.askyesno(
                "Disk alanı az", f"Yaklaşık {profile['download_gb']:g} GB gerekir. Yine de devam edilsin mi?"):
            return
        warning = "\n\n4 GB RAM'de temel mod önerilir; yerel AI yavaş olabilir." if ram_gb < 6 else ""
        if not meets_ram_recommendation(ram_gb, profile["min_ram_gb"]):
            warning = f"\n\nBu model en az {profile['min_ram_gb']} GB RAM için önerilir; bu bilgisayarda yavaş çalışabilir." + warning
        if not messagebox.askyesno("Model indirme onayı", f"Ollama ile {key} ({profile['download_gb']:g} GB) indirilip kurulsun mu? Yerel sohbet bu modele ayarlanacak.{warning}"):
            return

        def pull_and_select():
            safe_after(lambda: status.set(f"{key} indiriliyor; ilerleme durumu aşağıda görünecek..."))
            def progress(line):
                match = re.search(r"(\d{1,3})%", line)
                if match:
                    value = max(0, min(100, int(match.group(1))))
                    safe_after(lambda: bar.configure(value=value))
                safe_after(lambda: status.set(line))
            pull_model_profile(executable, key, progress)
            save_local_model_choice(key)
            safe_after(lambda: (status.set(f"{key} hazır ve yerel sohbet için seçildi."), messagebox.showinfo("Hazır", f"{key} kuruldu ve seçildi.")))
        start_job(pull_and_select)

    def install_voice():
        local = Path(os.environ.get("LOCALAPPDATA", Path.home()))
        if shutil.disk_usage(local).free < 700 * 1024**2:
            messagebox.showerror("Disk alanı az", "Ses modeli için en az 700 MB boş alan gerekir.")
            return
        if not messagebox.askyesno("Ses modeli indirilsin mi?", "Systran faster-whisper-small modeli yaklaşık 486 MB yer kaplar. %LOCALAPPDATA%\\Komur\\models klasörüne indirilir; indirmeyi iptal edebilirsiniz. Devam edilsin mi?"):
            return

        def download_voice():
            def progress(name, received, total):
                safe_after(lambda: (bar.configure(value=received * 100 / total), status.set(f"{name}: {received / 1024**2:.0f} / {total / 1024**2:.0f} MB")))
            path = download_voice_model(progress, voice_cancel)
            safe_after(lambda: (bar.configure(value=100), status.set(f"Ses modeli hazır: {path}"), messagebox.showinfo("Hazır", "Çevrimdışı ses tanıma modeli kuruldu.")))
        start_job(download_voice, voice=True)

    model_picker.bind("<<ComboboxSelected>>", lambda _event: select_profile())
    select_profile()
    ollama_button.configure(command=lambda: start_job(install_ollama_job))
    model_button.configure(command=install_model)
    voice_button.configure(command=install_voice)
    cancel_button.configure(command=voice_cancel.set, state="disabled")
    launch_button.configure(command=start_app)
    root.protocol("WM_DELETE_WINDOW", close)
    root.mainloop()


if __name__ == "__main__":
    launch_wizard()

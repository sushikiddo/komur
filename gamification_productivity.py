"""Dilim 5: Oyunlaştırma, Kedi Sepeti (Drag & Drop), To-Do Balık Avlama,
Dostluk Seviyesi, Patron Tuşu (Boss Key) ve Sağlık & Su Bekçisi.

Standart kütüphane tabanlıdır; GUI bağımsız birim testleriyle doğrudan
çalışacak ve Cat/DesktopCat döngüsüne kolayca bağlanabilecek şekilde tasarlanmıştır.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
import logging
import math
from pathlib import Path
import random
import re
import struct
import sys
import time
from typing import Any, Callable
import urllib.parse

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"})
CODE_LOG_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".tsx", ".jsx", ".log", ".txt",
    ".json", ".md", ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp",
    ".yaml", ".yml", ".csv", ".xml", ".html", ".css",
})
MAX_READ_BYTES = 262_144

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
CODE_OR_ERROR_RE = re.compile(
    r"(?:\bERROR\b|\bCRITICAL\b|\bFATAL\b|\bTraceback\b|\b[A-Za-z_]*Exception\b|\bdef\s+\w+|\bclass\s+\w+)"
)
ERROR_LINE_RE = re.compile(r"\b(?:ERROR|CRITICAL|FATAL|Traceback)\b")
EXCEPTION_RE = re.compile(r"\b[A-Za-z_]*(?:Exception|Error)\b")
DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)|^\s*(?:async\s+)?function\s+([A-Za-z_]\w*)", re.MULTILINE)
CLASS_RE = re.compile(r"^\s*class\s+([A-Za-z_]\w*)", re.MULTILINE)

WM_DROPFILES = 0x0233
GWLP_WNDPROC = -4

FISH_COLORS = ("#ff8a4c", "#4fc3f7", "#ffd54f", "#ff6f91", "#81c784", "#ba68c8")

XP_PER_LEVEL = 100
XP_REWARDS = {
    "pet": 10,
    "feed": 15,
    "play": 20,
    "fish_caught": 25,
    "pomodoro": 35,
    "pomodoro_complete": 35,
    "focus_complete": 35,
}

UNLOCK_TABLE = {
    1: {
        "label": "Başlangıç Dostluğu",
        "accessories": ["bow"],
        "tricks": ["basic_moves"],
        "modes": [],
        "titles": [],
        "unlocks": ["bow", "basic_moves"],
    },
    2: {
        "label": "Kış Dostu",
        "accessories": ["winter_set"],
        "tricks": ["spin"],
        "modes": [],
        "titles": [],
        "unlocks": ["winter_set", "spin"],
    },
    3: {
        "label": "Müzik & Pati Ortağı",
        "accessories": ["headphones"],
        "tricks": ["high_five"],
        "modes": [],
        "titles": [],
        "unlocks": ["headphones", "high_five"],
    },
    4: {
        "label": "Sihirli Kedi",
        "accessories": ["witch_hat"],
        "tricks": ["backflip"],
        "modes": [],
        "titles": [],
        "unlocks": ["witch_hat", "backflip"],
    },
    5: {
        "label": "Siber Efsane",
        "accessories": ["cyberpunk_collar"],
        "tricks": [],
        "modes": ["retro_pixel"],
        "titles": ["laser_master"],
        "unlocks": ["cyberpunk_collar", "retro_pixel", "laser_master"],
    },
}

BOSS_KEY_HOTKEY = "Ctrl+Shift+H"

HEALTH_WORK_THRESHOLD_SECONDS = 3600
HEALTH_POINTER_OFFSET_X = -60
HEALTH_POINTER_OFFSET_Y = -40
HEALTH_REMINDER_MESSAGE = (
    "1 saattir aralıksız çalışıyorsun! Hadi bir bardak su iç ve benim gibi gerin 🐾💧"
)


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def _normalize_payload(payload: str) -> str:
    text = str(payload or "").strip()
    if len(text) >= 2 and ((text[0] == '"' and text[-1] == '"') or (text[0] == "'" and text[-1] == "'")):
        text = text[1:-1].strip()
    if text.lower().startswith("file:///"):
        parsed = urllib.parse.urlparse(text)
        decoded = urllib.parse.unquote(parsed.path)
        if sys.platform == "win32" and len(decoded) >= 3 and decoded[0] == "/" and decoded[2] == ":":
            decoded = decoded[1:]
        text = decoded
    return text


def _read_image_dimensions(path: Path) -> tuple[int, int] | None:
    """Standart kütüphane ile temel resim başlıklarından (PNG/GIF/BMP/JPEG/WEBP) boyut okur."""
    try:
        with path.open("rb") as fh:
            head = fh.read(32)
            if len(head) >= 24 and head[:8] == b"\x89PNG\r\n\x1a\n":
                w, h = struct.unpack(">II", head[16:24])
                return (w, h)
            if len(head) >= 10 and head[:6] in (b"GIF87a", b"GIF89a"):
                w, h = struct.unpack("<HH", head[6:10])
                return (w, h)
            if len(head) >= 26 and head[:2] == b"BM":
                w, h = struct.unpack("<ii", head[18:26])
                return (abs(w), abs(h))
            if len(head) >= 30 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
                chunk = head[12:16]
                if chunk == b"VP8X" and len(head) >= 30:
                    w = 1 + int.from_bytes(head[24:27], "little")
                    h = 1 + int.from_bytes(head[27:30], "little")
                    return (w, h)
                if chunk == b"VP8 " and len(head) >= 30:
                    w, h = struct.unpack("<HH", head[26:30])
                    return (w & 0x3FFF, h & 0x3FFF)
            if len(head) >= 2 and head[:2] == b"\xff\xd8":
                fh.seek(2)
                while True:
                    marker_start = fh.read(1)
                    if not marker_start:
                        break
                    if marker_start != b"\xff":
                        continue
                    marker = fh.read(1)
                    while marker == b"\xff":
                        marker = fh.read(1)
                    if not marker or marker in (b"\xd8", b"\xd9"):
                        break
                    if 0xD0 <= marker[0] <= 0xD7 or marker[0] == 0x01:
                        continue
                    seg_len_bytes = fh.read(2)
                    if len(seg_len_bytes) < 2:
                        break
                    seg_len = struct.unpack(">H", seg_len_bytes)[0]
                    if marker[0] in (0xC0, 0xC1, 0xC2, 0xC3):
                        sof = fh.read(5)
                        if len(sof) == 5:
                            h, w = struct.unpack(">HH", sof[1:5])
                            return (w, h)
                        break
                    fh.seek(max(0, seg_len - 2), 1)
    except OSError:
        return None
    return None


def _inspect_code_or_log(text: str) -> dict[str, Any]:
    lines = text.splitlines() if text else []
    error_lines = [line.strip() for line in lines if ERROR_LINE_RE.search(line)]
    exceptions = EXCEPTION_RE.findall(text) if text else []
    defs = [m[0] or m[1] for m in DEF_RE.findall(text)] if text else []
    classes = CLASS_RE.findall(text) if text else []
    return {
        "line_count": len(lines),
        "errors": error_lines,
        "exceptions": exceptions,
        "defs": defs,
        "classes": classes,
        "error_count": len(error_lines),
        "exception_count": len(exceptions),
        "def_count": len(defs),
        "class_count": len(classes),
    }


def _derive_link_title(url: str, raw_text: str) -> str:
    prefix = raw_text.replace(url, "").strip(" -–—|:\t")
    if prefix:
        return prefix[:120]
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc or "Bağlantı"
    tail = parsed.path.strip("/").split("/")[-1] if parsed.path.strip("/") else ""
    return f"{host}/{tail}" if tail else host


# ---------------------------------------------------------------------------
# 1. Kedi Sepeti (Drag & Drop)
# ---------------------------------------------------------------------------
class CatBasketDropTarget:
    """Kedi sepetine bırakılan dosya, kod/log metni veya URL'yi işler."""

    def __init__(self, memory_store: Any = None):
        self.memory_store = memory_store
        self.history: list[dict[str, Any]] = []

    def handle_drop(self, payload: str, memory_store: Any = None) -> dict[str, Any]:
        memory = memory_store if memory_store is not None else self.memory_store
        raw = _normalize_payload(payload)

        if not raw:
            result = {"ok": False, "action": "noop", "message": "Sepete boş içerik bırakıldı."}
            self.history.append(result)
            return result

        # 1) URL / Link kontrolü (tek satırlı URL veya başlık + URL)
        if "\n" not in raw:
            url_match = URL_RE.search(raw)
            if url_match and (raw.lower().startswith(("http://", "https://")) or len(raw.split()) <= 8):
                result = self._handle_link(url_match.group(0), raw, memory)
                self.history.append(result)
                return result

        # 2) Dosya uzantısı kontrolü (tek satırda dosya yolu olabilir)
        if "\n" not in raw:
            candidate = Path(raw)
            ext = candidate.suffix.lower()
            if ext in IMAGE_EXTENSIONS:
                result = self._handle_image(candidate, ext)
                self.history.append(result)
                return result
            if ext in CODE_LOG_EXTENSIONS:
                result = self._handle_code_file(candidate, ext)
                self.history.append(result)
                return result

        # 3) Çok satırlı kod/hata metni veya kod/hata anahtar kelimesi
        if "\n" in raw or CODE_OR_ERROR_RE.search(raw):
            result = self._handle_code_text(raw, filename=None, path=None)
            self.history.append(result)
            return result

        # 4) Düz metin yedeği
        result = {
            "ok": True,
            "action": "text",
            "text": raw,
            "message": f"Sepete metin bırakıldı: {raw[:80]}",
        }
        self.history.append(result)
        return result

    def handle_drop_many(
        self,
        payloads: list[str] | tuple[str, ...],
        memory_store: Any = None,
    ) -> list[dict[str, Any]]:
        return [self.handle_drop(item, memory_store=memory_store) for item in payloads]

    def _handle_image(self, path: Path, ext: str) -> dict[str, Any]:
        exists = path.is_file()
        size_bytes = path.stat().st_size if exists else None
        dimensions = _read_image_dimensions(path) if exists else None

        dim_text = f"{dimensions[0]}x{dimensions[1]}" if dimensions else "boyut okunamadı"
        size_text = f"{size_bytes} bayt" if size_bytes is not None else "dosya diskte bulunamadı"
        summary = f"Görsel incelendi: {path.name} ({dim_text}, {size_text})."

        return {
            "ok": True,
            "action": "vision_analyze",
            "kind": "image",
            "path": str(path),
            "filename": path.name,
            "extension": ext,
            "exists": exists,
            "size_bytes": size_bytes,
            "dimensions": dimensions,
            "summary": summary,
            "message": summary,
        }

    def _handle_code_file(self, path: Path, ext: str) -> dict[str, Any]:
        exists = path.is_file()
        if exists:
            try:
                content = path.read_bytes()[:MAX_READ_BYTES].decode("utf-8", errors="replace")
            except OSError:
                content = ""
        else:
            content = ""
        result = self._handle_code_text(content, filename=path.name, path=str(path))
        result["extension"] = ext
        result["exists"] = exists
        return result

    def _handle_code_text(
        self,
        text: str,
        *,
        filename: str | None,
        path: str | None,
    ) -> dict[str, Any]:
        stats = _inspect_code_or_log(text)
        label = filename or "metin"
        summary = (
            f"{label}: {stats['line_count']} satır, "
            f"{stats['error_count']} hata, {stats['exception_count']} istisna, "
            f"{stats['def_count']} fonksiyon, {stats['class_count']} sınıf tespit edildi."
        )
        return {
            "ok": True,
            "action": "summarize_code_or_log",
            "kind": "code_or_log",
            "path": path,
            "filename": filename,
            "line_count": stats["line_count"],
            "errors": stats["errors"],
            "exceptions": stats["exceptions"],
            "defs": stats["defs"],
            "classes": stats["classes"],
            "detections": {
                "errors": stats["errors"],
                "exceptions": stats["exceptions"],
                "defs": stats["defs"],
                "classes": stats["classes"],
            },
            "summary": summary,
            "message": summary,
        }

    def _handle_link(self, url: str, raw_text: str, memory_store: Any) -> dict[str, Any]:
        title = _derive_link_title(url, raw_text)
        saved = False
        memory_result = None
        if memory_store is not None and callable(getattr(memory_store, "remember", None)):
            note = f"Bağlantı: {title} — {url}"[:2000]
            try:
                memory_result = memory_store.remember(note)
                saved = True
            except Exception:
                log.debug("memory_store.remember failed for link", exc_info=True)
        message = (
            f"Bağlantı hafızaya kaydedildi: {title} ({url})"
            if saved
            else f"Bağlantı algılandı: {title} ({url})"
        )
        return {
            "ok": True,
            "action": "save_link",
            "kind": "link",
            "url": url,
            "title": title,
            "saved": saved,
            "memory_result": memory_result,
            "message": message,
        }


def extract_dropped_files(hdrop: int, shell32: Any = None) -> list[str]:
    """Win32 HDROP tanıtıcısından bırakılan dosya yollarını güvenli biçimde okur."""
    if shell32 is None:
        if sys.platform != "win32":
            return []
        shell32 = ctypes.windll.shell32

    paths: list[str] = []
    try:
        count = int(shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0))
        for idx in range(count):
            length = int(shell32.DragQueryFileW(hdrop, idx, None, 0))
            buf = ctypes.create_unicode_buffer(length + 2)
            shell32.DragQueryFileW(hdrop, idx, buf, length + 1)
            if buf.value:
                paths.append(buf.value)
    finally:
        try:
            shell32.DragFinish(hdrop)
        except Exception:
            pass
    return paths


def enable_file_drop(
    tk_widget: Any,
    on_drop_callback: Callable[[list[str]], Any],
    *,
    user32: Any = None,
    shell32: Any = None,
) -> bool:
    """Tkinter widget'ına TkDnD veya Windows native WM_DROPFILES desteği bağlar."""
    if tk_widget is None or not callable(on_drop_callback):
        return False

    # 1) TkinterDnD2 gibi bir Tk DnD eklentisi varsa onu kullan
    if hasattr(tk_widget, "drop_target_register") and hasattr(tk_widget, "dnd_bind"):
        try:
            tk_widget.drop_target_register("DND_Files")
            tk_widget.dnd_bind("<<Drop>>", lambda evt: on_drop_callback([getattr(evt, "data", "")]))
            return True
        except Exception:
            log.debug("TkDnD registration failed; trying Win32 WM_DROPFILES", exc_info=True)

    # 2) Windows native WM_DROPFILES (testlerde enjekte edilen user32/shell32 ile de çalışır)
    if sys.platform != "win32" and (user32 is None or shell32 is None):
        return False

    try:
        hwnd = int(tk_widget.winfo_id())
    except Exception:
        return False

    try:
        u32 = user32 or ctypes.windll.user32
        s32 = shell32 or ctypes.windll.shell32
        s32.DragAcceptFiles(hwnd, True)

        if user32 is not None and shell32 is not None and not hasattr(u32, "CallWindowProcW"):
            # Hafif mock ortamında sadece DragAcceptFiles kaydı yeterli
            tk_widget._komur_drop_handler = lambda hdrop: on_drop_callback(extract_dropped_files(hdrop, s32))
            return True

        from ctypes import wintypes

        lresult_t = getattr(wintypes, "LRESULT", ctypes.c_ssize_t)
        wparam_t = getattr(wintypes, "WPARAM", ctypes.c_size_t)
        lparam_t = getattr(wintypes, "LPARAM", ctypes.c_ssize_t)
        wndproc_type = ctypes.WINFUNCTYPE(lresult_t, wintypes.HWND, wintypes.UINT, wparam_t, lparam_t)

        set_long = getattr(u32, "SetWindowLongPtrW", None) or u32.SetWindowLongW
        set_long.restype = ctypes.c_void_p
        prev_proc_holder: list[Any] = [None]

        def _wndproc(h_wnd, msg, w_param, l_param):
            if msg == WM_DROPFILES:
                files = extract_dropped_files(w_param, s32)
                if files:
                    try:
                        on_drop_callback(files)
                    except Exception:
                        log.exception("Drop callback failed")
                return 0
            return u32.CallWindowProcW(prev_proc_holder[0], h_wnd, msg, w_param, l_param)

        cb = wndproc_type(_wndproc)
        prev_proc_holder[0] = set_long(hwnd, GWLP_WNDPROC, ctypes.cast(cb, ctypes.c_void_p).value)
        tk_widget._komur_drop_wndproc = cb
        tk_widget._komur_prev_wndproc = prev_proc_holder[0]
        return True
    except Exception:
        log.debug("enable_file_drop failed", exc_info=True)
        return False


# ---------------------------------------------------------------------------
# 2. Dostluk Seviyesi (AffectionSystem)
# ---------------------------------------------------------------------------
class AffectionSystem:
    """Sevme, besleme, oyun, balık avlama ve Pomodoro ile dostluk XP/seviye sistemi."""

    def __init__(self, xp: int | None = None, settings: Any = None, memory_store: Any = None):
        self.settings = settings
        self.memory_store = memory_store
        if xp is None and settings is not None and callable(getattr(settings, "get", None)):
            xp = int(settings.get("affection_xp", 0) or 0)
        self.xp = max(0, int(xp or 0))
        self.history: list[dict[str, Any]] = []

    @property
    def level(self) -> int:
        return 1 + (self.xp // XP_PER_LEVEL)

    def get_unlocks(self, level: int | None = None) -> dict[str, Any]:
        target_level = self.level if level is None else max(1, int(level))
        accessories: list[str] = []
        tricks: list[str] = []
        modes: list[str] = []
        titles: list[str] = []
        all_items: list[str] = []

        for lvl in sorted(UNLOCK_TABLE):
            if lvl > target_level:
                break
            entry = UNLOCK_TABLE[lvl]
            accessories.extend(entry["accessories"])
            tricks.extend(entry["tricks"])
            modes.extend(entry["modes"])
            titles.extend(entry["titles"])
            all_items.extend(entry["unlocks"])

        return {
            "level": target_level,
            "accessories": accessories,
            "tricks": tricks,
            "modes": modes,
            "titles": titles,
            "all": all_items,
        }

    def add_xp(self, amount: int, reason: str = "") -> dict[str, Any]:
        gained = int(amount)
        if gained < 0:
            raise ValueError("XP miktarı negatif olamaz.")

        previous_level = self.level
        self.xp += gained
        new_level = self.level
        leveled_up = new_level > previous_level

        newly_unlocked: list[str] = []
        if leveled_up:
            for lvl in range(previous_level + 1, new_level + 1):
                if lvl in UNLOCK_TABLE:
                    newly_unlocked.extend(UNLOCK_TABLE[lvl]["unlocks"])

        event = {
            "xp": self.xp,
            "amount": gained,
            "reason": reason,
            "previous_level": previous_level,
            "level": new_level,
            "leveled_up": leveled_up,
            "newly_unlocked": newly_unlocked,
            "unlocks": self.get_unlocks(new_level),
            "progress_to_next": self.xp % XP_PER_LEVEL,
        }
        self.history.append(event)
        self._sync_persistence(event)
        return event

    def record_action(self, action: str) -> dict[str, Any]:
        key = str(action or "").strip().lower()
        if key not in XP_REWARDS:
            raise ValueError(f"Bilinmeyen dostluk eylemi: {action}")
        return self.add_xp(XP_REWARDS[key], reason=key)

    def _sync_persistence(self, event: dict[str, Any]) -> None:
        if self.settings is not None:
            try:
                if callable(getattr(self.settings, "update", None)):
                    self.settings.update(affection_xp=self.xp, affection_level=self.level)
                elif callable(getattr(self.settings, "set", None)):
                    self.settings.set("affection_xp", self.xp)
                    self.settings.set("affection_level", self.level)
            except Exception:
                log.debug("Affection settings sync failed", exc_info=True)

        if self.memory_store is not None and event["leveled_up"]:
            remember = getattr(self.memory_store, "remember", None)
            if callable(remember):
                unlocked = ", ".join(event["newly_unlocked"]) or "yeni bağ"
                try:
                    remember(f"Dostluk seviyesi {event['level']} oldu! Açılan ödüller: {unlocked}")
                except Exception:
                    log.debug("Affection memory sync failed", exc_info=True)


# ---------------------------------------------------------------------------
# 3. To-Do Balık Avlama (TodoFishPond)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PondBounds:
    left: float
    top: float
    right: float
    bottom: float


def _normalize_bounds(bounds: Any) -> PondBounds:
    if bounds is None:
        return PondBounds(0.0, 0.0, 800.0, 600.0)
    if isinstance(bounds, (tuple, list)) and len(bounds) == 4:
        l, t, r, b = (float(v) for v in bounds)
    elif isinstance(bounds, dict):
        l = float(bounds.get("left", 0.0))
        t = float(bounds.get("top", 0.0))
        r = float(bounds.get("right", 800.0))
        b = float(bounds.get("bottom", 600.0))
    else:
        l = float(getattr(bounds, "left", 0.0))
        t = float(getattr(bounds, "top", 0.0))
        r = float(getattr(bounds, "right", 800.0))
        b = float(getattr(bounds, "bottom", 600.0))
    return PondBounds(min(l, r), min(t, b), max(l, r), max(t, b))


class TodoFishPond:
    """Yapılacak görevleri ekranda sinüzoidal yüzen balıklara dönüştürür."""

    def __init__(
        self,
        affection: AffectionSystem | None = None,
        bounds: Any = None,
        seed: int | None = None,
    ):
        self.affection = affection
        self.bounds = _normalize_bounds(bounds)
        self._rng = random.Random(seed)
        self._tasks: dict[int, dict[str, Any]] = {}
        self._next_id = 1

    def add_task(self, title: str) -> dict[str, Any]:
        clean = str(title or "").strip()
        if not clean:
            raise ValueError("Görev başlığı boş olamaz.")

        task_id = self._next_id
        self._next_id += 1

        pad_x = min(20.0, (self.bounds.right - self.bounds.left) / 4)
        pad_y = min(20.0, (self.bounds.bottom - self.bounds.top) / 4)
        x = self._rng.uniform(self.bounds.left + pad_x, self.bounds.right - pad_x)
        base_y = self._rng.uniform(self.bounds.top + pad_y, self.bounds.bottom - pad_y)
        speed = self._rng.uniform(30.0, 55.0)
        vx = speed * self._rng.choice((-1.0, 1.0))
        phase = self._rng.uniform(0.0, math.tau)
        amplitude = self._rng.uniform(8.0, 16.0)
        frequency = self._rng.uniform(2.0, 3.6)
        color = FISH_COLORS[(task_id - 1) % len(FISH_COLORS)]

        fish = {
            "id": task_id,
            "title": clean,
            "x": x,
            "y": base_y,
            "base_y": base_y,
            "vx": vx,
            "phase": phase,
            "amplitude": amplitude,
            "frequency": frequency,
            "color": color,
            "caught": False,
        }
        self._tasks[task_id] = fish
        return dict(fish)

    def list_tasks(self, include_caught: bool = False) -> list[dict[str, Any]]:
        return [
            dict(fish)
            for fish in self._tasks.values()
            if include_caught or not fish["caught"]
        ]

    def step(self, dt: float, bounds: Any = None) -> list[dict[str, Any]]:
        area = _normalize_bounds(bounds) if bounds is not None else self.bounds
        step_dt = float(dt)
        if not math.isfinite(step_dt) or step_dt < 0.0:
            step_dt = 0.0

        for fish in self._tasks.values():
            if fish["caught"]:
                continue
            x = fish["x"] + fish["vx"] * step_dt
            if x <= area.left:
                x = area.left
                fish["vx"] = abs(fish["vx"])
            elif x >= area.right:
                x = area.right
                fish["vx"] = -abs(fish["vx"])
            fish["x"] = x

            fish["phase"] = (fish["phase"] + fish["frequency"] * step_dt) % math.tau
            raw_y = fish["base_y"] + math.sin(fish["phase"]) * fish["amplitude"]
            fish["y"] = max(area.top, min(area.bottom, raw_y))

        return self.list_tasks()

    def complete_task(self, task_id: int, cat_x: float = 0.0, cat_y: float = 0.0) -> dict[str, Any]:
        fish = self._tasks.get(task_id)
        if fish is None or fish["caught"]:
            return {
                "ok": False,
                "caught": False,
                "task_id": task_id,
                "error": "Görev bulunamadı veya zaten yakalandı.",
            }

        fish["caught"] = True
        pounce_target = {"x": fish["x"], "y": fish["y"]}
        distance = math.hypot(fish["x"] - float(cat_x), fish["y"] - float(cat_y))

        affection_result = None
        if self.affection is not None:
            affection_result = self.affection.record_action("fish_caught")
            xp_gained = affection_result["amount"]
        else:
            xp_gained = XP_REWARDS["fish_caught"]

        message = f"Yaşasın! '{fish['title']}' görevini tamamladın, balığı yakaladım! (+{xp_gained} XP) 🐟🐾"
        return {
            "ok": True,
            "caught": True,
            "task_id": task_id,
            "title": fish["title"],
            "fish": dict(fish),
            "pounce_target": pounce_target,
            "distance": round(distance, 2),
            "cat_state": "pounce",
            "xp_gained": xp_gained,
            "affection": affection_result,
            "message": message,
        }


# ---------------------------------------------------------------------------
# 4. Patron Tuşu (BossKeyController)
# ---------------------------------------------------------------------------
class BossKeyController:
    """Ctrl+Shift+H ile tüm görselleri/panelleri gizler, sesleri susturur ve geri yükler."""

    HOTKEY = BOSS_KEY_HOTKEY

    def __init__(self):
        self.active = False
        self.hidden = False
        self.muted = False
        self.stealth_mode = False
        self._saved: dict[str, Any] = {}

    @staticmethod
    def is_hotkey_event(event: Any) -> bool:
        keysym = str(getattr(event, "keysym", "") or "").lower()
        state = int(getattr(event, "state", 0) or 0)
        has_ctrl = bool(state & 0x4)
        has_shift = bool(state & 0x1)
        return keysym == "k" and has_ctrl and has_shift

    def toggle(self, app_or_state: Any = None) -> dict[str, Any]:
        if self.active:
            return self.restore(app_or_state)
        return self.activate(app_or_state)

    def activate(self, app_or_state: Any = None) -> dict[str, Any]:
        if self.active:
            return self._status(restored=False)

        self._saved = self._snapshot_state(app_or_state)
        self._apply_hidden(app_or_state, hide=True)

        self.active = True
        self.hidden = True
        self.muted = True
        self.stealth_mode = True
        return self._status(restored=False)

    def restore(self, app_or_state: Any = None) -> dict[str, Any]:
        if not self.active:
            return self._status(restored=False)

        self._apply_hidden(app_or_state, hide=False)
        saved_pos = self._saved.get("position")

        self.active = False
        self.hidden = False
        self.muted = bool(self._saved.get("muted", False))
        self.stealth_mode = False
        return self._status(restored=True, position=saved_pos)

    def _status(self, *, restored: bool, position: tuple[float, float] | None = None) -> dict[str, Any]:
        return {
            "active": self.active,
            "hidden": self.hidden,
            "muted": self.muted,
            "stealth_mode": self.stealth_mode,
            "hotkey": self.HOTKEY,
            "restored": restored,
            "position": position,
        }

    def _snapshot_state(self, target: Any) -> dict[str, Any]:
        if target is None:
            return {"muted": False, "sound": True, "position": None}

        if isinstance(target, dict):
            pos = (target["x"], target["y"]) if "x" in target and "y" in target else None
            sound_on = bool(target.get("sound", not target.get("muted", False)))
            return {
                "muted": bool(target.get("muted", not sound_on)),
                "sound": sound_on,
                "speech_bubbles": bool(target.get("speech_bubbles", True)),
                "position": pos,
                "panel_open": bool(target.get("panel_open", False)),
                "companions_visible": bool(target.get("companions_visible", True)),
            }

        brain = getattr(target, "brain", None)
        pos = (brain.x, brain.y) if brain is not None and hasattr(brain, "x") and hasattr(brain, "y") else None
        settings = getattr(target, "settings", None)
        eo = getattr(target, "effect_orchestrator", None)

        if settings is not None and callable(getattr(settings, "get", None)):
            sound_on = bool(settings.get("sound", True))
        elif eo is not None and hasattr(eo, "sound_enabled"):
            sound_on = bool(eo.sound_enabled)
        elif hasattr(target, "sound_enabled"):
            sound_on = bool(target.sound_enabled)
        else:
            sound_on = not bool(getattr(target, "muted", False))

        panel = getattr(target, "panel", None)
        panel_open = self._widget_exists(panel)
        assistant = getattr(target, "assistant", None)
        assistant_win = getattr(assistant, "window", None) if assistant is not None else None
        assistant_open = self._widget_exists(assistant_win)

        return {
            "muted": bool(getattr(target, "muted", not sound_on)),
            "sound": sound_on,
            "position": pos,
            "panel_open": panel_open,
            "assistant_open": assistant_open,
        }

    def _apply_hidden(self, target: Any, *, hide: bool) -> None:
        if target is None:
            return

        if isinstance(target, dict):
            if hide:
                target["hidden"] = True
                target["muted"] = True
                target["stealth_mode"] = True
                if "sound" in target:
                    target["sound"] = False
                if "speech_bubbles" in target:
                    target["speech_bubbles"] = False
                if "panel_open" in target:
                    target["panel_open"] = False
                if "companions_visible" in target:
                    target["companions_visible"] = False
            else:
                target["hidden"] = False
                target["stealth_mode"] = False
                target["muted"] = bool(self._saved.get("muted", False))
                if "sound" in target:
                    target["sound"] = bool(self._saved.get("sound", True))
                if "speech_bubbles" in target:
                    target["speech_bubbles"] = bool(self._saved.get("speech_bubbles", True))
                if "panel_open" in target:
                    target["panel_open"] = bool(self._saved.get("panel_open", False))
                if "companions_visible" in target:
                    target["companions_visible"] = bool(self._saved.get("companions_visible", True))
                pos = self._saved.get("position")
                if pos is not None:
                    target["x"], target["y"] = pos
            return

        self._apply_object_hidden(target, hide=hide)

    def _apply_object_hidden(self, app: Any, *, hide: bool) -> None:
        root = getattr(app, "root", None)
        bubble = getattr(app, "bubble", None)
        panel = getattr(app, "panel", None)
        assistant = getattr(app, "assistant", None)
        companions = getattr(app, "companions", ()) or ()
        brain = getattr(app, "brain", None)
        settings = getattr(app, "settings", None)
        eo = getattr(app, "effect_orchestrator", None)

        if hide:
            self._call_widget(root, "withdraw")
            if bubble is not None and callable(getattr(bubble, "hide", None)):
                bubble.hide()
            if self._saved.get("panel_open"):
                self._call_widget(panel, "withdraw")
            if assistant is not None:
                self._call_widget(getattr(assistant, "window", None), "withdraw")
                if callable(getattr(assistant, "hide", None)):
                    try:
                        assistant.hide()
                    except Exception:
                        pass
            for mate in companions:
                self._call_widget(getattr(mate, "window", None), "withdraw")

            app.hidden = True
            app.muted = True
            app.stealth_mode = True
            if hasattr(app, "sound_enabled"):
                app.sound_enabled = False
            if eo is not None and hasattr(eo, "sound_enabled"):
                eo.sound_enabled = False
            self._set_sound_setting(settings, False)
            return

        # Geri yükleme
        pos = self._saved.get("position")
        if pos is not None and brain is not None:
            if callable(getattr(brain, "move_to", None)):
                brain.move_to(pos[0], pos[1])
            else:
                brain.x, brain.y = pos

        self._call_widget(root, "deiconify")
        for mate in companions:
            self._call_widget(getattr(mate, "window", None), "deiconify")
        if self._saved.get("panel_open"):
            self._call_widget(panel, "deiconify")
        if self._saved.get("assistant_open") and assistant is not None:
            self._call_widget(getattr(assistant, "window", None), "deiconify")

        prev_sound = bool(self._saved.get("sound", True))
        prev_muted = bool(self._saved.get("muted", False))
        app.hidden = False
        app.muted = prev_muted
        app.stealth_mode = False
        if hasattr(app, "sound_enabled"):
            app.sound_enabled = prev_sound
        if eo is not None and hasattr(eo, "sound_enabled"):
            eo.sound_enabled = prev_sound
        self._set_sound_setting(settings, prev_sound)

    @staticmethod
    def _widget_exists(widget: Any) -> bool:
        if widget is None:
            return False
        fn = getattr(widget, "winfo_exists", None)
        if callable(fn):
            try:
                return bool(fn())
            except Exception:
                return False
        return True

    @staticmethod
    def _call_widget(widget: Any, method: str) -> None:
        if widget is None:
            return
        fn = getattr(widget, method, None)
        if callable(fn):
            try:
                fn()
            except Exception:
                pass

    @staticmethod
    def _set_sound_setting(settings: Any, value: bool) -> None:
        if settings is None or not callable(getattr(settings, "set", None)):
            return
        try:
            settings.set("sound", value, save=False)
        except TypeError:
            try:
                settings.set("sound", value)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# 5. Sağlık & Su Bekçisi (HealthWaterGuard)
# ---------------------------------------------------------------------------
class HealthWaterGuard:
    """Kesintisiz çalışma 1 saate ulaştığında esneme ve su içme hatırlatması üretir."""

    def __init__(
        self,
        threshold_seconds: float = HEALTH_WORK_THRESHOLD_SECONDS,
        cooldown_seconds: float = HEALTH_WORK_THRESHOLD_SECONDS,
    ):
        self.threshold_seconds = float(threshold_seconds)
        self.cooldown_seconds = float(cooldown_seconds)
        self.continuous_work_seconds = 0.0
        self.trigger_count = 0
        self._last_triggered_at: float | None = None

    def reset(self) -> None:
        self.continuous_work_seconds = 0.0
        self._last_triggered_at = None

    def step(
        self,
        dt: float,
        is_working: bool = True,
        pointer: tuple[float, float] | list[float] | None = (0.0, 0.0),
        now: float | None = None,
    ) -> dict[str, Any] | None:
        if not is_working:
            self.reset()
            return None
        delta = max(0.0, float(dt)) if math.isfinite(float(dt)) else 0.0
        self.continuous_work_seconds += delta
        return self.check(self.continuous_work_seconds, pointer=pointer, now=now)

    def check(
        self,
        continuous_work_seconds: float,
        pointer: tuple[float, float] | list[float] | None = (0.0, 0.0),
        now: float | None = None,
    ) -> dict[str, Any] | None:
        work_secs = max(0.0, float(continuous_work_seconds))
        self.continuous_work_seconds = work_secs

        if work_secs < self.threshold_seconds:
            self._last_triggered_at = None
            return None

        current_time = time.monotonic() if now is None else float(now)
        if self._last_triggered_at is not None and (current_time - self._last_triggered_at) < self.cooldown_seconds:
            return None

        self._last_triggered_at = current_time
        self.trigger_count += 1

        px, py = (0.0, 0.0) if pointer is None else (float(pointer[0]), float(pointer[1]))
        state = "stretch" if self.trigger_count % 2 == 1 else "yawn"
        return {
            "triggered": True,
            "target_x": px + HEALTH_POINTER_OFFSET_X,
            "target_y": py + HEALTH_POINTER_OFFSET_Y,
            "state": state,
            "message": HEALTH_REMINDER_MESSAGE,
            "continuous_work_seconds": work_secs,
            "triggered_at": current_time,
        }

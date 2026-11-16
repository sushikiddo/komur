"""Kömür: Windows desktop companion. Python 3.10+, standard library only.

A friendly tuxedo cat that lives on your desktop. Pet it, play, let it follow the
mouse, feed it, dress it in a new coat, resize it, give it friends, and send it to
sleep. Reverse-engineered from the original build and extended with customization,
a needs/mood system, Windows integration (tray, autostart, opacity, persistence)
and sound.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import logging
import logging.handlers
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import random
import threading
import time
import tempfile
import tkinter as tk
import tkinter.simpledialog as simpledialog
import tkinter.messagebox as messagebox
from tkinter import ttk, messagebox

from behavior import Bounds
from needs import HungryCatBrain
from renderer import CatRenderer
import autostart
import skins
import sound
import sounds
from effect_orchestrator import EffectOrchestrator
from settings import Settings, SIZE_LABELS, SIZE_SCALES
from tray import Tray
from bubble import SpeechBubble
from assistant_ui import AssistantUI
from activity_reactions import ActivityReactions

import subprocess
import ctypes
from ctypes import wintypes

WIDTH, HEIGHT = 260, 280          # logical base size; scaled by the size setting
BG = "#ff00ff"                    # transparent color key
TITLE = "Kömür — Kontrol paneli"
IS_WINDOWS = sys.platform == "win32"

STATE_LABELS = {
    "wander": "Geziniyor", "sit": "Oturuyor", "look": "Etrafı izliyor",
    "groom": "Temizleniyor", "stretch": "Geriniyor", "sleep": "Uyuyor",
    "yawn": "Esniyor", "play": "Top oynuyor", "follow": "Seni takip ediyor",
    "bored": "Canı sıkılıyor", "roll": "Yerde yuvarlanıyor",
}

# 100+ konuşma baloncuğu mesajı — gezirken, boşken, PC aktivite yorumları
SPEECH_MESSAGES = [
    # Giriş / selamlaşma
    "İyi oyunlar!", "Hoş geldin!", "Sen buradasın, harika!",
    "Başlayalım mı?", "Ne yapacaksın bugün?",
    # Gezilebilir / boşken yorumları
    "Biraz dolaşayım.", "Burası güzel bir yer.", "Hmm, ne bakıyorsun?",
    "Farene takılayım mı?", "Biraz yoruldum.", "Uyku geldiyor…",
    "Mama istiyorum.", "Sevilmek iyi.", "Sıcak burası.",
    "Fareyi gördüm! …hayal kurdum.", "Burayı keşfetmeliyim.",
    "Kendimi hissediyorum.", "Biraz esneyeyim.", "Topla oynamak isterim.",
    "Seni görmek güzel.", "Ne kadar güzel bir gün.",
    "Biraz dinleneyim.", "Fareyi takip ediyorum.", "Burada durayım.",
    # PC / bilgisayar aktivite yorumları
    "Klavyeye çok basıyorsun.", "Fareyi çok hareket ettiriyorsun.",
    "Ne kadar uzun bir dosya yazıyorsun.", "Ekrana çok bakıyorsun.",
    "Müzik dinliyor musun?", "Oyun oynuyor muyum?", "Ne kadar hızlı yazıyorsun.",
    "Bilgisayarda çok işlem var.", "Bu dosya neydi?", "İnternet geziyor musun?",
    "Yazı yazıyorsun, harika.", "Biraz ara vermelisin.", "Ekran parlak.",
    "Klavyenin sesi geliyor.", "Ne kadar fazla sekme açmışsın.",
    "Biraz stretching yapmalısın.", "Su içmelisin.",
    # Kedi-duyma / kişisel
    "Mırrr…", "Seni seviyorum.", "Kediyim, unutma!",
    "Sıcak bir yatak isterim.", "Mama vakti!", "Su kasedi isterim.",
    "Biraz susmalıyım.", "Tüylerimi düzenliyorum.", "Kulaklarım titriyor.",
    "Gözlerimi kırıyorum.", "Esneyeyim…", "Uyumak isterim.",
    "Ayışığı çok güzel.", "Pencereye bakayım.", "Kuş gördüm!",
    "Örümcek var mı?", "Topu nerede?", "Oynamak isterim.",
    "Seni izliyorum.", "Güvenliyim burda.", "Bu benim evim.",
    # Rastgele / 철학ik
    "Neden buradayım?", "Hayat güzel.", "Küçük şeyler önemli.",
    "Fare ile oynamak en iyisi.", "Sıcaklık seviyorum.",
    "Gölgeler güzel.", "Işık parlıyor.", "Sesler geliyor.",
    "Sessizlik de iyi.", "Zaman geçiyor.", "Ne yapayım?",
    "Biraz daha.", "Yeter bence.", "Devam edelim.",
    "Bir şeyler yapmalıyım.", "Dinlenmek gerekir.",
    "Fareyi yakalayamam ama uğraşayım.", "Seni görmek güzel.",
    "Bu bir macera.", "Kediler gizemlidir.", "Mırrr… iyilikler dilerim.",
    # Uzun / detaylı yorumlar
    "Bugün gerçekten productive bir gün gibi görünüyor, senin için iyi oldu!",
    "Fare imlecini takip etmek beni mutlu ediyor, sen de mutlu olmalısın.",
    "Biraz daha çalışıp sonra ara vermen sana iyi gelecektir, bence.",
    "Ekrandaki renkler güzel, senin için iyi bir seçenek olmuş gibi.",
    "Müzik çok rahatlatıcı, senin mood'un da iyi görünüyor.",
    "Dosya yöneticisi çok sekmeli, biraz karmaşık gibi görünüyor.",
    "Yazı yazarken kesintisiz olman güzel, konsantrasyonun yüksek.",
    "Oyun oynarken odaklanmışsın, bu başarının anahtarı.",
    "İnternet sayfaları çok fazla açılmış, odaklanman zor olabilir.",
    "Su içmeyi unutma, sağlığınız önemli, ben de mama istiyorum.",
    # Kısa ve nezih
    "Mrr.", "Hmm.", "Pff.", "Ah…", "Vay!", "Tamam.", "Peki.",
    "Anlıyorum.", "Evet.", "Hayır.", "Belki.", "Sonra.",
    "Şimdi.", "Hemen.", "Yavaşça.", "Hızlıca.",
    "Güzel.", "Harika.", "Mükemmel.", "İyi.", "Kötü.",
    "Normal.", "Farklı.", "Özel.", "Normal.", "Standart.",
]

DEFAULT_SKIN = "komur"


class PanelShortcut:
    """Own the hotkey on a worker thread so Tk cannot consume WM_HOTKEY."""

    def __init__(self):
        self.requested = threading.Event()
        self.stopped = threading.Event()
        self.ready = threading.Event()
        self.registered = False
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()
        self.ready.wait(0.5)

    def _listen(self):
        user32 = ctypes.windll.user32
        # id 19267, MOD_CONTROL|MOD_SHIFT|MOD_NOREPEAT (16390), 'K'
        self.registered = bool(user32.RegisterHotKey(None, 19267, 16390, ord("K")))
        self.ready.set()
        try:
            msg = wintypes.MSG()
            while self.registered and not self.stopped.wait(0.025):
                while user32.PeekMessageW(ctypes.byref(msg), None, 786, 786, 1):
                    if msg.wParam == 19267:
                        self.requested.set()
        finally:
            if self.registered:
                user32.UnregisterHotKey(None, 19267)

    def close(self):
        self.stopped.set()
        self.thread.join(timeout=0.5)


def setup_logging():
    directory = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Komur"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            directory / "komur.log", maxBytes=500000, backupCount=2, encoding="utf-8"
        )
        logging.basicConfig(
            level=logging.INFO, handlers=[handler],
            format="%(asctime)s %(levelname)s %(message)s",
        )
    except OSError:
        logging.basicConfig(level=logging.INFO)


def enable_dpi_awareness():
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


def monitor_bounds(root):
    """Each monitor's usable work area, including monitors left of the primary."""
    if IS_WINDOWS:
        class MonitorInfo(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD),
            ]

        areas = []
        ctypes.windll.user32.GetMonitorInfoW.argtypes = [
            wintypes.HMONITOR, ctypes.POINTER(MonitorInfo)
        ]
        callback_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
            ctypes.POINTER(wintypes.RECT), wintypes.LPARAM,
        )

        def collect(handle, dc, rect, data):
            info = MonitorInfo()
            info.cbSize = ctypes.sizeof(info)
            if ctypes.windll.user32.GetMonitorInfoW(handle, ctypes.byref(info)):
                r = info.rcWork
                areas.append(Bounds(r.left, r.top, r.right, r.bottom))
            return True

        callback = callback_type(collect)
        ctypes.windll.user32.EnumDisplayMonitors(None, None, callback, 0)
        if areas:
            return areas
    return [Bounds(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())]


def pointer_position(root):
    if IS_WINDOWS:
        point = wintypes.POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            return (point.x, point.y)
    return root.winfo_pointerxy()


def make_transparent(window):
    """Apply the borderless, topmost, color-keyed transparency to a window."""
    window.configure(bg=BG)
    window.overrideredirect(True)
    window.attributes("-topmost", True)
    if IS_WINDOWS:
        window.wm_attributes("-transparentcolor", BG)


def place_window(window, x, y, w, h):
    """Move a window to screen pixel (x, y). Uses SetWindowPos on Windows so an
    overrideredirect window honors the request, with a geometry fallback."""
    x, y = round(x), round(y)
    if IS_WINDOWS:
        try:
            user32 = ctypes.windll.user32
            user32.GetParent.argtypes = [wintypes.HWND]
            user32.GetParent.restype = wintypes.HWND
            user32.SetWindowPos.argtypes = [
                wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, ctypes.c_int, wintypes.UINT,
            ]
            hwnd = user32.GetParent(window.winfo_id()) or window.winfo_id()
            user32.SetWindowPos(hwnd, None, x, y, w, h, 20)  # NOSIZE off: set both
            return
        except OSError:
            pass
    window.geometry(f"{w}x{h}+{x}+{y}")


class Companion:
    """A second (or third…) cat in its own transparent window, driven by the
    main loop. Lighter than the primary cat: no panel, menu or hotkey."""

    def __init__(self, root, area, scale, skin, needs):
        self.w = round(WIDTH * scale)
        self.h = round(HEIGHT * scale)
        self.window = tk.Toplevel(root)
        make_transparent(self.window)
        self.canvas = tk.Canvas(self.window, width=self.w, height=self.h,
                                bg=BG, highlightthickness=0, borderwidth=0)
        self.canvas.pack()
        self.brain = HungryCatBrain(DesktopCat._movement_bounds(area, self.w, self.h),
                                    width=self.w, height=self.h, needs=needs)
        self.brain.move_to(area.left + 40, area.bottom - self.h - 20)
        self.renderer = skins.apply_skin(CatRenderer(self.canvas, self.w, self.h), skin)
        self.animation_time = 0.0
        self.window.geometry(f"{self.w}x{self.h}+0+0")
        self.window.update_idletasks()
        self._apply_position()

    def _apply_position(self):
        place_window(self.window, self.brain.x, self.brain.y, self.w, self.h)

    def set_opacity(self, value):
        try:
            self.window.attributes("-alpha", max(0.1, min(1.0, value / 100)))
        except tk.TclError:
            pass

    def step(self, dt, pointer):
        if not self.brain.paused:
            self.brain.step(dt, pointer)
            self.animation_time += dt
        self._apply_position()
        self.renderer.draw(self.brain, self.animation_time, "")

    def destroy(self):
        try:
            self.window.destroy()
        except tk.TclError:
            pass


class DesktopCat:
    def __init__(self, root=None, options=None):
        self.options = options
        self.settings = Settings.load()
        self.root = root or tk.Tk()
        self.root.title("Kömür")
        self.root.withdraw()
        self.root.report_callback_exception = self._callback_error
        make_transparent(self.root)

        scale = self.settings.scale
        self.w = round(WIDTH * scale)
        self.h = round(HEIGHT * scale)

        self.canvas = tk.Canvas(self.root, width=self.w, height=self.h, bg=BG,
                                highlightthickness=0, borderwidth=0)
        self.canvas.pack()

        self.areas = monitor_bounds(self.root)
        self.area_index = min(self.settings.get("area_index", 0), len(self.areas) - 1)
        area = self.areas[self.area_index]

        self.brain = HungryCatBrain(
            self._movement_bounds(area, self.w, self.h),
            width=self.w, height=self.h, needs=self.settings.get("needs"),
        )
        # restore last position, else bottom-right of the current monitor
        if self.settings.get("x") is not None and self.settings.get("y") is not None:
            self.brain.move_to(self.settings.get("x"), self.settings.get("y"))
        else:
            self.brain.move_to(area.right - self.w - 25, area.bottom - self.h - 15)

        self.renderer = skins.apply_skin(
            CatRenderer(self.canvas, self.w, self.h), self.settings.get("skin")
        )

        # Effect manager + particle system for realistic ses ve efenkler
        self.effect_orchestrator = EffectOrchestrator(
            self.canvas, self.w, self.h,
            sound_enabled=self.settings.get("sound"),
        )
        self.renderer.set_effect_orchestrator(self.effect_orchestrator)
        self._effect_state = self.brain.state

        self.last_time = time.monotonic()
        self.animation_time = 0.0
        self.message = f"Merhaba! Ben {self.settings.get('name')}. Sağ tıkla veya çift tıkla."
        self.message_until = self.last_time + 7
        self.drag_origin = None
        self.dragged = False
        self.menu_open = False
        self.closed = False
        self.after_id = None
        self.hotkey_id = None
        self.shortcut = None
        self.activation_event = None
        self.panel = None
        self.status_var = tk.StringVar()
        self.companions = []
        self._frames = 0
        self._last_speech_time = 0.0
        self._greeting_shown = False
        self._last_pointer = None
        self._pointer_move_count = 0
        self._last_click_time = 0.0
        self._click_count = 0
        self._last_key_time = 0.0
        self._key_count = 0

        # panel control variables
        self.name_var = tk.StringVar(value=self.settings.get("name"))
        self.skin_var = tk.StringVar(value=self.settings.get("skin"))
        self.size_var = tk.StringVar(value=self.settings.get("size"))
        self.opacity_var = tk.IntVar(value=self.settings.get("opacity"))
        self.sound_var = tk.BooleanVar(value=self.settings.get("sound"))
        self.needs_var = tk.BooleanVar(value=self.settings.get("needs"))
        self.autostart_var = tk.BooleanVar(value=self.settings.get("autostart"))
        self.friends_var = tk.IntVar(value=self.settings.get("friends"))
        self.quality_var = tk.StringVar(value=self.settings.get("sound_quality", "high"))
        self.density_var = tk.IntVar(value=self.settings.get("effects_density", 2))

        self._make_menu()
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Double-Button-1>", lambda event: self._on_speak_click())
        self.root.bind("<Button-3>", self._show_menu)
        self.root.bind("<Escape>", lambda event: self.command("wander"))
        self.root.bind("<F1>", lambda event: self.show_panel())
        self.root.bind("<Key>", self._on_key_press)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.root.geometry(f"{self.w}x{self.h}+0+0")
        self.root.update_idletasks()
        self._apply_position()
        self.root.deiconify()
        self.root.update_idletasks()
        self._apply_position()
        self._apply_opacity()

        self.tray = Tray(tooltip=f"{self.settings.get('name')} — Kömür")
        self._register_hotkey()
        self._rebuild_companions()
        self.bubble = SpeechBubble(self.root)
        self.assistant = AssistantUI(self)
        self._bubble_message = None
        self.activity_reactions = ActivityReactions()
        self._chat_anchor = None
        self._manual_reaction = None
        self._manual_reaction_until = 0.0
        self._init_speech()
        self._loop()

    # -- menu / hotkey ----------------------------------------------------
    def _make_menu(self):
        self.menu = tk.Menu(self.root, tearoff=False, font=("Segoe UI", 10))
        for label, command in (
            ("♥ Sev", "pet"), ("Mama ver", "feed"), ("Topla oyna", "play"),
            ("Fareyi takip et", "follow"), ("Gezin / Takibi bırak", "wander"),
            ("Uyu", "sleep"), ("Uyan", "wake"),
            ("Yerde yuvarlan", "roll"), ("Esne", "yawn"), ("Sıkıl", "bored"),
        ):
            self.menu.add_command(label=label, command=lambda name=command: self.command(name))
        self.menu.add_separator()
        self.menu.add_command(label="Duraklat / Devam et", command=self.toggle_pause)
        self.menu.add_command(label="Diğer ekrana geç", command=self.next_monitor)
        self.menu.add_command(label="Kömür ile konuş", command=self._on_speak_click)
        self.menu.add_command(label="Sohbet geçmişi ve ayarlar", command=self.assistant_history)
        self.menu.add_command(label="Kontrol paneli", command=self.show_panel)
        self.menu.add_separator()
        self.menu.add_command(label="Kapat", command=self.close)
        self.menu.bind("<Unmap>", lambda event: setattr(self, "menu_open", False))

    def _register_hotkey(self):
        if not IS_WINDOWS:
            return
        self.shortcut = PanelShortcut()
        if self.shortcut.registered:
            self.hotkey_id = 19267

    def _poll_hotkey(self):
        if self.activation_event is not None:
            kernel = ctypes.windll.kernel32
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            if kernel.WaitForSingleObject(self.activation_event, 0) == 0:
                self.show_panel()
        if self.shortcut is not None and self.shortcut.requested.is_set():
            self.shortcut.requested.clear()
            self.show_panel()

    def _poll_tray(self):
        if not getattr(self, "tray", None):
            return
        if self.tray.poll_show():
            self.show_panel()
        if self.tray.poll_quit():
            self.close()

    def _callback_error(self, error_type, error, traceback):
        logging.error("Tk callback failed", exc_info=(error_type, error, traceback))
        self.say("Bir sorun oluştu. Kontrol panelini açabilirsin.", 8)

    def say(self, text, seconds):
        self.message = text
        self.message_until = time.monotonic() + seconds

    def _init_speech(self):
        """Konuşma baloncuğu sistemini başlatır."""
        self._speech_message = ""
        self._speech_until = 0.0

    def _update_speech(self, now, pointer):
        self.assistant.tick(now)

    def _get_speech_message(self, now):
        return ""

    def _on_speak_click(self):
        self.assistant.show()

    def assistant_history(self):
        self.assistant.show_history()

    def _on_key_press(self, event):
        pass

    def command(self, name):
        if name in ("dance", "watch"):
            self._manual_reaction = "music" if name == "dance" else "video"
            self._manual_reaction_until = time.monotonic() + 20.0
            self.brain.command("wake")
            self.brain._change("sit", duration=20.0)
        else:
            self._manual_reaction = None
            self._manual_reaction_until = 0.0
            self.brain.command(name)
        self._sync_effect_state()
        self.say({
            "pet": "♥ Mırrr… Seni seviyorum!",
            "feed": "Nom nom… teşekkürler!",
            "play": "Top zamanı!",
            "knead": "Süpürüyorum…",
            "chirp": "Mır, mır!",
            "hiss": "Fıss!",
            "sneeze": "Hapsışım!",
            "follow": "Seni takip ediyorum. Gezin ile bırakabilirsin.",
            "wander": "Biraz dolaşayım.",
            "sleep": "İyi uykular…",
            "wake": "Günaydın!",
            "pause": "Duraklatıldı.",
            "resume": "Devam edelim!",
            "roll": "Biraz yerde yuvarlanayım!",
            "bored": "Canım sıkıldı, biraz oynayalım mı?",
            "yawn": "Uykum mu geliyor ne…",
        }.get(name, ""), 5)
        # Görsel efenkler
        if name == "pet":
            self.effect_orchestrator.trigger("pet", 0, 0)
        elif name == "feed":
            self.effect_orchestrator.trigger("feed", 0, 0)

        self._refresh_status()

    def _sync_effect_state(self):
        state = self.brain.state
        if state == self._effect_state:
            return
        self.effect_orchestrator.trigger_state_exit(self._effect_state, 0, 0)
        self.effect_orchestrator.trigger_state_enter(state, 0, 0)
        if state == "follow":
            self.effect_orchestrator.trigger("follow_start", 0, 0)
        self._effect_state = state

    def toggle_pause(self):
        self.command("resume" if self.brain.paused else "pause")

    # -- mouse ------------------------------------------------------------
    def _press(self, event):
        self.drag_origin = (event.x_root, event.y_root, self.brain.x, self.brain.y)
        self.dragged = False

    def _drag(self, event):
        if self.drag_origin is None:
            return
        px, py, x, y = self.drag_origin
        dx = event.x_root - px
        dy = event.y_root - py
        if dx * dx + dy * dy > 25:
            self.dragged = True
        if self.dragged:
            self.brain.move_to(x + dx, y + dy)
            self._apply_position()

    def _release(self, event):
        if self.drag_origin is None:
            return
        self.drag_origin = None
        if self.dragged:
            self.command("wander")
            self.say("Burayı sevdim!", 5)
            return
        # Tek tık (sürükle değil): kedile konuşma penceresi aç
        self._on_speak_click()

    def _show_menu(self, event):
        self.menu_open = True
        self.drag_origin = None
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            if not self.closed:
                self.menu.grab_release()
            if IS_WINDOWS:
                self.menu_open = False

    def _refresh_status(self):
        if self.closed:
            return
        if self.brain.paused:
            label = "Duraklatıldı"
        else:
            label = STATE_LABELS.get(self.brain.state, self.brain.state)
        extra = f"    •    {self.brain.mood}"
        if self.settings.get("needs"):
            extra += f"    •    Tokluk %{100 - self.brain.hunger:.0f}"
        self.status_var.set(
            f"{label}    •    Enerji %{self.brain.energy:.0f}"
            f"    •    Keyif %{self.brain.happiness:.0f}{extra}"
        )

    # -- appearance / settings -------------------------------------------
    def _apply_opacity(self):
        value = self.settings.get("opacity")
        try:
            self.root.attributes("-alpha", max(0.1, min(1.0, value / 100)))
        except tk.TclError:
            pass
        for mate in self.companions:
            mate.set_opacity(value)

    def _apply_skin(self):
        skins.apply_skin(self.renderer, self.settings.get("skin"))

    def _apply_size(self):
        scale = self.settings.scale
        self.w = round(WIDTH * scale)
        self.h = round(HEIGHT * scale)
        self.canvas.config(width=self.w, height=self.h)
        self.renderer = skins.apply_skin(
            CatRenderer(self.canvas, self.w, self.h), self.settings.get("skin")
        )
        self.brain.width = self.w
        self.brain.height = self.h
        area = self.areas[self.area_index]
        self.brain.set_bounds(self._movement_bounds(area, self.w, self.h))
        self.root.geometry(f"{self.w}x{self.h}+{round(self.brain.x)}+{round(self.brain.y)}")
        self.root.update_idletasks()
        self._apply_position()

    def _rebuild_companions(self):
        for mate in self.companions:
            mate.destroy()
        self.companions = []
        count = max(0, min(3, int(self.settings.get("friends") or 0)))
        area = self.areas[self.area_index]
        for _ in range(count):
            try:
                mate = Companion(self.root, area, self.settings.scale,
                                 self.settings.get("skin"), self.settings.get("needs"))
                mate.set_opacity(self.settings.get("opacity"))
                mate.brain.command("wander")
                self.companions.append(mate)
            except tk.TclError:
                break

    # -- panel ------------------------------------------------------------
    def show_panel(self):
        if self.panel is not None and self.panel.winfo_exists():
            self.panel.deiconify()
            self.panel.lift()
            self.panel.focus_force()
            return
        self.panel = tk.Toplevel(self.root)
        self.panel.title(TITLE)
        self.panel.resizable(False, False)
        self.panel.attributes("-topmost", True)
        nb = ttk.Notebook(self.panel)
        nb.pack(fill="both", expand=True, padx=2, pady=2)
        self._build_actions_tab(nb)
        self._build_look_tab(nb)
        self._build_system_tab(nb)
        self.panel.protocol("WM_DELETE_WINDOW", self.panel.withdraw)
        self._refresh_status()

    def _build_actions_tab(self, nb):
        content = ttk.Frame(nb, padding=18)
        nb.add(content, text="Davranış")
        ttk.Label(content, text=self.settings.get("name"),
                  font=("Segoe UI", 22, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(content, text="Masaüstündeki küçük dostun",
                  font=("Segoe UI", 10)).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 14))
        ttk.Label(content, textvariable=self.status_var).grid(
            row=2, column=0, columnspan=2, pady=(0, 12))
        buttons = [
            ("♥ Sev", "pet"), ("Mama ver", "feed"), ("Topla oyna", "play"),
            ("Süpür", "knead"), ("Kuş sesi", "chirp"), ("Fıss", "hiss"),
            ("Hapsıyor", "sneeze"),
            ("Fareyi takip et", "follow"), ("Gezin / Bırak", "wander"),
            ("Uyu", "sleep"), ("Uyan", "wake"),
            ("Yerde yuvarlan", "roll"), ("Esne", "yawn"), ("Sıkıl", "bored"),
        ]
        for index, (label, name) in enumerate(buttons):
            ttk.Button(content, text=label, width=20,
                       command=lambda n=name: self.command(n)).grid(
                row=3 + index // 2, column=index % 2, padx=4, pady=4, sticky="ew")
        row = 3 + (len(buttons) + 1) // 2
        ttk.Button(content, text="Duraklat / Devam et", command=self.toggle_pause).grid(
            row=row, column=0, padx=4, pady=4, sticky="ew")
        ttk.Button(content, text="Diğer ekrana geç", command=self.next_monitor).grid(
            row=row, column=1, padx=4, pady=4, sticky="ew")
        shortcut = ("Ctrl + Shift + K: paneli aç" if self.hotkey_id
                    else "Sağ tık veya çift tık: paneli aç")
        ttk.Label(content, text="Tıkla: sev  •  Sürükle: taşı\n" + shortcut +
                  "\nTakip açıkken Gezin ile durdurabilirsin.",
                  justify="left").grid(row=row + 1, column=0, columnspan=2, sticky="w", pady=14)

    def _build_look_tab(self, nb):
        content = ttk.Frame(nb, padding=18)
        nb.add(content, text="Görünüm")
        ttk.Label(content, text="İsim").grid(row=0, column=0, sticky="w", pady=4)
        name_entry = ttk.Entry(content, textvariable=self.name_var, width=22)
        name_entry.grid(row=0, column=1, sticky="ew", pady=4)
        name_entry.bind("<Return>", lambda e: self._on_name_change())
        name_entry.bind("<FocusOut>", lambda e: self._on_name_change())

        ttk.Label(content, text="Tüy rengi").grid(row=1, column=0, sticky="w", pady=4)
        skin_box = ttk.Combobox(content, state="readonly", width=20,
                                values=[skins.label(k) for k in skins.skin_order()])
        order = skins.skin_order()
        skin_box.current(order.index(self.settings.get("skin"))
                         if self.settings.get("skin") in order else 0)
        skin_box.grid(row=1, column=1, sticky="ew", pady=4)
        skin_box.bind("<<ComboboxSelected>>",
                      lambda e: self._on_skin_change(order[skin_box.current()]))

        ttk.Label(content, text="Boyut").grid(row=2, column=0, sticky="w", pady=4)
        size_keys = list(SIZE_SCALES.keys())
        size_box = ttk.Combobox(content, state="readonly", width=20,
                                values=[SIZE_LABELS[k] for k in size_keys])
        size_box.current(size_keys.index(self.settings.get("size"))
                         if self.settings.get("size") in size_keys else 1)
        size_box.grid(row=2, column=1, sticky="ew", pady=4)
        size_box.bind("<<ComboboxSelected>>",
                      lambda e: self._on_size_change(size_keys[size_box.current()]))

        ttk.Label(content, text="Saydamlık").grid(row=3, column=0, sticky="w", pady=4)
        scale = ttk.Scale(content, from_=20, to=100, variable=self.opacity_var,
                          command=lambda v: self._on_opacity_change())
        scale.grid(row=3, column=1, sticky="ew", pady=4)

        ttk.Label(content, text="Arkadaş sayısı").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Spinbox(content, from_=0, to=3, width=5, textvariable=self.friends_var,
                    command=self._on_friends_change).grid(row=4, column=1, sticky="w", pady=4)

    def _build_system_tab(self, nb):
        content = ttk.Frame(nb, padding=18)
        nb.add(content, text="Sistem")
        ttk.Checkbutton(content, text="Sesler (miyav / mırlama)",
                        variable=self.sound_var, command=self._on_sound_change).grid(
            row=0, column=0, sticky="w", pady=6)
        ttk.Checkbutton(content, text="İhtiyaç & ruh hali sistemi",
                        variable=self.needs_var, command=self._on_needs_change).grid(
            row=1, column=0, sticky="w", pady=6)
        auto = ttk.Checkbutton(content, text="Windows ile başlat",
                               variable=self.autostart_var, command=self._on_autostart_change)
        auto.grid(row=2, column=0, sticky="w", pady=6)
        if not autostart.available():
            auto.state(["disabled"])

        ttk.Label(content, text="Ses Kalitesi").grid(row=3, column=0, sticky="w", pady=4)
        quality_box = ttk.Combobox(content, state="readonly", width=20,
                                   values=["Yüksek (Gerçekçi WAV)", "Normal (Senteli)"])
        quality_box.current(0 if self.settings.get("sound_quality") == "high" else 1)
        quality_box.grid(row=3, column=1, sticky="ew", pady=4)
        quality_box.bind("<<ComboboxSelected>>",
                         lambda e: self._on_quality_change(["high", "normal"][quality_box.current()]))

        ttk.Label(content, text="Efekt Yoğunluğu").grid(row=4, column=0, sticky="w", pady=4)
        density_box = ttk.Combobox(content, state="readonly", width=20,
                                   values=["Düşük", "Normal", "Yüksek"])
        density_box.current(self.settings.get("effects_density", 2) - 1)
        density_box.grid(row=4, column=1, sticky="ew", pady=4)
        density_box.bind("<<ComboboxSelected>>",
                         lambda e: self._on_density_change(density_box.current() + 1))

        if getattr(self, "tray", None) and self.tray.available:
            ttk.Label(content, text="Sistem tepsisi: etkin (sağ tık: menü)").grid(
                row=5, column=0, sticky="w", pady=6)
        ttk.Separator(content, orient="horizontal").grid(
            row=6, column=0, sticky="ew", pady=10)
        ttk.Button(content, text="Paneli gizle", command=self.panel.withdraw).grid(
            row=7, column=0, sticky="ew", pady=4)
        ttk.Button(content, text="Kömür'ü kapat", command=self.close).grid(
            row=8, column=0, sticky="ew", pady=4)
        ttk.Separator(content, orient="horizontal").grid(
            row=9, column=0, sticky="ew", pady=10)
        ttk.Label(content, text="Kedile Konuş (AI Yardımcı)").grid(
            row=10, column=0, sticky="w", pady=4)
        ttk.Button(content, text="Konuşma penceresini aç",
                   command=self._on_speak_click).grid(
            row=11, column=0, sticky="ew", pady=4)
        ttk.Label(content, text="Günlük: %LOCALAPPDATA%\\Komur\\komur.log",
                  font=("Segoe UI", 8)).grid(row=9, column=0, sticky="w", pady=(10, 0))

    # -- panel callbacks --------------------------------------------------
    def _on_name_change(self):
        name = self.name_var.get().strip() or "Kömür"
        self.name_var.set(name)
        self.settings.set("name", name)
        self.say(f"Artık adım {name}!", 4)

    def _on_skin_change(self, skin):
        self.settings.set("skin", skin)
        self.skin_var.set(skin)
        self._apply_skin()
        for mate in self.companions:
            skins.apply_skin(mate.renderer, skin)
        self.say("Yeni kürk!", 4)

    def _on_size_change(self, size):
        self.settings.set("size", size)
        self.size_var.set(size)
        self._apply_size()
        self._rebuild_companions()
        self._apply_opacity()

    def _on_opacity_change(self):
        value = int(self.opacity_var.get())
        self.settings.set("opacity", value)
        self._apply_opacity()

    def _on_friends_change(self):
        self.settings.set("friends", int(self.friends_var.get()))
        self._rebuild_companions()
        self._apply_opacity()

    def _on_sound_change(self):
        enabled = bool(self.sound_var.get())
        self.settings.set("sound", enabled)
        if enabled:
            sound.play("meow", enabled=True)

    def _on_needs_change(self):
        enabled = bool(self.needs_var.get())
        self.settings.set("needs", enabled)
        self.brain.needs_enabled = enabled
        for mate in self.companions:
            mate.brain.needs_enabled = enabled

    def _on_autostart_change(self):
        want = bool(self.autostart_var.get())
        result = autostart.set_enabled(want)
        self.autostart_var.set(result)
        self.settings.set("autostart", result)

    def _on_quality_change(self, quality):
        self.settings.set("sound_quality", quality)
        self.quality_var.set(quality)
        self.effect_orchestrator.set_quality(quality)
        self.say(f"Ses kalitesi: {'Yüksek' if quality == 'high' else 'Normal'}", 3)

    def _on_density_change(self, density):
        self.settings.set("effects_density", density)
        self.density_var.set(density)
        self.effect_orchestrator.particles.MAX_PARTICLES = {1: 300, 2: 600, 3: 1000}[density]
        self.say(f"Efekt yoğunluğu: {'Düşük' if density == 1 else 'Normal' if density == 2 else 'Yüksek'}", 3)

    # -- monitors / geometry ---------------------------------------------
    def next_monitor(self):
        self.areas = monitor_bounds(self.root)
        self.area_index = (self.area_index + 1) % len(self.areas)
        area = self.areas[self.area_index]
        self.brain.set_bounds(self._movement_bounds(area, self.w, self.h))
        self.brain.move_to(area.right - self.w - 25, area.bottom - self.h - 15)
        self.settings.set("area_index", self.area_index)
        self.command("wander")
        self.say(f"Ekran {self.area_index + 1}/{len(self.areas)}", 5)

    @staticmethod
    def _movement_bounds(area, w=WIDTH, h=HEIGHT):
        return Bounds(area.left, area.top, max(area.left, area.right - w),
                      max(area.top, area.bottom - h))

    def _apply_position(self):
        place_window(self.root, self.brain.x, self.brain.y, self.w, self.h)

    # -- main loop --------------------------------------------------------
    def _loop(self):
        if self.closed:
            return
        try:
            now = time.monotonic()
            dt = max(0, min(now - self.last_time, 0.1))
            self.last_time = now
            self._poll_hotkey()
            self._poll_tray()
            if self.closed:
                return
            if self.drag_origin is None and not self.menu_open:
                pointer = pointer_position(self.root)
                reaction = self.activity_reactions.poll(now, self.settings.get("activity_reactions", True))
                compact = self.assistant.compact_visible
                if compact and self._chat_anchor is None:
                    self._chat_anchor = (self.brain.x, self.brain.y)
                elif not compact:
                    self._chat_anchor = None
                # Keep the input close enough to type while the cat remains animated.
                old_x, old_y = self.brain.x, self.brain.y
                self.brain.step(dt, pointer)
                if compact:
                    ax, ay = self._chat_anchor
                    self.brain.x = max(ax - 24, min(ax + 24, self.brain.x))
                    self.brain.y = max(ay - 16, min(ay + 16, self.brain.y))
                elif reaction == "gaming" and self.settings.get("focus_mode", True):
                    self.brain.x = old_x + (self.brain.x - old_x) * .15
                    self.brain.y = old_y + (self.brain.y - old_y) * .15
                self.brain.activity_reaction = (self._manual_reaction
                                                if now < self._manual_reaction_until else reaction)
                self._sync_effect_state()
                if not self.brain.paused:
                    self.animation_time += dt
                self.effect_orchestrator.step(dt)
                if not (reaction == "gaming" and self.settings.get("focus_mode", True)):
                    for mate in self.companions:
                        mate.step(dt, pointer)
                self._update_speech(now, pointer)
            self._apply_position()
            message = self.message if now < self.message_until else self._get_speech_message(now)
            if self.assistant.compact_visible:
                self.bubble.hide()
            elif self.settings.get("speech_bubbles") and message:
                if message != self._bubble_message or not self.bubble.visible:
                    self.bubble.show(message, self.brain.x, self.brain.y, self.w,
                                     seconds=max(0, self.message_until - now), now=now)
                self.bubble.update_position(self.brain.x, self.brain.y, self.w)
            elif not self.assistant.busy:
                self.bubble.hide()
            elif self.settings.get("speech_bubbles"):
                if not self.bubble.thinking:
                    self.bubble.show_thinking(self.brain.x, self.brain.y, self.w, seconds=130, now=now)
                self.bubble.update_position(self.brain.x, self.brain.y, self.w)
            self._bubble_message = message
            self.bubble.tick(now)
            self.renderer.draw(
                self.brain, self.animation_time, message=message,
                effect_orchestrator=self.effect_orchestrator,
            )
            self._frames += 1
            if self._frames % 20 == 0:
                self._refresh_status()
        except Exception:
            logging.exception("Animation frame failed")
            self.say("Bir çizim sorunu oluştu; yeniden deneniyor.", 2)
        finally:
            if not self.closed:
                self.after_id = self.root.after(33, self._loop)

    def close(self):
        if self.closed:
            return
        self.closed = True
        # remember where we are for next launch
        try:
            self.settings.update(x=round(self.brain.x), y=round(self.brain.y),
                                 area_index=self.area_index)
        except Exception:
            logging.debug("could not persist position", exc_info=True)
        for mate in self.companions:
            mate.destroy()
        shortcut = getattr(self, "shortcut", None)
        if shortcut:
            shortcut.close()
        tray = getattr(self, "tray", None)
        if tray:
            tray.close()
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
        self.assistant.close()
        self.bubble.destroy()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def acquire_instance():
    if not IS_WINDOWS:
        return (None, True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateEventW.argtypes = [
        ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR
    ]
    kernel.CreateEventW.restype = wintypes.HANDLE
    handle = kernel.CreateEventW(None, False, False, "Local\\KomurDesktopCat_v2_Activate")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return (handle, ctypes.get_last_error() != 183)  # 183 == ERROR_ALREADY_EXISTS


def main():
    parser = argparse.ArgumentParser(description="Kömür masaüstü kedisi")
    parser.add_argument("--panel", action="store_true", help="Kontrol panelini aç")
    parser.add_argument("--smoke-test", metavar="JSON_PATH", help=argparse.SUPPRESS)
    options = parser.parse_args()

    setup_logging()
    enable_dpi_awareness()
    handle, first = acquire_instance()
    if not first:
        # another instance is already running; poke it to open its panel.
        kernel = ctypes.windll.kernel32
        kernel.SetEvent.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.SetEvent(handle)
        kernel.CloseHandle(handle)
        return

    try:
        smoke_profile = None
        previous_localappdata = os.environ.get("LOCALAPPDATA")
        if options.smoke_test:
            smoke_profile = tempfile.TemporaryDirectory(prefix="komur-selfcheck-")
            os.environ["LOCALAPPDATA"] = smoke_profile.name
        app = DesktopCat(options=options)
        app.activation_event = handle
        if options.panel:
            app.show_panel()
        if options.smoke_test:
            def smoke_test():
                result = {"ok": False, "states": [],
                          "frozen": bool(getattr(sys, "frozen", False)),
                          "executable": sys.executable}
                try:
                    for command in ("pet", "feed", "play", "roll", "bored", "yawn", "follow", "sleep",
                                    "wake", "wander", "pause", "resume"):
                        app.command(command)
                        app.brain.step(0.033, (700, 450))
                        app.renderer.draw(app.brain, 1.5, message=app.message)
                        app.root.update_idletasks()
                        result["states"].append(app.brain.state)
                    app.show_panel()
                    app.assistant.show()
                    app.root.update_idletasks()
                    result["compact"] = app.assistant.compact_visible and app.assistant.window is None
                    app.assistant.show_history()
                    result["history_window"] = app.assistant.window.winfo_exists() == 1
                    result["voice"] = app.assistant.voice.status()
                    if result["voice"]["stt_available"]:
                        from faster_whisper import WhisperModel
                        import numpy as np
                        model = WhisperModel(str(app.assistant.voice.model_dir), device="cpu", compute_type="int8", local_files_only=True)
                        list(model.transcribe(np.zeros(16000, dtype=np.float32), language="tr", vad_filter=True)[0])
                        result["voice_runtime"] = True
                    app.assistant.memory.remember("Kurulum test notu")
                    result["memory"] = bool(app.assistant.memory.notes())
                    result["ok"] = True
                    result["window"] = [app.root.winfo_width(), app.root.winfo_height()]
                    result["hunger"] = round(app.brain.hunger, 1)
                    result["companions"] = len(app.companions)
                except Exception as error:
                    result["error"] = repr(error)
                Path(options.smoke_test).write_text(
                    json.dumps(result, ensure_ascii=False), encoding="utf-8")
                app.close()
            app.root.after(1000, smoke_test)
        app.run()
    except Exception:
        logging.exception("Startup failed")
        try:
            messagebox.showerror(
                "Kömür açılamadı",
                "Uygulama başlatılamadı. Ayrıntılar: %LOCALAPPDATA%\\Komur\\komur.log")
        except Exception:
            pass
        raise
    finally:
        if 'smoke_profile' in locals() and smoke_profile is not None:
            if previous_localappdata is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous_localappdata
            smoke_profile.cleanup()
        if handle:
            kernel = ctypes.WinDLL("kernel32")
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle(handle)


if __name__ == "__main__":
    main()

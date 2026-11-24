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
import math
import os
from pathlib import Path
import sys
import random
import threading
import time
import tempfile
import types
import tkinter as tk
import tkinter.simpledialog as simpledialog
import tkinter.messagebox as messagebox
from tkinter import ttk, messagebox

# Tüm modüller veri kökü olarak %LOCALAPPDATA%'yı okur (bazıları içe aktarılırken);
# macOS'ta bunu proje modülleri yüklenmeden önce ~/Library/Application Support yap.
if sys.platform == "darwin":
    os.environ.setdefault("LOCALAPPDATA", str(Path.home() / "Library" / "Application Support"))

from behavior import Bounds
from needs import HungryCatBrain
from focus import FocusSession, MESSAGES, phase_to_cat_state
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
from companion import Companion, step_companions
from panel import TITLE, show_panel as _show_panel
import window_utils
from window_utils import (BG, HEIGHT, IS_MAC, IS_WINDOWS, WIDTH, enable_dpi_awareness, make_transparent, monitor_bounds,
                          movement_bounds, place_window, pointer_position)

import subprocess
import ctypes
from ctypes import wintypes


STATE_LABELS = {
    "wander": "Geziniyor", "sit": "Oturuyor", "look": "Etrafı izliyor",
    "groom": "Temizleniyor", "stretch": "Geriniyor", "sleep": "Uyuyor",
    "yawn": "Esniyor", "play": "Top oynuyor", "follow": "Seni takip ediyor",
    "bored": "Canı sıkılıyor", "roll": "Yerde yuvarlanıyor",
    "drink": "Süt içiyor", "eat": "Mama yiyor", "scratch": "Tırmalıyor",
    "jump": "Zıplıyor", "box_sit": "Kutuda oturuyor", "perch": "Pencerede tünüyor",
    "laser_chase": "Lazer kovalıyor",
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
        self.requested = threading.Event()        # Ctrl+Shift+K -> panel
        self.boss_requested = threading.Event()   # Ctrl+Shift+H -> patron tuşu
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
        boss = bool(user32.RegisterHotKey(None, 19268, 16390, ord("H")))
        self.ready.set()
        try:
            msg = wintypes.MSG()
            while self.registered and not self.stopped.wait(0.025):
                while user32.PeekMessageW(ctypes.byref(msg), None, 786, 786, 1):
                    if msg.wParam == 19267:
                        self.requested.set()
                    elif msg.wParam == 19268:
                        self.boss_requested.set()
        finally:
            if self.registered:
                user32.UnregisterHotKey(None, 19267)
            if boss:
                user32.UnregisterHotKey(None, 19268)

    def close(self):
        self.stopped.set()
        self.thread.join(timeout=0.5)


def log_path():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Komur" / "komur.log"


def setup_logging():
    directory = log_path().parent
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
            activity=self.settings.get("activity_level"),
        )
        # restore last position, else bottom-right of the current monitor
        if self.settings.get("x") is not None and self.settings.get("y") is not None:
            self.brain.move_to(self.settings.get("x"), self.settings.get("y"))
        else:
            self.brain.move_to(area.right - self.w - 25, area.bottom - self.h - 15)

        self.renderer = skins.apply_skin(
            CatRenderer(self.canvas, self.w, self.h), self.settings.get("skin")
        )

        # Effect manager + particle system for realistic görsel efektler
        # Sesler kesin 3-olay listesiyle (sevme, esneme, uyanma) DesktopCat üzerinden çalınır.
        self.effect_orchestrator = EffectOrchestrator(
            self.canvas, self.w, self.h,
            sound_enabled=self.settings.get("sound"),
        )
        self.effect_orchestrator._play_sound = lambda *_args, **_kw: None
        self.renderer.set_effect_orchestrator(self.effect_orchestrator)
        self._effect_state = self.brain.state
        self._prev_sound_state = self.brain.state

        self.last_time = time.monotonic()
        self.animation_time = 0.0
        hint = "İki parmak tık: menü · sol tık: sev." if IS_MAC else "Sağ tık: menü · orta tık: sohbet."
        self.message = f"Merhaba! Ben {self.settings.get('name')}. {hint}"
        self.message_until = self.last_time + 7
        self.drag_origin = None
        self.dragged = False
        self.menu_open = False
        self._last_menu_toggle = -10.0
        self._pressed_while_active = True
        self._pressed_hud_was_open = False
        self._last_mac_chrome = self.last_time
        self._next_auto_perch_at = self.last_time + random.uniform(75.0, 120.0)
        self.closed = False
        self.hidden = False
        self.muted = False
        self.stealth_mode = False
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
        self.retro_var = tk.BooleanVar(value=bool(self.settings.get("retro_mode", False)))
        self.persona_var = tk.StringVar(value=self.settings.get("persona", "asil_tembel"))
        self.affection_var = tk.StringVar(
            value=f"Sv.{self.settings.get('affection_level', 1)} ({self.settings.get('affection_xp', 0)} XP)"
        )

        self._make_menu()
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        # Tk 8.6 ve öncesinde macOS (aqua) sağ tıkı <Button-2> olarak verir; Tk 8.7/9'dan itibaren
        # her platformda sağ tık <Button-3>, orta tık <Button-2>'dir.
        legacy_aqua = IS_MAC and tk.TkVersion < 8.7
        menu_button, chat_button = ("<Button-2>", "<Button-3>") if legacy_aqua else ("<Button-3>", "<Button-2>")
        self.canvas.bind(chat_button, lambda event: self.open_chat())
        self.canvas.bind(menu_button, self._show_menu)
        self.root.bind(menu_button, self._show_menu)
        if IS_MAC:
            self.canvas.bind("<Control-Button-1>", lambda event: (self._show_menu(event), "break")[1])
            window_utils.register_mac_right_click(self.root, self._show_menu_at)
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
        window_utils.ensure_floating(self.root)
        self._apply_opacity()

        self.tray = Tray(tooltip=f"{self.settings.get('name')} — Kömür")
        if hasattr(self.tray, "attach_tk"):
            self.tray.attach_tk(self.root, on_toggle_hide=self.toggle_boss_key)
        self._register_hotkey()
        self._rebuild_companions()
        self.bubble = SpeechBubble(self.root)
        self.assistant = AssistantUI(self)
        self._bubble_message = None
        self.activity_reactions = ActivityReactions()
        self._still_reaction = False
        self.focus = FocusSession()
        self._tod, self._tod_checked = "day", float("-inf")
        self._chat_anchor = None
        self._manual_reaction = None
        self._manual_reaction_until = 0.0
        self._cached_has_toast = False
        self.brain.vx = 0.0
        self.brain.vy = 0.0
        self.brain.pointer_xy = None
        self.brain.hide_internal_ball = False
        self._laser_dot = None
        self.effect_orchestrator.cat_screen_x = self.brain.x + self.w / 2
        self.effect_orchestrator.screen_w = max(1.0, area.right - area.left)
        self._init_speech()
        self._init_v2_modules(area)
        self._loop()

    def _init_v2_modules(self, area):
        """Initialize v2.0 subsystems defensively so missing optional pieces never crash startup."""
        self.physics = None
        self.acoustic = None
        self.hardware_mind = None
        self.dream_engine = None
        self.toybox = None
        self.weather = None
        try:
            from weather import WeatherWatcher
            self.weather = WeatherWatcher()
            self.weather.set_city(self.settings.get("weather_city", ""))
        except Exception:
            logging.debug("WeatherWatcher init failed", exc_info=True)
        try:
            from desktop_toys import ToyBox
            self.toybox = ToyBox(self.root)
        except Exception:
            logging.debug("ToyBox init failed", exc_info=True)
        self.meow_translator = None
        self.affection = None
        self.fish_pond = None
        self.basket = None
        self.boss_key = None
        self.health_guard = None

        bounds = (area.left, area.top, area.right, area.bottom)
        mem = getattr(self.assistant, "memory", None)

        try:
            from desktop_physics import DesktopPhysics
            self.physics = DesktopPhysics(cat_w=self.w, cat_h=self.h, bounds=bounds)
        except Exception:
            logging.debug("DesktopPhysics init failed", exc_info=True)

        try:
            from acoustic_engine import (
                DynamicPurrController,
                KeyboardReactiveAudio,
                LofiAmbiencePlayer,
            )
            self.acoustic = types.SimpleNamespace(
                purr=DynamicPurrController(),
                keyboard=KeyboardReactiveAudio(),
                lofi=LofiAmbiencePlayer(),
            )
        except Exception:
            logging.debug("AcousticEngine init failed", exc_info=True)

        try:
            from persona_dreams import (
                DreamEngine,
                HardwareMind,
                MeowTranslator,
            )
            self.hardware_mind = HardwareMind()
            self.meow_translator = MeowTranslator()
            if mem is None:
                from memory_store import MemoryStore
                mem = MemoryStore()
            self.dream_engine = DreamEngine(memory_store=mem)
        except Exception:
            logging.debug("Persona/Dreams init failed", exc_info=True)

        try:
            from gamification_productivity import (
                AffectionSystem,
                BossKeyController,
                CatBasketDropTarget,
                HealthWaterGuard,
                TodoFishPond,
                enable_file_drop,
            )
            self.affection = AffectionSystem(settings=self.settings, memory_store=mem)
            self.fish_pond = TodoFishPond(affection=self.affection, bounds=bounds)
            self.basket = CatBasketDropTarget(memory_store=mem)
            self.boss_key = BossKeyController()
            self.health_guard = HealthWaterGuard()
            enable_file_drop(self.root, self._on_file_drop)
        except Exception:
            logging.debug("Gamification/Productivity init failed", exc_info=True)

        try:
            self.brain.age_days = float(self.settings.get("age_days", 7.0))
            if hasattr(self.renderer, "set_retro_mode"):
                self.renderer.set_retro_mode(bool(self.settings.get("retro_mode", False)))
        except Exception:
            logging.debug("Renderer/age sync failed", exc_info=True)

        self.context_hud = None
        try:
            from context_hud import ModernContextHUD
            self.context_hud = ModernContextHUD(self)
        except Exception:
            logging.debug("ModernContextHUD init failed", exc_info=True)

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
        v2_menu = tk.Menu(self.menu, tearoff=False, font=("Segoe UI", 10))
        v2_menu.add_command(label="Karton kutu bırak", command=self.toggle_box_prop)
        for kind, label in (("yarn", "İplik yumağı at/kaldır"), ("bowl", "Süt kasesi koy/kaldır"),
                            ("post", "Tırmalama tahtası koy/kaldır")):
            v2_menu.add_command(label=label, command=lambda k=kind: self.toggle_toy(k))
        v2_menu.add_command(label="Pencere tepesine tüne", command=self.perch_active_window)
        v2_menu.add_command(label="Görev çubuğuna in", command=self.walk_on_taskbar_cmd)
        v2_menu.add_command(label="Retro Pixel modu", command=self.toggle_retro_mode)
        v2_menu.add_command(label="Hava durumu (şehir)…", command=self.choose_weather_city)
        v2_menu.add_command(label="Lofi Ambiyans aç/kapat", command=self.toggle_lofi_ambience)
        v2_menu.add_command(label="Patron Tuşu (Gizle)", command=self.toggle_boss_key)
        self.menu.add_cascade(label="v2.0 Özellikler", menu=v2_menu)
        self.menu.add_separator()
        self.menu.add_command(label="Pomodoro başlat / bitir", command=self.toggle_focus)
        self.menu.add_command(label="Duraklat / Devam et", command=self.toggle_pause)
        self.menu.add_command(label="Diğer ekrana geç", command=self.next_monitor)
        self.menu.add_command(label="Kömür ile konuş", command=self._on_speak_click)
        self.menu.add_command(label="Komut geçmişi ve ayarlar", command=self.assistant_history)
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
        if self.shortcut is None:
            return
        if self.shortcut.requested.is_set():
            self.shortcut.requested.clear()
            self.show_panel()
        boss = getattr(self.shortcut, "boss_requested", None)
        if boss is not None and boss.is_set():
            boss.clear()
            if self.settings.get("boss_key_mode", False):
                self.toggle_boss_key()

    def toggle_boss_key(self):
        if getattr(self, "boss_key", None) is None:
            return None
        return self.boss_key.toggle(self)

    def toggle_box_prop(self):
        """HUD/menü adı korunur: karton kutu artık masaüstü oyuncağıdır."""
        return self.toggle_toy("box")

    def toggle_toy(self, kind):
        """Masaüstü oyuncağını kedinin yanına koy ya da kaldır."""
        if getattr(self, "toybox", None) is None:
            return None
        from desktop_toys import LABELS, SIZES
        area = self.areas[self.area_index]
        tw, _ = SIZES[kind]
        cx = self.brain.x + self.w / 2
        side = 140 if self.brain.facing >= 0 else -140
        tx = cx + side
        if tx + tw / 2 > area.right - 10 or tx - tw / 2 < area.left + 10:
            tx = cx - side
        tx = max(area.left + tw / 2 + 10, min(area.right - tw / 2 - 10, tx))
        placed = self.toybox.toggle(kind, tx, self.brain.y + self.h * 0.93)
        if self.brain.state == "sleep" and (placed or kind == "box"):
            self.brain.command("wake")   # yeni oyuncak ya da kutusu kalkan kedi uyanır
        if kind == "box" and not placed and self.brain.state == "box_sit":
            self.brain.rest()
        self.say(f"{LABELS[kind]} {'hazır!' if placed else 'kaldırıldı.'}", 3)
        return placed

    def _step_toys(self, dt, now):
        box = getattr(self, "toybox", None)
        if box is None:
            return
        box.set_visible(not self.hidden)
        if not box.toys or self.hidden:
            return
        if self._frames % 30 == 0 or not hasattr(self, "_toy_platforms"):
            rect = window_utils.active_window_rect(ignore_hwnds=self._own_hwnds())
            # küçük pencereler raf sayılmaz
            self._toy_platforms = [(rect[0], rect[1], rect[2])] if rect and rect[2] - rect[0] >= 160 else []
        area = self.areas[self.area_index]
        perched = bool(getattr(getattr(self, "physics", None), "perched", False))
        # oyuncaklar kedinin yürüdüğü zemine (yuva hizasındaki ayak çizgisi) oturur
        if not perched:
            self._toy_ground = min(area.bottom, self.brain.home_y + self.h * 0.93)
        elif not hasattr(self, "_toy_ground"):
            self._toy_ground = area.bottom
        brain = self.brain
        if box.box_until and brain.state != "box_sit":
            box.exit_box()
        idle = (not brain.paused and not perched and not getattr(brain, "_goal", False)
                and brain.state in ("sit", "look", "groom", "wander", "bored", "yawn"))
        event = box.step(
            dt, now, (area.left, area.top, area.right, self._toy_ground), self._toy_platforms,
            (brain.x + self.w / 2, brain.y + self.h * 0.85),
            idle,
            float(getattr(brain, "hunger", 0.0)),
        )
        if not event:
            if brain.state == "box_sit" and not box.box_until:
                brain.rest()
            return
        action = event["action"]
        if perched and action in ("go", "drink", "scratch", "box"):
            if action == "box":
                box.exit_box()
            return
        anchors = box.anchors()
        cat_cx = brain.x + self.w / 2
        if action == "go":
            tx, bottom = event["target"]
            if event.get("kind") in ("bowl", "post"):
                # oyuncağın yanına dur: başı (ön tarafı) kasenin/tahtanın üstüne gelsin
                side = 1.0 if tx >= cat_cx else -1.0
                tx -= side * min(self.w * 0.25, 55.0)
            brain.go_to(tx - self.w / 2, bottom - self.h * 0.93)
        elif action == "bat":
            if "yarn" in anchors:
                tx, _ = anchors["yarn"]
                brain.facing = 1 if tx >= cat_cx else -1
            brain._change("play", duration=1.1)
            brain.hide_internal_ball = True
        elif action == "drink":
            if "bowl" in anchors:
                tx, tb = anchors["bowl"]
                brain.facing = 1 if tx >= cat_cx else -1
                target_x = tx - self.w * (0.78 if brain.facing > 0 else 0.22)
                brain.x = max(brain.bounds.left, min(brain.bounds.right, target_x))
                brain.y = max(brain.bounds.top, min(brain.bounds.bottom, tb - self.h * 0.93))
            if hasattr(brain, "hunger"):
                brain.hunger = max(0.0, brain.hunger - 35.0)
            brain.happiness = min(100.0, brain.happiness + 8.0)
            brain._change("drink", duration=6.0)
            self.say("Süt! Lık lık lık… 🥛", 5)
        elif action == "scratch":
            if "post" in anchors:
                tx, tb = anchors["post"]
                brain.facing = 1 if tx >= cat_cx else -1
                target_x = tx - self.w * (0.76 if brain.facing > 0 else 0.24)
                brain.x = max(brain.bounds.left, min(brain.bounds.right, target_x))
                brain.y = max(brain.bounds.top, min(brain.bounds.bottom, tb - self.h * 0.93))
            brain._change("scratch", duration=5.5)
            self.say("Tırmalama zamanı! 🐾", 4)
            if getattr(self, "affection", None) is not None:
                try:
                    self.affection.record_action("play")
                except Exception:
                    logging.debug("Affection action failed", exc_info=True)
        elif action == "box":
            stay = float(event.get("stay", 25.0))
            if "box" in anchors:
                tx, tb = anchors["box"]
                brain.x = max(brain.bounds.left, min(brain.bounds.right, tx - self.w / 2))
                brain.y = max(brain.bounds.top, min(brain.bounds.bottom, tb - self.h * 0.93))
                brain.home_x, brain.home_y = brain.x, brain.y
            brain._change("box_sit", duration=stay)
            self.say("Kutu benim! 📦", 4)

    def _ensure_laser_dot(self):
        if getattr(self, "_laser_dot", None) is not None:
            return self._laser_dot
        try:
            from desktop_toys import _LaserDotWindow
            self._laser_dot = _LaserDotWindow(self.root)
        except Exception:
            logging.debug("LaserDotWindow init failed", exc_info=True)
            self._laser_dot = None
        return self._laser_dot

    def _hide_laser_dot(self, destroy=False):
        dot = getattr(self, "_laser_dot", None)
        if dot is None:
            return
        try:
            if destroy:
                dot.destroy()
                self._laser_dot = None
            else:
                dot.hide()
        except Exception:
            pass

    def toggle_laser(self):
        if getattr(self, "physics", None) is None:
            return None
        if self.physics.chasing_laser:
            self.physics.clear_props("laser")
            self._hide_laser_dot(destroy=False)
            self.brain.hide_internal_ball = False
            self.brain.rest()
            self.say("Lazer kapatıldı.", 3)
            return False
        if getattr(self, "toybox", None) is not None and self.toybox.box_until:
            self.toybox.exit_box()
        ptr = None
        try:
            ptr = pointer_position(self.root)
        except Exception:
            ptr = None
        lx = ptr[0] if ptr else self.brain.x + 40
        ly = ptr[1] if ptr else self.brain.y + 40
        self.physics.spawn_prop("laser", lx, ly)
        self.brain.hide_internal_ball = False
        self.brain._change("laser_chase", duration=float("inf"))
        dot = self._ensure_laser_dot()
        if dot is not None and not self.hidden:
            dot.show(lx, ly)
        self.say("Lazer yakalama zamanı! 🔴", 4)
        return True

    def _own_hwnds(self):
        """Return known HWND integers for Komur's own windows so active_window_rect ignores them."""
        hwnds = set()
        candidates = [getattr(self, "root", None), getattr(self, "panel", None)]
        bubble = getattr(self, "bubble", None)
        if bubble is not None:
            candidates.append(getattr(bubble, "window", None) or getattr(bubble, "root", None))
        assistant = getattr(self, "assistant", None)
        if assistant is not None:
            candidates.append(getattr(assistant, "window", None))
            candidates.append(getattr(assistant, "compact_window", None))
        hud = getattr(self, "context_hud", None)
        if hud is not None:
            candidates.append(getattr(hud, "window", None))
        toybox = getattr(self, "toybox", None)
        if toybox is not None:
            for toy in getattr(toybox, "toys", {}).values():
                candidates.append(getattr(toy, "win", None))
        laser_dot = getattr(self, "_laser_dot", None)
        if laser_dot is not None:
            candidates.append(getattr(laser_dot, "win", None))
        for mate in getattr(self, "companions", ()) or ():
            candidates.append(getattr(mate, "root", None) or getattr(mate, "window", None))
        for win in candidates:
            if win is None:
                continue
            try:
                wid = int(win.winfo_id())
                if wid:
                    hwnds.add(wid)
                    if IS_WINDOWS:
                        parent = ctypes.windll.user32.GetParent(wid)
                        if parent:
                            hwnds.add(int(parent))
            except Exception:
                continue
        return hwnds

    def _stop_laser(self):
        if getattr(self, "physics", None) is not None and self.physics.chasing_laser:
            self.physics.clear_props("laser")
        self._hide_laser_dot(destroy=False)
        self.brain.hide_internal_ball = False

    def _stop_perch(self):
        physics = getattr(self, "physics", None)
        if physics is not None:
            physics.perched = False
            physics.perch_rect = None
            physics.perch_hwnd = None
            physics._jump = None
            if physics.surface == "window_top":
                physics.surface = "ground"
        self._was_perched = False

    def perch_active_window(self, quiet=False):
        """Jump onto the top edge of the active foreground window."""
        if getattr(self, "physics", None) is None:
            return False
        self._stop_laser()
        area = self.areas[self.area_index]
        self.physics.bounds = (area.left, area.top, area.right, area.bottom)
        hwnd = window_utils.foreground_hwnd(ignore_hwnds=self._own_hwnds())
        rect = window_utils.window_rect(hwnd) if hwnd else None
        if rect is None:
            if not quiet:
                self.say("Tünenecek aktif pencere bulunamadı.", 3)
            return False
        if getattr(self, "toybox", None) is not None and self.toybox.box_until:
            self.toybox.exit_box()
        self.physics.x, self.physics.y = self.brain.x, self.brain.y
        ok = self.physics.perch_on_window(rect, cat_x=self.brain.x, hwnd=hwnd, animate=True)
        if ok:
            self._was_perched = True
            # yuva pencere tepesi: kedi orada yatay dolaşır/oturur (ekran üstüne sıkışmışsa kırpılmış y)
            cx = max(rect[0], min(max(rect[0], rect[2] - self.w), self.brain.x))
            target_y = self.physics._perch_y(rect[1])
            self.brain.home_x, self.brain.home_y = cx, target_y
            jump = getattr(self.physics, "_jump", None)
            if jump is not None:
                if abs(jump["x1"] - jump["x0"]) > 1.0:
                    self.brain.facing = 1 if jump["x1"] > jump["x0"] else -1
                self.brain._change("jump", duration=self.physics.JUMP_SECONDS + 0.2)
            else:
                self.brain._change("perch", duration=15.0)
            self._apply_position()
            if not quiet:
                self.say("Pencere tepesine zıpladım! 🐾", 4)
        return ok

    def walk_on_taskbar_cmd(self):
        """Move the cat down onto the top edge of the Windows taskbar."""
        if getattr(self, "physics", None) is None:
            return False
        self._stop_laser()
        self._stop_perch()
        tb = window_utils.taskbar_rect()
        if tb is None:
            self.say("Görev çubuğu bulunamadı.", 3)
            return False
        ok = self.physics.walk_on_taskbar(tb, cat_x=self.brain.x)
        if ok:
            self.brain.x, self.brain.y = self.physics.x, self.physics.y
            self.brain.rest()
            self._apply_position()
            self.say("Görev çubuğuna indim!", 4)
        return ok

    def toggle_retro_mode(self):
        enabled = not bool(self.settings.get("retro_mode", False))
        self.settings.set("retro_mode", enabled)
        if hasattr(self, "retro_var"):
            self.retro_var.set(enabled)
        if getattr(self, "renderer", None) is not None and hasattr(self.renderer, "set_retro_mode"):
            self.renderer.set_retro_mode(enabled)
        self.say(f"Retro Pixel modu {'açıldı' if enabled else 'kapandı'}.", 3)
        return enabled

    def choose_weather_city(self, city=None):
        """Gerçek hava durumunu aç (şehir) ya da kapat (boş). Açıkken şehir adı Open-Meteo'ya gider."""
        if getattr(self, "weather", None) is None:
            return False
        if city is None:
            from tkinter import simpledialog
            city = simpledialog.askstring(
                "Hava durumu",
                "Şehir adı (boş bırakırsan kapanır). "
                "Açıkken yalnız şehir adı Open-Meteo'ya gönderilir.",
                initialvalue=self.settings.get("weather_city", ""), parent=self.root)
            if city is None:
                return False
        city = city.strip()
        if city and city == self.weather.city and self.settings.get("weather_enabled", False):
            text = self.weather.describe()      # aynı şehir: yeniden çekmeden mevcut durumu söyle
            if text:
                self.say(text, 7)
            else:
                self.weather.request_announce()
                self.say(f"{city} için bakıyorum… 🌦️", 4)
            return True
        self.settings.update(weather_city=city, weather_enabled=bool(city))
        self.weather.set_city(city)
        self.brain.weather = None
        self.say(f"{city} için bakıyorum… 🌦️" if city else "Hava durumu kapatıldı.", 4)
        return bool(city)

    def _step_weather(self):
        watcher = getattr(self, "weather", None)
        if watcher is None:
            return
        watcher.poll(self.settings.get("weather_enabled", False))
        self.brain.weather = watcher.condition
        text = watcher.take_announcement()   # şehir seçildikten sonraki ilk sonuç hemen söylenir
        if text:
            self.say(text, 7)
        change = watcher.take_change()
        if change:
            from weather import MESSAGES, SETTLE
            if change in SETTLE:
                self.brain.settle(SETTLE[change])
            if change in MESSAGES and self.settings.get("speech_bubbles", True):
                self.say_unsolicited(MESSAGES[change], 7)

    def toggle_lofi_ambience(self):
        lofi = getattr(getattr(self, "acoustic", None), "lofi", None)
        if lofi is None:
            return False
        if lofi.is_playing:
            lofi.stop()
            self.settings.set("lofi_ambience", False)
            self.say("Lofi ambiyans durduruldu.", 3)
            return False
        lofi.start(master_vol=max(0.1, min(1.0, (self.settings.get("sound_volume", 70) or 70) / 200.0)))
        self.settings.set("lofi_ambience", True)
        self.say("Lofi odak ambiyansı başladı. 🎧", 3)
        return True

    def _on_file_drop(self, paths):
        if not paths or getattr(self, "basket", None) is None:
            return []
        results = self.basket.handle_drop_many(list(paths))
        if results:
            msg = results[-1].get("message")
            if msg:
                self.say(msg, 8)
        return results

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

    def start_focus(self, work_min=25, break_min=5):
        self.focus.start(work_min, break_min, now=time.monotonic())

    def stop_focus(self):
        self.focus.stop()

    def toggle_focus(self):
        if self.focus.phase == "idle":
            self.start_focus()
        else:
            self.stop_focus()
            self.say("Pomodoro bitirildi.", 6)

    def handle_focus_command(self, command):
        """Sohbetten gelen ayrıştırılmış odak komutunu uygular; sohbete yazılacak kısa yanıtı döner."""
        if command["action"] == "stop":
            if self.focus.phase == "idle":
                return "Şu an açık bir pomodoro yok."
            self.stop_focus()
            return "Pomodoro bitirildi."
        self.start_focus(command["work_min"], command["break_min"])
        return f"Pomodoro başladı: {command['work_min']} dk odak, {command['break_min']} dk mola. Ben sessizce uyurum."

    def _tick_focus(self, now):
        events = self.focus.tick(now)
        for event in events:
            self.say(MESSAGES[event], 8)
            if event == "work_done" and getattr(self, "affection", None) is not None:
                try:
                    self.affection.record_action("pomodoro")
                except Exception:
                    logging.debug("Affection pomodoro XP failed", exc_info=True)
        if events:
            state = phase_to_cat_state(self.focus.phase)
            if state:
                self.brain.settle(state)

    def say(self, text, seconds):
        self.message = text
        self.message_until = time.monotonic() + seconds

    UNSOLICITED_GAP = 900.0   # kendiliğinden konuşma (etkinlik/alışkanlık) en fazla 15 dk'da bir

    def say_unsolicited(self, text, seconds):
        """Kullanıcı istemeden konuşma: tek bir genel sınırla seyrek tutulur. Söylendiyse True."""
        now = time.monotonic()
        if now - getattr(self, "_last_unsolicited", float("-inf")) < self.UNSOLICITED_GAP:
            return False
        self._last_unsolicited = now
        self.say(text, seconds)
        return True

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

    def open_chat(self):
        """Komut yazma balonunu aç (çift tık / HUD kartı)."""
        self.assistant.show()

    def assistant_history(self):
        self.assistant.show_history()

    def _on_key_press(self, event):
        kb = getattr(getattr(self, "acoustic", None), "keyboard", None)
        if kb is not None:
            try:
                kb.record_keystroke()
            except Exception:
                logging.debug("Keyboard reactive tracking failed", exc_info=True)

    def _sound_enabled(self) -> bool:
        return bool(self.sound_var.get()) and bool(self.settings.get("sound", True)) and not self.muted

    def _play_cat_sound(self, kind: str, volume: int = 70) -> None:
        if not self._sound_enabled():
            return
        try:
            area = self.areas[self.area_index]
            sounds.play(
                kind,
                enabled=True,
                quality=self.settings.get("sound_quality", "high"),
                volume=volume,
                pan_x=self.brain.x + self.w / 2,
                screen_w=max(1.0, area.right - area.left),
                pitch_shift="auto",
            )
        except Exception:
            logging.debug("Cat sound playback failed: %s", kind, exc_info=True)

    def toggle_sound(self) -> bool:
        """Kedi seslerini tek tıkla aç veya kapat; ayarı kaydet ve HUD'u güncelle."""
        enabled = not bool(self.sound_var.get())
        self.sound_var.set(enabled)
        self.settings.set("sound", enabled)
        orchestrator = getattr(self, "effect_orchestrator", None)
        if orchestrator is not None:
            orchestrator.sound_enabled = enabled
        hud = getattr(self, "context_hud", None)
        if hud is not None:
            try:
                if hud.visible or callable(getattr(hud, "refresh", None)):
                    hud.refresh()
            except tk.TclError:
                pass
        self.say("Sesler açıldı" if enabled else "Sesler kapatıldı", 3)
        return enabled

    def command(self, name):
        self.brain.hide_internal_ball = False
        if name not in ("pause", "resume", "laser_chase"):
            self._stop_laser()
        if name in ("follow", "wander", "play", "roll", "box_sit", "drink", "scratch"):
            self._stop_perch()
        if name not in ("pause", "resume") and getattr(self, "toybox", None) is not None and self.toybox.box_until:
            self.toybox.exit_box()
        if name in ("dance", "watch"):
            self._manual_reaction = "music" if name == "dance" else "video"
            self._manual_reaction_until = time.monotonic() + 20.0
            self.brain.command("wake")
            self.brain._change("sit", duration=20.0)
        else:
            self._manual_reaction = None
            self._manual_reaction_until = 0.0
            self.brain.command(name)
            if name == "feed" and self.brain.state == "sit":
                self.brain.visual_pose = "eat"
                self.brain.visual_pose_duration = 4.0
            elif name == "pet" and self.brain.state == "sit":
                self.brain.visual_pose = "purr_idle"
                self.brain.visual_pose_duration = 3.5
        if name == "pet":
            self._play_cat_sound("purr", volume=70)
            self._prev_sound_state = self.brain.state
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
        orchestrator = getattr(self, "effect_orchestrator", None)
        if orchestrator is not None:
            orchestrator.cat_screen_x = self.brain.x + self.w / 2
            if name in ("pet", "feed"):
                orchestrator.trigger(name, 0, 0)

        if name in ("pet", "feed", "play") and getattr(self, "affection", None) is not None:
            try:
                ev = self.affection.record_action(name)
                if ev.get("leveled_up"):
                    self.say(f"Dostluk Seviye {ev['level']} oldu! ✨", 6)
            except Exception:
                logging.debug("Affection action failed", exc_info=True)

        self._refresh_status()

    def _sync_effect_state(self):
        state = self.brain.state
        prev_sound = getattr(self, "_prev_sound_state", self._effect_state)
        if state != prev_sound:
            if state == "yawn":
                self._play_cat_sound("yawn", volume=70)
            elif prev_sound == "sleep" and state not in ("sleep", "paused") and not getattr(self.brain, "paused", False):
                self._play_cat_sound("meow", volume=65)
            self._prev_sound_state = state
        if state == self._effect_state:
            return
        self.effect_orchestrator.cat_screen_x = self.brain.x + self.w / 2
        self.effect_orchestrator.trigger_state_exit(self._effect_state, 0, 0)
        self.effect_orchestrator.trigger_state_enter(state, 0, 0)
        if state == "follow":
            self.effect_orchestrator.trigger("follow_start", 0, 0)
        self._effect_state = state

    def toggle_pause(self):
        self.command("resume" if self.brain.paused else "pause")

    # -- mouse ------------------------------------------------------------
    def _press(self, event):
        if IS_MAC and (
            (getattr(event, "state", 0) & 0x4)
            or (time.monotonic() - getattr(self, "_last_menu_toggle", -10.0) < 0.35)
        ):
            return
        self._pressed_while_active = window_utils.last_left_click_was_active() and window_utils.mac_app_is_active()
        self._pressed_hud_was_open = bool(getattr(getattr(self, "context_hud", None), "visible", False))
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
            phys = getattr(self, "physics", None)
            if phys is not None and phys.perched:
                phys.perched = False
                phys.perch_rect = None
                phys.perch_hwnd = None
                phys._jump = None
                phys.surface = "ground"
            if getattr(self, "toybox", None) is not None and self.toybox.box_until:
                self.toybox.exit_box()
            self.brain.move_to(x + dx, y + dy)
            self._apply_position()

    def _release(self, event):
        if self.drag_origin is None:
            return
        self.drag_origin = None
        pressed_active = getattr(self, "_pressed_while_active", True)
        hud_was_open = getattr(self, "_pressed_hud_was_open", False)
        self._pressed_while_active = True
        self._pressed_hud_was_open = False
        if self.dragged:
            self.brain.rest()  # birakilan yer yeni yuva (move_to ayarladi)
            self.say("Burayı sevdim!", 5)
            return
        if (
            pressed_active
            and not hud_was_open
            and not self.menu_open
            and (time.monotonic() - getattr(self, "_last_menu_toggle", -10.0) >= 0.35)
        ):
            # Tek tık (sürükle değil): sevme. Sohbet orta tık / HUD ile açılır.
            self.command("pet")

    def _show_menu_at(self, x_root, y_root):
        self._show_menu(types.SimpleNamespace(x_root=int(x_root), y_root=int(y_root)))

    def _show_menu(self, event):
        now = time.monotonic()
        if now - getattr(self, "_last_menu_toggle", -10.0) < 0.20:
            return
        self._last_menu_toggle = now
        self.drag_origin = None
        hud = getattr(self, "context_hud", None)
        if hud is not None:
            try:
                if hud.visible:
                    hud.hide()
                    self.menu_open = False
                else:
                    hud.show(event.x_root, event.y_root)
                return
            except Exception:
                logging.debug("ModernContextHUD show failed, falling back to tk.Menu", exc_info=True)
        self.menu_open = True
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
        if getattr(self, "affection", None) is not None and hasattr(self, "affection_var"):
            self.affection_var.set(f"Sv.{self.affection.level} ({self.affection.xp} XP)")

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
        step_x = self.w + 24
        for idx in range(count):
            # Arkadaş kediyi ana kedinin hemen yanında (görünür yerde) başlat.
            prefer_left = self.brain.x - (idx + 1) * step_x
            prefer_right = self.brain.x + (idx + 1) * step_x
            if prefer_left >= area.left + 12:
                mx = prefer_left
            elif prefer_right <= area.right - self.w - 12:
                mx = prefer_right
            else:
                mx = area.left + 40 + idx * step_x
            my = self.brain.y
            try:
                mate = Companion(self.root, area, self.settings.scale,
                                 self.settings.get("skin"), self.settings.get("needs"),
                                 self.settings.get("activity_level"),
                                 start_pos=(mx, my), on_menu=self._show_menu, index=idx)
                mate.set_opacity(self.settings.get("opacity"))
                self.companions.append(mate)
            except tk.TclError:
                break

    # -- panel (panel.py) -------------------------------------------------
    def show_panel(self):
        _show_panel(self)

    # -- monitors / geometry ---------------------------------------------
    def next_monitor(self):
        self._stop_laser()
        self._stop_perch()
        self.areas = monitor_bounds(self.root)
        self.area_index = (self.area_index + 1) % len(self.areas)
        area = self.areas[self.area_index]
        self.brain.set_bounds(self._movement_bounds(area, self.w, self.h))
        self.brain.move_to(area.right - self.w - 25, area.bottom - self.h - 15)
        self.settings.set("area_index", self.area_index)
        self.brain.rest()
        self.say(f"Ekran {self.area_index + 1}/{len(self.areas)}", 5)

    @staticmethod
    def _movement_bounds(area, w=WIDTH, h=HEIGHT):
        return movement_bounds(area, w, h)

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
            if IS_MAC and not self.hidden:
                window_utils.poll_mac_right_clicks(pointer_position(self.root))
            self._tick_focus(now)
            if self.drag_origin is None and not self.menu_open:
                pointer = pointer_position(self.root)
                reaction = self.activity_reactions.poll(now, self.settings.get("activity_reactions", True))
                self._apply_activity_reaction(now)
                compact = self.assistant.compact_visible
                if compact and self._chat_anchor is None:
                    self._chat_anchor = (self.brain.x, self.brain.y)
                elif not compact:
                    self._chat_anchor = None
                # Keep the input close enough to type while the cat remains animated.
                old_x, old_y = self.brain.x, self.brain.y
                prev_state = self.brain.state
                self.brain.step(dt, pointer)
                if not self.brain.paused:
                    self._maybe_post_meal_groom(prev_state)
                physics = getattr(self, "physics", None)
                if compact and physics is not None and (physics.falling or physics.perched or physics.chasing_laser):
                    self._chat_anchor = (self.brain.x, self.brain.y)   # düşüş/tünek/lazer çapaya takılmasın
                elif compact:
                    ax, ay = self._chat_anchor
                    self.brain.x = max(ax - 24, min(ax + 24, self.brain.x))
                    self.brain.y = max(ay - 16, min(ay + 16, self.brain.y))
                elif getattr(self.brain, "_goal", False):
                    pass   # kullanıcının koyduğu oyuncağa gidiş yavaşlatılmaz
                elif (reaction == "gaming" and self.settings.get("focus_mode", True)) or self._still_reaction or self.focus.phase == "work":
                    self.brain.x = old_x + (self.brain.x - old_x) * .15
                    # dikey (düşüş/yuvaya iniş) sönümlenmez: kedi havada asılı kalmasın
                self.brain.activity_reaction = (self._manual_reaction
                                                if now < self._manual_reaction_until else reaction)
                self._sync_effect_state()
                if not self.brain.paused:
                    self.animation_time += dt
                    self.effect_orchestrator.step(dt)
                    self._step_v2_subsystems(dt, pointer, now)
                    self._maybe_auto_perch(now, reaction)
                else:
                    self._hide_laser_dot(destroy=False)
                inv_dt = 1.0 / max(dt, 0.001)
                self.brain.vx = (self.brain.x - old_x) * inv_dt
                self.brain.vy = (self.brain.y - old_y) * inv_dt
                self.brain.pointer_xy = pointer
                self.effect_orchestrator.cat_screen_x = self.brain.x + self.w / 2
                area = self.areas[self.area_index]
                self.effect_orchestrator.screen_w = max(1.0, area.right - area.left)
                if not (reaction == "gaming" and self.settings.get("focus_mode", True)) and self.companions:
                    step_companions(self.companions, dt, pointer, primary_cat=self)
                self._update_speech(now, pointer)
            if not self.hidden:
                self._apply_position()
            else:
                self._hide_laser_dot(destroy=False)
            message = self.message if now < self.message_until else self._get_speech_message(now)
            if self.hidden or self.assistant.compact_visible:
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
            self.renderer.accessory = self.settings.get("accessory")
            self.renderer.time_of_day = self._time_of_day(now)
            if hasattr(self.renderer, "set_retro_mode"):
                self.renderer.set_retro_mode(bool(self.settings.get("retro_mode", False)))
            self.brain.age_days = float(self.settings.get("age_days", 7.0))
            if not self.hidden:
                self.renderer.draw(
                    self.brain, self.animation_time, message=message,
                    effect_orchestrator=self.effect_orchestrator,
                )
            self._frames += 1
            if IS_MAC and not self.hidden and now - getattr(self, "_last_mac_chrome", 0.0) >= 2.5:
                self._last_mac_chrome = now
                window_utils._mac_apply_window_chrome(order_front=True)
            if self._frames % 20 == 0:
                self._refresh_status()
        except Exception:
            logging.exception("Animation frame failed")
            self.say("Bir çizim sorunu oluştu; yeniden deneniyor.", 2)
        finally:
            if not self.closed:
                self.after_id = self.root.after(16, self._loop)

    def _step_v2_subsystems(self, dt, pointer, now):
        """Advance v2.0 physics, fish pond, health guard, and periodic sensors safely."""
        try:
            self._step_toys(dt, now)
        except Exception:
            logging.debug("ToyBox step failed", exc_info=True)
        if getattr(self, "physics", None) is not None:
            try:
                area = self.areas[self.area_index]
                self.physics.bounds = (area.left, area.top, area.right, area.bottom)
                dot = getattr(self, "_laser_dot", None)
                if dot is not None and (self.hidden or not self.physics.chasing_laser):
                    if dot.visible:
                        dot.hide()
                if self._frames % 30 == 0 or not hasattr(self, "_cached_has_toast"):
                    self._cached_has_toast = bool(window_utils.has_toast_notification())
                has_toast = self._cached_has_toast
                if (
                    self.physics.chasing_laser
                    or self.physics.props
                    or self.physics.falling
                    or self.physics.perched
                    or self.physics.paw_trails
                    or has_toast
                ):
                    if self.physics.chasing_laser and not self.hidden and pointer is not None:
                        dot = self._ensure_laser_dot()
                        if dot is not None:
                            if not dot.visible:
                                dot.show(pointer[0], pointer[1])
                            else:
                                dot.update(pointer[0], pointer[1], dt)
                    perch_hwnd = getattr(self.physics, "perch_hwnd", None)
                    if self.physics.perched and perch_hwnd:
                        window_rect = window_utils.window_rect(perch_hwnd)   # kilitli pencereyi izle
                    elif self.physics.perched:
                        window_rect = window_utils.active_window_rect(ignore_hwnds=self._own_hwnds())
                    else:
                        window_rect = None
                    taskbar_rect = window_utils.taskbar_rect()
                    was_jumping = bool(getattr(self.physics, "_jump", None) is not None)
                    px, py = self.physics.step(
                        dt, self.brain.x, self.brain.y,
                        facing=getattr(self.brain, "facing", 1),
                        pointer=pointer,
                        window_rect=window_rect,
                        taskbar_rect=taskbar_rect,
                        has_toast=has_toast,
                    )
                    if (
                        self.physics.chasing_laser
                        or self.physics.in_box
                        or self.physics.on_bed
                        or self.physics.falling
                        or self.physics.perched
                        or self.physics.toast_curious
                    ):
                        self.brain.x, self.brain.y = px, py
                        if self.physics.chasing_laser:
                            self.brain.home_x, self.brain.home_y = px, py
                            laser_prop = next(
                                (p for p in self.physics.props if p.active and p.kind == "laser"),
                                None,
                            )
                            if laser_prop is not None:
                                ldx = laser_prop.x - (px + self.w * 0.5)
                                ldy = laser_prop.y - (py + self.h * 0.5)
                                if abs(ldx) > 2.0:
                                    self.brain.facing = 1 if ldx > 0 else -1
                                if math.hypot(ldx, ldy) <= 28.0:
                                    if self.brain.state != "play":
                                        self.brain._change("play", duration=float("inf"))
                                    self.brain.hide_internal_ball = True
                                else:
                                    if self.brain.state != "laser_chase":
                                        self.brain._change("laser_chase", duration=float("inf"))
                                    self.brain.hide_internal_ball = False
                        elif self.physics.perched:
                            jump = getattr(self.physics, "_jump", None)
                            if jump is not None:
                                if abs(jump["x1"] - jump["x0"]) > 1.0:
                                    self.brain.facing = 1 if jump["x1"] > jump["x0"] else -1
                                if self.brain.state != "jump":
                                    self.brain.state = "jump"
                            else:
                                self.brain.home_y = py
                                if was_jumping:
                                    self.brain.home_x, self.brain.home_y = px, py
                                    self.brain._change("perch", duration=15.0)
                    perched = bool(self.physics.perched)
                    if getattr(self, "_was_perched", False) and not perched:
                        # düştü/indi: yuva yeniden zemine ve perch pozu sonlandır
                        self.brain.home_x = self.brain.x
                        self.brain.home_y = area.bottom - self.h
                        if self.brain.state in ("perch", "jump"):
                            if self.physics.startled:
                                self.brain._change("startle", duration=0.8)
                            else:
                                self.brain.rest()
                    self._was_perched = perched
                if not self.physics.chasing_laser and self.brain.state != "play":
                    self.brain.hide_internal_ball = False
                self.brain.props = list(self.physics.props)
                self.brain.paw_trails = list(self.physics.paw_trails)
                self.brain.on_bed = self.physics.on_bed
                self.brain.startled = self.physics.startled
            except Exception:
                logging.debug("DesktopPhysics step failed", exc_info=True)

        if getattr(self, "fish_pond", None) is not None:
            try:
                self.fish_pond.step(dt)
                self.brain.fishes = self.fish_pond.list_tasks()
            except Exception:
                logging.debug("TodoFishPond step failed", exc_info=True)

        if getattr(self, "health_guard", None) is not None:
            try:
                reminder = self.health_guard.step(dt, is_working=True, pointer=pointer, now=now)
                if reminder and self.settings.get("speech_bubbles", True):
                    self.say_unsolicited(reminder["message"], 8)
            except Exception:
                logging.debug("HealthWaterGuard step failed", exc_info=True)

        if self._frames % 60 == 0:
            try:
                self._step_weather()
            except Exception:
                logging.debug("Weather step failed", exc_info=True)

        if self._frames % 300 == 0:
            if getattr(self, "hardware_mind", None) is not None:
                try:
                    thermal = self.hardware_mind.evaluate()
                    if thermal and self.settings.get("speech_bubbles", True):
                        self.say_unsolicited(thermal["message"], 6)
                except Exception:
                    logging.debug("HardwareMind poll failed", exc_info=True)

    def _glide_to_video_corner(self) -> bool:
        """Video izlerken altyazıları kapatmamak için en yakın alt köşeye yumuşakça geç."""
        phys = getattr(self, "physics", None)
        if phys is not None and (phys.perched or phys.falling or phys.chasing_laser):
            return False
        if self.brain.paused or self.brain.state in ("follow", "play", "sleep", "box_sit", "drink", "eat", "scratch"):
            return False
        area = self.areas[self.area_index]
        left_x = area.left + 18
        right_x = max(area.left, area.right - self.w - 18)
        bottom_y = max(area.top, area.bottom - self.h - 14)
        corner_x = right_x if self.brain.x >= (left_x + right_x) * 0.5 else left_x
        self.brain.home_x, self.brain.home_y = corner_x, bottom_y
        if math.hypot(corner_x - self.brain.x, bottom_y - self.brain.y) > 40.0:
            return bool(self.brain.go_to(corner_x, bottom_y))
        return False

    def _maybe_post_meal_groom(self, prev_state: str):
        """Mama veya süt sonrası gerçek bir kedi gibi kısa bir pati temizleme (groom) yap."""
        if (
            prev_state in ("drink", "eat")
            and self.brain.state != prev_state
            and self.brain.state in ("sit", "look", "wander")
            and random.random() < 0.6
        ):
            self.brain._change("groom", duration=random.uniform(3.0, 5.0))

    def _maybe_auto_perch(self, now: float, reaction: str):
        """Kullanıcı aktif çalışırken seyrek olarak aktif pencere tepesine zıplayıp izle."""
        if now < getattr(self, "_next_auto_perch_at", float("inf")):
            return
        self._next_auto_perch_at = now + random.uniform(75.0, 120.0)
        if reaction not in ("coding", "writing", "reading"):
            return
        if self.hidden or self.brain.paused or self.assistant.compact_visible or self.focus.phase == "work":
            return
        if self.brain.state not in ("wander", "sit", "look") or getattr(self.brain, "_goal", False):
            return
        phys = getattr(self, "physics", None)
        if phys is None or phys.perched or phys.falling or phys.chasing_laser or phys.in_box:
            return
        toybox = getattr(self, "toybox", None)
        if toybox is not None and toybox.box_until:
            return
        hwnd = window_utils.foreground_hwnd(ignore_hwnds=self._own_hwnds())
        rect = window_utils.window_rect(hwnd) if hwnd else None
        if not rect or (rect[2] - rect[0]) < max(240, self.w + 40) or (rect[3] - rect[1]) < 120:
            return
        try:
            from context import _is_fullscreen
            if _is_fullscreen(hwnd):
                return
        except Exception:
            return
        self.perch_active_window(quiet=True)

    def _apply_activity_reaction(self, now):
        """Algılanan etkinlik değiştiğinde bir kez: sakin bir duruma geç, seyrek kısa mesaj."""
        reaction = self.activity_reactions.take_reaction()
        if not reaction:
            return
        self._still_reaction = bool(reaction.get("still"))
        if now < self._manual_reaction_until or self.assistant.compact_visible:
            return
        if reaction.get("welcome_back"):
            self.brain.settle("stretch")
            self._prev_sound_state = self.brain.state
            if self._sound_enabled():
                self._play_cat_sound("chirp", volume=int(self.settings.get("sound_volume", 70) or 70))
        elif reaction.get("class") == "video":
            if not self._glide_to_video_corner():
                self.brain.settle("sit")
        else:
            state = {"loaf": "sit", "watch": "sit"}.get(reaction.get("state"), reaction.get("state"))
            self.brain.settle(state)
        if self._still_reaction and self.brain.state == "wander" and not getattr(self.brain, "_goal", False):
            self.brain.rest()   # yalnız kendiliğinden gezinmeyi durdur; takip/oyun/uyku/hedef yürüyüşü bozulmaz
        if reaction.get("message") and self.settings.get("speech_bubbles", True) and now >= self.message_until:
            self.say_unsolicited(reaction["message"], 8)

    def _time_of_day(self, now):
        if not self.settings.get("day_night", True):
            return "day"
        if now - self._tod_checked >= 60:
            hour = time.localtime().tm_hour
            self._tod = "night" if hour >= 22 or hour < 6 else "evening" if hour >= 18 else "day"
            self._tod_checked = now
        return self._tod

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.activity_reactions.close()
        except Exception:
            logging.debug("activity reactions close failed", exc_info=True)
        # remember where we are for next launch
        try:
            self.settings.update(x=round(self.brain.x), y=round(self.brain.y),
                                 area_index=self.area_index)
        except Exception:
            logging.debug("could not persist position", exc_info=True)
        for mate in self.companions:
            mate.destroy()
        if getattr(self, "toybox", None) is not None:
            self.toybox.close()
        self._hide_laser_dot(destroy=True)
        shortcut = getattr(self, "shortcut", None)
        if shortcut:
            shortcut.close()
        tray = getattr(self, "tray", None)
        if tray:
            tray.close()
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
        acoustic = getattr(self, "acoustic", None)
        if acoustic is not None:
            for sub in (getattr(acoustic, "lofi", None),):
                if sub is not None and callable(getattr(sub, "stop", None)):
                    try:
                        sub.stop()
                    except Exception:
                        pass
        self.assistant.close()
        hud = getattr(self, "context_hud", None)
        if hud is not None:
            try:
                hud.destroy()
            except Exception:
                pass
        self.bubble.destroy()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


_instance_lock = None


def acquire_instance():
    if IS_MAC:
        # Tek kopya: veri klasöründeki kilit dosyası; süreç kapanınca kilit kendiliğinden kalkar.
        import fcntl
        global _instance_lock
        directory = Path(os.environ["LOCALAPPDATA"]) / "Komur"
        directory.mkdir(parents=True, exist_ok=True)
        lock = open(directory / "komur.lock", "w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            lock.close()
            return (None, False)
        _instance_lock = lock
        return (None, True)
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
        if not IS_WINDOWS:
            return   # macOS: zaten açık bir Kömür var
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
                    result["command"] = app.assistant.commands.respond("uyu").reply
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
                "Uygulama başlatılamadı. Ayrıntılar: " + str(log_path()))
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

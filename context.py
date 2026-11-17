"""Kömür — kullanıcı ne yapıyor? Ön plan penceresi, kategori ve etkinlik takibi.

``get_foreground_info()`` ctypes ile aktif pencerenin başlığını ve işlem adını
okur; ``categorize()`` bunu bir kategoriye (coding, browsing, gaming, office,
chat, media, files, other) ve alt ipucuna (YouTube, GitHub…) çevirir.
``ActivityTracker`` birkaç saniyede bir örnekleyip kategori başına süre, kesintisiz
oturum süresi ve boşta kalma süresini tutar; ``summary()`` AI istemine eklenir,
``suggest_remark(now)`` kedinin kendiliğinden konuşması için olay önerir.

Pencere başlıkları özel içerik taşıyabilir: diske yazılmaz, yalnızca bellekte tutulur.
"""
from __future__ import annotations

import ctypes
import datetime as _dt
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field

IS_WINDOWS = sys.platform == "win32"

CATEGORY_LABELS = {
    "coding": "kod yazıyor", "browsing": "internette geziyor", "gaming": "oyun oynuyor",
    "office": "ofis işi yapıyor", "chat": "sohbet ediyor", "media": "müzik/video ile ilgileniyor",
    "files": "dosyalarla uğraşıyor", "other": "bilgisayarda bir şeyler yapıyor", "idle": "boşta",
}

# process name (lowercase, uzantısız) -> kategori
_PROCESS_CATEGORIES = {
    "coding": {"code", "code - insiders", "cursor", "pycharm", "pycharm64", "idea", "idea64", "devenv", "antigravity",
               "windowsterminal", "wt", "powershell", "pwsh", "cmd", "conhost", "mintty", "alacritty", "wezterm-gui",
               "sublime_text", "notepad++", "atom", "rider", "rider64", "clion", "clion64", "webstorm", "webstorm64",
               "goland64", "datagrip64", "androidstudio", "studio64", "zed", "neovide", "nvim", "vim", "gvim", "emacs",
               "claude", "python", "pythonw", "jupyter-lab", "unity", "unityhub", "godot", "ue4editor", "unrealEditor".lower()},
    "browsing": {"chrome", "msedge", "firefox", "opera", "opera_gx", "brave", "vivaldi", "launcher", "iexplore", "yandex",
                 "arc", "zen"},
    "gaming": {"valorant", "valorant-win64-shipping", "league of legends", "leagueclient", "leagueclientux",
               "league of legends", "rdr2", "hogwartslegacy", "minecraft", "tlauncher", "javaw", "minecraftlauncher",
               "cs2", "csgo", "dota2", "gta5", "gtav", "fortniteclient-win64-shipping", "eldenring", "witcher3",
               "cyberpunk2077", "rocketleague", "r5apex", "overwatch", "pubg", "tslgame", "mtd", "20minutestilldawn",
               "20 minutes till dawn", "steam_app", "steamwebhelper", "epicgameslauncher", "riotclientservices",
               "riotclientux", "roblox", "robloxplayerbeta", "amongus", "terraria", "stardew valley", "stardewvalley",
               "hades", "hollow_knight", "celeste", "fc24", "fc25", "fifa23", "efootball", "rainbowsix", "genshinimpact",
               "wutheringwaves", "zenlesszonezero", "starrail", "farcry6", "forza", "forzahorizon5", "ac_shipping",
               "assassinscreed", "baldursgate3", "bg3", "bg3_dx11", "palworld", "lethalcompany", "phasmophobia",
               "deadbydaylight", "rust", "rustclient", "ark", "shootergame", "sotgame", "halo", "doometernal",
               "spiderman", "godofwar", "horizonzerodawn", "thelastofus", "tlou-i", "ghostoftsushima"},
    "office": {"winword", "excel", "powerpnt", "onenote", "outlook", "acrord32", "acrobat", "libreoffice", "soffice",
               "soffice.bin", "wps", "notion", "obsidian", "msaccess", "teams", "ms-teams"},
    "chat": {"discord", "whatsapp", "telegram", "signal", "slack", "skype", "zoom", "messenger", "viber", "element"},
    "media": {"spotify", "vlc", "obs64", "obs32", "mpc-hc64", "mpc-hc", "potplayermini64", "potplayer", "wmplayer",
              "musicbee", "foobar2000", "aimp", "itunes", "groove", "music.ui", "video.ui", "netflix", "kodi",
              "premiere", "adobe premiere pro", "afterfx", "davinciresolve", "resolve", "audacity", "photoshop",
              "illustrator", "figma", "blender", "capcut", "clipchamp", "lightroom"},
    "files": {"explorer", "totalcmd", "totalcmd64", "7zfm", "winrar", "everything", "onedrive"},
}
_PROCESS_TO_CATEGORY = {p: c for c, names in _PROCESS_CATEGORIES.items() for p in names}

# pencere başlığında geçen ipuçları (küçük harf) -> (alt ipucu, kategori geçersiz kılma)
_TITLE_HINTS = [
    ("youtube", "YouTube", "browsing"), ("netflix", "Netflix", "media"), ("twitch", "Twitch", "browsing"),
    ("github", "GitHub", "coding"), ("gitlab", "GitLab", "coding"), ("stack overflow", "StackOverflow", "coding"),
    ("stackoverflow", "StackOverflow", "coding"), ("chatgpt", "ChatGPT", "browsing"), ("claude", "Claude", "browsing"),
    ("gemini", "Gemini", "browsing"), ("instagram", "Instagram", "browsing"), ("twitter", "Twitter/X", "browsing"),
    (" / x", "Twitter/X", "browsing"), ("reddit", "Reddit", "browsing"), ("spotify", "Spotify", "media"),
    ("whatsapp", "WhatsApp", "chat"), ("discord", "Discord", "chat"), ("gmail", "Gmail", "browsing"),
    ("outlook", "Outlook", "office"), ("google docs", "Google Docs", "office"), ("google sheets", "Google Sheets", "office"),
    ("docs.google", "Google Docs", "office"), ("wikipedia", "Wikipedia", "browsing"), ("vikipedi", "Vikipedi", "browsing"),
    ("linkedin", "LinkedIn", "browsing"), ("udemy", "Udemy", "browsing"), ("coursera", "Coursera", "browsing"),
    ("leetcode", "LeetCode", "coding"), ("hackerrank", "HackerRank", "coding"), ("codeforces", "Codeforces", "coding"),
    ("kick.com", "Kick", "browsing"), ("steam", "Steam", "gaming"), ("epic games", "Epic Games", "gaming"),
    ("visual studio code", "VS Code", "coding"), ("visual studio", "Visual Studio", "coding"),
    ("pycharm", "PyCharm", "coding"), ("jupyter", "Jupyter", "coding"), ("colab", "Colab", "coding"),
    ("valorant", "VALORANT", "gaming"), ("league of legends", "League of Legends", "gaming"),
    ("minecraft", "Minecraft", "gaming"), ("red dead", "RDR2", "gaming"), ("hogwarts", "Hogwarts Legacy", "gaming"),
    ("20 minutes till dawn", "20 Minutes Till Dawn", "gaming"), ("counter-strike", "CS2", "gaming"),
    ("trendyol", "alışveriş", "browsing"), ("hepsiburada", "alışveriş", "browsing"), ("amazon", "alışveriş", "browsing"),
]

# Oyun pencereleri için başlık ipuçları tarayıcı sekmesinde de olabilir (ör. YouTube'da Valorant videosu);
# tarayıcı işlemi için kategori geçersiz kılmayı yalnızca "coding/office/media/chat" türleri yapsın.
_BROWSER_OVERRIDE_ALLOWED = {"coding", "office", "media", "chat"}


def _basename(process_path: str) -> str:
    name = os.path.basename(process_path or "")
    if name.lower().endswith(".exe"):
        name = name[:-4]
    return name


def categorize(process_name: str, title: str = "") -> tuple[str, str | None]:
    """(kategori, alt ipucu). ``process_name`` 'Code.exe' veya tam yol olabilir."""
    base = _basename(process_name).lower().strip()
    title_l = (title or "").lower()
    category = _PROCESS_TO_CATEGORY.get(base)
    if category is None:
        # kısmi eşleşme (ör. "VALORANT-Win64-Shipping", "steam_app_123")
        for key, cat in _PROCESS_TO_CATEGORY.items():
            if len(key) >= 4 and key in base:
                category = cat
                break
    if category is None and base:
        if any(t in base for t in ("shipping", "game", "launcher", "unrealengine", "ue4", "ue5")):
            category = "gaming"
    hint = None
    for needle, label, cat in _TITLE_HINTS:
        if needle in title_l:
            hint = label
            if category is None:
                category = cat
            elif category == "browsing" and cat in _BROWSER_OVERRIDE_ALLOWED:
                category = cat if cat != "coding" else "browsing"  # GitHub'da gezinmek hâlâ browsing; hint yeter
            break
    if category is None:
        category = "other" if base else "idle"
    return category, hint


def get_foreground_info() -> dict:
    """{'title', 'process_name', 'process_path', 'pid', 'category', 'hint'} — Windows dışında boş."""
    info = {"title": "", "process_name": "", "process_path": "", "pid": 0, "category": "idle", "hint": None}
    if not IS_WINDOWS:
        return info
    try:
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return info
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        info["title"] = buf.value
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        info["pid"] = pid.value
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if handle:
            try:
                size = wintypes.DWORD(1024)
                path_buf = ctypes.create_unicode_buffer(size.value)
                if kernel32.QueryFullProcessImageNameW(handle, 0, path_buf, ctypes.byref(size)):
                    info["process_path"] = path_buf.value
                    info["process_name"] = os.path.basename(path_buf.value)
            finally:
                kernel32.CloseHandle(handle)
    except Exception:
        return info
    info["category"], info["hint"] = categorize(info["process_name"], info["title"])
    return info


def idle_seconds() -> float:
    """Son klavye/fare girdisinden bu yana geçen saniye (GetLastInputInfo)."""
    if not IS_WINDOWS:
        return 0.0
    try:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(lii)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return 0.0
        tick = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
        return max(0.0, ((tick - lii.dwTime) & 0xFFFFFFFF) / 1000.0)
    except Exception:
        return 0.0


def _is_fullscreen(hwnd=None) -> bool:
    """Ön plan penceresi ekranı tamamen kaplıyor mu (oyun tam ekran sezgisi)."""
    if not IS_WINDOWS:
        return False
    try:
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        hwnd = hwnd or user32.GetForegroundWindow()
        if not hwnd:
            return False
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        return rect.left <= 0 and rect.top <= 0 and rect.right >= sw and rect.bottom >= sh
    except Exception:
        return False


def parse_mic_key_name(name: str) -> str:
    """Kayıt defteri alt anahtar adından süreç adı: 'C:#Apps#Zoom.exe' -> 'zoom'."""
    base = (name or "").rsplit("#", 1)[-1].lower()
    return base[:-4] if base.endswith(".exe") else base


def mic_in_use_apps() -> set[str]:
    """Mikrofonu şu an kullanan uygulama adları (Windows gizlilik kayıt defteri; yalnız bellekte)."""
    if not IS_WINDOWS:
        return set()
    apps: set[str] = set()
    try:
        import winreg
        root = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
        for sub in ("", r"\NonPackaged"):
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, root + sub)
            except OSError:
                continue
            with key:
                i = 0
                while True:
                    try:
                        name = winreg.EnumKey(key, i)
                    except OSError:
                        break
                    i += 1
                    if name == "NonPackaged":
                        continue
                    try:
                        with winreg.OpenKey(key, name) as k:
                            start = winreg.QueryValueEx(k, "LastUsedTimeStart")[0]
                            stop = winreg.QueryValueEx(k, "LastUsedTimeStop")[0]
                    except OSError:
                        continue
                    if start and not stop:
                        apps.add(parse_mic_key_name(name))
    except Exception:
        return set()
    if apps:
        # Çöken/zorla kapatılan uygulama kayıtta "kullanıyor" olarak kalabilir: yalnız çalışanları say.
        running = _running_process_names()
        if running is not None:
            apps = {a for a in apps if a in running}
    return apps


def _running_process_names() -> set[str] | None:
    """Çalışan süreç adları (küçük harf, .exe'siz); okunamazsa None."""
    import subprocess
    try:
        out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=5,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    names = {line.split('","')[0].strip('"').lower() for line in out.splitlines() if line.strip()}
    return {n[:-4] if n.endswith(".exe") else n for n in names}


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, m = divmod(seconds // 60, 60)
    if h and m:
        return f"{h} saat {m} dakika"
    if h:
        return f"{h} saat"
    return f"{max(m, 1)} dakika" if seconds >= 30 else "az önce"


@dataclass
class ActivityTracker:
    """Birkaç saniyede bir ``sample(now)`` çağır; süreleri ve oturumları takip eder."""
    sample_interval: float = 5.0
    idle_threshold: float = 300.0        # 5 dk girdisizlik = boşta
    remark_interval: float = 270.0       # en sık ~4.5 dk'da bir konuş
    long_session: float = 2 * 3600       # 2 saat kesintisiz aynı kategori
    long_gaming: float = 90 * 60         # tam ekran oyunda sadece 90 dk üstü
    probe: callable = field(default=get_foreground_info, repr=False)
    idle_probe: callable = field(default=idle_seconds, repr=False)
    fullscreen_probe: callable = field(default=_is_fullscreen, repr=False)
    clock: callable = field(default=_dt.datetime.now, repr=False)

    def __post_init__(self):
        self.totals: dict[str, float] = defaultdict(float)
        self.current: dict = {"category": "idle", "hint": None, "title": "", "process_name": ""}
        self.session_category: str | None = None
        self.session_start: float | None = None
        self.last_sample: float | None = None
        self.last_switch: float | None = None
        self.prev_category: str | None = None
        self.was_idle = False
        self.idle_since: float | None = None
        self.idle_for = 0.0
        self.fullscreen = False
        self.last_remark_time: float = -1e9
        self.remarked_long_session_for: str | None = None
        self.start_time: float | None = None
        self.app_switches = 0
        self._pending_events: list[dict] = []
        self.recent_titles: list[str] = []   # son 5 başlık (bellekte)

    # -- örnekleme -----------------------------------------------------------
    def sample(self, now: float) -> dict | None:
        if self.last_sample is not None and now - self.last_sample < self.sample_interval:
            return None
        dt = 0.0 if self.last_sample is None else min(now - self.last_sample, self.sample_interval * 3)
        self.last_sample = now
        if self.start_time is None:
            self.start_time = now

        info = self.probe() or {}
        self.idle_for = float(self.idle_probe() or 0.0)
        idle = self.idle_for >= self.idle_threshold
        category = "idle" if idle else (info.get("category") or "other")
        self.fullscreen = bool(self.fullscreen_probe()) if category == "gaming" else False

        if idle and not self.was_idle:
            self.idle_since = now - self.idle_for
        if not idle and self.was_idle:
            away = now - (self.idle_since or now)
            self._pending_events.append({"type": "came_back_from_idle", "away_seconds": away,
                                         "category": category})
            self.session_category, self.session_start = category, now
        self.was_idle = idle

        if not idle:
            self.totals[category] += dt
            if category != self.session_category:
                if self.session_category not in (None, "idle") and self.session_start is not None \
                        and now - self.session_start >= 60 and self.last_switch is not None \
                        and now - self.last_switch >= 60:
                    self._pending_events.append({"type": "switched_app", "from": self.session_category,
                                                 "to": category, "hint": info.get("hint")})
                self.prev_category = self.session_category
                self.session_category, self.session_start = category, now
                self.last_switch = now
                self.app_switches += 1
                self.remarked_long_session_for = None
        self.current = {"category": category, "hint": info.get("hint"), "title": info.get("title", ""),
                        "process_name": info.get("process_name", "")}
        title = info.get("title") or ""
        if title and (not self.recent_titles or self.recent_titles[-1] != title):
            self.recent_titles = (self.recent_titles + [title])[-5:]
        return self.current

    # -- sorgular ------------------------------------------------------------
    def session_seconds(self, now: float) -> float:
        if self.session_start is None or self.was_idle:
            return 0.0
        return max(0.0, now - self.session_start)

    def summary(self, now: float | None = None) -> str:
        """AI istemine eklenecek kısa Türkçe özet."""
        now = time.monotonic() if now is None else now
        cat = self.current.get("category", "idle")
        parts = []
        if cat == "idle":
            parts.append(f"Kullanıcı {format_duration(self.idle_for)} süredir bilgisayarın başında değil gibi.")
        else:
            desc = CATEGORY_LABELS.get(cat, cat)
            hint = self.current.get("hint")
            app = self.current.get("process_name") or ""
            where = f" ({hint})" if hint else (f" ({app})" if app else "")
            parts.append(f"Kullanıcı şu an {desc}{where}; aktif pencere: \"{(self.current.get('title') or '')[:80]}\".")
            sess = self.session_seconds(now)
            if sess >= 120:
                parts.append(f"Bu etkinlik {format_duration(sess)} süredir kesintisiz sürüyor.")
        top = sorted(((v, k) for k, v in self.totals.items() if v >= 60), reverse=True)[:3]
        if top:
            parts.append("Bugün: " + ", ".join(f"{CATEGORY_LABELS.get(k, k)} {format_duration(v)}" for v, k in top) + ".")
        hour = self.clock().hour
        if hour >= 23 or hour < 5:
            parts.append("Saat geç (gece).")
        return " ".join(parts)

    def suggest_remark(self, now: float) -> dict | None:
        """Kedinin kendiliğinden konuşması için olay; sık değil, oyunda tam ekranken neredeyse hiç."""
        if now - self.last_remark_time < self.remark_interval:
            return None
        cat = self.current.get("category", "idle")
        sess = self.session_seconds(now)
        gaming_fullscreen = cat == "gaming" and self.fullscreen
        event = None

        if gaming_fullscreen:
            if sess >= self.long_gaming and self.remarked_long_session_for != "gaming":
                event = {"type": "long_session", "category": "gaming", "seconds": sess}
                self.remarked_long_session_for = "gaming"
        else:
            while self._pending_events and event is None:
                candidate = self._pending_events.pop(0)
                if candidate["type"] == "came_back_from_idle" and candidate.get("away_seconds", 0) >= self.idle_threshold:
                    event = candidate
                elif candidate["type"] == "switched_app" and candidate["to"] != "idle":
                    event = candidate
            if event is None and cat not in ("idle",) and sess >= self.long_session \
                    and self.remarked_long_session_for != cat:
                event = {"type": "long_session", "category": cat, "seconds": sess}
                self.remarked_long_session_for = cat
            if event is None and cat != "idle":
                hour = self.clock().hour
                if (hour >= 1 and hour < 5) and getattr(self, "_late_night_said", None) != self.clock().date():
                    event = {"type": "late_night", "category": cat, "hour": hour}
                    self._late_night_said = self.clock().date()
        if event is None:
            self._pending_events.clear()
            return None
        event.setdefault("category", cat)
        event["hint"] = self.current.get("hint")
        event["title"] = self.current.get("title", "")
        self.last_remark_time = now
        return event

    def mark_remarked(self, now: float):
        """Dışarıdan (ör. AI yorumu) konuşulduğunda aralığı sıfırla."""
        self.last_remark_time = now

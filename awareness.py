"""Kömür farkındalığı: saf (Windows'a bağlı olmayan) sınıflandırma + tepki tablosu.

Gizlilik: pencere/medya başlıkları yalnızca bu fonksiyonların argümanı olarak bellekte
geçer; hiçbir yere yazılmaz, loglanmaz, ağa gönderilmez. Dönen değerler sabit etiketlerdir.
"""
from __future__ import annotations

import random

CLASSES = ("video", "music", "gaming", "coding", "writing", "reading", "meeting", "idle", "away", "none")

IDLE_SECONDS = 60.0
AWAY_SECONDS = 300.0
TYPING_SECONDS = 30.0   # bu kadar süredir girdi yoksa "klavye aktif" sayılmaz

_LAUNCHERS = ('steam', 'epicgameslauncher', 'riotclient', 'leagueclient', 'battle.net', 'gamingservices',
              'goggalaxy', 'eaapp', 'eadesktop', 'ubisoftconnect')
_BROWSERS = ('chrome', 'google chrome', 'safari', 'msedge', 'edge', 'microsoft edge', 'firefox', 'opera', 'brave',
              'brave browser', 'vivaldi', 'yandex', 'arc', 'zen',
              '308046b0af4a39cb')  # son: Firefox AUMID
_MUSIC_APPS = ('spotify', 'musicbee', 'foobar2000', 'aimp', 'itunes', 'music', 'apple music', 'applemusic', 'music.ui', 'zunemusic',
               'deezer', 'tidal', 'amazonmusic', 'youtubemusic')
_VIDEO_APPS = ('netflix', 'vlc', 'iina', 'tv', 'apple tv', 'quicktime player', 'quicktime', 'video.ui', 'zunevideo', 'kodi', 'disneyplus', 'primevideo', 'mpc-hc',
               'potplayer', 'mpv', 'hbo', 'twitch')
_PLAYERS = ('vlc', 'iina', 'tv', 'apple tv', 'quicktime player', 'quicktime', 'mpc-hc', 'potplayer', 'mpv', 'kodi', 'netflix', 'wmplayer', 'video.ui', 'disneyplus')
_VIDEO_TITLE = ('youtube', 'netflix', 'twitch', 'disney', 'prime video', 'hbo', 'apple tv', ' izle')
_MUSIC_TITLE = ('youtube music', 'spotify')
_CALL_APPS = ('zoom', 'zoom.us', 'teams', 'msteams', 'discord', 'skype', 'webex', 'slack', 'whatsapp', 'telegram', 'signal', 'facetime')
_MEET_TITLE = ('meet -', 'meet.google', 'zoom meeting', 'microsoft teams', '| teams')
_WRITING_APPS = ('winword', 'microsoft word', 'wordpad', 'notepad', 'notes', 'pages', 'textedit', 'onenote', 'obsidian', 'notion', 'soffice', 'libreoffice', 'wps')
_WRITING_HINTS = ('google docs',)
_READING_APPS = ('acrord32', 'acrobat', 'sumatrapdf', 'foxitreader', 'kindle', 'preview', 'books')


def _proc(info) -> str:
    name = ((info or {}).get('process_name') or '').lower().strip()
    name = name.replace('\\', '/').rsplit('/', 1)[-1]
    return name[:-4] if name.endswith('.exe') else name


def _has(text: str, needles) -> bool:
    return any(n in text for n in needles)


def is_browser(name: str) -> bool:
    # Kısa adlar (arc, zen, edge) yalnız tam eşleşir: "archicad"/"arcgis" tarayıcı değildir.
    name = (name or '').lower()
    return name in _BROWSERS or any(b in name for b in _BROWSERS if len(b) >= 5)


def active_game(info) -> bool:
    name = _proc(info)
    return bool(name and (info or {}).get('category') == 'gaming' and not _has(name, _LAUNCHERS))


def browser_hint(info) -> str | None:
    """Ön plandaki tarayıcı sekmesi bilinen bir video/müzik sitesi mi? 'video' | 'music' | None."""
    info = info or {}
    if not is_browser(_proc(info)):
        return None
    title = (info.get('title') or '').lower()
    hint = (info.get('hint') or '').lower()
    text = title + ' ' + hint
    if _has(text, _MUSIC_TITLE):
        return 'music'
    if _has(text, _VIDEO_TITLE):
        return 'video'
    return None


def media_kind(sessions, info=None, fullscreen=False, browser_memory=None) -> str | None:
    """Çalan GSMTC oturumlarından 'video' | 'music' | None.

    sessions: [{'app', 'type', 'title', 'artist'}] (yalnız Playing olanlar). Başlıklar
    yalnızca burada okunur, saklanmaz. browser_memory: tarayıcı oturumu için son bilinen tür.
    """
    video = music = False
    for s in sessions or []:
        app = (s.get('app') or '').lower()
        ptype = (s.get('type') or '').lower()
        title = ((s.get('title') or '') + ' ' + (s.get('artist') or '')).lower()
        if is_browser(app) and ptype == 'music':
            # Chrome, YouTube videolarını bile "Music" bildirir: tarayıcıda bu türe değil sekmeye bak.
            kind = (browser_hint(info) if is_browser(_proc(info)) else None) or browser_memory
            if kind is None and _has(title, _VIDEO_TITLE) and not _has(title, _MUSIC_TITLE):
                kind = 'video'
            video, music = video or kind == 'video', music or kind != 'video'
        elif ptype == 'video':
            video = True
        elif ptype == 'music':
            music = True
        elif _has(app, _MUSIC_APPS):
            music = True
        elif _has(app, _VIDEO_APPS):
            video = True
        elif _has(title, _MUSIC_TITLE):
            music = True
        elif _has(title, _VIDEO_TITLE):
            video = True
        elif browser_memory in ('video', 'music') and (is_browser(app) or not app):
            video, music = video or browser_memory == 'video', music or browser_memory == 'music'
        elif is_browser(app) and fullscreen and is_browser(_proc(info)):
            video = True   # tam ekran tarayıcıda oynayan şey büyük ihtimalle video
    if video:
        return 'video'
    return 'music' if music else None


def classify_activity(info, media=None, idle=0.0, fullscreen=False, mic_apps=(), playing=False) -> str:
    """Tek örnekten ham sınıf. Öncelik: oyun > video > toplantı > away/idle > müzik > çalışma türleri.

    info: get_foreground_info(); media: media_kind() sonucu; idle: girdisiz saniye;
    mic_apps: mikrofonu şu an kullanan süreç adları; playing: herhangi bir medya oturumu çalıyor mu.
    """
    info = info or {}
    proc = _proc(info)
    cat = info.get('category') or 'other'
    title = (info.get('title') or '').lower()
    if active_game(info):
        return 'gaming'

    working = cat in ('coding', 'office') and idle < TYPING_SECONDS
    video = media == 'video'
    if not video and fullscreen and not active_game(info):
        if _has(proc, _PLAYERS) or (is_browser(proc) and (playing or browser_hint(info) == 'video')):
            video = True
    # Oynayan video, açık duran bir sesli kanaldan (ör. Discord) önce gelir: birlikte izleme yaygın.
    if video and not (working and idle < 15):
        return 'video'

    # Mikrofonu tutan arama uygulaması, kullanıcı uzaktaysa toplantı sayılmaz.
    mics = {str(m).lower().replace('.exe', '') for m in (mic_apps or ())}
    if idle < AWAY_SECONDS and (any(_has(m, _CALL_APPS) for m in mics) or (
            mics and is_browser(proc) and _has(title, _MEET_TITLE))):
        return 'meeting'

    if idle >= AWAY_SECONDS:
        return 'away'
    if idle >= IDLE_SECONDS:
        return 'idle'
    if media == 'music':
        return 'music'

    hint = (info.get('hint') or '').lower()
    if cat == 'coding':
        return 'coding' if idle < TYPING_SECONDS else 'none'
    if _has(proc, _WRITING_APPS) or _has(hint, _WRITING_HINTS):
        return 'writing'
    if _has(proc, _READING_APPS):
        return 'reading'
    if cat == 'office' and not _has(proc, ('excel', 'powerpnt', 'outlook', 'teams')):
        return 'writing'
    if cat == 'browsing' or is_browser(proc):
        return 'reading'
    return 'none'


class Stabilizer:
    """Histerezis: yeni sınıf ardışık ``need`` örnekte görülmeden geçerli olmaz."""

    def __init__(self, need: int = 2):
        self.need = need
        self.value = 'none'
        self._cand = None
        self._count = 0
        self._first = True

    def feed(self, raw: str) -> str:
        if self._first:           # açılışta ilk örneği hemen benimse
            self._first = False
            self.value = raw
            return raw
        if raw == self.value:
            self._cand, self._count = None, 0
            return self.value
        if raw == self._cand:
            self._count += 1
        else:
            self._cand, self._count = raw, 1
        if self._count >= self.need:
            self.value, self._cand, self._count = raw, None, 0
        return self.value


# --- Tepki tablosu (yalnız veri) -------------------------------------------------
# state: kedi durumu adı; messages: seyrek, sakin Türkçe cümleler (boş = sessiz);
# cooldown: aynı sınıf için iki mesaj arası en az saniye; still: kedi hareketsiz/sakin kalsın.
REACTIONS = {
    "video":   {"state": "watch",  "messages": ["Köşeye çekildim, sessizce izliyorum.", "Kenarda kıvrıldım, rahat et."],
                "cooldown": 600, "still": True, "corner": True},
    "music":   {"state": "dance",  "messages": ["Güzel şarkı...", "Bu parça hoşuma gitti."],
                "cooldown": 600, "still": False, "dance_seconds": 20},   # kısa dans, sonra mırlama
    "gaming":  {"state": "focus",  "messages": [], "cooldown": 600, "still": True},
    "coding":  {"state": "sit",    "messages": ["Ben köşede uyuklayayım, sen devam et."],
                "cooldown": 900, "still": True, "edge": True},
    "writing": {"state": "loaf",   "messages": ["Yazmana engel olmam."], "cooldown": 900, "still": True},
    "reading": {"state": "look",   "messages": ["Ne okuyorsun öyle?"], "cooldown": 900, "still": True},
    "meeting": {"state": "sit",    "messages": [], "cooldown": 600, "still": True},
    "idle":    {"state": "groom",  "messages": [], "cooldown": 600, "still": False},
    "away":    {"state": "sleep",  "messages": [], "cooldown": 600, "still": True},
    "none":    {"state": None,     "messages": [], "cooldown": 600, "still": False},
}
WELCOME_BACK = "Hoş geldin!"
MIN_MESSAGE_GAP = 600        # aynı sınıf için kesin alt sınır (sn)
WELCOME_COOLDOWN = 300
_ACTIVE_CLASSES = frozenset({"coding", "writing", "reading", "music", "gaming", "meeting"})


class ReactionPlanner:
    """Sınıf değişimini kedi tepkisine çevirir: {'class','state','message'|None}."""

    def __init__(self, table=None, rng=None):
        self.table = table or REACTIONS
        self.rng = rng or random.Random()
        self._last_msg: dict[str, float] = {}

    def _may_speak(self, key, cooldown, now):
        last = self._last_msg.get(key)
        return last is None or now - last >= max(cooldown, MIN_MESSAGE_GAP if key != 'welcome' else cooldown)

    def plan(self, old: str, new: str, now: float):
        if old == new:
            return None
        entry = self.table.get(new) or self.table["none"]
        message = None
        welcome_back = (old == 'away' and new != 'away') or (old == 'idle' and new in _ACTIVE_CLASSES)
        if old == 'away' and new != 'away' and self._may_speak('welcome', WELCOME_COOLDOWN, now):
            message = WELCOME_BACK
            self._last_msg['welcome'] = now
        elif entry["messages"] and self._may_speak(new, entry["cooldown"], now):
            message = self.rng.choice(entry["messages"])
            self._last_msg[new] = now
        return {
            "class": new,
            "from_class": old,
            "state": entry["state"],
            "message": message,
            "still": entry.get("still", False),
            "welcome_back": welcome_back,
        }

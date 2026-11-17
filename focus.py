"""Pomodoro / odak oturumu mantigi (GUI'den bagimsiz, saf Python).

Zaman disaridan verilir (`now` parametresi; verilmezse time.monotonic).
Kural: her calisma (work) fazindan sonra bir mola gelir; mola suresi,
tamamlanan ddongu sayisi 4'un kati ise 15 dakika (uzun mola), degilse
`break_min`. Son calisma fazindan sonra da mola gelir ve bu molanin bitisinde
`session_finished` olayi uretilir.
"""
import re
import time

LONG_BREAK_MIN = 15
LONG_BREAK_EVERY = 4

MESSAGES = {
    "work_started": "Odak zamani! Ben kosede uyuyorum, sen calis.",
    "break_started": "Mola zamani! Biraz gerin.",
    "long_break_started": "Uzun mola zamani! Biraz yuru, su ic.",
    "session_finished": "Pomodoro bitti, harikasin!",
}

_WORK = "work"
_BREAK = "break"


def _now(now):
    return time.monotonic() if now is None else now


class FocusSession:
    """Calisma/mola dongusu. Fazlar: idle, work, break, paused."""

    def __init__(self):
        self.phase = "idle"
        self.completed_cycles = 0
        self.is_long_break = False
        self._work_s = 25 * 60
        self._break_s = 5 * 60
        self._cycles = 4
        self._phase_end = None
        self._paused_remaining = None
        self._resume_phase = None
        self._pending_work_started = False

    # ----- kontrol -------------------------------------------------------
    def start(self, work_min=25, break_min=5, cycles=4, now=None):
        """Yeni oturum baslatir. 'work_started' bir sonraki tick() ile doner."""
        now = _now(now)
        self._work_s = int(work_min * 60)
        self._break_s = int(break_min * 60)
        self._cycles = int(cycles)
        self.completed_cycles = 0
        self.is_long_break = False
        self._paused_remaining = None
        self._resume_phase = None
        self._enter(_WORK, now, self._work_s)
        self._pending_work_started = True

    def stop(self):
        self.phase = "idle"
        self._phase_end = None
        self._paused_remaining = None
        self._resume_phase = None
        self._pending_work_started = False
        self.is_long_break = False

    def pause(self, now=None):
        if self.phase not in (_WORK, _BREAK):
            return
        now = _now(now)
        self._paused_remaining = self.remaining(now)
        self._resume_phase = self.phase
        self.phase = "paused"
        self._phase_end = None

    def resume(self, now=None):
        if self.phase != "paused":
            return
        now = _now(now)
        self.phase = self._resume_phase
        self._phase_end = now + self._paused_remaining
        self._paused_remaining = None
        self._resume_phase = None

    # ----- zaman ----------------------------------------------------------
    def remaining(self, now=None):
        """Mevcut fazin kalan saniyesi (duraklatilmissa dondurulmus deger)."""
        if self.phase == "paused":
            return float(self._paused_remaining)
        if self.phase in (_WORK, _BREAK) and self._phase_end is not None:
            return max(0.0, self._phase_end - _now(now))
        return 0.0

    def tick(self, now=None):
        """Gecen zamana gore fazlari ilerletir; olay adlarini sirayla doner."""
        now = _now(now)
        events = []
        if self._pending_work_started:
            self._pending_work_started = False
            events.append("work_started")
        while self.phase in (_WORK, _BREAK) and now >= self._phase_end:
            end = self._phase_end
            if self.phase == _WORK:
                self.completed_cycles += 1
                self.is_long_break = self.completed_cycles % LONG_BREAK_EVERY == 0
                if self.is_long_break:
                    events.append("long_break_started")
                    self._enter(_BREAK, end, LONG_BREAK_MIN * 60)
                else:
                    events.append("break_started")
                    self._enter(_BREAK, end, self._break_s)
            else:
                if self.completed_cycles >= self._cycles:
                    events.append("session_finished")
                    self.phase = "idle"
                    self._phase_end = None
                    self.is_long_break = False
                else:
                    events.append("work_started")
                    self._enter(_WORK, end, self._work_s)
        return events

    def _enter(self, phase, start, duration_s):
        self.phase = phase
        self._phase_end = start + duration_s
        if phase == _WORK:
            self.is_long_break = False


# ----- Turkce komut ayristirma -----------------------------------------------
_ASCII_MAP = str.maketrans("ışğüöç", "isguoc")
_FOCUS_RE = re.compile(r"\b(pomodoro\w*|odak\w*)")
_STOP_RE = re.compile(r"\b(bitir\w*|durdur\w*|iptal\w*|kapat\w*|sonlandir\w*|bitsin)\b")
_RATIO_RE = re.compile(r"(\d+)\s*/\s*(\d+)")
_MINUTES_RE = re.compile(r"(\d+)\s*(?:dk|dakika)")


def _fold(text):
    """Kucuk harf + Turkce karakterleri ASCII'ye indirger (I/İ/ı dahil)."""
    t = text.replace("İ", "i").replace("I", "i").lower()
    t = t.replace("̇", "")
    return t.translate(_ASCII_MAP)


def _clamp(value, low, high):
    return max(low, min(high, value))


def parse_focus_command(text):
    """'pomodoro baslat', '25 dakika odaklan', 'odak modu 50/10', 'pomodoro bitir'.

    Dondurur: {"action": "start", "work_min": int, "break_min": int},
    {"action": "stop"} veya None (odak ile ilgisi olmayan metin).
    Odak anahtar kelimesi (pomodoro / odak*) yoksa her zaman None doner.
    Durdurma niyeti baslatmadan once kontrol edilir.
    """
    t = _fold(text or "")
    if not _FOCUS_RE.search(t):
        return None
    if _STOP_RE.search(t):
        return {"action": "stop"}

    work_min, break_min = 25, 5
    ratio = _RATIO_RE.search(t)
    if ratio:
        work_min, break_min = int(ratio.group(1)), int(ratio.group(2))
    else:
        minutes = _MINUTES_RE.search(t)
        if minutes:
            work_min = int(minutes.group(1))
    return {
        "action": "start",
        "work_min": _clamp(work_min, 1, 180),
        "break_min": _clamp(break_min, 1, 60),
    }


def phase_to_cat_state(phase):
    """Kedi durumu: calisirken uyur (dikkat dagitmaz), molada gerinir."""
    if phase == _WORK:
        return "sleep"
    if phase == _BREAK:
        return "stretch"
    return None

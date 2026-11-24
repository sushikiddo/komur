"""Kömür — yazılı komut motoru (yapay zekâ yok).

Yazılan metin ``intents`` ile komuta çevrilir ve ``PCActions`` ile yürütülür; komut
değilse kısa bir yardım cevabı döner. Ağ, model veya API anahtarı kullanılmaz.

Kullanım::

    engine = CommandEngine(settings.get, PCActions(), tracker.summary)
    result = engine.respond("not defterini aç")   # eşzamanlı; iş parçacığında çağır
    result.reply, result.actions_done, result.needs_confirmation
    engine.confirm(pending)                        # kullanıcı "Evet" dediyse
"""
from __future__ import annotations

import datetime as _dt
import logging
import random
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from intents import MAX_TOOL_ITERATIONS, WEATHER_UNKNOWN, parse_action_plan, parse_intent
from pc_actions import APP_LABELS, PCActions, PendingAction, is_failure, is_pending, resolve_app_key

log = logging.getLogger(__name__)

HABIT_MIN_DAYS = 3                 # alışkanlık sayılması için aynı saatte farklı gün sayısı
MAX_TRANSCRIPT = 20


@dataclass
class CommandResult:
    reply: str
    actions_done: list[str] = field(default_factory=list)
    needs_confirmation: list[PendingAction] = field(default_factory=list)
    error: str | None = None
    remaining_actions: list[dict] = field(default_factory=list)


class CommandEngine:
    min_interval = 270.0   # comment_on_context için önerilen en kısa aralık (sn)

    def __init__(self, settings_get: Callable[..., Any], actions: PCActions,
                 context_provider: Callable[[], Any] | None = None, *,
                 clock: Callable[[], _dt.datetime] = _dt.datetime.now,
                 rng: random.Random | None = None,
                 habits: Any = None):
        self.settings_get = settings_get
        self.actions = actions
        self.context_provider = context_provider
        self.clock = clock
        self.rng = rng or random.Random()
        self.transcript: list[tuple[str, str]] = []   # ("user"|"assistant", metin)
        self._recent_comments: list[str] = []
        self.cancelled = threading.Event()
        self.habits = habits                       # MemoryStore benzeri: record_habit / top_habit (isteğe bağlı)
        self._habit_suggested: set[tuple[int, str]] = set()

    def _get(self, key, default=None):
        try:
            value = self.settings_get(key, default)
        except TypeError:
            value = self.settings_get(key)
        return default if value is None else value

    def reset(self):
        self.transcript.clear()

    def respond(self, user_text: str) -> CommandResult:
        self.cancelled.clear()
        text = (user_text or "").strip()
        if not text:
            return CommandResult("Bir şey yazmadın ki. Mrr?")
        plan = parse_action_plan(text)
        if plan:
            result = self.execute_plan(plan)
            self._remember("user", text)
            self._remember("assistant", result.reply)
            return result
        return self._respond_offline(text)

    def confirm(self, pending: PendingAction) -> str:
        """Kullanıcı onayladı: eylemi çalıştır ve sohbete not düş."""
        if self.cancelled.is_set():
            return "Olmadı: işlem durduruldu; onaylanan yeni adım başlatılmadı."
        result = self.actions.execute(pending.name, pending.args, confirmed=True)
        text = result if isinstance(result, str) else "Onay sonrası bir şey ters gitti."
        self._remember("user", f"[Kullanıcı '{pending.name}' eylemini onayladı. Sonuç: {text}]")
        self._remember("assistant", text)
        return text

    def execute_plan(self, actions: list[dict]) -> CommandResult:
        """Execute bounded steps once, suspending the rest at every approval boundary."""
        result = CommandResult("")
        outcomes = []
        if len(actions) > MAX_TOOL_ITERATIONS:
            result.reply = "Bu isteği altıdan az adıma bölelim."
            return result
        for index, action in enumerate(actions):
            outcome, failed = self._run_action(action["name"], action.get("args", {}), result)
            if result.needs_confirmation:
                result.remaining_actions = actions[index + 1:]
                outcomes.append(result.needs_confirmation[-1].description)
                break
            outcomes.append(outcome)
            if failed or is_pending(outcome):
                if index + 1 < len(actions):
                    outcomes.append("Sonuç kesinleşmediği için kalan adımları çalıştırmadım.")
                break
        result.reply = "\n".join(outcomes)
        return result

    def confirm_and_continue(self, pending, remaining) -> CommandResult:
        outcome = self.confirm(pending)
        if is_failure(outcome) or is_pending(outcome) or not remaining:
            return CommandResult(outcome)
        result = self.execute_plan(remaining)
        result.reply = outcome + "\n" + result.reply
        return result

    def _remember(self, role: str, text: str):
        self.transcript.append((role, text))
        del self.transcript[:-MAX_TRANSCRIPT]

    def _weather_now(self) -> str:
        try:
            ctx = self.context_provider() if self.context_provider else None
        except Exception:
            return ""
        weather = ctx.get("weather") if isinstance(ctx, dict) else None
        return weather.strip()[:80] if isinstance(weather, str) else ""


    # -- eylem yürütme (ortak) ----------------------------------------------
    def _run_action(self, name: str, args: dict, result: CommandResult) -> tuple[str, bool]:
        """(araç sonucu metni, hata mı). Tehlikeli eylemler PendingAction olarak biriktirilir."""
        if self.cancelled.is_set():
            return "İşlem durduruldu; yeni adım başlatılmadı.", True
        try:
            outcome = self.actions.execute(name, args or {}, confirmed=False)
        except Exception:
            # Execution may already have occurred; do not fall through and repeat it.
            result.error = "Eylem sonucu doğrulanamadı."
            return "Eylem sonucu doğrulanamadı; tekrar denemeden önce kontrol et.", True
        if isinstance(outcome, PendingAction):
            result.needs_confirmation.append(outcome)
            return f"Onayın gerekiyor: {outcome.description}", False
        failed = is_failure(outcome)
        if not failed and not is_pending(outcome):
            result.actions_done.append(outcome)
            self._record_habit(name, args or {})
        return outcome, failed


    # -- alışkanlık hafızası -------------------------------------------------
    def _habits_enabled(self) -> bool:
        return self.habits is not None and bool(self._get("habit_memory", True))

    def _record_habit(self, name: str, args: dict):
        """Yalnız katalogdaki uygulama/oyun anahtarı + saat kaydedilir; kullanıcı/model metni asla."""
        if not self._habits_enabled():
            return
        raw = args.get("name") if name == "open_app" else args.get("game") if name == "launch_game" else None
        key = resolve_app_key(str(raw)) if raw else None
        if not key:
            return
        now = self.clock()
        try:
            self.habits.record_habit(key, now.hour, now.date().toordinal())
        except Exception:  # noqa: BLE001
            log.debug("habit record failed", exc_info=True)

    def habit_suggestion(self) -> str | None:
        """Şu saatte alışkanlık varsa (en az HABIT_MIN_DAYS farklı gün) kısa, tek seferlik öneri METNİ döner.
        Ne zaman gösterileceğine çağıran karar verir; model çağrısı yok, eylem çalıştırmaz.
        Bugün aynı eylem zaten yapıldıysa ya da bu gün için öneri verildiyse None."""
        if not self._habits_enabled():
            return None
        now = self.clock()
        day = now.date().toordinal()
        try:
            top = self.habits.top_habit(now.hour, HABIT_MIN_DAYS)
        except Exception:  # noqa: BLE001
            log.debug("habit lookup failed", exc_info=True)
            return None
        if not top:
            return None
        action, _count, last_day = top
        self._habit_suggested = {item for item in self._habit_suggested if item[0] == day}
        if last_day == day or (day, action) in self._habit_suggested:
            return None
        self._habit_suggested.add((day, action))
        label = APP_LABELS.get(action, action)
        part = ("sabah" if 5 <= now.hour < 12 else "öğleden sonra" if now.hour < 18
                else "akşam" if now.hour < 23 else "gece")
        return self.rng.choice([
            f"Her {part} bu saatlerde {label} açıyorsun. Şimdi açayım mı?",
            f"{part.capitalize()} {label} vaktin gelmiş gibi. İstersen açarım.",
        ])

    def _respond_offline(self, text: str) -> CommandResult:
        result = CommandResult("")
        intent = parse_intent(text)
        if intent is not None:
            name, args, lead = intent
            if name == "_chat":
                result.reply = lead
                if lead == WEATHER_UNKNOWN:
                    weather = self._weather_now()
                    if weather:
                        result.reply = f"Şu an {weather}."
            else:
                outcome, failed = self._run_action(name, args, result)
                if result.needs_confirmation:
                    pending = result.needs_confirmation[-1]
                    result.reply = f"{pending.description} Onaylarsan yapıyorum."
                else:
                    result.reply = (lead + " " if lead else "") + outcome
        else:
            result.reply = self.rng.choice(FALLBACK_REPLIES)
        self._remember("user", text)
        self._remember("assistant", result.reply)
        return result

    # -- bağlam yorumu -------------------------------------------------------

    def comment_on_context(self, ctx: dict | str | None) -> str | None:
        """Kullanıcının o an yaptığı şeye dair hazır, kısa bir laf (model yok)."""
        if isinstance(ctx, str):
            ctx = {"summary": ctx}
        ctx = dict(ctx or {})
        return self._comment_offline(ctx) if ctx else None

    def _comment_offline(self, ctx: dict) -> str | None:
        from context import format_duration
        cat = ctx.get("category", "other")
        hint = ctx.get("hint") or ""
        event = ctx.get("type")
        pool: list[str] = []
        if event == "long_session":
            pool = [line.format(d=format_duration(ctx.get("seconds", 0)))
                    for line in LONG_SESSION_LINES.get(cat, LONG_SESSION_LINES["other"])]
        elif event == "came_back_from_idle":
            pool = [line.format(d=format_duration(ctx.get("away_seconds", 0))) for line in BACK_FROM_IDLE_LINES]
        elif event == "late_night":
            pool = LATE_NIGHT_LINES
        elif event == "switched_app":
            pool = SWITCH_LINES.get(ctx.get("to", cat), []) or CATEGORY_LINES.get(cat, [])
        if not pool:
            pool = list(HINT_LINES.get(hint, [])) or list(CATEGORY_LINES.get(cat, []))
            if hint in HINT_LINES and cat in CATEGORY_LINES:
                pool = list(HINT_LINES[hint]) + list(CATEGORY_LINES[cat])[:2]
        if not pool:
            return None
        fresh = [p for p in pool if p not in self._recent_comments] or pool
        choice = self.rng.choice(fresh)
        self._recent_comments = (self._recent_comments + [choice])[-12:]
        return choice



FALLBACK_REPLIES = [
    "Bunu komut olarak anlayamadım. 'Yardım' yazarsan neler yapabildiğimi gösteririm.",
    "Mrr, bu bir komut değil galiba. 'Not defterini aç', 'sesi %30 yap', 'uyu' gibi yazabilirsin.",
]

# ---------------------------------------------------------------------------
# Çevrimdışı bağlam yorumları (kategori / ipucu / olay)
# ---------------------------------------------------------------------------
CATEGORY_LINES = {
    "coding": [
        "Kod yazıyorsun, ben de klavyenin kenarına kıvrıldım. Kolay gelsin.",
        "O hata mesajı korkutmasın; çoğu zaman tek satırlık bir şeydir.",
        "Arada kaydetmeyi unutma, Ctrl+S'in dostu olmayan kedi yoktur.",
        "Değişken isimleri anlamlıysa gelecekteki sen sana teşekkür eder.",
        "Bir fonksiyon ekrana sığmıyorsa belki ikiye bölmenin vakti gelmiştir.",
        "Çalışıyorsa önce commit at, sonra güzelleştirirsin.",
        "Takıldığın yeri bana anlatır gibi yüksek sesle anlat; lastik ördek yerine kedi de olur.",
        "Testler yeşil olunca mırlayacağım, haberin olsun.",
    ],
    "browsing": [
        "İnternette dolaşıyorsun; dikkat, sekmeler çoğalınca ben de sayamıyorum.",
        "Aradığını bulursan bana da anlat, meraklıyım.",
        "Gözlerini arada ekrandan uzağa çevir, 20 saniye yeter.",
        "Okuduğun şey ilginçse not almamı isteyebilirsin.",
    ],
    "gaming": [
        "Oyun zamanı! Ben seyirciyim, bol şans.",
        "Kazanırsan ben de mırlayacağım, kaybedersen sorun değil, sonraki maç bizim.",
        "Su içmeyi unutma, oyuncu da kedi gibi susar.",
        "Maç arasında bir gerin, boynun teşekkür eder.",
    ],
    "office": [
        "Belgeyle uğraşıyorsun; arada Ctrl+S'e basmak hiç fena olmaz.",
        "Uzun bir yazıysa kısa paragraflar hem sana hem okuyana iyi gelir.",
        "Tablolar karışırsa başlık satırını dondurmayı dene.",
        "Sunumda az yazı, çok görsel; kediler de öyle sever.",
    ],
    "chat": [
        "Sohbet koyulaşmış, ben kulak misafiriyim sadece.",
        "Arkadaşlarına selam söyle, mrr.",
        "Mesajlaşırken gülüyorsan günün iyi geçiyor demektir.",
    ],
    "media": [
        "Müzik mi açtın? Kuyruğumla tempo tutuyorum.",
        "Bu parça güzelmiş, sesi biraz açayım mı dersen söyle.",
        "Film izlerken ışığı biraz kıs, gözlerin rahat eder.",
        "Hangi sanatçıyı dinliyorsun, merak ettim.",
    ],
    "files": [
        "Dosya düzenliyorsun; masaüstü temizlenince kafa da hafifler.",
        "İndirilenler klasörü bazen kara delik gibidir, bakmakta fayda var.",
        "Önemli dosyaların yedeğini almak hiç fena fikir değil.",
    ],
    "other": [
        "Buradayım, bir şey lazımsa seslen.",
        "Sakin bir gün gibi görünüyor, sevdim.",
        "Ne yapıyorsan iyi gidiyor gibi, devam.",
    ],
}

HINT_LINES = {
    "YouTube": [
        "YouTube'da ne izliyorsun? Kedi videosuysa ben de bakayım.",
        "Bir video daha deyip saatler geçer, biliyorum, ben de öyle yapıyorum.",
        "Reklam gelirse benimle konuş, zaman geçer.",
    ],
    "GitHub": [
        "GitHub'dasın; bir PR açıyorsan açıklamayı kısa ve net tut.",
        "Yıldız vermeyi unutma, geliştiricileri mutlu eder.",
    ],
    "StackOverflow": [
        "StackOverflow, demek takıldın. Kabul edilen cevaba değil, en yeni cevaba da bak.",
        "Oradaki kodu yapıştırmadan önce bir okumakta fayda var, mrr.",
    ],
    "ChatGPT": ["Bir yapay zekâyla daha konuşuyorsun; kıskanmadım, hiç kıskanmadım."],
    "Claude": ["Claude ile konuşuyorsun; o akıllı, ben tatlıyım, iş bölümü yaptık."],
    "Netflix": ["Netflix açık; patlamış mısır varsa bana da bir tane."],
    "Instagram": ["Instagram'da kaydırmak kolay, durmak zor. Beş dakika sonra hatırlatayım mı?"],
    "Twitter/X": ["Zaman tüneli bitmez, biliyorsun değil mi?"],
    "Reddit": ["Reddit'te bir konu daha, bir konu daha… Tanıdık geliyor."],
    "VALORANT": ["Valorant'ta kafa vuruşları senin olsun. Sakin ol, nefes al, nişan al."],
    "League of Legends": ["LoL'de takım arkadaşlarına kızma, kediler bile birbirine katlanıyor."],
    "Minecraft": ["Minecraft'ta ne inşa ediyorsun? Bir kedi evi fena olmaz."],
    "Spotify": ["Spotify'da ne çalıyor? Mırıltıma eşlik etsin."],
    "alışveriş": ["Alışveriş sepetine bakmadan önce iki kere düşün, kedim diyor."],
}

LONG_SESSION_LINES = {
    "coding": [
        "{d} süredir kod yazıyorsun; kısa bir mola, hatta bir bardak su iyi gelir.",
        "{d} oldu, gözlerini dinlendir; kod kaçmıyor, ben de buradayım.",
        "Uzun süredir odaklısın ({d}). Beş dakika gerinmek verimi düşürmez, artırır.",
    ],
    "gaming": [
        "{d} süredir oynuyorsun; bir mola verip su içsen mi? Sonra devam.",
        "{d} geçti. Maç biter bitmez kısa bir ara iyi gelir, gözlerin de dinlenir.",
    ],
    "browsing": [
        "{d} süredir internettesin; aradığını buldun mu, yoksa kaybolduk mu?",
        "{d} oldu, biraz kalk dolaş; sekmeler seni bekler.",
    ],
    "office": [
        "{d} süredir çalışıyorsun; kısa bir ara ver, dönünce daha hızlı bitirirsin.",
    ],
    "media": ["{d} süredir izliyorsun/dinliyorsun; biraz gerinmek iyi gelir."],
    "chat": ["{d} süredir sohbettesin, çay molası?"],
    "other": ["{d} süredir bilgisayar başındasın; kısa bir mola iyi gelir."],
}

BACK_FROM_IDLE_LINES = [
    "Hoş geldin, {d} yoktun; ben de kestirdim.",
    "Geri döndün! {d} sonra klavye yine ısınacak.",
    "Neredeydin, {d} geçti? Neyse, devam edelim.",
]

SWITCH_LINES = {
    "coding": ["Kod moduna geçtik, kolay gelsin.", "Editör açıldı; bugün ne yazıyoruz?"],
    "gaming": ["Oyun zamanı mı? İyi oyunlar!", "Oyun açıldı; bol şans, ben seyirciyim."],
    "browsing": ["Tarayıcıya geçtin; arada beni de unutma.", "Bir şey mi aradın? Yardım isteyebilirsin."],
    "office": ["Ofis işine döndük; başarılar.", "Belge açıldı, odaklanma zamanı."],
    "chat": ["Sohbete geçtin; selam söyle.", "Mesajlar birikti sanırım."],
    "media": ["Müzik/film zamanı, keyfini çıkar.", "Biraz mola; iyi fikir."],
    "files": ["Dosyalarla uğraşıyorsun; dikkatli sil.", "Klasörler toparlanıyor mu?"],
}

LATE_NIGHT_LINES = [
    "Saat epey geç oldu; kediler bile uyuyor, sen de düşün.",
    "Gece geç; birazdan yatmak kötü fikir değil, sabah daha iyi düşünürsün.",
    "Bu saatte hâlâ ayaktasın; bir kedi olarak uykuyu şiddetle tavsiye ederim.",
]


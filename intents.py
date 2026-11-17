"""Çevrimdışı Türkçe niyet çözümleme: komut cümlesini (eylem, argüman, giriş) üçlüsüne çevirir.

Yaprak modül: yalnızca pc_actions'a bağlıdır, ai'yi içe aktarmaz. ai.py bu adları yeniden dışa aktarır.
"""
from __future__ import annotations

import random
import re
from typing import Callable

from pc_actions import FOLDER_ALIASES, normalize, resolve_app_key

MAX_TOOL_ITERATIONS = 6            # araç turu ve eylem planı üst sınırı (ai.py de kullanır)


_FILLERS = ("lutfen", "bana", "hadi", "hemen", "bi", "bir", "simdi", "acaba", "rica etsem", "komur", "kedim", "kedi")
_OPEN_VERBS = r"(?:ac(?:ar misin|abilir misin|sana|ar misiniz|ilsin|ip ver|iver)?|baslat(?:ir misin|abilir misin)?|calistir(?:ir misin)?|getir)"
_CLOSE_VERBS = r"(?:kapat(?:ir misin|abilir misin|sana)?|kapa|sonlandir)"
_SEARCH_VERBS = r"(?:ara(?:t|yabilir misin|r misin|ma yap)?|arastir|bul(?:ur musun)?)"


def _strip_fillers(s: str) -> str:
    words = [w for w in s.split() if w not in _FILLERS]
    return " ".join(words).strip(" ,.!?")


def _strip_suffix(obj: str, tester: Callable[[str], bool]) -> str:
    """Türkçe belirtme/yönelme ekini kaldır, ama yalnızca sonuç ``tester`` ile tanınıyorsa."""
    obj = obj.strip(" '")
    if tester(obj):
        return obj
    for suffix in ("'yi", "'yu", "'i", "'u", "'a", "'e", "'ye", "'ya", "nin", "nun", "yi", "yu", "ni", "nu", "in", "un",
                   "i", "u", "a", "e"):
        if obj.endswith(suffix) and len(obj) > len(suffix) + 1:
            cand = obj[: -len(suffix)].rstrip("'")
            if tester(cand):
                return cand
    return obj


def _minutes_in(n: str) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(saat|dakika|dk|saniye|sn)", n)
    if not m:
        m2 = re.search(r"\b(yarim|bir|iki|uc|on|on bes|yirmi|otuz|kirk bes)\s*(saat|dakika|dk)\b", n)
        if not m2:
            return None
        words = {"yarim": 0.5, "bir": 1, "iki": 2, "uc": 3, "on": 10, "on bes": 15, "yirmi": 20, "otuz": 30, "kirk bes": 45}
        value, unit = words[m2.group(1)], m2.group(2)
    else:
        value, unit = float(m.group(1).replace(",", ".")), m.group(2)
    if unit == "saat":
        return value * 60
    if unit in ("saniye", "sn"):
        return max(value / 60, 1 / 60)
    return value


def parse_action_plan(text: str) -> list[dict] | None:
    """Only split explicit command clauses; quoted notes and ordinary dialogue stay whole."""
    n = normalize(text).strip()
    if re.match(r"^(?:not (?:al|yaz|olustur|tut|ekle)\b|bunu hatirla|aklinda tut|hatirla|komut|powershell|cmd)", n):
        return None
    protected = re.sub(r"\b(saniye|dakika|saat|gün|gun|hafta)\s+sonra\b", r"\1 __KOMUR_TEMPORAL__", text, flags=re.I)
    parts = [part.replace('__KOMUR_TEMPORAL__', 'sonra') for part in
             re.split(r"\s*(?:;|\b(?:ve sonra|ardindan|ardından|sonra)\b)\s*", protected, flags=re.I)]
    if len(parts) < 2 or len(parts) > MAX_TOOL_ITERATIONS:
        return None
    plan = []
    for part in parts:
        intent = parse_intent(part)
        if not intent or intent[0] == "_chat":
            return None
        plan.append({"name": intent[0], "args": intent[1]})
    return plan


def _game_name(text):
    game = re.sub(r"\s+(?:oyununu|oyunu)$", "", text).strip(" '")
    game = re.sub(r"[ '\s]+(?:yi|yu|yı|yü|i|u|ı|ü)$", "", game).strip()
    for alias in ("lol", "cs", "cs2", "csgo"):
        if game in {alias + suffix for suffix in ("i", "u", "yi", "yu")}:
            return alias
    return game


def parse_intent(text: str) -> tuple[str, dict, str] | None:
    """Türkçe komutu (eylem_adı, argümanlar, giriş_cümlesi) üçlüsüne çevirir; sohbet için
    ("_chat", {}, yanıt) döner; anlaşılmazsa None."""
    raw = text.strip().replace("’", "'").replace("‘", "'")
    n = normalize(raw)
    n_clean = _strip_fillers(n)

    # Direct game requests bypass ambiguous app-name resolution and work without an LLM.
    game_text = re.sub(r"^steam(?:'?(?:i|den|dan|de|da))?\s+acip\s+", "", n_clean)
    game_text = re.sub(r"^steam\s*'?(?:den|dan|de|da)?\s+", "", game_text)
    if re.match(r"^(?:not (?:al|yaz|olustur|tut|ekle)\b|bunu hatirla|aklinda tut|hatirla|komut|powershell|cmd)", n_clean):
        game_text = ''
    install = re.fullmatch(r"(.+?)\s+(?:oyununu\s+)?(?:indir|yukle|kur|indirmeye al)", game_text)
    if install and ("steam" in n_clean):
        game = _game_name(install.group(1))
        return "install_game", {"game": game}, ""
    launch = re.fullmatch(r"(.+?)\s+(?:oyununu\s+)?(?:ac|baslat|oyna|gir)", game_text)
    if launch:
        game = _game_name(launch.group(1))
        known = {"lol", "league of legends", "league", "cs", "cs2", "csgo", "cs go", "counter strike", "counter-strike", "counter strike 2", "counter-strike 2", "dota 2", "pubg"}
        if game in known or ("steam" in n_clean and game not in {"steam", "steami"}):
            return "launch_game", {"game": game}, ""

    if re.fullmatch(r"(?:hatirlaticilari|alarmlari|bekleyen hatirlaticilari) (?:goster|listele)", n_clean):
        return "list_reminders", {}, ""
    cancel = re.fullmatch(r"(?:hatirlatici|alarm)\s+(\d+)\s+(?:iptal et|sil)", n_clean)
    if cancel:
        return "cancel_reminder", {"reminder_id": int(cancel.group(1))}, ""
    if re.fullmatch(r"(?:not|hafiza notu)\s+(\d+)\s+(?:unut|sil)", n_clean):
        return "forget_memory", {"note_id": int(re.search(r"\d+", n_clean).group())}, ""
    recurring = re.fullmatch(r"her\s+(?:(\d+)\s+)?(dakika|saat|gun|hafta)(?:da)?\s+(?:bir\s+)?(.+?)\s+hatirlat", n_clean)
    if recurring:
        interval = int(recurring.group(1) or 1) * {'dakika': 1, 'saat': 60, 'gun': 1440, 'hafta': 10080}[recurring.group(2)]
        return "recurring_reminder", {'minutes': interval, 'label': _original_span(raw, recurring.group(3)) or recurring.group(3)}, ""

    memory = re.search(r"^(?:bunu hatirla|aklinda tut|hatirla)\s*[:,-]?\s*(.+)$", n)
    if memory:
        return "remember_fact", {"text": _original_span(raw, memory.group(1)) or memory.group(1)}, ""
    if re.fullmatch(r"(?:neler hatirliyorsun|hafizani goster|notlarini goster|beni taniyor musun)", n_clean):
        return "recall_memories", {"query": ""}, ""
    memory = re.search(r"^gecmiste\s+(.+?)\s+ara$", n_clean)
    if memory:
        return "recall_memories", {"query": _original_span(raw, memory.group(1)) or memory.group(1)}, ""

    url_read = re.search(r"https?://[^\s<>'\"]+", raw, re.I)
    if url_read and re.search(r"\b(?:oku|incele|ozetle|ozet|okuyup)\b", n):
        return "web_read", {"url": url_read.group(0).rstrip(".,;!?")}, ""

    # Explicit requests directed at the cat; do not interpret general conversation as actions.
    cat_commands = (
        (r"\b(?:(?:yerde|yere)\s+)?(?:yuvarlan|takla at)\b", "roll"),
        (r"\b(?:esne)\b", "yawn"),
        (r"\b(?:uykuya dal|uyu)\b", "sleep"),
        (r"\b(?:uyan)\b", "wake"),
        (r"\b(?:beni takip et|pesimden gel)\b", "follow"),
        (r"\b(?:dolas|gezintiye cik)\b", "wander"),
        (r"\b(?:oyna|topla oyna)\b", "play"),
        (r"\b(?:mama ye|mama ver)\b", "feed"),
        (r"\b(?:kendini sevdir|seni seveyim)\b", "pet"),
        (r"\b(?:sikil|canin sikilsin)\b", "bored"),
        (r"\b(?:dans et|oyna bakalim)\b", "dance"),
        (r"\b(?:film izle|misir ye|benimle izle)\b", "watch"),
    )
    for pattern, behavior in cat_commands:
        if re.fullmatch(pattern, n_clean):
            return "cat_behavior", {"behavior": behavior}, ""

    # -- kapatma / yeniden başlatma / iptal
    if re.search(r"(kapat|kapan|yeniden baslat).*(iptal)|iptal.*(kapat|yeniden baslat)", n):
        return "cancel_shutdown", {}, ""
    if re.search(r"\b(bilgisayar|pc|makine|sistem)\w*\b.*\b(yeniden baslat|restart|resetle)|\b(yeniden baslat|restart)\b", n):
        return "restart", {"minutes": int(_minutes_in(n) or 0)}, ""
    if re.search(r"\b(bilgisayar|pc|makine|sistem|windows)\w*\b.*\bkapat|\bkapat\w*\s+(bilgisayar|pc)\w*|\bshutdown\b", n):
        return "shutdown", {"minutes": int(_minutes_in(n) or 0)}, ""
    if re.search(r"\b(ekran|bilgisayar|pc|oturum)\w*\s+kilitle|\bkilitle\b", n):
        return "lock_screen", {}, ""

    # -- çöp kutusu
    if re.search(r"(cop kutusu|geri donusum|recycle)", n) and re.search(r"(bosalt|temizle|sil)", n):
        return "empty_recycle_bin", {}, ""

    # -- ekran görüntüsü
    if re.search(r"(ekran goruntusu|ekran resmi|screenshot|\bss\b|ekrani cek|ekranin fotografi)", n):
        return "screenshot", {}, ""

    # -- ses
    m = re.search(r"\bses\w*\b.*?%?\s*(\d{1,3})\s*%?|%\s*(\d{1,3})\s*.*\bses", n)
    if m and re.search(r"\bses", n) and re.search(r"(yap|ayarla|getir|olsun|cek|indir|cikar|ver|yuzde|%)", n):
        pct = int(m.group(1) or m.group(2))
        return "set_volume", {"percent": pct}, ""
    if re.search(r"\bses\w*\b.*(kapat|sustur|kes|mute)|\bsustur\b|\bmute\b", n):
        return "mute_toggle", {}, ""
    if re.search(r"\bses\w*\b.*(kis|azalt|dusur|alcalt|indir|kistir)", n):
        return "volume_down", {"steps": 5}, ""
    if re.search(r"\bses\w*\b.*(ac|artir|yukselt|arttir|yukselt|cogalt)|\bsesi ac\b", n) and not re.search(r"(muzik|sarki|spotify)", n):
        return "volume_up", {"steps": 5}, ""

    # -- YouTube'da belirli bir par?ay? a?ma / ?alma
    yt_text = re.sub(r"^(?:(?:komur|lutfen|bana|hadi|hemen|simdi)\s+)+", "", n)
    yt = re.search(r"^(?:youtube|yutup)\s*(?:'?(?:dan|den|tan|ten|da|de|ta|te))?\s+(.+?)\s+(?:ara\s+)?(?:ac|izle|oynat|cal)(?:\s|$)", yt_text)
    if yt:
        query = yt.group(1).strip()
        return "youtube_play", {"query": _original_span(raw, query) or query}, ""
    yt = re.search(r"^(.+?)\s+(?:youtube|yutup)\s*(?:'?(?:da|de|ta|te))?\s+(?:ara\s+)?(?:ac|izle|oynat|cal)\b", yt_text)
    if yt:
        query = yt.group(1).strip()
        return "youtube_play", {"query": _original_span(raw, query) or query}, ""
    # -- medya
    if re.search(r"(sonraki|bir sonraki|diger)\s+(sarki|parca|muzik)|(sarki|parca)\w*\s+(gec|atla|degistir)|\bskip\b", n):
        return "media_next", {}, ""
    if re.search(r"(onceki|bir onceki)\s+(sarki|parca|muzik)|geri (al|sar)", n):
        return "media_prev", {}, ""
    if re.search(r"(muzik|sarki|parca|medya|video)\w*\s*(durdur|duraklat|baslat|oynat|calsin|cal|devam)|(durdur|duraklat|devam et)\s*(muzik|sarki)?$", n):
        return "media_play_pause", {}, ""

    # -- saat / tarih / sistem
    if re.search(r"saat kac|saat ne|kac saat oldu|tarih ne|bugun (gunlerden|ayin kaci|ne)|hangi gun|bugunun tarihi", n):
        return "get_time", {}, ""
    if re.search(r"sistem bilgi|sistem durum|bilgisayar(in)? durumu|\bram\b|cpu|islemci|disk\w*\s+(durum|bos|dolu)|pil\w*\s*(durum|yuzde|kac)|bellek|ne kadar bos", n):
        return "system_info", {}, ""

    # -- zamanlayıcı / hatırlatıcı
    mins = _minutes_in(n)
    if mins and re.search(r"(hatirlat|zamanlayici|sayac|alarm|timer|uyar|haber ver|soyle)", n):
        label_m = re.search(r"(?:sonra|icin)\s+(.+?)\s*(?:diye|hatirlat|uyar|haber ver|soyle)", n_clean)
        label = raw
        if label_m:
            # orijinal metinden (Türkçe karakterli) parçayı yakalamaya çalış
            orig = re.search(r"(?:sonra|için)\s+(.+?)\s*(?:diye|hatırlat|uyar|haber ver|söyle)", raw, re.I)
            label = (orig.group(1) if orig else label_m.group(1)).strip(" ,.")
        else:
            label = "Süre doldu!"
        return "set_timer", {"minutes": mins, "label": label}, ""
    if re.search(r"^(zamanlayici|sayac|alarm|timer)", n) and not mins:
        return "_chat", {}, "Kaç dakika sonra hatırlatayım? Mesela 'on dakika sonra çay demle diye hatırlat' diyebilirsin."

    # -- not
    m = re.search(r"^(?:not (?:al|yaz|olustur|tut|ekle))\s*[:\-]?\s*(.+)$", n)
    if m:
        orig = re.search(r"^(?:not (?:al|yaz|oluştur|tut|ekle))\s*[:\-]?\s*(.+)$", raw, re.I)
        body = (orig.group(1) if orig else m.group(1)).strip()
        return "create_note", {"text": body, "title": "Not"}, ""
    if re.search(r"\bnot (al|yaz|olustur)\b", n):
        return "_chat", {}, "Ne yazayım? 'not al: süt al' gibi söylersen masaüstüne yazarım."

    # -- komut
    m = re.search(r"^(?:komut(?:u)? (?:calistir|cal)|powershell(?:de|'de)?|cmd(?:de|'de)?)\s*[:\-]?\s*(.+)$", n)
    if m:
        orig = re.search(r"^(?:komut(?:u)? (?:çalıştır|çalistir|calistir|çal)|powershell(?:de|'de)?|cmd(?:de|'de)?)\s*[:\-]?\s*(.+)$", raw, re.I)
        return "run_command", {"command": (orig.group(1) if orig else m.group(1)).strip()}, ""

    # -- G?ncel bilgi edinme (arama sayfas? a?ma iste?inden ayr?)
    if re.search(r"\b(?:arastir|internetten|internette|webden|webde)\b", n_clean) and not re.search(r"\b(?:youtube|yutup)\b", n_clean):
        return "web_research", {"query": raw}, ""
    # -- arama
    m = re.search(r"^(?:(youtube|yutup|google|wikipedia|vikipedi)\s*(?:'?(?:da|de|ta|te))?\s+)?(.+?)\s+(?:diye|hakkinda|icin)?\s*" + _SEARCH_VERBS + r"(?:\s+(?:youtube|google)\w*)?$", n_clean)
    if m and not re.search(r"\b(ac|baslat)\b", n_clean):
        site = m.group(1) or ""
        query = m.group(2).strip()
        tail = re.search(r"(youtube|yutup|google)\w*$", n_clean)
        if tail and not site:
            site = tail.group(1)
        query = re.sub(r"^(youtube|yutup|google|wikipedia|vikipedi)\s*(?:'?(?:da|de|ta|te))?\s+", "", query).strip()
        query = re.sub(r"\s+(diye|hakkinda|icin)$", "", query).strip()
        # orijinal (Türkçe karakterli) sorguyu yakalamaya çalış
        orig = _original_span(raw, query)
        site_key = "youtube" if site in ("youtube", "yutup") else ("wikipedia" if site in ("wikipedia", "vikipedi") else "google")
        return "web_search", {"query": orig or query, "site": site_key}, ""
    m = re.search(r"(youtube|yutup)\s*(?:'?(?:da|de|ta|te))?\s+(.+?)\s+(?:ac|izle|oynat|cal)\b", n_clean)
    if m:
        return "web_search", {"query": _original_span(raw, m.group(2)) or m.group(2), "site": "youtube"}, ""

    # -- URL
    m = re.search(r"((?:https?://)?[\w.-]+\.(?:com|net|org|tr|io|dev|gg|tv|me|co|edu|gov)(?:\.tr)?(?:/\S*)?)", n)
    if m and re.search(r"\b(ac|git|gir|goster)\b", n):
        return "open_url", {"url": m.group(1)}, ""

    # -- klasör
    m = re.search(r"\b(masaustu|indirilenler|belgeler(?:im)?|dokumanlar|resimler(?:im)?|fotograflar|muzik(?:ler)?|videolar(?:im)?|downloads|desktop|documents|pictures)\w*\s+(?:klasor\w*\s+)?" + _OPEN_VERBS, n_clean)
    if m:
        key = m.group(1)
        for alias, folder in FOLDER_ALIASES.items():
            if key.startswith(alias):
                return "open_folder", {"path_or_known": folder}, ""
    m = re.search(r"\b([a-z]:\\[^\s]+)\s+" + _OPEN_VERBS, n_clean)
    if m:
        orig = re.search(r"([A-Za-z]:\\[^\s]+)", raw)
        return "open_folder", {"path_or_known": orig.group(1) if orig else m.group(1)}, ""

    # -- uygulama kapat
    m = re.search(r"^(.+?)\s+" + _CLOSE_VERBS + r"(?:\s+(?:lutfen|bakalim))?$", n_clean)
    if m and not re.search(r"\b(bilgisayar|pc|ses|ekran|isik)\b", m.group(1)):
        obj = _strip_suffix(m.group(1), lambda s: resolve_app_key(s) is not None)
        force = bool(re.search(r"\b(zorla|force)\b", n))
        key = resolve_app_key(obj)
        if key:
            return "close_app", {"name": key, "force": force}, ""

    # -- uygulama aç
    typo = re.search(r"^([a-z]+)\s+" + _OPEN_VERBS + r"$", n_clean)
    if typo:
        word = typo.group(1)
        for suffix in ("iu", "ui", "ii", "uu"):
            if word.endswith(suffix) and resolve_app_key(word[:-len(suffix)]):
                return "open_app", {"name": resolve_app_key(word[:-len(suffix)])}, ""
    m = re.search(r"^(.+?)\s+" + _OPEN_VERBS + r"(?:\s+(?:lutfen|bakalim|hadi))?$", n_clean) or \
        re.search(r"^" + _OPEN_VERBS + r"\s+(.+?)$", n_clean)
    if m:
        obj = m.group(1).strip()
        obj = re.sub(r"^(uygulama\w*|program\w*)\s+", "", obj)
        if not re.search(r"\b(ses|ekran|isik|kapi|pencere)\b", obj):
            key_obj = _strip_suffix(obj, lambda s: resolve_app_key(s) is not None)
            key = resolve_app_key(key_obj)
            if key:
                return "open_app", {"name": key}, ""
            if len(obj.split()) <= 3:
                return "open_app", {"name": key_obj}, ""
    # tek kelime uygulama adı ("spotify", "valorant")
    key = resolve_app_key(n_clean)
    if key and len(n_clean.split()) <= 2 and key not in ("browser",):
        return "open_app", {"name": key}, ""

    # -- sohbet
    return _small_talk(n, raw)


def _original_span(raw: str, normalized_piece: str) -> str | None:
    """Normalleştirilmiş parçanın orijinal (Türkçe karakterli) karşılığını kelime sayısına göre al."""
    words = raw.split()
    target = normalized_piece.split()
    if not target:
        return None
    for i in range(len(words) - len(target) + 1):
        if [normalize(w).strip("',.!?") for w in words[i:i + len(target)]] == [t.strip("',.!?") for t in target]:
            return " ".join(words[i:i + len(target)]).strip(" ,.!?'")
    return None


def _small_talk(n: str, raw: str) -> tuple[str, dict, str] | None:
    def any_in(*keys):
        return any(re.search(r"\b" + k + r"\b", n) for k in keys)

    if any_in("merhaba", "selam", "selamlar", "gunaydin", "iyi gunler", "iyi aksamlar", "hey", "hello", "hi", "naber", "nbr"):
        return "_chat", {}, random.choice([
            "Merhaba! Ben Kömür, mrr. Bugün ne yapıyoruz?",
            "Selam! Buradayım, ne lazımsa söyle.",
            "Hoş geldin! Bir şey açmamı ya da aramamı ister misin?",
        ])
    if any_in("nasilsin", "nasil gidiyor", "iyi misin", "keyfin nasil", "ne haber"):
        return "_chat", {}, random.choice([
            "İyiyim, klavyenin yanında kıvrılmış seni izliyorum. Sen nasılsın?",
            "Gayet keyifliyim, mrr. Senin günün nasıl geçiyor?",
        ])
    if any_in("tesekkur", "tesekkurler", "sagol", "sag ol", "eyvallah", "thanks", "tsk"):
        return "_chat", {}, random.choice(["Rica ederim, mrr.", "Ne demek! Başka bir şey lazımsa buradayım.", "Her zaman."])
    # "canım" tek başına hitap; "canım sıkıldı" gibi cümleler sevgi sözü değildir.
    if any_in("seni seviyorum", "cok tatlisin", "askim") or n.strip(" !.") in ("canim", "canim benim"):
        return "_chat", {}, "Ben de seni seviyorum. Mırrr."
    if any_in("adin ne", "kimsin", "sen kimsin", "nesin sen", "ne is yaparsin"):
        return "_chat", {}, ("Ben Kömür, masaüstünde yaşayan siyah-beyaz smokinli bir kediyim. "
                             "Uygulama açar, arama yapar, hatırlatıcı kurar, sohbet ederim.")
    if any_in("yardim", "help", "neler yapabilirsin", "ne yapabilirsin", "komutlar", "nasil kullanilir"):
        return "_chat", {}, ("Şöyle diyebilirsin: 'not defterini aç', 'youtube'da lofi ara', 'sesi %30 yap', "
                             "'ekran görüntüsü al', 'saat kaç', '10 dakika sonra çay diye hatırlat', "
                             "'sistem bilgisi', 'çöp kutusunu boşalt'. Tehlikeli şeyleri önce sana sorarım.")
    if any_in("miyav", "mirla", "purr", "meow", "mrr"):
        return "_chat", {}, random.choice(["Miyav! Mırrr…", "Mrr? Dilimi konuşuyorsun, güzel.", "Miyaaav."])
    if any_in("mama", "acim", "ac misin", "yemek"):
        return "_chat", {}, "Mama lafını duyunca kulaklarım dikildi. Sağ tık menüsünden mama verebilirsin!"
    if any_in("oyun oynayalim", "oynayalim", "top", "oynamak"):
        return "_chat", {}, "Top mu dedin? 'Topla oyna' deyince hemen koşarım."
    if any_in("uyu", "uyku", "iyi geceler", "yat"):
        return "_chat", {}, "Esnedim bile. İyi geceler, güzel rüyalar."
    if any_in("saka", "fikra", "guldur", "espri"):
        return "_chat", {}, random.choice([
            "Kediler neden bilgisayarı sever? Fare var diye. Mrr, biliyorum, kötüydü.",
            "Programcı kedi mi olur? Olur, sürekli 'mouse' peşinde koşar.",
        ])
    if any_in("hava", "hava durumu", "yagmur", "sicaklik"):
        return "_chat", {}, "Hava durumuna bakamıyorum ama 'hava durumu ara' dersen tarayıcıda açarım."
    return None

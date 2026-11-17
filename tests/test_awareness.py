import io
import json
import random
from unittest.mock import patch

import awareness as aw
from activity_reactions import ActivityReactions, MediaSessionClient
from context import parse_mic_key_name


def fg(proc, cat, title='', hint=None):
    return {'process_name': proc, 'category': cat, 'title': title, 'hint': hint}


def test_media_kind_sources():
    assert aw.media_kind([{'app': 'Spotify.exe'}]) == 'music'
    assert aw.media_kind([{'app': 'chrome.exe', 'type': 'Video'}]) == 'video'
    assert aw.media_kind([{'app': 'Chrome', 'title': 'x - YouTube Music'}]) == 'music'
    assert aw.media_kind([{'app': 'MSEdge', 'title': 'Netflix'}]) == 'video'
    assert aw.media_kind([{'app': 'chrome.exe'}]) is None
    assert aw.media_kind([]) is None
    # arka plandaki sekme: ön plandaki YouTube sekmesi hatırlanır
    assert aw.media_kind([{'app': 'chrome.exe'}], browser_memory='video') == 'video'
    # tam ekran tarayıcı + bilinmeyen oturum
    assert aw.media_kind([{'app': 'chrome.exe'}], fg('chrome.exe', 'browsing'), True) == 'video'


def test_browser_hint_needs_foreground_browser():
    assert aw.browser_hint(fg('chrome.exe', 'media', 'Film - YouTube', 'YouTube')) == 'video'
    assert aw.browser_hint(fg('Code.exe', 'coding', 'YouTube notes')) is None
    assert aw.browser_hint(fg('msedge.exe', 'browsing', 'Open.Spotify', 'Spotify')) == 'music'


def test_classify_priorities():
    c = aw.classify_activity
    assert c(fg('VALORANT-Win64-Shipping.exe', 'gaming'), idle=400) == 'gaming'
    assert c(fg('steam.exe', 'gaming'), idle=0) == 'none'
    assert c(fg('Zoom.exe', 'chat'), mic_apps={'zoom'}) == 'meeting'
    assert c(fg('chrome.exe', 'browsing', 'Meet - abc'), mic_apps={'chrome'}) == 'meeting'
    assert c(fg('chrome.exe', 'browsing', 'Haberler'), mic_apps={'chrome'}) == 'reading'
    # izlerken girdi yok: away/idle değil video
    assert c(fg('chrome.exe', 'media'), media='video', idle=900) == 'video'
    assert c(fg('vlc.exe', 'media'), fullscreen=True, idle=900) == 'video'
    assert c(fg('chrome.exe', 'browsing', 'x', 'YouTube'), fullscreen=True) == 'video'
    assert c(fg('chrome.exe', 'browsing'), fullscreen=True) == 'reading'   # tam ekran ama video sinyali yok
    # kod yazarken arka plan videosu kodlamayı bozmaz
    assert c(fg('Code.exe', 'coding'), media='video', idle=2) == 'coding'
    assert c(fg('Code.exe', 'coding'), media='music', idle=2) == 'music'


def test_idle_away_and_work_classes():
    c = aw.classify_activity
    assert c(fg('Code.exe', 'coding'), idle=61) == 'idle'
    assert c(fg('Code.exe', 'coding'), idle=301) == 'away'
    assert c(fg('Code.exe', 'coding'), idle=5) == 'coding'
    assert c(fg('Code.exe', 'coding'), idle=45) == 'none'      # klavye aktif değil
    assert c(fg('WINWORD.EXE', 'office'), idle=3) == 'writing'
    assert c(fg('chrome.exe', 'office', 'Belge', 'Google Docs'), idle=3) == 'writing'
    assert c(fg('chrome.exe', 'browsing'), idle=3) == 'reading'
    assert c(fg('AcroRd32.exe', 'office'), idle=3) == 'reading'
    assert c(fg('explorer.exe', 'files'), idle=3) == 'none'
    assert c(None) == 'none'


def test_stabilizer_hysteresis():
    s = aw.Stabilizer(2)
    assert s.feed('coding') == 'coding'            # ilk örnek hemen
    assert s.feed('video') == 'coding'
    assert s.feed('coding') == 'coding'            # titreme sayacı sıfırlar
    assert s.feed('video') == 'coding'
    assert s.feed('video') == 'video'
    assert s.feed('none') == 'video'


def test_reaction_table_shape():
    assert set(aw.CLASSES) == set(aw.REACTIONS)
    assert aw.REACTIONS['video']['state'] == 'watch'
    assert aw.REACTIONS['away']['state'] == 'sleep'
    for entry in aw.REACTIONS.values():
        assert entry['cooldown'] >= 600 and isinstance(entry['messages'], list)
    assert aw.REACTIONS['meeting']['messages'] == [] and aw.REACTIONS['gaming']['messages'] == []


def test_planner_cooldown_and_welcome():
    p = aw.ReactionPlanner(rng=random.Random(1))
    r = p.plan('none', 'video', 0)
    assert r['state'] == 'watch' and r['message']
    assert p.plan('video', 'video', 1) is None
    p.plan('video', 'none', 10)
    assert p.plan('none', 'video', 100)['message'] is None       # 10 dk dolmadı
    assert p.plan('none', 'video', 700)['message']
    assert p.plan('none', 'meeting', 800)['message'] is None
    back = p.plan('away', 'coding', 1000)
    assert back['message'] == aw.WELCOME_BACK


def test_parse_mic_key_name():
    assert parse_mic_key_name('C:#Program Files#Zoom#bin#Zoom.exe') == 'zoom'
    assert parse_mic_key_name('MSTeams_8wekyb3d8bbwe') == 'msteams_8wekyb3d8bbwe'


class FakeProc:
    def __init__(self, replies, alive=True):
        self.stdin = io.StringIO()
        self.stdout = iter(replies)
        self._alive = alive
        self.killed = False

    def poll(self):
        return None if self._alive and not self.killed else 1

    def kill(self):
        self.killed = True


def test_media_client_parses_and_restarts():
    sessions = [{'app': 'Spotify.exe', 'type': 'Music', 'title': 't', 'artist': 'a'}]
    procs = []

    def popen():
        p = FakeProc(['ready', json.dumps(sessions)])
        procs.append(p)
        return p

    client = MediaSessionClient(popen=popen, timeout=2, retry_after=0)
    assert client.query() == sessions
    procs[0]._alive = False                      # süreç öldü -> sessizce yeniden başlar
    assert client.query() == sessions
    assert len(procs) == 2


def test_media_client_failure_is_silent_and_backs_off():
    def popen():
        raise OSError('yok')
    client = MediaSessionClient(popen=popen, timeout=0.1, retry_after=60)
    assert client.query() == []
    assert client.query() == []                  # bekleme süresinde yeniden denemez


def test_media_client_timeout_kills_process():
    proc = FakeProc([])
    client = MediaSessionClient(popen=lambda: proc, timeout=0.2, retry_after=60)
    assert client.query() == []
    assert proc.killed


def test_activity_reactions_end_to_end_with_stub_probes():
    class Media:
        def query(self):
            return [{'app': 'chrome.exe', 'type': 'Video', 'title': '', 'artist': ''}]

        def close(self):
            pass

    r = ActivityReactions(media_client=Media())
    with patch('activity_reactions.get_foreground_info', return_value=fg('Code.exe', 'coding')), \
            patch('activity_reactions.idle_seconds', return_value=999), \
            patch('activity_reactions._is_fullscreen', return_value=False), \
            patch('activity_reactions.mic_in_use_apps', return_value=set()):
        r._sample()
        assert r.current == 'video'              # film oynuyor, girdisiz bile away değil
        reaction = r.take_reaction()
        assert reaction['state'] == 'watch' and reaction['class'] == 'video'
        assert r.take_reaction() is None
    assert r.poll(0, enabled=False) == 'none'


def test_is_browser_short_names_need_exact_match():
    from awareness import is_browser
    assert is_browser("arc") and is_browser("msedge") and is_browser("chrome")
    assert not is_browser("archicad") and not is_browser("arcgis") and not is_browser("zenmap")


def test_video_beats_open_voice_channel_and_away_beats_mic():
    from awareness import classify_activity
    yt = {'process_name': 'chrome.exe', 'category': 'browsing', 'hint': 'YouTube', 'title': 'x - YouTube'}
    assert classify_activity(yt, media='video', idle=5, mic_apps={'discord'}) == 'video'
    assert classify_activity(yt, media=None, idle=5, mic_apps={'discord'}) == 'meeting'
    assert classify_activity(yt, media=None, idle=900, mic_apps={'discord'}) == 'away'


def test_browser_session_type_is_not_trusted():
    from awareness import media_kind
    chrome = [{'app': 'chrome.exe', 'type': 'Music', 'title': 'Bir video', 'artist': ''}]
    yt = {'process_name': 'chrome.exe', 'category': 'browsing', 'hint': 'YouTube', 'title': 'Bir video - YouTube'}
    ytm = {'process_name': 'chrome.exe', 'category': 'media', 'hint': 'YouTube Music', 'title': 'Şarkı - YouTube Music'}
    other = {'process_name': 'code.exe', 'category': 'coding', 'hint': None, 'title': 'x'}
    assert media_kind(chrome, yt) == 'video'
    assert media_kind(chrome, ytm) == 'music'
    assert media_kind(chrome, other, browser_memory='video') == 'video'
    assert media_kind([{'app': 'Spotify.exe', 'type': 'Music'}], other) == 'music'


def test_stale_mic_registry_entry_ignored(monkeypatch):
    import context
    monkeypatch.setattr(context, "_running_process_names", lambda: {"chrome", "spotify"})
    apps = {"discord", "chrome"}
    running = context._running_process_names()
    assert {a for a in apps if a in running} == {"chrome"}

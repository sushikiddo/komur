from types import SimpleNamespace
from unittest.mock import patch

from activity_reactions import ActivityReactions, active_game, media_playback
from renderer import CatRenderer


def test_game_launcher_is_not_game():
    assert not active_game({'process_name': 'steam.exe', 'category': 'gaming'})
    assert not active_game({'process_name': 'RiotClientServices.exe', 'category': 'gaming'})
    assert active_game({'process_name': 'VALORANT-Win64-Shipping.exe', 'category': 'gaming'})
    assert not active_game({'process_name': 'chrome.exe', 'category': 'media'})


def test_media_requires_playing_and_known_type():
    with patch('activity_reactions.os.name', 'nt'), patch('activity_reactions.subprocess.run') as run:
        run.return_value = SimpleNamespace(returncode=0, stdout='music\n')
        assert media_playback() == 'music'
        run.return_value.stdout = 'none\n'
        assert media_playback() == 'none'
        run.return_value.stdout = 'unknown\n'
        assert media_playback() == 'none'
        run.side_effect = OSError()
        assert media_playback() == 'none'


def test_game_takes_priority_and_disabled_clears():
    detector = ActivityReactions()
    with patch('activity_reactions.get_foreground_info', return_value={'process_name': 'game.exe', 'category': 'gaming'}), patch('activity_reactions.media_playback') as media:
        detector._sample()
        assert detector.current == 'gaming'
        media.assert_not_called()
    assert detector.poll(0, enabled=False) == 'none'


def test_renderer_draws_popcorn_and_dances():
    renderer = CatRenderer.__new__(CatRenderer)
    # Exercise the real draw dispatch with lightweight primitives:
    # video uses a calm realistic watching pose (no cartoon popcorn bucket),
    # and music applies subtle head tilt instead of cartoon vertical hopping.
    renderer.canvas = SimpleNamespace(delete=lambda *a: None)
    renderer.effect_orchestrator = None
    renderer._palette = lambda: None
    renderer._pupil = lambda *a: 0
    seen = []
    renderer._sit = lambda *a: seen.append(('sit', renderer.dx, renderer.dy, renderer._dance_tilt, getattr(renderer, '_reaction', 'none')))
    renderer._poly = lambda *a, **k: seen.append(('tub',))
    renderer._line = lambda *a, **k: None
    renderer._oval = lambda *a, **k: None
    brain = SimpleNamespace(state='sit', facing=1, paused=False, activity_reaction='video')
    renderer.draw(brain, 1)
    assert ('tub',) not in seen
    assert seen[0][4] == 'video'
    seen.clear()
    brain.activity_reaction = 'music'
    renderer.draw(brain, 1)
    assert seen[0][3] != 0.0
    assert seen[0][2] == 0.0


def test_lobby_and_unknown_media_source_classification():
    assert not active_game({'process_name': 'LeagueClientUx.exe', 'category': 'gaming'})
    with patch('activity_reactions.os.name', 'nt'), patch('activity_reactions.subprocess.run') as run:
        run.return_value = SimpleNamespace(returncode=0, stdout='playing|Spotify.exe')
        assert media_playback() == 'music'
        run.return_value.stdout = 'playing|chrome.exe'
        assert media_playback({'process_name': 'chrome.exe', 'category': 'media', 'hint': 'YouTube'}) == 'video'
        assert media_playback({'process_name': 'firefox.exe', 'category': 'media', 'hint': 'YouTube'}) == 'none'
        run.return_value.stdout = 'none'
        assert media_playback({'process_name': 'chrome.exe', 'category': 'media', 'hint': 'YouTube'}) == 'none'


def test_explicit_reaction_is_timed_and_wakes_cat():
    from cat import DesktopCat
    from behavior import CatBrain, Bounds
    cat = DesktopCat.__new__(DesktopCat)
    cat.brain = CatBrain(Bounds(0, 0, 300, 300), seed=1)
    cat.brain.command('sleep')
    cat._sync_effect_state = lambda: None
    cat._refresh_status = lambda: None
    cat.say = lambda *args: None
    with patch('cat.time.monotonic', return_value=100):
        cat.command('dance')
        assert cat._manual_reaction == 'music'
        assert cat._manual_reaction_until == 120
        assert cat.brain.state == 'sit'
        cat.command('watch')
        assert cat._manual_reaction == 'video'
        cat.command('sleep')
        assert cat._manual_reaction is None
        assert cat.brain.state == 'sleep'

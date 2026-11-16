import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pc_actions import PCActions, PendingAction, is_failure
from steam_actions import installed_games, resolve_game, search_store, download_state


class GameActions(unittest.TestCase):
    def test_aliases_and_failure_classification(self):
        for alias in ('csgo', 'cs go', 'counter strike'):
            self.assertEqual(resolve_game(alias)[0], 730)
        self.assertEqual(resolve_game('dota2')[0], 570)
        self.assertEqual(resolve_game('pubg')[0], 578080)
        self.assertTrue(is_failure('Oyun bulunamadı veya adı belirsiz: x'))
        self.assertTrue(is_failure('Oyun açılamadı: hata'))

    def test_observed_steam_states(self):
        with patch.object(Path, 'read_text', return_value='"StateFlags" "256"'):
            self.assertEqual(download_state(730, [Path('Steam')]), 'updating')
        with patch.object(Path, 'read_text', return_value='"StateFlags" "4"'):
            self.assertEqual(download_state(730, [Path('Steam')]), 'unknown')
        actions = PCActions(startfile=lambda _: None)
        with patch('steam_actions.process_running', return_value=True):
            self.assertIn('işlemi çalışıyor', actions.launch_game('cs2'))
        with patch('steam_actions.download_state', return_value='updating'):
            self.assertIn('etkinliği gözlendi', actions.install_game('cs2'))

    def test_steam_launch_and_install_confirmation(self):
        opened = []
        actions = PCActions(startfile=opened.append)
        self.assertIn('Bekliyor:', actions.execute('launch_game', {'game': 'cs2'}))
        self.assertEqual(opened, ['steam://rungameid/730'])
        self.assertIsInstance(actions.execute('install_game', {'game': 'cs2'}), PendingAction)
        self.assertEqual(len(opened), 1)
        self.assertIn('Bekliyor:', actions.execute('install_game', {'game': 'cs2'}, confirmed=True))
        self.assertEqual(opened[-1], 'steam://install/730')

    def test_manifest_exact_match(self):
        manifest = Path('appmanifest_123.acf')
        with patch.object(Path, 'glob', return_value=[manifest]), patch.object(
            Path, 'read_text', side_effect=lambda *args, **kwargs: '"appid" "123"\n"name" "Example Game"'
        ):
            games = installed_games([Path('Steam')])
        self.assertEqual(resolve_game('example game', games), (123, 'Example Game'))
        self.assertIsNone(resolve_game('example', games))

    def test_store_requires_unique_exact_match(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, n): return json.dumps({'items': [{'id': 10, 'name': 'Example'}, {'id': 11, 'name': 'Example 2'}]}).encode()
        with patch('urllib.request.urlopen', return_value=Response()):
            self.assertEqual(search_store('example'), (10, 'Example'))
            self.assertIsNone(search_store('exam'))

    def test_lol_launches_product_and_reports_unverified(self):
        calls = []
        actions = PCActions(resolver=lambda _: ('exec', ['RiotClientServices.exe', '--launch-product=league_of_legends', '--launch-patchline=live']),
                            popen=calls.append, runner=lambda *a: (_ for _ in ()).throw(OSError()))
        result = actions.open_app('lol')
        self.assertIn('--launch-product=league_of_legends', calls[0])
        self.assertTrue(result.startswith('Bekliyor:'))

if __name__ == '__main__': unittest.main()

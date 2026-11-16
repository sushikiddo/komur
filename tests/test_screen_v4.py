import unittest
from unittest.mock import patch
from screen_assist import ScreenAssist


class ScreenPreviewTests(unittest.TestCase):
    def setUp(self):
        self.window = {'hwnd': 1, 'pid': 2, 'title': 'Editor'}
        self.control = {'id': '1.2', 'label': 'Save', 'enabled': True, 'invokable': True,
                        'automation_id': 'save', 'type': 'ControlType.Button'}
        self.calls = []
        self.screen = ScreenAssist(clock=lambda: 1, backend=self.backend)
        self.screen._snapshots['s'] = (0, dict(self.window, controls=[self.control]))

    def backend(self, mode, window, **kwargs):
        self.calls.append(mode)
        if mode == 'preview':
            return {'title': 'Editor', 'name': 'Save', 'type': 'Button',
                    'bounds': {'left': 1, 'top': 2, 'width': 3, 'height': 4}}
        return {'controls': []}

    def test_preview_is_read_only_and_preserves_snapshot(self):
        with patch.object(self.screen, '_window', return_value=self.window):
            result = self.screen.target_preview('s', 'Save')
        self.assertEqual(result['name'], 'Save')
        self.assertEqual(self.calls, ['preview'])
        self.assertIn('s', self.screen._snapshots)

    def test_click_reports_observation_not_success(self):
        with patch.object(self.screen, '_window', return_value=self.window):
            result = self.screen.click('s', 'Save', confirmed=True)
        self.assertEqual(self.calls, ['click', 'inspect'])
        self.assertIn('sonuç doğrulanmadı', result)
        self.assertEqual(self.screen._snapshots, {})

    def test_changed_window_cannot_preview(self):
        with patch.object(self.screen, '_window', return_value=dict(self.window, pid=3)):
            with self.assertRaisesRegex(RuntimeError, 'Window changed'):
                self.screen.target_preview('s', 'Save')
        self.assertEqual(self.calls, [])

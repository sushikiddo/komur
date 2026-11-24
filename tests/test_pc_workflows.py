import sys
import json
import socket
import subprocess
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock

from pc_actions import PCActions, PendingAction, resolve_app
from web_actions import public_get, read_page, youtube_video, research
from riot_actions import launch_valorant, VALORANT_ENDPOINT


class WebWorkflows(unittest.TestCase):
    def test_read_prefers_semantic_main_and_preserves_paragraphs(self):
        html = '<head><title>noise</title></head><body><nav>old versions</nav><div>outside</div><section role="main"><h1>Latest release</h1><p>Download <b>Version 9</b> now.</p><header>noise</header><p>Second paragraph.</p></section><footer>noise</footer></body>'
        output = read_page('https://example.com', lambda _: ('https://example.com', html))
        self.assertTrue(output.endswith('Latest release\nDownload Version 9 now.\nSecond paragraph.'))
        self.assertNotIn('noise', output)
        self.assertNotIn('old versions', output)
        self.assertNotIn('outside', output)

    def test_read_article_and_generic_body_fallback(self):
        for html in ('<body>noise<article><p>Actual content.</p></article></body>',
                     '<html><head>noise</head><body><nav>noise</nav><p>Actual content.</p><footer>noise</footer></body></html>'):
            output = read_page('https://example.com', lambda _: ('https://example.com', html))
            self.assertTrue(output.endswith('Actual content.'))
            self.assertNotIn('noise', output)

    def test_read_main_content_bounded(self):
        output = read_page('https://example.com', lambda _: ('https://example.com', '<main>' + 'x' * 9000 + '</main>'))
        self.assertEqual(output.count('x'), 6001)  # One x in example.com.

    def test_research_returns_sources(self):
        output = research('test', lambda _: ('https://www.bing.com/search', '<rss><channel><item><title>Result</title><link>https://example.com</link><description>Summary</description></item></channel></rss>'))
        self.assertIn('Kaynak: https://example.com', output)
        self.assertIn('tam sayfalar okunmadı', output)

    def test_youtube_uses_video_not_search_page(self):
        fetch = Mock(return_value=('https://www.youtube.com/results', '{"videoRenderer":{"videoId":"abcDEF123_-"}}'))
        self.assertEqual(youtube_video('a song', fetch), 'https://www.youtube.com/watch?v=abcDEF123_-&autoplay=1')

    def test_youtube_does_not_invent_missing_video(self):
        with self.assertRaises(ValueError):
            youtube_video('song', lambda _: ('url', '<html>Consent</html>'))

    def test_youtube_open_is_honest(self):
        start = Mock()
        with patch('web_actions.youtube_video', return_value='https://www.youtube.com/watch?v=abcDEF123_-&autoplay=1'):
            result = PCActions(startfile=start).execute('youtube_play', {'query': 'song'})
        self.assertIn('doğrulanmadı', result)
        start.assert_called_once()

    def test_reject_private_and_mixed_dns(self):
        for ip in ('127.0.0.1', '10.0.0.1', '169.254.169.254', '::1'):
            with self.subTest(ip=ip), patch('web_actions.socket.getaddrinfo', return_value=[(2, 1, 6, '', (ip, 443))]):
                with self.assertRaises(ValueError):
                    public_get('https://example.com/')

    def test_reject_unsafe_urls(self):
        for url in ('file:///etc/passwd', 'https://user:password@example.com', 'http://example.com:8080'):
            with self.assertRaises(ValueError):
                public_get(url)

    def test_redirect_revalidates_destination(self):
        connection = Mock()
        response = connection.getresponse.return_value
        response.status = 302
        response.getheader.return_value = 'http://127.0.0.1/'
        with patch('web_actions.socket.getaddrinfo', side_effect=[[(2, 1, 6, '', ('8.8.8.8', 443))], [(2, 1, 6, '', ('127.0.0.1', 80))]]), patch('web_actions.http.client.HTTPSConnection', return_value=connection):
            with self.assertRaises(ValueError):
                public_get('https://example.com')
        connection.close.assert_called_once()

    def test_read_is_bounded_at_output_and_labels_untrusted(self):
        output = read_page('https://example.com', lambda _: ('https://example.com', '<script>bad</script><p>Good</p>'))
        self.assertIn('GÜVENİLMEYEN', output)
        self.assertIn('Good', output)
        self.assertNotIn('bad', output)


class AppWorkflows(unittest.TestCase):
    def test_native_riot_endpoint_and_no_redirects(self):
        conn = Mock()
        options = Mock(status=204)
        options.getheader.return_value = 'DELETE, OPTIONS, POST, PUT'
        accepted = Mock(status=204)
        conn.getresponse.side_effect = [options, accepted]
        factory = Mock(return_value=conn)
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / 'lockfile'
            lock.write_text('Riot Client:123:54321:test-ephemeral:https')
            result = launch_valorant('RiotClientServices.exe', lock, lambda *args: True, factory)
        self.assertEqual(result, 'accepted')
        self.assertEqual(factory.call_args.args[:2], ('127.0.0.1', 54321))
        self.assertEqual(conn.request.call_args_list[1].args[:2], ('POST', VALORANT_ENDPOINT))
        conn.close.assert_called_once()

    def test_native_riot_refuses_unverified_listener(self):
        factory = Mock()
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / 'lockfile'
            lock.write_text('Riot Client:123:54321:test-ephemeral:https')
            result = launch_valorant('RiotClientServices.exe', lock, lambda *args: False, factory)
        self.assertEqual(result, 'unavailable')
        factory.assert_not_called()

    def test_native_post_timeout_is_pending(self):
        conn = Mock()
        options = Mock(status=204)
        options.getheader.return_value = 'POST'
        conn.getresponse.side_effect = [options, TimeoutError()]
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / 'lockfile'
            lock.write_text('Riot Client:123:54321:test-ephemeral:https')
            result = launch_valorant('RiotClientServices.exe', lock, lambda *args: True, Mock(return_value=conn))
        self.assertEqual(result, 'pending')

    @unittest.skipUnless(sys.platform == 'win32', 'Riot istemci yolları Windows yoludur')
    def test_valorant_product_arguments(self):
        with patch('pc_actions.Path.read_text', return_value=json.dumps({'rc_live': 'C:/Games/RiotClientServices.exe'})), patch('pc_actions.Path.is_file', return_value=True):
            kind, argv = resolve_app('valorant')
        self.assertEqual(kind, 'exec')
        self.assertEqual(argv[1:], ['--launch-product=valorant', '--launch-patchline=live'])

    def test_valorant_pending_not_false_success(self):
        launch = Mock()
        actions = PCActions(popen=launch, riot_launcher=lambda _: 'unavailable', resolver=lambda _: ('exec', ['RiotClientServices.exe', '--launch-product=valorant']),
                            runner=lambda *args: subprocess.CompletedProcess([], 0, '', ''))
        self.assertIn('Bekliyor', actions.open_app('valorant'))
        launch.assert_called_once()

    def test_valorant_process_check(self):
        actions = PCActions(popen=Mock(), riot_launcher=lambda _: 'accepted', resolver=lambda _: ('exec', ['RiotClientServices.exe']),
                            runner=lambda *args: subprocess.CompletedProcess([], 0, '"VALORANT-Win64-Shipping.exe","12"', ''))
        self.assertIn('oyun işlemi çalışıyor', actions.open_app('valorant'))

    def test_commands_still_require_confirmation(self):
        runner = Mock()
        actions = PCActions(runner=runner)
        self.assertIsInstance(actions.execute('run_command', {'command': 'anything'}), PendingAction)
        runner.assert_not_called()


if __name__ == '__main__':
    unittest.main()

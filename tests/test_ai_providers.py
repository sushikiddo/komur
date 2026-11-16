import unittest
from unittest.mock import patch
import json
import threading
import urllib.error
import urllib.request
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from ai import CatAI, parse_intent
from pc_actions import PCActions

class Actions:
    def __init__(self): self.calls = []
    def describe_for_prompt(self): return 'test'
    def tool_definitions(self): return []
    def execute(self, name, args, confirmed=False):
        self.calls.append((name, args))
        return 'ok'

class Response:
    def __init__(self, data): self.data = data
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, size): return json.dumps(self.data).encode()

class ProviderTests(unittest.TestCase):
    def setUp(self):
        patcher = patch('ai.local_runtime.ensure_local_service')
        self.ensure_service = patcher.start()
        self.addCleanup(patcher.stop)

    def test_openai_fallback_and_action(self):
        actions = Actions()
        settings = {'ai_openai_key':'test-key', 'ai_backend':'openai'}
        ai = CatAI(settings.get, actions, which=lambda _: None)
        data = {'choices':[{'message':{'content':json.dumps({'reply':'Opening', 'actions':[{'name':'open_app','args':{'name':'valorant'}}]})}}]}
        with patch('ai._openai_urlopen', return_value=Response(data)) as call:
            result = ai.respond('Can you launch my game?')
        self.assertEqual(result.backend, 'OpenAI API')
        self.assertEqual(actions.calls, [('open_app', {'name':'valorant'})])
        self.assertEqual(call.call_args.args[0].full_url, 'https://api.openai.com/v1/chat/completions')

    def test_remote_custom_url_rejected_before_sending_key(self):
        actions = Actions()
        settings = {'ai_openai_key':'test-key', 'ai_openai_base_url':'https://example.com/v1', 'ai_backend':'openai'}
        ai = CatAI(settings.get, actions, which=lambda _: None)
        with patch('ai._openai_urlopen') as call:
            result = ai.respond('hi')
        call.assert_not_called()
        self.assertEqual(result.backend, 'Çevrimdışı')

    def test_parser(self):
        self.assertEqual(parse_intent('valorant\u0131u a\u00e7')[:2], ('open_app', {'name':'valorant'}))
        self.assertEqual(parse_intent("youtube'da tarkan \u015f\u0131mar\u0131k \u00e7al")[0], 'youtube_play')
        self.assertEqual(parse_intent('internetten hava durumunu ara\u015ft\u0131r')[0], 'web_research')
        self.assertEqual(parse_intent('youtubedan tarkan aç')[0], 'youtube_play')
        self.assertEqual(parse_intent('tarkan youtubeda ara aç')[0], 'youtube_play')
        self.assertEqual(parse_intent('takla at')[:2], ('cat_behavior', {'behavior': 'roll'}))

    def test_connection_check_never_runs_actions(self):
        actions = Actions()
        ai = CatAI({'ai_openai_key': 'test'}.get, actions, which=lambda _: None)
        with patch('ai._openai_urlopen', return_value=Response({'choices': [{'message': {'content': 'OK'}}]})):
            self.assertIn('başarılı', ai.check_connection())
        self.assertEqual(actions.calls, [])

    def test_research_followup_and_failed_followup(self):
        actions = Actions()
        actions.execute = lambda name, args, confirmed=False: 'Kaynak: https://example.com bilgi'
        ai = CatAI({'ai_openai_key': 'test', 'ai_backend': 'openai'}.get, actions, which=lambda _: None)
        first = {'choices': [{'message': {'content': json.dumps({'reply': 'Bakıyorum', 'actions': [{'name': 'web_research', 'args': {'query': 'test'}}]})}}]}
        second = {'choices': [{'message': {'content': 'Yanıt. https://example.com'}}]}
        with patch('ai._openai_urlopen', side_effect=[Response(first), Response(second)]) as call:
            result = ai._respond_openai('araştır')
        self.assertIn('Yanıt. https://example.com', result.reply)
        followup = json.loads(call.call_args.args[0].data)
        self.assertNotIn('tools', followup)
        self.assertIn('untrusted_sources', followup['messages'][1]['content'])
        with patch('ai._openai_urlopen', side_effect=[Response(first), OSError('down')]):
            result = ai._respond_openai('tekrar araştır')
        self.assertIn('https://example.com', result.reply)
        self.assertTrue(result.error)

    def test_malformed_action_rejected_before_any_execution(self):
        actions = Actions()
        ai = CatAI({'ai_openai_key': 'test', 'ai_backend': 'openai'}.get, actions, which=lambda _: None)
        first = {'choices': [{'message': {'content': json.dumps({'actions': [{'name': 'open_app', 'args': {}}, {'name': 'open_app', 'args': 'invalid'}]})}}]}
        with patch('ai._openai_urlopen', return_value=Response(first)):
            ai.respond('unrecognized input')
        self.assertEqual(actions.calls, [])

    def test_redirect_is_not_followed(self):
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length', '0')))
                seen.append(self.path)
                self.send_response(302)
                self.send_header('Location', '/stolen')
                self.send_header('Content-Length', '0')
                self.end_headers()
            def log_message(self, *args): pass
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            ai = CatAI({'ai_openai_base_url': f'http://127.0.0.1:{server.server_port}/v1', 'ai_backend': 'openai'}.get, Actions(), which=lambda _: None)
            self.assertIn('302', ai.check_connection())
            self.assertEqual(seen, ['/v1/chat/completions'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_auth_failure_is_reported(self):
        ai = CatAI({'ai_openai_key': 'test'}.get, Actions(), which=lambda _: None)
        error = urllib.error.HTTPError('https://api.openai.com', 401, 'unauthorized', {}, None)
        with patch('ai._openai_urlopen', side_effect=error):
            self.assertIn('401', ai.check_connection())

    def test_local_provider_uses_loopback_and_never_cloud_key(self):
        settings = {'ai_backend': 'local', 'ai_openai_key': 'secret-cloud-key'}
        ai = CatAI(settings.get, Actions(), which=lambda _: None)
        self.assertEqual(ai.available_backends(), ['local', 'offline'])
        response = {'choices': [{'message': {'content': json.dumps({'reply': 'Merhaba', 'actions': []})}}]}
        with patch('ai._openai_urlopen', return_value=Response(response)) as call:
            result = ai.respond('hello')
        request = call.call_args.args[0]
        self.assertEqual(request.full_url, 'http://127.0.0.1:11434/api/chat')
        body = json.loads(request.data)
        self.assertEqual(body['options']['num_ctx'], 8192)
        self.assertEqual(body['keep_alive'], '60s')
        self.assertIs(body['think'], False)
        self.assertEqual(request.get_header('Authorization'), 'Bearer local')
        self.assertEqual(json.loads(request.data)['model'], 'qwen2.5:7b')
        self.assertEqual(result.backend, 'Yerel model (Ollama)')
        with patch('ai._openai_urlopen', return_value=Response(response)):
            self.assertIn('Yerel model', ai.check_connection())

    def test_local_provider_rejects_remote_url(self):
        settings = {'ai_backend': 'local', 'ai_local_base_url': 'https://example.com/v1', 'ai_openai_key': 'secret'}
        ai = CatAI(settings.get, Actions(), which=lambda _: None)
        with patch('ai._openai_urlopen') as call:
            ai.respond('unrecognized input')
        call.assert_not_called()

    def test_local_provider_rejects_cloud_model_before_sending_prompt(self):
        settings = {'ai_backend': 'local', 'ai_local_model': 'qwen3:cloud'}
        ai = CatAI(settings.get, Actions(), which=lambda _: None)
        with patch('ai._openai_urlopen') as call:
            ai.respond('unrecognized input')
            self.assertIn('qwen2.5:7b', ai.check_connection())
        call.assert_not_called()
        self.ensure_service.assert_not_called()

    def test_known_command_runs_without_model_and_records_history(self):
        actions = Actions()
        ai = CatAI({'ai_backend': 'local'}.get, actions, which=lambda _: None)
        with patch('ai._openai_urlopen') as call:
            result = ai.respond('valorantıu aç')
        call.assert_not_called()
        self.ensure_service.assert_not_called()
        self.assertEqual(result.backend, 'Yerel komut')
        self.assertEqual(actions.calls, [('open_app', {'name': 'valorant'})])
        self.assertEqual(ai.transcript[-2][1], 'valorantıu aç')

    def test_dangerous_direct_action_still_needs_confirmation(self):
        ai = CatAI({'ai_backend': 'local'}.get, PCActions(), which=lambda _: None)
        with patch('ai._openai_urlopen') as call:
            result = ai.respond('bilgisayarı kapat')
        call.assert_not_called()
        self.assertTrue(result.needs_confirmation)
        self.assertEqual(result.backend, 'Yerel komut')

    def test_greeting_uses_model_and_game_play_is_not_cat(self):
        self.assertNotEqual((parse_intent('valorant oyna') or (None,))[0], 'cat_behavior')
        ai = CatAI({'ai_backend': 'local'}.get, Actions(), which=lambda _: None)
        response = {'choices': [{'message': {'content': json.dumps({'reply': 'Selam', 'actions': []})}}]}
        with patch('ai._openai_urlopen', return_value=Response(response)) as call:
            result = ai.respond('merhaba')
        call.assert_called_once()
        self.assertEqual(result.backend, 'Yerel model (Ollama)')
        self.ensure_service.assert_called_once()

    def test_cli_malformed_actions_do_not_execute_partial_list(self):
        actions = Actions()
        payload = {'result': json.dumps({'reply': '', 'actions': [
            {'name': 'open_app', 'args': {'name': 'valorant'}},
            {'name': 'open_app', 'args': 'invalid'}]})}
        runner = lambda *args: subprocess.CompletedProcess([], 0, json.dumps(payload), '')
        ai = CatAI({'ai_backend': 'cli'}.get, actions, which=lambda _: 'claude', cli_runner=runner)
        ai.respond('Can you launch my game?')
        self.assertEqual(actions.calls, [])

    def test_anthropic_disconnect_retains_pending_outcome(self):
        actions = Actions()
        actions.execute = lambda *args, **kwargs: 'Bekliyor: oyun henüz başlamadı.'
        ai = CatAI({'ai_api_key': 'test'}.get, actions, client_factory=lambda **kwargs: object(), which=lambda _: None)
        class Message:
            content = [{'type': 'tool_use', 'name': 'open_app', 'input': {'name': 'valorant'}, 'id': '1'}]
            stop_reason = 'tool_use'
        with patch.object(ai, '_create_message', side_effect=[Message(), OSError('disconnected')]):
            result = ai._respond_api('oyunu çalıştır')
        self.assertIn('Bekliyor:', result.reply)
        self.assertNotIn('onay bekliyorum', result.reply)

    def test_loopback_request_disables_environment_proxy(self):
        import ai as ai_module
        request = urllib.request.Request('http://127.0.0.1:11434/v1/chat/completions')
        with patch('ai.urllib.request.build_opener') as builder:
            ai_module._openai_urlopen(request)
        proxy = next(h for h in builder.call_args.args if isinstance(h, urllib.request.ProxyHandler))
        self.assertEqual(proxy.proxies, {})

    def test_url_read_is_direct_and_source_is_always_attached(self):
        actions = Actions()
        def read(name, args, confirmed=False):
            actions.calls.append((name, args))
            return 'Kaynak: https://www.python.org/downloads/\nPython 3.15.2'
        actions.execute = read
        ai = CatAI({'ai_backend': 'local'}.get, actions, which=lambda _: None)
        answer = {'choices': [{'message': {'content': 'Python 3.15.2'}}]}
        with patch('ai._openai_urlopen', return_value=Response(answer)) as call:
            result = ai.respond('https://www.python.org/downloads/ sayfasını oku ve sürümü söyle')
        self.assertEqual(actions.calls, [('web_read', {'url': 'https://www.python.org/downloads/'})])
        self.assertIn('https://www.python.org/downloads/', result.reply)
        self.assertEqual(call.call_count, 1)

    def test_intro_is_exact_and_remaining_question_goes_to_model(self):
        ai = CatAI({'ai_backend': 'local'}.get, Actions(), which=lambda _: None)
        answer = {'choices': [{'message': {'content': json.dumps({'reply': '4 eder.', 'actions': []})}}]}
        with patch('ai._openai_urlopen', return_value=Response(answer)):
            result = ai.respond('Kendini kısaca tanıt ve 2+2 kaç?')
        self.assertEqual(result.reply, 'Ben Kömür, masaüstündeki smokin kedinim. 4 eder.')

if __name__ == '__main__': unittest.main()


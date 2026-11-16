"""Read-only live smoke checks; no real PC actions or microphone recording."""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai import CatAI, BackendUnavailable
from pc_actions import PCActions
from settings import Settings
from activity_reactions import _SCRIPT
from voice import VoiceService


class SafeActions(PCActions):
    def __init__(self):
        super().__init__()
        self.logged = []

    def execute(self, name, args=None, confirmed=False):
        self.logged.append({'name': name, 'args': args, 'confirmed': confirmed})
        return 'Test eylemi kaydedildi; gerçek işlem yapılmadı.'


class OneRequestCat(CatAI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_count = 0

    def _openai_request(self, payload, local_provider=False):
        if self.request_count or not local_provider:
            raise BackendUnavailable('Smoke test permits one local request only')
        self.request_count += 1
        return super()._openai_request(payload, local_provider=True)


def main():
    actions = SafeActions()
    settings = Settings.load()
    def get(key, default=None):
        if key == 'ai_backend': return 'local'
        if key == 'ai_enabled': return True
        return settings.get(key, default)
    ai = OneRequestCat(get, actions)
    start = time.monotonic()
    response = ai.respond('Selam Kömür, bugün biraz yoruldum; iki laf edelim.')
    result = {'conversation': {'backend': response.backend, 'reply': response.reply,
                               'elapsed_seconds': round(time.monotonic() - start, 2),
                               'local_request_count': ai.request_count,
                               'status': 'ok' if response.backend == 'Yerel model (Ollama)' else 'unavailable',
                               'error': response.error, 'logged_actions': actions.logged,
                               'real_actions_executed': False}}
    try:
        media = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', _SCRIPT],
                               capture_output=True, text=True, timeout=10,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        output = media.stdout.strip()
        classification = output if output in ('none', 'music', 'video') else ('playing' if output.startswith('playing|') else 'unexpected')
        result['media'] = {'returncode': media.returncode, 'classification': classification}
    except (OSError, subprocess.SubprocessError) as exc:
        result['media'] = {'status': 'unavailable', 'error_type': type(exc).__name__}
    try:
        result['voice'] = VoiceService().status()
    except Exception as exc:
        result['voice'] = {'status': 'unavailable', 'error_type': type(exc).__name__}
    path = Path(__file__).resolve().parents[1] / 'live-v4-review.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

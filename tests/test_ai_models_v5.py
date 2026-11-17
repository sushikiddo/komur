"""v5 görev 1: güncel model adları, hızlı model, düşünme bloğu temizliği."""
from types import SimpleNamespace

from ai import CatAI, DEFAULT_MODEL, FAST_MODEL
from pc_actions import PCActions


def make(settings, calls=None, content=None):
    calls = calls if calls is not None else []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(content=content or [{"type": "text", "text": "Mrr."}], stop_reason="end_turn")
    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    return CatAI(settings.get, PCActions(), lambda: "test", client_factory=lambda **kw: client,
                 which=lambda _: None)


def test_default_and_legacy_model_upgrade():
    assert DEFAULT_MODEL == "claude-sonnet-5-5" and FAST_MODEL == "claude-haiku-5-5"
    assert make({}).model() == DEFAULT_MODEL
    assert make({"ai_model": "claude-sonnet-4-5"}).model() == DEFAULT_MODEL  # eski varsayılan


def test_user_chosen_model_is_untouched_and_fast_model_follows():
    ai = make({"ai_model": "claude-opus-5-5"})
    assert ai.model() == "claude-opus-5-5"
    assert ai.fast_model() == "claude-opus-5-5"
    assert make({}).fast_model() == FAST_MODEL


def test_request_uses_model_and_low_effort_without_sdk_param():
    calls = []
    ai = make({"ai_backend": "api", "ai_api_key": "k"}, calls)
    ai.respond("nasılsın bakalım uzun bir şey")
    assert calls[0]["model"] == "claude-sonnet-5-5"
    assert calls[0]["extra_body"] == {"output_config": {"effort": "low"}}
    assert "output_config" not in calls[0]


def test_comment_uses_haiku_by_default():
    calls = []
    ai = make({"ai_backend": "api", "ai_api_key": "k"}, calls)
    assert ai.comment_on_context({"category": "coding"}) == "Mrr."
    assert calls[0]["model"] == "claude-haiku-5-5"


def test_thinking_blocks_dropped_from_history_after_turn():
    content = [{"type": "thinking", "thinking": "", "signature": "x"}, {"type": "text", "text": "Selam"}]
    ai = make({"ai_backend": "api", "ai_api_key": "k"}, content=content)
    ai.respond("merhaba kömür nasılsın")
    assistant = [m for m in ai.history if m["role"] == "assistant"][-1]
    assert [b["type"] for b in assistant["content"]] == ["text"]

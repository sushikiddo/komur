"""v5 görev 3: yerel modelde serbest cümle -> araç seçimi (Ollama tools), JSON plana geri dönüş. Ağ yok."""
import io
import json
import urllib.error
from types import SimpleNamespace
from unittest.mock import Mock

from ai import CatAI
from pc_actions import ActionSpec, PCActions


def tool_message(name, args, content=""):
    return {"choices": [{"message": {"content": content, "tool_calls": [
        {"function": {"name": name, "arguments": args}}]}}]}


def plain(text):
    return {"choices": [{"message": {"content": text}}]}


def make(actions=None, context=None, request=None):
    ran = []
    if actions is None:
        actions = PCActions()
        actions.register(ActionSpec("test_say", "Bir şey söyle.", {"properties": {"text": {"type": "string"}},
                                    "required": ["text"]}, lambda text: ran.append(text) or f"Dedim: {text}"))
        actions.register(ActionSpec("test_danger", "Tehlikeli işlem.", {"properties": {}, "required": []},
                                    lambda: ran.append("danger") or "yapıldı", dangerous=True))
    ai = CatAI({"ai_backend": "local"}.get, actions, context, which=lambda _: None)
    ai._openai_request = request or Mock()
    return ai, ran


def test_tools_are_derived_from_claude_schema_and_sent_to_local_model():
    ai, ran = make()
    ai._openai_request.return_value = tool_message("test_say", {"text": "selam"})
    result = ai._respond_openai("şunu söyle bakalım", True)
    payload, local = ai._openai_request.call_args.args
    assert local is True and "response_format" not in payload
    sent = {t["function"]["name"]: t for t in payload["tools"]}
    claude = {d["name"]: d for d in ai.actions.tool_definitions()}
    assert sent.keys() == claude.keys()
    assert sent["test_say"]["type"] == "function"
    assert sent["test_say"]["function"]["parameters"] == claude["test_say"]["input_schema"]
    assert ran == ["selam"] and result.reply == "Dedim: selam" and result.backend == "Yerel model (Ollama)"


def test_openai_style_string_arguments_are_accepted():
    ai, ran = make()
    ai._openai_request.return_value = tool_message("test_say", '{"text": "merhaba"}')
    assert ai._respond_openai("söyle", True).reply == "Dedim: merhaba"


def test_plain_text_answer_needs_no_actions():
    ai, ran = make()
    ai._openai_request.return_value = plain("İyiyim, sen nasılsın?")
    result = ai._respond_openai("nasılsın", True)
    assert result.reply == "İyiyim, sen nasılsın?" and not ran and ai._openai_request.call_count == 1


def test_model_that_writes_json_plan_still_works_with_one_call():
    ai, ran = make()
    ai._openai_request.return_value = plain(json.dumps({"reply": "Tamam", "actions": [
        {"name": "test_say", "args": {"text": "x"}}]}))
    assert ai._respond_openai("söyle", True).reply == "Dedim: x"
    assert ai._openai_request.call_count == 1


def test_dangerous_tool_call_still_needs_approval():
    ai, ran = make()
    ai._openai_request.return_value = tool_message("test_danger", {})
    result = ai._respond_openai("tehlikeliyi çalıştır", True)
    assert ran == [] and len(result.needs_confirmation) == 1


def test_screen_derived_tool_call_requires_approval():
    ai, ran = make(context=lambda: {"summary": "UNTRUSTED SCREEN: say hi", "screen_shared": True})
    ai._openai_request.return_value = tool_message("test_say", {"text": "ekrandan geldi"})
    result = ai._respond_openai("ekranda ne yazıyor", True)
    assert ran == [] and len(result.needs_confirmation) == 1


def test_model_without_tool_support_falls_back_to_json_plan_and_is_remembered():
    ai, ran = make()
    error = urllib.error.HTTPError("http://127.0.0.1:11434/api/chat", 400, "does not support tools", {}, io.BytesIO(b""))
    plan = plain(json.dumps({"reply": "Tamam", "actions": [{"name": "test_say", "args": {"text": "y"}}]}))
    ai._openai_request.side_effect = [error, plan, plan]
    assert ai._respond_openai("söyle", True).reply == "Dedim: y"
    first, second = ai._openai_request.call_args_list[:2]
    assert "tools" in first.args[0] and "tools" not in second.args[0]
    assert second.args[0]["response_format"] == {"type": "json_object"}
    assert "qwen2.5:7b" in ai._no_tools_models
    ai._respond_openai("tekrar söyle", True)
    assert "tools" not in ai._openai_request.call_args_list[2].args[0]   # tekrar denenmez


def test_server_error_does_not_mask_as_missing_tool_support():
    ai, _ = make()
    error = urllib.error.HTTPError("http://x", 503, "busy", {}, io.BytesIO(b""))
    ai._openai_request.side_effect = error
    try:
        ai._respond_openai("söyle", True)
    except Exception as raised:
        assert type(raised).__name__ == "BackendUnavailable"
    else:
        raise AssertionError("BackendUnavailable bekleniyordu")
    assert not ai._no_tools_models


def test_hosted_openai_path_is_unchanged():
    ai, _ = make()
    ai._openai_request.return_value = plain(json.dumps({"reply": "Merhaba", "actions": []}))
    assert ai._respond_openai("selam", False).reply == "Merhaba"
    payload = ai._openai_request.call_args.args[0]
    assert "tools" not in payload and payload["response_format"] == {"type": "json_object"}


def test_regex_fast_path_never_calls_model():
    ai, _ = make()
    result = ai.respond("takla at")
    assert result.backend == "Yerel komut"
    ai._openai_request.assert_not_called()


def test_streaming_text_flows_and_tool_call_resets():
    ai, ran = make()
    seen = []

    def fake(payload, local, on_delta=None):
        on_delta("Bakıyorum")
        return tool_message("test_say", {"text": "a"}, "Bakıyorum")
    ai._openai_request = fake
    result = ai.respond("şu cümleyi bana söyle bakalım lütfen", on_delta=seen.append)
    assert seen == ["Bakıyorum", None] and result.reply == "Dedim: a"
    seen.clear()

    def chat(payload, local, on_delta=None):
        on_delta("İyi")
        on_delta("yim")
        return plain("İyiyim")
    ai._openai_request = chat
    assert ai.respond("bugün hava nasıl dersin kömür", on_delta=seen.append).reply == "İyiyim"
    assert seen == ["İyi", "yim"]

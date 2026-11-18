"""v5 görev 2: akıcı yanıt (Claude akışı, Ollama/OpenAI akışı, arayüz kuyruğu). Ağ yok, hepsi sahte."""
import json
import queue
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ai import CatAI


class Actions:
    def __init__(self):
        self.calls = []

    def describe_for_prompt(self):
        return "test"

    def tool_definitions(self):
        return []

    def execute(self, name, args, confirmed=False):
        self.calls.append((name, args))
        return "ok"


class FakeStream:
    def __init__(self, events, final):
        self.events, self.final = events, final

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __iter__(self):
        return iter(self.events)

    def get_final_message(self):
        return self.final


def text_event(text):
    return SimpleNamespace(type="text", text=text)


def claude_ai(streams, actions=None):
    queue_ = list(streams)

    def stream(**kwargs):
        return FakeStream(*queue_.pop(0))

    def create(**kwargs):
        raise AssertionError("akış açıkken create çağrılmamalı")
    client = SimpleNamespace(messages=SimpleNamespace(stream=stream, create=create))
    return CatAI({"ai_backend": "api", "ai_api_key": "k"}.get, actions or Actions(), lambda: "test",
                 client_factory=lambda **kw: client, which=lambda _: None)


def test_claude_stream_forwards_text_and_keeps_final_reply():
    final = SimpleNamespace(content=[{"type": "text", "text": "Merhaba dostum"}], stop_reason="end_turn")
    ai = claude_ai([([text_event("Merhaba "), text_event("dostum")], final)])
    pieces = []
    result = ai.respond("selam kömür nasılsın bugün", on_delta=pieces.append)
    assert pieces == ["Merhaba ", "dostum"]
    assert result.reply == "Merhaba dostum"


def test_claude_stream_goes_silent_and_resets_on_tool_use():
    tool_start = SimpleNamespace(type="content_block_start", content_block=SimpleNamespace(type="tool_use"))
    first = SimpleNamespace(content=[{"type": "tool_use", "id": "1", "name": "open_app", "input": {"name": "notepad"}}],
                            stop_reason="tool_use")
    second = SimpleNamespace(content=[{"type": "text", "text": "Açtım"}], stop_reason="end_turn")
    actions = Actions()
    ai = claude_ai([([text_event("Bakayım"), tool_start], first), ([text_event("Açtım")], second)], actions)
    pieces = []
    result = ai.respond("bana bir yazı düzenleyici hazırlar mısın", on_delta=pieces.append)
    assert pieces == ["Bakayım", None]              # araç başlayınca sıfırlandı, sonrası akmadı
    assert actions.calls == [("open_app", {"name": "notepad"})]
    assert result.reply == "ok"                      # kesin yanıt araç sonucu; "tamamlandı" uydurulmaz


def test_callback_error_does_not_break_reply():
    final = SimpleNamespace(content=[{"type": "text", "text": "Tamam"}], stop_reason="end_turn")
    ai = claude_ai([([text_event("Tamam")], final)])

    def broken(piece):
        raise RuntimeError("ui")
    assert ai.respond("selam kömür nasılsın bugün", on_delta=broken).reply == "Tamam"


class LineResponse:
    def __init__(self, lines):
        self.lines = [line if isinstance(line, bytes) else line.encode("utf-8") for line in lines]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def readline(self):
        return self.lines.pop(0) if self.lines else b""


def local_ai(base=None):
    settings = {"ai_backend": "local"}
    if base:
        settings["ai_local_base_url"] = base
    return CatAI(settings.get, Actions(), which=lambda _: None)


def test_ollama_native_stream_is_aggregated():
    lines = [json.dumps({"message": {"content": "Mer"}, "done": False}) + "\n",
             json.dumps({"message": {"content": "haba"}, "done": False}) + "\n",
             json.dumps({"message": {"content": "", "tool_calls": [
                 {"function": {"name": "open_app", "arguments": {"name": "spotify"}}}]}, "done": True}) + "\n"]
    pieces = []
    with patch("ai.local_runtime.ensure_local_service"), \
            patch("ai._openai_urlopen", return_value=LineResponse(lines)) as call:
        data = local_ai()._openai_request({"model": "qwen2.5:7b", "messages": [], "tools": [{"type": "function"}]},
                                          True, on_delta=pieces.append)
    sent = json.loads(call.call_args.args[0].data)
    assert sent["stream"] is True and sent["tools"] == [{"type": "function"}]
    assert pieces == ["Mer", "haba"]
    message = data["choices"][0]["message"]
    assert message["content"] == "Merhaba"
    assert message["tool_calls"][0]["function"] == {"name": "open_app", "arguments": {"name": "spotify"}}


def test_openai_compatible_sse_stream_is_aggregated():
    def sse(delta):
        return "data: " + json.dumps({"choices": [{"delta": delta}]}) + "\n\n"
    lines = [sse({"content": "Se"}), sse({"content": "lam"}),
             sse({"tool_calls": [{"index": 0, "function": {"name": "open_app", "arguments": '{"na'}}]}),
             sse({"tool_calls": [{"index": 0, "function": {"arguments": 'me":"x"}'}}]}), "data: [DONE]\n"]
    pieces = []
    with patch("ai.local_runtime.ensure_local_service"), \
            patch("ai._openai_urlopen", return_value=LineResponse(lines)) as call:
        data = local_ai("http://127.0.0.1:9999/v1")._openai_request(
            {"model": "qwen2.5:7b", "messages": []}, True, on_delta=pieces.append)
    assert call.call_args.args[0].full_url == "http://127.0.0.1:9999/v1/chat/completions"
    assert json.loads(call.call_args.args[0].data)["stream"] is True
    assert pieces == ["Se", "lam"]
    message = data["choices"][0]["message"]
    assert message["content"] == "Selam"
    assert message["tool_calls"][0]["function"] == {"name": "open_app", "arguments": '{"name":"x"}'}


def test_stream_size_is_capped():
    big = b"x" * (1024 * 1024 + 1)
    with patch("ai.local_runtime.ensure_local_service"), \
            patch("ai._openai_urlopen", return_value=LineResponse([big])):
        with pytest.raises(ValueError):
            local_ai()._openai_request({"model": "qwen2.5:7b", "messages": []}, True, on_delta=lambda p: None)


def test_delta_sink_never_leaks_json_plans():
    ai = CatAI({}.get, Actions())
    got = []
    ai._on_delta = got.append
    sink = ai._delta_sink()
    for piece in ('  {"re', 'ply": "x"}'):
        sink(piece)
    assert got == []
    plain = []
    ai._on_delta = plain.append
    sink = ai._delta_sink()
    for piece in (" ", "Merhaba", " dünya"):
        sink(piece)
    assert "".join(plain) == " Merhaba dünya"


def test_local_summary_streams_plain_text():
    ai = local_ai()
    lines = [json.dumps({"message": {"content": "Özet"}, "done": True}) + "\n"]
    pieces = []
    ai._on_delta = pieces.append
    with patch("ai.local_runtime.ensure_local_service"), \
            patch("ai._openai_urlopen", return_value=LineResponse(lines)):
        assert ai._summarize_research("soru", ["Kaynak: https://a.example metin"], True) == \
            "Özet\nKaynak: https://a.example"
    assert pieces == ["Özet"]


def test_ui_drains_only_current_request_and_resets():
    from assistant_ui import AssistantUI
    ui = object.__new__(AssistantUI)
    ui.delta_events = queue.Queue()
    ui._stream_id, ui._partial, ui._cancel_requested, ui.closed = 2, "", False, False
    shown = []
    ui.compact = SimpleNamespace(set_partial=shown.append)
    for item in ((1, "eski"), (2, "Mer"), (2, "haba"), (2, None), (2, "Yeni")):
        ui.delta_events.put(item)
    ui.drain_deltas()
    assert ui._partial == "Yeni" and shown == ["Yeni"]
    ui._cancel_requested = True
    ui.delta_events.put((2, " iptal"))
    ui.drain_deltas()
    assert ui._partial == "Yeni"
    ui.clear_partial()
    assert ui._partial == "" and shown[-1] == ""


def test_bubble_shows_partial_without_touching_chat_log():
    from chat_bubble import ChatBubble
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable: {exc}")
    root.withdraw()
    assistant = SimpleNamespace(
        app=SimpleNamespace(root=root, brain=SimpleNamespace(x=300, y=300), w=140, h=150,
                            settings=SimpleNamespace(get=lambda key: False)),
        chat_log=[("Sen", "Merhaba")], listening=False, show_history=lambda: None,
        toggle_listening=lambda: None, share_screen=lambda: None, share_clipboard=lambda: None, set_voice_enabled=lambda v: None,
        send_text=lambda v: True)
    chat = ChatBubble(assistant)
    try:
        chat.show()
        chat.set_partial("Merhaba, ben")
        content = chat.messages.get("1.0", "end")
        assert "Kömür: Merhaba, ben" in content
        assert assistant.chat_log == [("Sen", "Merhaba")]
        chat.set_partial("")
        assert "Merhaba, ben" not in chat.messages.get("1.0", "end")
    finally:
        chat.destroy()
        root.destroy()

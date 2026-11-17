"""OpenAI uyumlu / Ollama yerel sohbet çağrılarının tel biçimi: istek gövdesi ve akış okuma.

Ağ erişimi yok: urlopen ve zaman aşımı ai.py'de kalır (testler ai._openai_urlopen'u yamalar).
"""
from __future__ import annotations

import json
import threading
from typing import Callable


def chat_payload(payload: dict, native: bool, streaming: bool) -> dict:
    """Ollama yerel (/api/chat) ya da OpenAI uyumlu gövdeyi hazırlar."""
    if native:
        options = {"num_ctx": 8192, "num_predict": payload.get("max_tokens", 600),
                   "temperature": payload.get("temperature", 0.2)}
        return {"model": payload["model"], "messages": payload["messages"], "stream": streaming,
                "options": options, "keep_alive": "60s", "think": False,
                **({"format": "json"} if payload.get("response_format") else {}),
                **({"tools": payload["tools"]} if payload.get("tools") else {})}
    if streaming:
        return {**payload, "stream": True}
    return payload


def read_stream(response, native: bool, on_delta: Callable[[str], None], cancelled: threading.Event) -> dict:
    """Ollama (satır başına JSON) ve OpenAI uyumlu (SSE) akışını tek ``choices[0].message`` yanıtında toplar."""
    pieces: list[str] = []
    calls: dict[int, dict] = {}
    total = 0
    for raw in iter(response.readline, b""):
        total += len(raw)
        if total > 1024 * 1024:
            raise ValueError("stream too large")
        if cancelled.is_set():
            break
        line = raw.decode("utf-8", "replace").strip()
        if not native:
            if not line.startswith("data:"):
                continue
            line = line[5:].strip()
            if line == "[DONE]":
                break
        if not line:
            continue
        try:
            chunk = json.loads(line)
        except ValueError:
            continue
        if native:
            message = chunk.get("message") or {}
            for call in message.get("tool_calls") or []:
                function = call.get("function") or {}
                calls[len(calls)] = {"name": function.get("name"), "arguments": function.get("arguments")}
        else:
            message = ((chunk.get("choices") or [{}])[0]).get("delta") or {}
            for call in message.get("tool_calls") or []:
                slot = calls.setdefault(call.get("index", 0), {"name": "", "arguments": ""})
                function = call.get("function") or {}
                slot["name"] = function.get("name") or slot["name"]
                slot["arguments"] += function.get("arguments") or ""
        piece = message.get("content") or ""
        if piece:
            pieces.append(piece)
            on_delta(piece)
        if native and chunk.get("done"):
            break
    message = {"content": "".join(pieces)}
    if calls:
        message["tool_calls"] = [{"function": c} for c in calls.values()]
    return {"choices": [{"message": message}]}

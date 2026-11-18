from types import SimpleNamespace

from screen_vision import MAX_CONTEXT, build_request, classify, error_lines, locations, offline_summary

TRACE = '''Traceback (most recent call last):
  File "C:\\app\\main.py", line 12, in <module>
    run()
  File "C:\\app\\core.py", line 40, in run
    return 1 / 0
ZeroDivisionError: division by zero'''


def test_classify_error_code_text_empty():
    assert classify(TRACE) == "error"
    assert classify("def f(x):\n    return x\nclass A:\n    pass") == "code"
    assert classify("Bugün hava güzel.") == "text"
    assert classify("  \n") == "empty"


def test_error_lines_and_locations_pick_the_real_failure():
    assert error_lines(TRACE)[-1] == "ZeroDivisionError: division by zero"
    assert locations(TRACE)[-1] == "C:\\app\\core.py:40"
    assert locations("src/app.ts:17:5 - error TS2322: x") == ["src/app.ts:17"]


def test_build_request_bounds_context_and_keeps_errors():
    question, context, kind = build_request("x" * (MAX_CONTEXT * 2) + "\n" + TRACE)
    assert kind == "error" and "çözüm" in question
    assert context.startswith("Öne çıkan hata satırları:")
    assert "ZeroDivisionError" in context.split("Kaynak: pano")[0]
    assert len(context) < MAX_CONTEXT + 400
    assert build_request("") == (None, None, "empty")


def test_offline_summary_and_ai_fallback(monkeypatch):
    assert "core.py:40" in offline_summary(TRACE)
    from ai import CatAI
    fake = SimpleNamespace(available_backends=lambda: ["offline"], _remember=lambda *a: None)
    result = CatAI.explain_screen(fake, "soru", TRACE)
    assert result.backend == "Yerel komut" and "ZeroDivisionError" in result.reply

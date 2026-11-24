"""Focused checks for the small chat bubble contract."""
from pathlib import Path
import sys
from types import SimpleNamespace
import tkinter as tk

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat_bubble import ChatBubble


def make_bubble():
    root = tk.Tk()
    root.withdraw()
    calls = []
    assistant = SimpleNamespace(
        app=SimpleNamespace(root=root, brain=SimpleNamespace(x=300, y=300), w=140, h=150,
                            settings=SimpleNamespace(get=lambda key: False)),
        chat_log=[("Sen", "Merhaba"), ("Kömür", "Selam")],
        show_history=lambda: calls.append("history"),
        send_text=lambda value: calls.append(("send", value)) or True)
    return root, assistant, calls, ChatBubble(assistant)


def test_compact_size_recent_chat_and_send():
    try:
        root, assistant, calls, chat = make_bubble()
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable: {exc}")
    try:
        assert chat.WIDTH <= 300 and chat.HEIGHT <= 230
        chat.refresh()
        content = chat.messages.get("1.0", "end")
        assert "Sen: Merhaba" in content and "Kömür: Selam" in content
        chat.entry.insert(0, "  test  ")
        chat.send()
        assert ("send", "test") in calls
        assert chat.entry.get() == ""
        chat.hide()
        assert not chat.visible
    finally:
        chat.destroy()
        root.destroy()


def test_busy_and_empty_send_keep_expected_state():
    try:
        root, assistant, calls, chat = make_bubble()
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable: {exc}")
    try:
        chat.set_busy(True)
        assert str(chat.send_button["state"]) == "disabled"
        chat.set_busy(False)
        assert str(chat.send_button["state"]) == "normal"
        chat.send()
        assert not any(isinstance(call, tuple) and call[0] == "send" for call in calls)
    finally:
        chat.destroy()
        root.destroy()


def test_compact_bubble_does_not_chase_cat_and_drags():
    try:
        root, assistant, calls, chat = make_bubble()
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable: {exc}")
    try:
        assert chat.WIDTH <= 260 and chat.HEIGHT <= 180
        chat.show()
        first = chat._placed_at
        assistant.app.brain.x += 120          # yakın: peşinden gitme
        chat.update_position()
        assert chat._placed_at == first
        assistant.app.brain.x += 900          # uzak: yeniden konumlan
        chat.update_position()
        assert chat._placed_at != first
        chat.window.update()                  # macOS: geometry() boşta uygulanır; winfo_x güncellensin
        chat._drag_start(SimpleNamespace(x_root=chat.window.winfo_x() + 5, y_root=chat.window.winfo_y() + 5))
        chat._drag_move(SimpleNamespace(x_root=chat.window.winfo_x() + 45, y_root=chat.window.winfo_y() + 25))
        moved = chat._placed_at
        chat.update_position()                # sürüklenen konum korunur
        assert chat._placed_at == moved
    finally:
        chat.destroy()
        root.destroy()

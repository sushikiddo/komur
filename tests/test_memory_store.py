from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from memory_store import MemoryStore


def test_history_and_notes_survive_reopen(tmp_path):
    path = tmp_path / "memory.sqlite3"
    store = MemoryStore(path)
    store.add_message("user", "Merhaba")
    store.add_message("assistant", "Selam")
    store.remember("Çayı seviyorum")
    reopened = MemoryStore(path)
    assert [(x["role"], x["content"]) for x in reopened.messages()] == [
        ("user", "Merhaba"), ("assistant", "Selam")]
    assert reopened.notes()[0]["content"] == "Çayı seviyorum"


def test_concurrent_thread_writes(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    def write(i):
        store.add_message("user", f"message-{i}")
        store.remember(f"note-{i}")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, range(40)))
    assert len(store.messages()) == 40
    assert len(store.notes()) == 40


def test_reminders_survive_restart_and_completion(tmp_path):
    path = tmp_path / "memory.sqlite3"
    reminder_id = MemoryStore(path).add_reminder("İlaç", 123456.0)
    reopened = MemoryStore(path)
    assert reopened.pending_reminders()[0]["id"] == reminder_id
    reopened.complete_reminder(reminder_id)
    assert MemoryStore(path).pending_reminders() == []


def test_clear_removes_conversation_and_notes_but_preserves_reminders(tmp_path):
    path = tmp_path / "memory.sqlite3"
    store = MemoryStore(path)
    store.add_message("user", "gizli konuşma")
    store.remember("gizli not")
    store.add_reminder("hatırlat", 42)
    store.clear_conversation()
    reopened = MemoryStore(path)
    assert reopened.messages() == []
    assert reopened.notes() == []
    assert reopened.pending_reminders()[0]["label"] == "hatırlat"


def test_secrets_redacted_and_sql_input_is_literal(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    secret = "sk-abcdefghijklmnop"
    injection = "'); DROP TABLE messages; --"
    store.add_message("user", f"{secret} {injection}")
    store.remember(f"password=supersecret {injection}")
    store.add_reminder(f"Bearer abcdefghijklmnop {injection}", 1)
    assert secret not in store.messages()[0]["content"]
    assert "supersecret" not in store.notes()[0]["content"]
    assert "abcdefghijklmnop" not in store.pending_reminders()[0]["label"]
    assert store.messages(query=injection)
    assert store.notes(query=injection)
    store.add_message("assistant", "still intact")
    assert len(store.messages()) == 2


def test_corrupt_database_fails_explicitly(tmp_path):
    path = tmp_path / "memory.sqlite3"
    path.write_bytes(b"not a sqlite database")
    with pytest.raises(sqlite3.DatabaseError):
        MemoryStore(path)
    assert path.read_bytes() == b"not a sqlite database"

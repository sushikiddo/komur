import json
import sqlite3
from unittest.mock import Mock

import pytest

from ai import CatAI, parse_intent, parse_action_plan
from pc_actions import PCActions, ActionSpec, PendingAction
from memory_store import MemoryStore


@pytest.mark.parametrize('text,name,game', [
    ('lolü aç', 'launch_game', 'lol'),
    ("LoL'ü aç", 'launch_game', 'lol'),
    ('steami açıp cs yi başlat', 'launch_game', 'cs'),
    ('Steam’den Counter Strike indir', 'install_game', 'counter strike'),
    ('Steamden Stardew Valley indir', 'install_game', 'stardew valley'),
    ('cs oyna', 'launch_game', 'cs'),
    ('Steam açıp CS2 aç', 'launch_game', 'cs2'),
    ('Steam’den CS2’yi indir', 'install_game', 'cs2'),
])
def test_game_commands(text, name, game):
    assert parse_intent(text)[:2] == (name, {'game': game})


def test_plan_never_splits_note_content():
    assert parse_action_plan('not al: önce çalış sonra dinlen') is None
    assert len(parse_action_plan('not defterini aç sonra sesi yüzde 30 yap')) == 2
    assert parse_intent('not al: steam aç')[0] == 'create_note'
    plan = parse_action_plan('hesap makinesi aç; 5 dakika sonra su içmeyi hatırlat')
    assert [step['name'] for step in plan] == ['open_app', 'set_timer']


def actions_with_log(first='Tamam', dangerous=False):
    calls = []
    actions = PCActions()
    actions.register(ActionSpec('first', '', {'properties': {}}, lambda: calls.append('first') or first, dangerous=dangerous))
    actions.register(ActionSpec('second', '', {'properties': {}}, lambda: calls.append('second') or 'Tamam'))
    return actions, calls


def test_plan_suspends_at_confirmation_and_resumes_once():
    actions, calls = actions_with_log(dangerous=True)
    ai = CatAI({'ai_backend': 'offline'}.get, actions)
    result = ai.execute_plan([{'name': 'first'}, {'name': 'second'}])
    assert not calls and result.needs_confirmation
    result = ai.confirm_and_continue(result.needs_confirmation[0], result.remaining_actions)
    assert calls == ['first', 'second']


@pytest.mark.parametrize('outcome', ['Olmadı: bulunamadı', 'Bekliyor: sonuç doğrulanmadı'])
def test_plan_stops_after_failed_or_pending_step(outcome):
    actions, calls = actions_with_log(outcome)
    result = CatAI({}.get, actions).execute_plan([{'name': 'first'}, {'name': 'second'}])
    assert calls == ['first']
    assert 'kalan adımları' in result.reply


def test_model_plan_suspends_at_approval():
    actions, calls = actions_with_log(dangerous=True)
    ai = CatAI({'ai_backend': 'local'}.get, actions)
    ai._openai_request = Mock(return_value={'choices': [{'message': {'content': json.dumps({
        'reply': 'Yapıyorum', 'actions': [{'name': 'first'}, {'name': 'second'}]})}}]})
    result = ai._respond_openai('İki işi yap', True)
    assert not calls
    assert result.remaining_actions == [{'name': 'second'}]


def test_memory_edit_backup_are_transactional_and_redacted(tmp_path):
    memory = MemoryStore(tmp_path / 'original.sqlite3')
    memory.remember('Eski not')
    row = memory.notes()[0]
    memory.update_note(row['id'], 'şifre=secret yeni not')
    assert 'secret' not in memory.context()
    memory.backup(tmp_path / 'backup.sqlite3')
    backup = MemoryStore(tmp_path / 'backup.sqlite3')
    assert backup.notes() == memory.notes()
    with pytest.raises(ValueError):
        memory.backup(memory.path)


def test_recurring_reminder_reschedules_without_replaying_missed_intervals(tmp_path, monkeypatch):
    import memory_store
    store = MemoryStore(tmp_path / 'repeat.sqlite3')
    monkeypatch.setattr(memory_store.time, 'time', lambda: 1000)
    reminder = store.add_reminder('Mola', 100, repeat_seconds=60)
    assert store.complete_reminder(reminder) == 1060
    assert store.pending_reminders()[0]['due'] == 1060
    store.cancel_reminder(reminder)
    assert not store.pending_reminders()


def test_recurring_command_and_cancel():
    assert parse_intent('her 30 dakikada bir mola hatırlat')[:2] == (
        'recurring_reminder', {'minutes': 30, 'label': 'mola'})
    assert parse_intent('hatırlatıcı 2 iptal et')[:2] == ('cancel_reminder', {'reminder_id': 2})


def test_cancellation_prevents_next_action():
    actions, calls = actions_with_log()
    ai = CatAI({}.get, actions)
    ai.cancelled.set()
    ai.execute_plan([{'name': 'first'}, {'name': 'second'}])
    assert not calls

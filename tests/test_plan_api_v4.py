"""Offline proof of execution boundaries across API plans and confirmations."""
from types import SimpleNamespace

import pytest

from ai import CatAI
from pc_actions import ActionSpec, PCActions, PendingAction, is_pending
from screen_assist import ScreenAssist


@pytest.mark.parametrize('boundary', ['pending', 'failure', 'confirmation'])
def test_anthropic_stops_and_pairs_every_tool_id(boundary):
    executed, requests = [], []
    actions = PCActions()
    outcome = {'pending': 'Bekliyor: sonuç doğrulanmadı',
               'failure': 'Olmadı: uygulama bulunamadı', 'confirmation': 'Tamam'}[boundary]
    actions.register(ActionSpec('first', '', {'properties': {}},
                               lambda: executed.append('first') or outcome,
                               dangerous=boundary == 'confirmation'))
    for name in ('second', 'third'):
        actions.register(ActionSpec(name, '', {'properties': {}},
                                   lambda name=name: executed.append(name) or 'Tamam'))
    blocks = [{'type': 'tool_use', 'id': 'id-' + name, 'name': name, 'input': {}}
              for name in ('first', 'second', 'third')]

    def create(**kwargs):
        requests.append(kwargs)
        assert len(requests) == 1, 'A blocked plan must not request another model turn'
        return SimpleNamespace(content=blocks, stop_reason='tool_use')

    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    ai = CatAI({'ai_api_key': 'test'}.get, actions,
               client_factory=lambda **kwargs: client)
    result = ai._respond_api('Run the requested steps in order')

    assert len(requests) == 1
    assert not result.error
    assert executed == ([] if boundary == 'confirmation' else ['first'])
    paired = ai.history[-1]['content']
    assert [row['tool_use_id'] for row in paired] == [block['id'] for block in blocks]
    assert all(row['type'] == 'tool_result' for row in paired)
    assert all(row.get('is_error') for row in paired[1:])
    assert not result.actions_done
    if boundary == 'confirmation':
        assert [pending.name for pending in result.needs_confirmation] == ['first']
        assert result.remaining_actions == [{'name': 'second', 'args': {}},
                                            {'name': 'third', 'args': {}}]
        resumed = ai.confirm_and_continue(result.needs_confirmation[0], result.remaining_actions)
        assert executed == ['first', 'second', 'third']
        assert not resumed.needs_confirmation
    else:
        assert not result.needs_confirmation
        assert not result.remaining_actions
        assert paired[0].get('is_error', False) == (boundary == 'failure')


@pytest.mark.parametrize('continue_plan', [False, True])
def test_cancelled_confirmation_never_executes(continue_plan):
    executed = []
    actions = PCActions()
    for name in ('first', 'second'):
        actions.register(ActionSpec(name, '', {'properties': {}},
                                   lambda name=name: executed.append(name) or 'Tamam',
                                   dangerous=name == 'first'))
    ai = CatAI({}.get, actions)
    pending = actions.execute('first', {})
    assert isinstance(pending, PendingAction)
    ai.cancelled.set()
    result = (ai.confirm_and_continue(pending, [{'name': 'second'}]).reply
              if continue_plan else ai.confirm(pending))
    assert 'durduruldu' in result
    assert executed == []


@pytest.mark.parametrize('observation', ['unchanged', 'controls_changed', 'window_changed'])
def test_unverified_screen_click_does_not_continue(monkeypatch, observation):
    window = {'hwnd': 1, 'pid': 2, 'title': 'Editor'}
    control = {'id': 'save', 'label': 'Save', 'enabled': True, 'invokable': True,
               'automation_id': 'save', 'type': 'ControlType.Button'}
    calls = []

    def backend(mode, target, **kwargs):
        calls.append(mode)
        return {'controls': [] if observation == 'controls_changed' else [control]}

    screen = ScreenAssist(clock=lambda: 1, backend=backend)
    screen._snapshots['snapshot'] = (0, dict(window, controls=[control]))

    def current_window(hwnd):
        return dict(window, title='Saved') if observation == 'window_changed' and calls else window

    monkeypatch.setattr(screen, '_window', current_window)
    actions = PCActions()
    actions.register(ActionSpec('screen_click', '', {'properties': {}},
                               lambda: screen.click('snapshot', 'Save', confirmed=True), dangerous=True))
    actions.register(ActionSpec('second', '', {'properties': {}},
                               lambda: calls.append('second') or 'Tamam'))
    ai = CatAI({}.get, actions)
    pending = actions.execute('screen_click', {})
    result = ai.confirm_and_continue(pending, [{'name': 'second'}])
    assert is_pending(result.reply)
    assert calls.count('click') == 1
    assert 'second' not in calls
    assert not result.actions_done
    assert not screen._snapshots

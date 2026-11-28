import json
import os
from types import SimpleNamespace

import pytest

import companion
import settings as settings_mod
from desktop_toys import YarnPhysics
from settings import Settings


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return settings_mod.config_path()


def test_save_atomic_no_temp_left(cfg):
    s = Settings()
    s.set("name", "Pamuk")
    assert json.loads(cfg.read_text(encoding="utf-8"))["name"] == "Pamuk"
    assert [p.name for p in cfg.parent.iterdir()] == [cfg.name]


def test_failed_replace_keeps_old_file(cfg, monkeypatch):
    Settings().set("name", "Eski")
    def boom(*a, **k):
        raise OSError("disk")
    monkeypatch.setattr(settings_mod.os, "replace", boom)
    Settings().set("name", "Yeni")
    assert json.loads(cfg.read_text(encoding="utf-8"))["name"] == "Eski"
    assert [p.name for p in cfg.parent.iterdir()] == [cfg.name]


def test_wrong_types_fall_back_to_defaults():
    s = Settings({"effects_density": "high", "sound": "yes", "opacity": 55,
                  "x": 120, "accessories": "bad", "age_days": 3})
    assert s.get("effects_density") == 2
    assert s.get("sound") is True
    assert s.get("opacity") == 55
    assert s.get("x") == 120
    assert s.get("accessories") == {}
    assert s.get("age_days") == 3


def _cat(x, state="sit", change=False):
    brain = SimpleNamespace(x=x, y=0, width=100, height=100, state=state, facing=1, energy=20.0)
    if change:
        brain.calls = []
        def _change(st, duration=None):
            brain.calls.append(st)
            brain.state = st
        brain._change = _change
    return SimpleNamespace(brain=brain, w=100, h=100, social_state=None, social_partner=None)


def test_primary_cat_not_overridden():
    a, user = _cat(0), _cat(40, state="dance")
    assert companion.apply_social_interaction(a, user, interaction="cuddle_sleep", passive_b=True) == "cuddle_sleep"
    assert user.brain.state == "dance"
    assert user.brain.x == 40 and user.brain.facing == 1
    assert not hasattr(user.brain, "emote")
    assert a.brain.state == "sleep"


def test_interaction_does_not_retrigger_each_frame():
    a, b = _cat(0, change=True), _cat(40, change=True)
    for _ in range(5):
        companion.apply_social_interaction(a, b, interaction="mutual_groom")
    assert a.brain.calls == ["groom"] and b.brain.calls == ["groom"]


def test_yarn_wakes_when_platform_gone():
    area = (0, 0, 500, 500)
    plat = [(0, 300, 500)]
    y = YarnPhysics(100, 100)
    for _ in range(600):
        y.step(1 / 60, area, plat)
    assert y.resting and abs(y.y + y.r - 300) < 2
    assert y.step(1 / 60, area, plat) is False
    y.step(1 / 60, area, [])
    assert not y.resting
    for _ in range(600):
        y.step(1 / 60, area, [])
    assert abs(y.y + y.r - 500) < 2


def _app(**cfg):
    from costumes import normalize_accessories  # noqa: F401
    st = Settings({**cfg})
    st.save = lambda: None
    return SimpleNamespace(settings=st, renderer=SimpleNamespace(accessory=None))


def test_set_accessory_updates_slots_and_keeps_others():
    import settings_ui
    from costumes import slot_for
    app = _app(accessories={"neck": "scarf", "eyes": "glasses"}, accessory="scarf")
    ui = SimpleNamespace(app=app)
    settings_ui.set_accessory(ui, settings_ui.ACCESSORY_LABELS["hat"])
    slots = app.settings.get("accessories")
    assert slots.get(slot_for("hat")) == "hat"
    assert slots.get("eyes") == "glasses"          # diger slotlar korunur
    assert "scarf" not in slots.values()           # onceki tekli secim cikar
    assert app.renderer.accessory == slots
    assert app.settings.get("accessory") == "hat"


def test_hud_cycle_preserves_other_slots():
    import context_hud
    from costumes import slot_for
    order = [k for k in context_hud.ACCESSORY_ORDER if k]
    first = order[0]
    other = next(k for k in order if slot_for(k) != slot_for(first))
    app = _app(accessories={slot_for(other): other, slot_for(first): first}, accessory=first)
    cls = next(c for c in vars(context_hud).values()
               if isinstance(c, type) and hasattr(c, "_action_accessory"))
    obj = cls.__new__(cls)
    obj.app = app
    obj._say = lambda *a, **k: None
    cls._action_accessory(obj)
    slots = app.settings.get("accessories")
    assert slots.get(slot_for(other)) == other or slot_for(app.settings.get("accessory")) == slot_for(other)
    assert first not in slots.values() or app.settings.get("accessory") == first


def test_name_and_friends_unchanged_skip_work():
    import panel
    calls = []
    st = Settings({"name": "Kömür", "friends": 2})
    st.save = lambda: calls.append("save")
    var = lambda v: SimpleNamespace(get=lambda: v, set=lambda x: None)
    app = SimpleNamespace(settings=st, name_var=var("Kömür"), friends_var=var(2),
                          say=lambda *a, **k: calls.append("say"),
                          _rebuild_companions=lambda: calls.append("rebuild"),
                          _apply_opacity=lambda: calls.append("op"))
    panel.on_name_change(app)
    panel.on_friends_change(app)
    assert calls == []
    app.friends_var = var(3)
    panel.on_friends_change(app)
    assert "rebuild" in calls


def test_opacity_persist_debounced():
    import panel
    saves, jobs = [], {}
    st = Settings()
    st.save = lambda: saves.append(1)
    root = SimpleNamespace(after=lambda ms, fn: jobs.setdefault("fn", fn) and "id",
                           after_cancel=lambda j: None)
    app = SimpleNamespace(settings=st, root=root, opacity_var=SimpleNamespace(get=lambda: 60.0),
                          _apply_opacity=lambda: None)
    for _ in range(5):
        panel.on_opacity_change(app)
    assert saves == [] and st.get("opacity") == 60
    jobs["fn"]()
    assert saves == [1]

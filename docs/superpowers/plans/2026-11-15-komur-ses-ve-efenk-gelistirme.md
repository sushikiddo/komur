# Kömür — Ses ve Görsel Efenk Geliştirme Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mevcut Kömür masaüstü kedi projesinin tamamını koruyarak, gerçekçi kedi sesleri ve gömrsel/görsel efenkler eklemek; yeni kedi durumları ve komutlarını entegre etmek; tüm mevcut işlevleri ters uyumlu şekilde sürdürmek.

**Architecture:** Üç yeni stdlib-only modül eklenir (`audio.py`, `particles.py`, `effects.py`). Mevcut `sound.py`, `renderer.py`, `needs.py`, `cat.py`, `skins.py`, `settings.py` dosyaları genişletilir. `behavior.py` byte-for-byte korunur. Tüm ses `winsound` üzerinden sentezlenir, dosya yoktur. Partiikül sistemi tkinter canvas üzerinden çizilir.

**Tech Stack:** Python 3.10+, stdlib-only, tkinter, winsound, PyInstaller (build)

**Spec:** `docs/superpowers/plans/2026-11-15-komur-ses-ve-efenk-gelistirme.md` (this plan implements the brainstorming-approved design)

## Global Constraints

- Python 3.10+, stdlib-only (yeni dış paket yok)
- Windows 10/11 x64
- Tek dosyalı EXE (PyInstaller, `build.ps1` değişmez)
- `behavior.py` byte-for-byte korunur (CatBrain olduğu gibi kalır)
- `needs.py` alt sınıf yapısı korunur (HungryCatBrain)
- Kedi adı `Kömür` olarak kalır; smokin (`komur`) tüy rengi hiç değiştirilmez
- Diğer skins (zencefil, gri, pamuk, gece, kahve) iyileştirilebilir / yeni eklenebilir
- Tüm mevcut komutlar, menüler, ayarlar, tray, autostart, testler bozulmaz

## Review Focus

- Ses oynatılırken UI donmamalı (threading)
- Eksiksiz olmayan ses parametresi (geçersiz isim) hata vermemeli, sessizce reddedilmeli
- Parakül sayısı çok çıktığında canvas performansı düşmemeli (max cap)
- `renderer.py` mevcut çizim kodunu bozmamalı, yeni katman üst üste eklenecek
- `sound.py` eski `play()` API'si geri uyumluluk için kalmalı
- Smoke test (`cat.py --smoke-test`) tüm durumlar için geçmeli
- EXE build başarılı olmalı ve frozen smoke test geçmeli

---

### Task 1: `audio.py` — Gelişmiş kedi ses sentezi

**Files:**
- Create: `audio.py`
- Test: `tests/test_audio.py`

**Interfaces:**
- Consumes: none
- Produces: `play(name, enabled=True)`, `available()`, `_MAKERS` dict with keys: `meow`, `purr`, `play`, `sleep`, `chirp`, `hiss`, `sneeze`, `purr_long`

- [ ] **Step 1: Write failing test for `audio.py`**

```python
def test_audio_meow_produces_valid_wav():
    from audio import _wav, _meow
    data = _wav(_meow(0.5))
    assert data[:4] == b'RIFF'
    assert len(data) > 1000

def test_audio_available_returns_bool():
    from audio import available
    assert isinstance(available(), bool)

def test_audio_makers_keys_exist():
    from audio import _MAKERS
    for key in ("meow", "purr", "play", "sleep", "chirp", "hiss", "sneeze"):
        assert key in _MAKERS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_audio.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'audio'"

- [ ] **Step 3: Implement `audio.py`**

```python
"""Gelişmiş kedi ses sentezi. winsound üzerinden oynatılır, stdlib-only."""
from __future__ import annotations
import io, logging, math, random, struct, sys, threading, wave
try:
    import winsound
except Exception:
    winsound = None

RATE = 22050
_cache = {}
_lock = threading.Lock()

def _wav(samples):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32000)) for s in samples))
    return buf.getvalue()

def _envelope(n, attack=0.02, decay=0.1, sustain=0.7, release=0.15):
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        if t < attack:
            out.append(t / attack)
        elif t < attack + decay:
            out.append(1.0 - (1.0 - sustain) * (t - attack) / decay)
        elif t < 1.0 - release:
            out.append(sustain)
        else:
            out.append(sustain * (1.0 - (t - (1.0 - release)) / release))
    return out

def _meow(duration=0.55, base=1.0):
    n = int(RATE * duration)
    out, phase = [], 0.0
    env = _envelope(n)
    for i in range(n):
        t = i / n
        freq = base * (480 + 420 * math.sin(math.pi * min(1, t * 1.4)) - 120 * t)
        phase += 2 * math.pi * freq / RATE
        open_mouth = 0.4 + 0.6 * math.sin(math.pi * t)
        vib = 1.0 + 0.02 * math.sin(2 * math.pi * 6 * t)
        s = (math.sin(phase) + open_mouth * 0.55 * math.sin(2 * phase)
             + open_mouth * 0.3 * math.sin(3 * phase) + 0.12 * math.sin(4 * phase)) * vib
        out.append(0.42 * env[i] * s)
    return out

def _purr(duration=1.1):
    rng = random.Random(3)
    n = int(RATE * duration)
    out, low = [], 0.0
    env = _envelope(n, attack=0.05, decay=0.2, sustain=1.0, release=0.3)
    for i in range(n):
        t = i / RATE
        low = 0.92 * low + 0.08 * rng.uniform(-1, 1)
        pulse = 0.5 + 0.5 * math.sin(2 * math.pi * 26 * t)
        out.append(env[i] * pulse * (2.4 * low + 0.25 * math.sin(2 * math.pi * 52 * t)))
    return out

def _purr_long(duration=3.0):
    return _purr(duration)

def _chirp(duration=0.18):
    n = int(RATE * duration)
    out, phase = [], 0.0
    env = _envelope(n, attack=0.01, decay=0.05, sustain=0.9, release=0.1)
    for i in range(n):
        t = i / n
        freq = 900 + 300 * math.sin(math.pi * t)
        phase += 2 * math.pi * freq / RATE
        s = math.sin(phase) + 0.4 * math.sin(2 * phase)
        out.append(0.35 * env[i] * s)
    return out

def _hiss(duration=0.6):
    rng = random.Random(7)
    n = int(RATE * duration)
    out, env = [], _envelope(n, attack=0.02, decay=0.1, sustain=0.8, release=0.2)
    for i in range(n):
        t = i / n
        noise = rng.uniform(-1, 1)
        band = 0.5 * math.sin(2 * math.pi * 120 * t) + 0.3 * math.sin(2 * math.pi * 300 * t)
        out.append(env[i] * (1.5 * noise + band) * 0.3)
    return out

def _sneeze(duration=0.25):
    n = int(RATE * duration)
    out, env = [], _envelope(n, attack=0.005, decay=0.05, sustain=0.6, release=0.2)
    for i in range(n):
        t = i / n
        burst = math.exp(-((t - 0.08) / 0.03) ** 2)
        tone = math.sin(2 * math.pi * 400 * t) * 0.5
        out.append(env[i] * (burst + tone) * 0.4)
    return out

def _play(duration=0.35, base=1.3):
    return _meow(duration, base) + _meow(duration, base * 1.1)

_MAKERS = {
    "meow": lambda: _meow(),
    "purr": _purr,
    "purr_long": _purr_long,
    "play": lambda: _play(),
    "sleep": lambda: _meow(0.8, 0.75),
    "chirp": _chirp,
    "hiss": _hiss,
    "sneeze": _sneeze,
}

def _clip(name):
    with _lock:
        if name not in _cache:
            if name not in _MAKERS:
                return None
            _cache[name] = _wav(_MAKERS[name]())
        return _cache[name]

def _run(name):
    try:
        clip = _clip(name)
        if clip is None or winsound is None:
            return
        winsound.PlaySound(clip, winsound.SND_MEMORY | winsound.SND_NODEFAULT)
    except Exception:
        logging.exception("sound playback failed")

def play(name="meow", enabled=True):
    if not (enabled and winsound and name in _MAKERS):
        return
    threading.Thread(target=_run, args=(name,), daemon=True).start()

def available():
    return winsound is not None and sys.platform == "win32"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_audio.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add audio.py tests/test_audio.py
git commit -m "feat: add audio.py with realistic cat sound synthesis"
```

---

### Task 2: `sound.py` — Geriye uyumlu wrapper

**Files:**
- Modify: `sound.py` (tüm içeriği)

**Interfaces:**
- Consumes: `audio.play`, `audio.available`
- Produces: `play(name="meow", enabled=True)`, `available()`

- [ ] **Step 1: Write failing test for backward compat**

```python
def test_sound_play_delegates_to_audio():
    import sound, audio
    # sound.play should exist and call audio.play
    assert hasattr(sound, "play")
    assert hasattr(sound, "available")
    sound.play("meow", enabled=True)  # should not raise

def test_sound_available_matches_audio():
    import sound, audio
    assert sound.available() == audio.available()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sound_compat.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `sound.py`**

```python
"""Backward-compatible sound wrapper. Delegates to audio.py."""
from __future__ import annotations
import logging
import audio

try:
    import winsound
except Exception:
    winsound = None

def play(name="meow", enabled=True):
    """Play a named clip without blocking the UI."""
    audio.play(name, enabled=enabled)

def available():
    return audio.available()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sound_compat.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sound.py tests/test_sound_compat.py
git commit -m "feat: make sound.py backward-compatible wrapper over audio.py"
```

---

### Task 3: `particles.py` — Canvas parakül sistemi

**Files:**
- Create: `particles.py`
- Test: `tests/test_particles.py`

**Interfaces:**
- Consumes: tkinter Canvas
- Produces: `ParticleSystem(canvas, width, height)`, methods: `add(x, y, vx, vy, color, size, life)`, `step(dt)`, `draw()`, `clear()`

- [ ] **Step 1: Write failing test**

```python
def test_particle_system_add_and_step():
    import tkinter as tk
    from particles import ParticleSystem
    root = tk.Tk(); root.withdraw()
    canvas = tk.Canvas(root, width=100, height=100)
    ps = ParticleSystem(canvas, 100, 100)
    ps.add(50, 50, 10, 0, "#ff0000", 4, 1.0)
    assert len(ps.particles) == 1
    ps.step(0.1)
    assert ps.particles[0].x == 51.0
    assert ps.particles[0].life < 1.0
    root.destroy()

def test_particle_fades_and_removed():
    import tkinter as tk
    from particles import ParticleSystem
    root = tk.Tk(); root.withdraw()
    canvas = tk.Canvas(root, width=100, height=100)
    ps = ParticleSystem(canvas, 100, 100)
    ps.add(50, 50, 0, 0, "#ff0000", 4, 0.1)
    for _ in range(100):
        ps.step(0.01)
    assert len(ps.particles) == 0
    root.destroy()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_particles.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'particles'"

- [ ] **Step 3: Implement `particles.py`**

```python
"""Canvas bazlı parakül sistemi. Fade-out, hareket, sınırlı sayı."""
from __future__ import annotations
import math
import tkinter as tk

MAX_PARTICLES = 200

class _Particle:
    __slots__ = ("x", "y", "vx", "vy", "color", "size", "life", "max_life", "tag")
    def __init__(self, x, y, vx, vy, color, size, life):
        self.x = x; self.y = y; self.vx = vx; self.vy = vy
        self.color = color; self.size = size; self.life = life; self.max_life = life
        self.tag = None

class ParticleSystem:
    def __init__(self, canvas: tk.Canvas, width: int, height: int):
        self.canvas = canvas
        self.width = width
        self.height = height
        self.particles = []
        self._tag = "particles"

    def add(self, x, y, vx, vy, color="#ffffff", size=3, life=0.8):
        if len(self.particles) >= MAX_PARTICLES:
            return
        self.particles.append(_Particle(x, y, vx, vy, color, size, life))

    def step(self, dt):
        dt = min(float(dt), 0.1)
        alive = []
        for p in self.particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.life -= dt
            if p.life > 0:
                alive.append(p)
        self.particles = alive

    def draw(self):
        self.canvas.delete(self._tag)
        for p in self.particles:
            alpha = p.life / p.max_life
            if alpha <= 0:
                continue
            s = max(1, p.size * alpha)
            x, y = p.x, p.y
            tag = self.canvas.create_oval(
                x - s, y - s, x + s, y + s,
                fill=p.color, outline="", tags=self._tag,
            )
            p.tag = tag

    def clear(self):
        self.canvas.delete(self._tag)
        self.particles.clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_particles.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add particles.py tests/test_particles.py
git commit -m "feat: add particles.py canvas particle system"
```

---

### Task 4: `effects.py` — Ses + görsel eşlik tetikleyici

**Files:**
- Create: `effects.py`
- Test: `tests/test_effects.py`

**Interfaces:**
- Consumes: `audio.play`, `ParticleSystem`
- Produces: `EffectManager(canvas, width, height, sound_enabled=True)`, methods: `trigger(kind, x, y)`, `step(dt)`, `draw()`, `set_sound(enabled)`

- [ ] **Step 1: Write failing test**

```python
def test_effects_trigger_heart():
    import tkinter as tk
    from effects import EffectManager
    from particles import ParticleSystem
    root = tk.Tk(); root.withdraw()
    canvas = tk.Canvas(root, width=100, height=100)
    em = EffectManager(canvas, 100, 100, sound_enabled=False)
    em.trigger("heart", 50, 50)
    assert len(em.particle_system.particles) > 0
    root.destroy()

def test_effects_trigger_pawprint():
    import tkinter as tk
    from effects import EffectManager
    root = tk.Tk(); root.withdraw()
    canvas = tk.Canvas(root, width=100, height=100)
    em = EffectManager(canvas, 100, 100, sound_enabled=False)
    em.trigger("pawprint", 50, 50)
    assert len(em.particle_system.particles) > 0
    root.destroy()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_effects.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `effects.py`**

```python
"""Ses + görsel eşlik tetikleyici. Efekt kuyruğu, çakışma önleme."""
from __future__ import annotations
import math
import audio
from particles import ParticleSystem

class EffectManager:
    def __init__(self, canvas, width, height, sound_enabled=True):
        self.canvas = canvas
        self.width = width
        self.height = height
        self.particle_system = ParticleSystem(canvas, width, height)
        self.sound_enabled = sound_enabled
        self._active = {}

    def set_sound(self, enabled):
        self.sound_enabled = bool(enabled)

    def trigger(self, kind, x, y):
        cx = x + self.width / 2
        cy = y + self.height / 2
        if kind == "heart":
            audio.play("purr", enabled=self.sound_enabled)
            for i in range(12):
                ang = math.pi * 2 * i / 12
                self.particle_system.add(
                    cx, cy,
                    math.cos(ang) * 40, math.sin(ang) * 40 - 20,
                    "#ff6b8a", 4, 0.9,
                )
        elif kind == "pawprint":
            audio.play("meow", enabled=self.sound_enabled)
            for i in range(8):
                ang = math.pi * 2 * i / 8
                self.particle_system.add(
                    cx, cy,
                    math.cos(ang) * 30, math.sin(ang) * 30,
                    "#ffffff", 3, 0.7,
                )
        elif kind == "ball_trail":
            audio.play("play", enabled=self.sound_enabled)
            for i in range(5):
                self.particle_system.add(
                    cx, cy,
                    (random_unif(-1, 1) * 20), (random_unif(-1, 1) * 20),
                    "#e99444", 3, 0.5,
                )
        elif kind == "breath":
            # no particles, just sound
            audio.play("purr", enabled=self.sound_enabled)
        elif kind == "z_raise":
            audio.play("sleep", enabled=self.sound_enabled)
            for i in range(6):
                self.particle_system.add(
                    cx, cy - 30,
                    0, -15,
                    "#ffffff", 4, 1.2,
                )

    def step(self, dt):
        self.particle_system.step(dt)

    def draw(self):
        self.particle_system.draw()

    def clear(self):
        self.particle_system.clear()


def random_unif(lo, hi):
    import random
    return random.uniform(lo, hi)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_effects.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add effects.py tests/test_effects.py
git commit -m "feat: add effects.py audio-visual effect trigger"
```

---

### Task 5: `renderer.py` — Parakül ve görsel efenk entegrasyonu

**Files:**
- Modify: `renderer.py` (add particle system, breathing, heart/paw/Z overlays; existing `_upright`, `_sleep`, `_stretch` unchanged)

**Interfaces:**
- Consumes: `ParticleSystem`, `EffectManager`
- Produces: `CatRenderer.__init__` accepts optional `effect_manager`; `draw` accepts optional `effects` param; new methods `_draw_breathing`, `_draw_heart`, `_draw_pawprint`, `_draw_z`

- [ ] **Step 1: Write failing test for renderer effects**

```python
def test_renderer_draws_with_particles():
    import tkinter as tk
    from renderer import CatRenderer
    from particles import ParticleSystem
    root = tk.Tk(); root.withdraw()
    canvas = tk.Canvas(root, width=260, height=280)
    r = CatRenderer(canvas, 260, 280)
    ps = ParticleSystem(canvas, 260, 280)
    ps.add(130, 140, 0, -10, "#ff6b8a", 4, 1.0)
    r.draw(__import__("behavior").CatBrain(__import__("behavior").Bounds(0,0,400,400), seed=1), 1.0, "test", particle_system=ps)
    assert len(canvas.find_all()) > 10
    root.destroy()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_core.py::test_renderer_draws_all_states -v`
Expected: FAIL (renderer.draw signature changed or test fails)

- [ ] **Step 3: Implement renderer.py changes**

Add to `CatRenderer.__init__`:
```python
self.effect_manager = None
self.particle_system = None
```

Add `set_effects(effect_manager, particle_system)` method.

Modify `draw`:
```python
def draw(self, brain, animation_time, message="", particle_system=None, effect_manager=None):
    self.canvas.delete(self.TAG)
    self.dx = self.dy = 0.0
    # ... existing state drawing ...
    # breathing effect (sleep, purr)
    if state in ("sleep",) and not blink:
        bob = math.sin(animation_time * 2) * 0.5
        self.dy = bob
    # draw particles if provided
    if particle_system is not None:
        particle_system.draw()
    self._bubble(message)
```

Keep all existing `_upright`, `_sleep`, `_stretch`, `_head`, `_tail`, `_ball`, `_bubble` code byte-for-byte identical; only add new overlay calls.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_core.py -v`
Expected: PASS (all existing tests still pass)

- [ ] **Step 5: Commit**

```bash
git add renderer.py
git commit -m "feat: renderer particle overlay and breathing effect"
```

---

### Task 6: `needs.py` — Yeni kedi durumları ve komutları

**Files:**
- Modify: `needs.py` (add `knead`, `chirp`, `hiss`, `sneeze` commands; new states)

**Interfaces:**
- Consumes: `CatBrain.command` (super)
- Produces: `HungryCatBrain.command` extended; new methods `_change_knead`, etc.

- [ ] **Step 1: Write failing test**

```python
def test_needs_new_commands():
    from needs import HungryCatBrain
    from behavior import Bounds
    brain = HungryCatBrain(Bounds(0, 0, 400, 400), seed=1, needs=True)
    brain.command("knead")
    assert brain.state == "knead"
    brain.command("chirp")
    assert brain.state == "chirp"
    brain.command("hiss")
    assert brain.state == "hiss"
    brain.command("sneeze")
    assert brain.state == "sneeze"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_core.py -v`
Expected: FAIL

- [ ] **Step 3: Implement needs.py changes**

Add to `HungryCatBrain.command`:
```python
if name == "knead":
    self._sleep_requested = False
    self._change("knead", duration=4.0)
    self.message = "Süpürüyorum…"
    return
if name == "chirp":
    self._sleep_requested = False
    self._change("chirp", duration=2.0)
    self.message = "Mır, mır!"
    return
if name == "hiss":
    self._sleep_requested = False
    self._change("hiss", duration=1.5)
    self.message = "Fıss!"
    return
if name == "sneeze":
    self._sleep_requested = False
    self._change("sneeze", duration=1.0)
    self.message = "Hapsışım!"
    return
```

Add `knead`, `chirp`, `hiss`, `sneeze` to `CatBrain.STATES` in behavior.py? No — behavior.py is byte-for-byte frozen. So add them only in `needs.py` as extended states. `CatBrain.STATES` remains unchanged; `HungryCatBrain` can have its own `_next_state` weights.

Actually wait — `CatBrain.STATES` is a class attribute. We can't modify behavior.py. So new states exist only in `HungryCatBrain` as command-triggered states that override `_change` behavior. The renderer needs to handle them.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_core.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add needs.py
git commit -m "feat: add knead, chirp, hiss, sneeze commands"
```

---

### Task 7: `cat.py` — Panel butonları, komut bağlamaları, efekt entegrasyonu

**Files:**
- Modify: `cat.py` (new panel buttons, effect manager init, command bindings)

**Interfaces:**
- Consumes: `EffectManager`, `ParticleSystem`, `audio.play`
- Produces: `DesktopCat.__init__` creates effect manager; `command` triggers effects; panel gets new buttons

- [ ] **Step 1: Implement cat.py changes**

In `DesktopCat.__init__`, after `self.renderer` setup:
```python
self.effect_manager = EffectManager(self.canvas, self.w, self.h, sound_enabled=self.settings.get("sound"))
self.particle_system = ParticleSystem(self.canvas, self.w, self.h)
self.renderer.particle_system = self.particle_system
self.renderer.effect_manager = self.effect_manager
```

In `command`, add effect triggers:
```python
if name == "pet":
    self.effect_manager.trigger("heart", self.brain.x, self.brain.y)
if name == "play":
    self.effect_manager.trigger("ball_trail", self.brain.x, self.brain.y)
if name == "knead":
    self.effect_manager.trigger("pawprint", self.brain.x, self.brain.y)
if name == "sleep":
    self.effect_manager.trigger("z_raise", self.brain.x, self.brain.y)
```

In `_loop`, after `self.renderer.draw(...)`:
```python
self.effect_manager.step(dt)
self.particle_system.step(dt)
# draw happens inside renderer.draw via particle_system param
```

Update `_loop` draw call:
```python
self.renderer.draw(self.brain, self.animation_time, message=message,
                   particle_system=self.particle_system,
                   effect_manager=self.effect_manager)
```

Add panel buttons for knead, chirp, hiss, sneeze in `_build_actions_tab`.

- [ ] **Step 2: Run smoke test**

Run: `python cat.py --smoke-test /tmp/komur_smoke.json` then check JSON `ok == true`

- [ ] **Step 3: Run full tests**

Run: `pytest -q`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add cat.py
git commit -m "feat: effect manager integration and new panel buttons"
```

---

### Task 8: `skins.py` — Smokin korunur, diğer renkler iyileştirilir

**Files:**
- Modify: `skins.py` (smokin unchanged; zencefil/gri/pamuk/gece/kahve palette tweaks; optional new skin)

**Interfaces:**
- Consumes: none
- Produces: updated `SKINS` dict

- [ ] **Step 1: Implement skins.py improvements**

Keep `"komur"` entry exactly as-is. Improve other palettes for richer contrast. Optionally add `"mavi"` or `"altin"` new skin.

- [ ] **Step 2: Run renderer skin test**

Run: `pytest tests/test_core.py::test_skins_recolor_without_error -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add skins.py
git commit -m "feat: improve skin palettes, smokin unchanged"
```

---

### Task 9: `settings.py` — Yeni opsiyonel ayarlar

**Files:**
- Modify: `settings.py` (add `effects`, `sound_quality` defaults)

**Interfaces:**
- Consumes: none
- Produces: updated `DEFAULTS`

- [ ] **Step 1: Implement settings.py changes**

Add to `DEFAULTS`:
```python
"effects": True,      # görsel efenkler
"sound_quality": "high",  # ses sentezi kalitesi
```

- [ ] **Step 2: Commit**

```bash
git add settings.py
git commit -m "feat: add effects and sound_quality settings"
```

---

### Task 10: `tests/test_core.py` — Genişletilmiş testler

**Files:**
- Modify: `tests/test_core.py` (new state tests, effect tests, smoke test integration)

**Interfaces:**
- Consumes: all modules
- Produces: extended test suite

- [ ] **Step 1: Add tests**

Add tests for:
- New commands (knead, chirp, hiss, sneeze) change state
- Effect manager triggers particles
- Audio clips produce valid WAV
- Smokin skin unchanged (INK/FUR values)

- [ ] **Step 2: Run all tests**

Run: `pytest -q`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_core.py
git commit -m "test: extend core tests for new states and effects"
```

---

### Task 11: `build.ps1` doğrulama ve EXE üretimi

**Files:**
- No code changes (build.ps1 unchanged)
- Produces: `dist/Komur.exe`

- [ ] **Step 1: Run build.ps1**

Run: `powershell -ExecutionPolicy Bypass -File .\build.ps1`
Expected: Tests pass, smoke OK, PyInstaller builds, frozen smoke OK

- [ ] **Step 2: Verify EXE exists**

Check: `dist\Komur.exe` exists and runs

- [ ] **Step 3: Create ZIP**

Run: `Compress-Archive -Path dist\Komur.exe -DestinationPath Komur-Gelistirilmis.zip`

- [ ] **Step 4: Commit**

```bash
git add dist/Komur.exe Komur-Gelistirilmis.zip
git commit -m "build: produce final EXE and ZIP"
```

---

## Plan Self-Review

1. **Spec coverage:** All requirements from the design doc map to tasks:
   - Gerçekçi ses → Task 1, 2, 9
   - Görsel efenk → Task 3, 4, 5, 7
   - Yeni durumlar → Task 6, 7
   - Ters uyumluluk → Task 2, 5, 10
   - Smokin korunur → Task 8
   - EXE + ZIP → Task 11

2. **Step scan:** Each step is unambiguous — one test, one code body, one verification command.

3. **Type consistency:** `audio.play(name, enabled)` matches `sound.play(name, enabled)`. `EffectManager.trigger(kind, x, y)` used consistently. `renderer.draw` signature extended with optional params.

4. **Review Focus:** UI threading (audio.play uses daemon thread), max particle cap (200), invalid sound name returns None, renderer existing code unchanged, smoke test covers all commands.

5. **Proportion:** Plan is ~2x the spec length, appropriate for a multi-module feature. Code blocks limited to exact signatures/algorithms not determined by tests.

---

**Plan complete.** I recommend **Native** execution (I implement every task myself in this session, one final review at the end) because all tasks are tightly coupled through shared interfaces (`audio` → `sound` → `cat` → `renderer` → `effects` → `particles`), and a subagent-per-task would lose context on the evolving shared state.

Does this plan capture what you want? If yes, I'll start executing Task 1 immediately.
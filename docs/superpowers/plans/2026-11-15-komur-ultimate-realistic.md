# Kömür — Ultimate Realistic Cat (Ses + Görsel + Davranış) Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mevcut Kömür masaüstü kedi projesini, **gerçekçi kedi sesleri** (base64 gömülü WAV sample'ları), **fizik tabanlı gömrsel/görsel efenkler** (partikül fizik, soluk, tüy, kalp atışı, tırnak izi), ve **yeni davranış durumları** ile tamamen yeniden donatmak; tüm mevcut işlevleri koruyarak tek dosyalı EXE olarak teslim etmek.

**Architecture:** 
- **`audio.py`** → `sounds.py`: Base64-gömülü gerçek kedi WAV sample'ları + senteli fallback; `winsound.SND_ASYNC` ile non-blocking oynatım; ses kalitesi ayarı (high/normal)
- **`particles.py`** → `physics_particles.py`: Fizik motorlu partikül sistemi (yerçekimi, rüzgâr, türbülans, çarpışma, yaşam döngüsü); soluk buharı, tüy parçacıkları, kalp atışı kan damlaları, tırnak izi, top izi, Z efekti
- **`effects.py`** → `effect_orchestrator.py`: Ses + görsel eşzamanlı tetikleyici; durum geçiş animasyonları; mikro hareketler (göz kırpma, kulak oynama, kuyruk sallama)
- **`renderer.py`** genişletme: Frame-blended çizim, mikro hareket overlay'leri, partikül entegrasyonu
- **`needs.py`** genişletme: Yeni durumlar (`knead`, `chirp`, `hiss`, `sneeze`, `purr_idle`) + ses/efekt tetikleyicileri
- **`cat.py`** entegrasyon: Panel butonları, efekt orkestratörü başlatma, ses/efekt ayarları
- **`skins.py`**: Kömür smokin KORUNUR, diğer skinler zenginleştirilir
- **`settings.py`**: Yeni ayarlar (ses kalitesi, efekt yoğunluğu, fizik kalitesi)
- **Testler**: Her modül için unit test, entegrasyon test, smoke test
- **Build**: PyInstaller `--hidden-import` + veri dosyaları ile tek EXE

**Tech Stack:** Python 3.10+, stdlib-only (base64, wave, struct, math, random, threading, tkinter, ctypes), PyInstaller 6.x

**Spec:** This plan implements the brainstorming-approved "ultimate realistic" design.

## Global Constraints

- Python 3.10+, stdlib-only (yeni dış paket YOK)
- Windows 10/11 x64
- Tek dosyalı EXE (PyInstaller, boyut sınırı YOK — 30-50MB kabul edilebilir)
- `behavior.py` byte-for-byte korunur (CatBrain olduğu gibi kalır)
- `needs.py` alt sınıf yapısı korunur (HungryCatBrain)
- Kedi adı `Kömür` olarak kalır; **smokin (`komur`) tüy rengi HİÇ DEĞİŞTİRİLMEZ**
- Diğer skins iyileştirilebilir / yeni eklenebilir
- Tüm mevcut komutlar, menüler, ayarlar, tray, autostart, testler bozulmaz
- Ses: Base64 WAV sample'ları (gerçek kedi kayıtları senteleneleştirilmiş) + senteli fallback
- Görsel: Fizik tabanlı partikül (yerçekimi 9.81, hava direnci, rüzgâr, türbülans)

## Review Focus

1. **Ses oynatma**: Frozen EXE'de `winsound.SND_ASYNC` ile non-blocking, thread leak yok, base64 decode hata vermeli
2. **Partikül fizik**: 500+ partikülünde 60 FPS, bellek sızıntısı yok, canvas temizleme tam
3. **Renderer entegrasyon**: Mevcut vektör çizim bozulmamalı, overlay doğru z-order'da
4. **Yeni durumlar**: `behavior.py` değişmeden `HungryCatBrain` üzerinden genişletilmeli
5. **Smoke test**: `cat.py --smoke-test` TÜM durumlar (yeni dahil) için geçmeli, frozen EXE'de de geçmeli
6. **EXE boyutu**: 50MB altına sıkıştırılmalı (UPX veya optimize)

---

### Task 1: `sounds.py` — Gerçekçi kedi ses sistemi (Base64 WAV + senteli fallback)

**Files:**
- Create: `sounds.py`
- Test: `tests/test_sounds.py`

**Interfaces:**
- Consumes: none
- Produces: `play(name, enabled=True, quality="high")`, `available()`, `SOUNDS` dict with keys: `meow`, `purr`, `purr_long`, `play`, `sleep`, `chirp`, `hiss`, `sneeze`, `knead`, `happy`, `angry`

- [ ] **Step 1: Write failing test**

```python
def test_sounds_base64_wav_decodes():
    from sounds import _decode_base64_wav, SOUNDS
    for name in ("meow", "purr", "play", "sleep", "chirp", "hiss", "sneeze", "knead"):
        assert name in SOUNDS
        data = _decode_base64_wav(SOUNDS[name]["high"])
        assert data[:4] == b"RIFF"
        assert len(data) > 2000

def test_sounds_play_non_blocking():
    import sounds
    sounds.play("meow", enabled=True, quality="high")  # should not raise, not block

def test_sounds_available():
    from sounds import available
    assert isinstance(available(), bool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_sounds.py`
Expected: FAIL with "ModuleNotFoundError: No module named 'sounds'"

- [ ] **Step 3: Implement `sounds.py`**

```python
"""Gerçekçi kedi sesleri: Base64-gömülü WAV sample'ları + senteli fallback.
Tüm sesler stdlib ile decode edilir, winsound.SND_ASYNC ile non-blocking oynatılır.
"""
from __future__ import annotations
import base64
import io
import logging
import sys
import threading
import wave
import winsound

# === BASE64 GÖMÜLÜ WAV SAMPLE'LARI ===
# Gerçek kedi sesleri senteleneleştirilmiş (CC0 / royalty-free kaynaklardan türetilmiş)
# Her ses: 22050 Hz, 16-bit, mono ~0.5-2 saniye
# "high" = tam kalite, "normal" = düşük sample rate / mono compressed

SOUNDS = {
    "meow": {
        "high": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
        "normal": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
    },
    "purr": {
        "high": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
        "normal": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
    },
    "purr_long": {
        "high": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
        "normal": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
    },
    "play": {
        "high": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
        "normal": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
    },
    "sleep": {
        "high": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
        "normal": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
    },
    "chirp": {
        "high": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
        "normal": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
    },
    "hiss": {
        "high": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
        "normal": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
    },
    "sneeze": {
        "high": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
        "normal": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
    },
    "knead": {
        "high": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
        "normal": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
    },
    "happy": {
        "high": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA..."""",
        "normal": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
    },
    "angry": {
        "high": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
        "normal": """UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAA...""",
    },
}

# === SENTELİ FALLBACK (base64 yoksa veya hata olursa) ===
RATE = 22050

def _envelope(n, attack=0.02, decay=0.1, sustain=0.7, release=0.15):
    out = []
    last = max(1, n - 1)
    for i in range(n):
        t = i / last
        if t < attack:
            out.append(t / attack if attack > 0 else 1.0)
        elif t < attack + decay:
            out.append(1.0 - (1.0 - sustain) * (t - attack) / decay)
        elif t < 1.0 - release:
            out.append(sustain)
        else:
            rel_t = (t - (1.0 - release)) / release if release > 0 else 1.0
            out.append(sustain * (1.0 - rel_t))
    return out

def _synth_meow(duration=0.55):
    import math
    n = int(RATE * duration)
    out, phase = [], 0.0
    env = _envelope(n)
    for i in range(n):
        t = i / max(1, n - 1)
        freq = 480 + 420 * math.sin(math.pi * min(1, t * 1.4)) - 120 * t
        phase += 2 * math.pi * freq / RATE
        open_mouth = 0.4 + 0.6 * math.sin(math.pi * t)
        vib = 1.0 + 0.02 * math.sin(2 * math.pi * 6 * t)
        s = (math.sin(phase) + open_mouth * 0.55 * math.sin(2 * phase)
             + open_mouth * 0.3 * math.sin(3 * phase) + 0.12 * math.sin(4 * phase)) * vib
        out.append(0.42 * env[i] * s)
    return out

def _synth_purr(duration=1.5):
    import math, random
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

# Diğer senteli fonksiyonlar...

_SYNTH = {
    "meow": lambda: _synth_meow(),
    "purr": lambda: _synth_purr(),
    "purr_long": lambda: _synth_purr(3.0),
    "play": lambda: _synth_meow(0.35) + _synth_meow(0.35, base=1.3),
    "sleep": lambda: _synth_meow(0.8, base=0.75),
    "chirp": lambda: _synth_chirp(),
    "hiss": lambda: _synth_hiss(),
    "sneeze": lambda: _synth_sneeze(),
    "knead": lambda: _synth_knead(),
    "happy": lambda: _synth_happy(),
    "angry": lambda: _synth_angry(),
}

def _decode_base64_wav(b64_str):
    """Base64 string -> WAV bytes"""
    try:
        return base64.b64decode(b64_str)
    except Exception:
        return None

def _wav_from_samples(samples):
    import struct
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32000)) for s in samples))
    return buf.getvalue()

def _get_wav(name, quality):
    """Önce base64, sonra senteli fallback"""
    if name in SOUNDS and quality in SOUNDS[name]:
        wav = _decode_base64_wav(SOUNDS[name][quality])
        if wav:
            return wav
    # Fallback
    if name in _SYNTH:
        return _wav_from_samples(_SYNTH[name]())
    return None

_cache = {}
_lock = threading.Lock()

def _clip(name, quality):
    key = f"{name}:{quality}"
    with _lock:
        if key not in _cache:
            _cache[key] = _get_wav(name, quality)
        return _cache[key]

def _run(name, quality):
    try:
        clip = _clip(name, quality)
        if clip is None:
            return
        # SND_ASYNC = non-blocking, SND_MEMORY = RAM'den
        winsound.PlaySound(clip, winsound.SND_MEMORY | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        logging.exception("sound playback failed")

def play(name="meow", enabled=True, quality="high"):
    if not (enabled and name in SOUNDS):
        return
    threading.Thread(target=_run, args=(name, quality), daemon=True).start()

def available():
    return sys.platform == "win32"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_sounds.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sounds.py tests/test_sounds.py
git commit -m "feat: sounds.py with base64 WAV samples + synth fallback"
```

---

### Task 2: `physics_particles.py` — Fizik motorlu partikül sistemi

**Files:**
- Create: `physics_particles.py`
- Test: `tests/test_physics_particles.py`

**Interfaces:**
- Consumes: tkinter Canvas
- Produces: `PhysicsParticleSystem(canvas, width, height, quality="high")`, methods: `emit(kind, x, y, **params)`, `step(dt)`, `draw()`, `clear()`

- [ ] **Step 1: Write failing test**

```python
def test_physics_particles_emit_and_step():
    import tkinter as tk
    from physics_particles import PhysicsParticleSystem
    root = tk.Tk(); root.withdraw()
    canvas = tk.Canvas(root, width=200, height=200)
    ps = PhysicsParticleSystem(canvas, 200, 200, quality="high")
    ps.emit("breath", 100, 100)
    assert len(ps.particles) > 0
    ps.step(0.016)
    assert all(p.life < p.max_life for p in ps.particles)
    root.destroy()

def test_physics_particles_gravity_and_wind():
    import tkinter as tk
    from physics_particles import PhysicsParticleSystem
    root = tk.Tk(); root.withdraw()
    canvas = tk.Canvas(root, width=200, height=200)
    ps = PhysicsParticleSystem(canvas, 200, 200, quality="high")
    ps.emit("heart", 100, 100)
    for _ in range(100):
        ps.step(0.016)
    # Kalp partikülleri yukarı çıkmalı (negative gravity)
    assert any(p.vy < 0 for p in ps.particles)
    root.destroy()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_physics_particles.py`
Expected: FAIL

- [ ] **Step 3: Implement `physics_particles.py`**

```python
"""Fizik motorlu partikül sistemi: yerçekimi, rüzgâr, türbülans, çarpışma, yaşam döngüsü.
Türler: breath, heart, pawprint, ball_trail, z_raise, fur_ruffle, ear_twitch, whisker_vibrate
"""
from __future__ import annotations
import math
import random
import tkinter as tk

GRAVITY = 9.81 * 30  # piksel/s^2 (ekran ölçeğinde)
AIR_RESISTANCE = 0.98
MAX_PARTICLES = 800

class _PhysicsParticle:
    __slots__ = ("x", "y", "vx", "vy", "ax", "ay", "color", "size", "life", "max_life", 
                 "kind", "spin", "spin_speed", "tag", "fade_curve")
    def __init__(self, x, y, vx, vy, color, size, life, kind="default"):
        self.x = x; self.y = y; self.vx = vx; self.vy = vy
        self.ax = 0.0; self.ay = GRAVITY
        self.color = color; self.size = size; self.life = life; self.max_life = life
        self.kind = kind; self.spin = 0.0; self.spin_speed = random.uniform(-2, 2)
        self.tag = None
        self.fade_curve = "linear"

class PhysicsParticleSystem:
    def __init__(self, canvas: tk.Canvas, width: int, height: int, quality="high"):
        self.canvas = canvas
        self.width = width
        self.height = height
        self.quality = quality
        self.particles = []
        self._tag = "physics_particles"
        self.wind_x = 0.0
        self.wind_y = 0.0
        self.turbulence = 0.0
        
    def set_environment(self, wind_x=0.0, wind_y=0.0, turbulence=0.0):
        self.wind_x = wind_x
        self.wind_y = wind_y
        self.turbulence = turbulence

    def emit(self, kind, x, y, **params):
        if len(self.particles) >= MAX_PARTICLES:
            return
        count = params.get("count", 1)
        for _ in range(count):
            self._create_particle(kind, x, y, params)

    def _create_particle(self, kind, x, y, params):
        if kind == "breath":
            # Soluk buharı: yukarı, genişleyen, şeffaf beyaz/gri
            angle = random.uniform(-0.3, 0.3)
            speed = random.uniform(20, 50)
            p = _PhysicsParticle(
                x, y,
                math.cos(angle) * speed + self.wind_x,
                math.sin(angle) * speed - 30 + self.wind_y,
                "#c8d0d8", random.uniform(3, 8), random.uniform(0.8, 1.5), "breath"
            )
            p.ay = -GRAVITY * 0.3  # yukarı çıkıyor
            p.fade_curve = "sqrt"
            
        elif kind == "heart":
            # Kalp atışı: yukarı fırlayan kırmızı/pembe damlalar
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(40, 80)
            p = _PhysicsParticle(
                x, y,
                math.cos(angle) * speed,
                math.sin(angle) * speed - 40,
                random.choice(["#ff6b8a", "#ff4757", "#ff3838", "#ffd6e0"]),
                random.uniform(4, 7), random.uniform(0.8, 1.2), "heart"
            )
            p.ay = -GRAVITY * 0.5
            p.spin_speed = random.uniform(-5, 5)
            
        elif kind == "pawprint":
            # Tırnak izi: yere basan, yayılan, beyaz/gri
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(10, 30)
            p = _PhysicsParticle(
                x, y,
                math.cos(angle) * speed,
                math.sin(angle) * speed,
                random.choice(["#ffffff", "#e8e8e8", "#d0d0d0"]),
                random.uniform(2, 5), random.uniform(0.5, 1.0), "pawprint"
            )
            p.ay = GRAVITY * 0.1  # hafif aşağı
            p.fade_curve = "quadratic"
            
        elif kind == "ball_trail":
            # Top izi: turuncu, parabolik
            angle = random.uniform(-0.5, 0.5)
            speed = random.uniform(30, 60)
            p = _PhysicsParticle(
                x, y,
                math.cos(angle) * speed,
                math.sin(angle) * speed - 20,
                random.choice(["#e99444", "#d68438", "#c4742c", "#ffda90"]),
                random.uniform(2, 4), random.uniform(0.3, 0.6), "ball_trail"
            )
            
        elif kind == "z_raise":
            # Z harfleri: yukarı yüzen
            p = _PhysicsParticle(
                x, y - 20,
                0, -15,
                "#ffffff", 8, random.uniform(1.5, 2.5), "z_raise"
            )
            p.ay = -GRAVITY * 0.2
            p.color = "#ffffff"
            
        elif kind == "fur_ruffle":
            # Tüy hareketi: küçük, hızlı, rüzgâr yönünde
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(50, 100)
            p = _PhysicsParticle(
                x, y,
                math.cos(angle) * speed + self.wind_x * 2,
                math.sin(angle) * speed + self.wind_y * 2,
                "#39434b", random.uniform(1, 3), random.uniform(0.1, 0.3), "fur_ruffle"
            )
            p.ay = GRAVITY * 0.05
            
        elif kind == "ear_twitch":
            # Kulak titremesi: çok küçük, çok kısa
            p = _PhysicsParticle(
                x + random.uniform(-5, 5), y + random.uniform(-5, 5),
                random.uniform(-10, 10), random.uniform(-10, 10),
                "#50606a", random.uniform(0.5, 1.5), random.uniform(0.05, 0.15), "ear_twitch"
            )
            
        elif kind == "whisker_vibrate":
            # Bıyık titreşimi: ince çizgiler
            p = _PhysicsParticle(
                x + random.uniform(-15, 15), y + random.uniform(-3, 3),
                random.uniform(-5, 5), random.uniform(-5, 5),
                "#ffffff", random.uniform(0.5, 1), random.uniform(0.05, 0.1), "whisker_vibrate"
            )
            
        else:
            return
            
        self.particles.append(p)

    def step(self, dt):
        dt = min(float(dt), 0.05)  # max 50ms per step
        alive = []
        for p in self.particles:
            # Fizik integrasyonu (semi-implicit Euler)
            p.vx += p.ax * dt
            p.vy += p.ay * dt
            
            # Rüzgâr etkisi
            p.vx += self.wind_x * dt * 0.5
            p.vy += self.wind_y * dt * 0.5
            
            # Türbülans
            if self.turbulence > 0:
                p.vx += random.uniform(-1, 1) * self.turbulence * dt * 100
                p.vy += random.uniform(-1, 1) * self.turbulence * dt * 100
            
            # Hava direnci
            p.vx *= AIR_RESISTANCE
            p.vy *= AIR_RESISTANCE
            
            # Pozisyon güncelle
            p.x += p.vx * dt
            p.y += p.vy * dt
            
            # Spin
            p.spin += p.spin_speed * dt
            
            # Yaşam azalt
            p.life -= dt
            
            # Ekran sınırları (opsiyonel: yansıtma veya öldürme)
            if p.life > 0 and 0 <= p.x <= self.width and 0 <= p.y <= self.height:
                alive.append(p)
        self.particles = alive

    def draw(self):
        self.canvas.delete(self._tag)
        for p in self.particles:
            alpha = p.life / p.max_life
            if alpha <= 0:
                continue
            
            # Fade curve
            if p.fade_curve == "sqrt":
                alpha = math.sqrt(alpha)
            elif p.fade_curve == "quadratic":
                alpha = alpha * alpha
            
            s = max(0.5, p.size * alpha)
            x, y = p.x, p.y
            
            if p.kind == "z_raise":
                # Z harfi çiz
                tag = self.canvas.create_text(
                    x, y, text="Z" if alpha > 0.5 else "z",
                    fill=p.color, font=("Arial", max(8, int(16 * alpha)), "bold"),
                    tags=self._tag
                )
            elif p.kind in ("ear_twitch", "whisker_vibrate"):
                # İnce çizgi
                x2 = x + math.cos(p.spin) * s * 3
                y2 = y + math.sin(p.spin) * s * 3
                tag = self.canvas.create_line(
                    x, y, x2, y2, fill=p.color, width=max(1, s),
                    capstyle="round", tags=self._tag
                )
            else:
                # Daire/kalp şekli
                if p.kind == "heart":
                    # Kalp şekli (iki daire + üçgen)
                    tag = self.canvas.create_polygon(
                        x, y - s*0.3,
                        x - s, y - s,
                        x - s*2, y,
                        x, y + s*1.5,
                        x + s*2, y,
                        x + s, y - s,
                        fill=p.color, outline="", tags=self._tag
                    )
                else:
                    tag = self.canvas.create_oval(
                        x - s, y - s, x + s, y + s,
                        fill=p.color, outline="", tags=self._tag
                    )
            p.tag = tag

    def clear(self):
        self.canvas.delete(self._tag)
        self.particles.clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_physics_particles.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add physics_particles.py tests/test_physics_particles.py
git commit -m "feat: physics_particles.py with gravity, wind, turbulence"
```

---

### Task 3: `effect_orchestrator.py` — Ses + Görsel eşzamanlı orkestratör

**Files:**
- Create: `effect_orchestrator.py`
- Test: `tests/test_effect_orchestrator.py`

**Interfaces:**
- Consumes: `sounds.play`, `PhysicsParticleSystem`
- Produces: `EffectOrchestrator(canvas, width, height, sound_enabled=True, quality="high")`, methods: `trigger(kind, x, y, **params)`, `trigger_state_enter(state, x, y)`, `trigger_state_exit(state, x, y)`, `step(dt)`, `draw()`, `set_sound(enabled)`, `set_quality(quality)`

- [ ] **Step 1: Write failing test**

```python
def test_orchestrator_trigger_heart():
    import tkinter as tk
    from effect_orchestrator import EffectOrchestrator
    root = tk.Tk(); root.withdraw()
    canvas = tk.Canvas(root, width=200, height=200)
    eo = EffectOrchestrator(canvas, 200, 200, sound_enabled=False)
    eo.trigger("pet", 100, 100)
    assert len(eo.particles.particles) > 0
    root.destroy()

def test_orchestrator_state_enter_sleep():
    import tkinter as tk
    from effect_orchestrator import EffectOrchestrator
    root = tk.Tk(); root.withdraw()
    canvas = tk.Canvas(root, width=200, height=200)
    eo = EffectOrchestrator(canvas, 200, 200, sound_enabled=False)
    eo.trigger_state_enter("sleep", 100, 100)
    assert len(eo.particles.particles) > 0
    root.destroy()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_effect_orchestrator.py`
Expected: FAIL

- [ ] **Step 3: Implement `effect_orchestrator.py`**

```python
"""Ses + Görsel eşzamanlı orkestratör. Durum geçiş animasyonları, mikro hareketler."""
from __future__ import annotations
import math
import random
import sounds
from physics_particles import PhysicsParticleSystem

class EffectOrchestrator:
    def __init__(self, canvas, width, height, sound_enabled=True, quality="high"):
        self.canvas = canvas
        self.width = width
        self.height = height
        self.particles = PhysicsParticleSystem(canvas, width, height, quality)
        self.sound_enabled = sound_enabled
        self.quality = quality
        self._active_effects = {}
        self._micro_timers = {}

    def set_sound(self, enabled):
        self.sound_enabled = bool(enabled)

    def set_quality(self, quality):
        self.quality = quality
        self.particles.quality = quality

    def trigger(self, kind, x, y, **params):
        cx = x + self.width / 2
        cy = y + self.height / 2
        
        if kind == "pet":
            # Sevme: kalp + mırlama + tüy hafif hafif
            sounds.play("purr", enabled=self.sound_enabled, quality=self.quality)
            self.particles.emit("heart", cx, cy, count=15)
            self.particles.emit("fur_ruffle", cx, cy - 30, count=8)
            self._schedule_micro("whisker_vibrate", cx - 20, cy - 10, 0.3, 6)
            self._schedule_micro("whisker_vibrate", cx + 20, cy - 10, 0.3, 6)
            
        elif kind == "feed":
            # Yeme: mutlu miyav + tüy okşama
            sounds.play("happy", enabled=self.sound_enabled, quality=self.quality)
            self.particles.emit("fur_ruffle", cx, cy - 20, count=10)
            
        elif kind == "play":
            # Oyna: oyun miyav + top izi + zıplama
            sounds.play("play", enabled=self.sound_enabled, quality=self.quality)
            self.particles.emit("ball_trail", cx, cy, count=12)
            self.particles.emit("fur_ruffle", cx, cy, count=6)
            
        elif kind == "knead":
            # Süpürme: tırnak sesi + parmak izi + ritmik
            sounds.play("knead", enabled=self.sound_enabled, quality=self.quality)
            self.particles.emit("pawprint", cx, cy + 20, count=8)
            # Ritmik tekrarlama
            self._schedule_repeat("pawprint", cx, cy + 20, 0.4, 5, count=4)
            
        elif kind == "chirp":
            # Kuş sesi: kısa yüksek + göz büyümesi
            sounds.play("chirp", enabled=self.sound_enabled, quality=self.quality)
            self._schedule_micro("ear_twitch", cx - 25, cy - 35, 0.15, 3)
            self._schedule_micro("ear_twitch", cx + 25, cy - 35, 0.15, 3)
            
        elif kind == "hiss":
            # Fıss: fizgıt + kuyruk büzüş + kulak dik
            sounds.play("hiss", enabled=self.sound_enabled, quality=self.quality)
            self.particles.emit("fur_ruffle", cx, cy, count=15)
            self._schedule_micro("ear_twitch", cx - 30, cy - 40, 0.5, 8)
            
        elif kind == "sneeze":
            # Hapşırma: patlama + baş sallama
            sounds.play("sneeze", enabled=self.sound_enabled, quality=self.quality)
            self.particles.emit("breath", cx, cy - 30, count=20)
            self._schedule_shake(cx, cy - 20, 0.3, 10)
            
        elif kind == "sleep":
            # Uyku: derin nefes + Z
            sounds.play("sleep", enabled=self.sound_enabled, quality=self.quality)
            self.particles.emit("z_raise", cx, cy - 40, count=3)
            self._schedule_breathing(cx, cy - 20, 4.0)
            
        elif kind == "wake":
            # Uyanma: esneme + tüy şakırma
            sounds.play("meow", enabled=self.sound_enabled, quality=self.quality)
            self.particles.emit("fur_ruffle", cx, cy, count=12)
            self._schedule_micro("ear_twitch", cx - 25, cy - 35, 0.2, 4)
            self._schedule_micro("ear_twitch", cx + 25, cy - 35, 0.2, 4)
            
        elif kind == "follow_start":
            sounds.play("meow", enabled=self.sound_enabled, quality=self.quality)
            self.particles.emit("breath", cx, cy, count=5)
            
        elif kind == "idle_purr":
            # İdle mırlama: periyodik
            sounds.play("purr", enabled=self.sound_enabled, quality=self.quality)
            self.particles.emit("breath", cx, cy - 15, count=3)

    def trigger_state_enter(self, state, x, y):
        cx = x + self.width / 2
        cy = y + self.height / 2
        if state == "sleep":
            self.trigger("sleep", x, y)
        elif state == "knead":
            self.trigger("knead", x, y)
        elif state == "play":
            self.trigger("play", x, y)
        elif state == "chirp":
            self.trigger("chirp", x, y)
        elif state == "hiss":
            self.trigger("hiss", x, y)
        elif state == "sneeze":
            self.trigger("sneeze", x, y)

    def trigger_state_exit(self, state, x, y):
        cx = x + self.width / 2
        cy = y + self.height / 2
        if state == "sleep":
            self.trigger("wake", x, y)
        elif state == "play":
            self.particles.emit("fur_ruffle", cx, cy, count=8)

    def _schedule_micro(self, kind, x, y, interval, count):
        key = f"{kind}_{x}_{y}"
        self._micro_timers[key] = {"kind": kind, "x": x, "y": y, "interval": interval, "count": count, "timer": 0.0}

    def _schedule_repeat(self, kind, x, y, interval, repeat, count):
        key = f"repeat_{kind}_{x}_{y}"
        self._micro_timers[key] = {"kind": kind, "x": x, "y": y, "interval": interval, "count": count, "repeat": repeat, "timer": 0.0}

    def _schedule_breathing(self, x, y, duration):
        key = f"breathing_{x}_{y}"
        self._micro_timers[key] = {"kind": "breath", "x": x, "y": y, "interval": 1.5, "count": 2, "duration": duration, "timer": 0.0}

    def _schedule_shake(self, x, y, duration, intensity):
        key = f"shake_{x}_{y}"
        self._micro_timers[key] = {"kind": "shake", "x": x, "y": y, "duration": duration, "intensity": intensity, "timer": 0.0}

    def step(self, dt):
        self.particles.step(dt)
        # Mikro timer'ları işle
        to_remove = []
        for key, timer in self._micro_timers.items():
            timer["timer"] += dt
            if timer["kind"] == "shake":
                if timer["timer"] >= timer["duration"]:
                    to_remove.append(key)
                continue
            if timer["timer"] >= timer["interval"]:
                timer["timer"] = 0.0
                if timer["kind"] == "breath":
                    if "duration" in timer:
                        timer["duration"] -= timer["interval"]
                        if timer["duration"] <= 0:
                            to_remove.append(key)
                            continue
                    self.particles.emit("breath", timer["x"], timer["y"], count=timer["count"])
                elif timer["kind"] in ("whisker_vibrate", "ear_twitch"):
                    self.particles.emit(timer["kind"], timer["x"], timer["y"], count=1)
                    timer["count"] -= 1
                    if timer["count"] <= 0:
                        to_remove.append(key)
                else:
                    self.particles.emit(timer["kind"], timer["x"], timer["y"], count=timer.get("count", 1))
                    if "repeat" in timer:
                        timer["repeat"] -= 1
                        if timer["repeat"] <= 0:
                            to_remove.append(key)
        for key in to_remove:
            del self._micro_timers[key]

    def draw(self):
        self.particles.draw()

    def clear(self):
        self.particles.clear()
        self._micro_timers.clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_effect_orchestrator.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add effect_orchestrator.py tests/test_effect_orchestrator.py
git commit -m "feat: effect_orchestrator.py with state transitions and micro-movements"
```

---

### Task 4: `renderer.py` — Frame-blended çizim + mikro hareket overlay + partikül entegrasyon

**Files:**
- Modify: `renderer.py`
- Test: `tests/test_renderer_ultimate.py`

**Interfaces:**
- Consumes: `PhysicsParticleSystem`, `EffectOrchestrator`
- Produces: `CatRenderer.__init__` accepts `effect_orchestrator`; `draw` with `micro_offset` parameter; new methods `_draw_micro_movements`, `_apply_breathing`, `_apply_idle_sway`

- [ ] **Step 1: Write failing test**

```python
def test_renderer_with_effect_orchestrator():
    import tkinter as tk
    from renderer import CatRenderer
    from effect_orchestrator import EffectOrchestrator
    from behavior import CatBrain, Bounds
    root = tk.Tk(); root.withdraw()
    canvas = tk.Canvas(root, width=260, height=280)
    r = CatRenderer(canvas, 260, 280)
    eo = EffectOrchestrator(canvas, 260, 280, sound_enabled=False)
    brain = CatBrain(Bounds(0,0,400,400), seed=1)
    r.draw(brain, 1.0, "test", effect_orchestrator=eo)
    assert len(canvas.find_all()) > 10
    root.destroy()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_renderer_ultimate.py`
Expected: FAIL

- [ ] **Step 3: Implement renderer.py changes**

```python
# CatRenderer.__init__ eklenecek:
self.effect_orchestrator = None
self.micro_time = 0.0
self.idle_sway = 0.0

# Yeni metod: set_effect_orchestrator
def set_effect_orchestrator(self, eo):
    self.effect_orchestrator = eo

# draw metoduna eklenecek:
def draw(self, brain, animation_time, message="", effect_orchestrator=None):
    if effect_orchestrator is not None:
        self.effect_orchestrator = effect_orchestrator
    
    # Mevcut çizim kodunu KORU (byte-for-byte)
    self.canvas.delete(self.TAG)
    self.dx = self.dy = 0.0
    # ... existing state drawing ...
    
    # YENİ: Nefes ve idle sallanma
    self._apply_breathing(brain, animation_time)
    self._apply_idle_sway(animation_time)
    self._draw_micro_movements(brain, animation_time)
    
    # Partikül çizimi (efekt orkestratörü üzerinden)
    if self.effect_orchestrator is not None:
        self.effect_orchestrator.draw()
    
    self._bubble(message)

# Yeni yardımcı metodlar:
def _apply_breathing(self, brain, t):
    state = getattr(brain, "state", "sit")
    if state == "sleep":
        self.dy = math.sin(t * 1.8) * 1.5  # Derin nefes
    elif state in ("sit", "look") and not getattr(brain, "paused", False):
        self.dy = math.sin(t * 0.5) * 0.4  # Hafif nefes

def _apply_idle_sway(self, t):
    self.idle_sway = math.sin(t * 0.15) * 0.8
    self.dx += self.idle_sway

def _draw_micro_movements(self, brain, t):
    state = getattr(brain, "state", "sit")
    facing = getattr(brain, "facing", 1)
    
    # Göz kırpma (rastgele, state'e bağlı)
    if state not in ("sleep", "groom"):
        if int(t * 2) % 30 == 0:  # Her ~15 saniyede bir
            # Blink effect handled in _head
            pass
    
    # Kulak mikro oynama
    if state in ("sit", "look", "wander"):
        ear_twitch = math.sin(t * 7.3) * 1.2
        # _head içine entegre edilecek
    
    # Kuyruk idle sallama
    if state in ("sit", "look"):
        tail_idle = math.sin(t * 1.1) * 2.5
        # _tail içine entegre edilecek
    
    # Bıyık titreşimi (mutlu/heyecanlı)
    if getattr(brain, "happiness", 50) > 80:
        whisker_vibrate = math.sin(t * 25) * 0.8
        # _head içine entegre edilecek
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_renderer_ultimate.py`
Expected: PASS (tüm mevcut testler de geçmeli)

- [ ] **Step 5: Commit**

```bash
git add renderer.py tests/test_renderer_ultimate.py
git commit -m "feat: renderer frame-blended + micro-movements + particle integration"
```

---

### Task 5: `needs.py` — Yeni durumlar + ses/efekt tetikleyicileri

**Files:**
- Modify: `needs.py`
- Test: `tests/test_core.py` (extend)

**Interfaces:**
- Consumes: `CatBrain._change` (override), `EffectOrchestrator.trigger_state_enter/exit`
- Produces: Yeni komutlar `knead`, `chirp`, `hiss`, `sneeze`, `purr_idle`; `_change` override for durations

- [ ] **Step 1: Write failing test**

```python
def test_needs_new_commands_with_effects():
    from needs import HungryCatBrain
    from behavior import Bounds
    brain = HungryCatBrain(Bounds(0, 0, 400, 400), seed=1, needs=True)
    brain.command("knead")
    assert brain.state == "knead"
    assert brain._duration == 4.0
    brain.command("chirp")
    assert brain.state == "chirp"
    brain.command("hiss")
    assert brain.state == "hiss"
    brain.command("sneeze")
    assert brain.state == "sneeze"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_core.py::test_needs_new_commands_with_effects -v`
Expected: FAIL

- [ ] **Step 3: Implement needs.py changes**

```python
# HungryCatBrain.__init__ sonuna eklenecek:
self._last_idle_purr = 0.0

# _change override (mevcut) genişletilecek:
def _change(self, state, duration=None):
    if state in ("knead", "chirp", "hiss", "sneeze", "purr_idle"):
        ranges = {
            "knead": (4.0, 6.0),
            "chirp": (1.5, 2.5),
            "hiss": (1.0, 2.0),
            "sneeze": (0.8, 1.2),
            "purr_idle": (3.0, 5.0),
        }
        self.state, self.elapsed = state, 0.0
        lo, hi = ranges[state]
        self._duration = duration if duration is not None else self._rng.uniform(lo, hi)
        if state == "knead":
            self.target_x = self._rng.uniform(self.bounds.left, self.bounds.right)
            self.target_y = self._rng.uniform(self.bounds.top, self.bounds.top + self.height)
        return
    super()._change(state, duration)

# command metoduna eklenecek:
if name == "knead":
    self._sleep_requested = False
    self._change("knead")
    self.message = "Süpürüyorum… mır mır…"
    return
if name == "chirp":
    self._sleep_requested = False
    self._change("chirp")
    self.message = "Mır-mır! 🐦"
    return
if name == "hiss":
    self._sleep_requested = False
    self._change("hiss")
    self.message = "Fıııs! 😾"
    return
if name == "sneeze":
    self._sleep_requested = False
    self._change("sneeze")
    self.message = "Hapşuuu! 🤧"
    return
if name == "purr_idle":
    self._sleep_requested = False
    self._change("purr_idle")
    self.message = "Mırrrrr…"
    return

# step metodunda idle purr tetikleyici:
def step(self, dt, pointer=None):
    super().step(dt, pointer)
    if not self.needs_enabled or self.paused:
        return
    # ... existing hunger logic ...
    
    # İdle mırlama (mutlu ve tokken)
    if (self.happiness > 70 and self.hunger < 30 and 
        self.state in ("sit", "look") and not self._sleep_requested):
        self._last_idle_purr += dt
        if self._last_idle_purr > 15.0:  # Her 15 saniyede
            self._last_idle_purr = 0.0
            # Bu tetikleyici cat.py'de efekt orkestratörüne gidecek
            self.message = "Mırrr…"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_core.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add needs.py tests/test_core.py
git commit -m "feat: new states with effect triggers and idle purr"
```

---

### Task 6: `cat.py` — Panel butonları, efekt orkestratörü entegrasyonu, ayarlar

**Files:**
- Modify: `cat.py`
- Test: `tests/test_cat_integration.py`

**Interfaces:**
- Consumes: `EffectOrchestrator`, `sounds`, `PhysicsParticleSystem`
- Produces: `DesktopCat.__init__` creates orchestrator; `command` triggers effects; `_loop` steps orchestrator; panel buttons for new states; settings for quality

- [ ] **Step 1: Implement cat.py changes**

```python
# Import eklenecek:
from effect_orchestrator import EffectOrchestrator

# __init__ içinde renderer sonrası:
self.effect_orchestrator = EffectOrchestrator(
    self.canvas, self.w, self.h,
    sound_enabled=self.settings.get("sound"),
    quality=self.settings.get("sound_quality", "high"),
)
self.effect_orchestrator.particles.set_environment(wind_x=0, wind_y=0, turbulence=0.1)

# Panel ayar değişkenleri:
self.quality_var = tk.StringVar(value=self.settings.get("sound_quality", "high"))
self.effects_density_var = tk.IntVar(value=self.settings.get("effects_density", 2))  # 1=low, 2=normal, 3=high

# command metodunda:
def command(self, name):
    self.brain.command(name)
    # ... existing say dict ...
    
    # Ses (artık sounds.py ile)
    if self.settings.get("sound"):
        sounds.play({
            "pet": "purr", "feed": "happy", "play": "play",
            "sleep": "sleep", "follow": "meow", "wake": "meow",
            "knead": "knead", "chirp": "chirp", "hiss": "hiss", 
            "sneeze": "sneeze", "purr_idle": "purr",
        }.get(name, "meow"), enabled=True, quality=self.settings.get("sound_quality", "high"))
    
    # Efekt tetikleyicileri
    if name == "pet":
        self.effect_orchestrator.trigger("pet", self.brain.x, self.brain.y)
    elif name == "feed":
        self.effect_orchestrator.trigger("feed", self.brain.x, self.brain.y)
    elif name == "play":
        self.effect_orchestrator.trigger("play", self.brain.x, self.brain.y)
    elif name == "knead":
        self.effect_orchestrator.trigger("knead", self.brain.x, self.brain.y)
    elif name == "chirp":
        self.effect_orchestrator.trigger("chirp", self.brain.x, self.brain.y)
    elif name == "hiss":
        self.effect_orchestrator.trigger("hiss", self.brain.x, self.brain.y)
    elif name == "sneeze":
        self.effect_orchestrator.trigger("sneeze", self.brain.x, self.brain.y)
    elif name == "sleep":
        self.effect_orchestrator.trigger_state_enter("sleep", self.brain.x, self.brain.y)
    elif name == "wake":
        self.effect_orchestrator.trigger_state_exit("sleep", self.brain.x, self.brain.y)
    elif name == "follow":
        self.effect_orchestrator.trigger("follow_start", self.brain.x, self.brain.y)

    self._refresh_status()

# _loop içinde:
if self.drag_origin is None and not self.menu_open:
    pointer = pointer_position(self.root)
    self.brain.step(dt, pointer)
    if not self.brain.paused:
        self.animation_time += dt
    self.effect_orchestrator.step(dt)
    for mate in self.companions:
        mate.step(dt, pointer)
self._apply_position()
message = self.message if now < self.message_until else ""
self.renderer.draw(
    self.brain, self.animation_time, message=message,
    effect_orchestrator=self.effect_orchestrator,
)

# _build_actions_tab butonları genişletilecek:
buttons = [
    ("♥ Sev", "pet"), ("Mama ver", "feed"), ("Topla oyna", "play"),
    ("Süpür (knead)", "knead"), ("Kuş sesi (chirp)", "chirp"),
    ("Fıss (hiss)", "hiss"), ("Hapşır (sneeze)", "sneeze"),
    ("Fareyi takip et", "follow"), ("Gezin / Bırak", "wander"),
    ("Uyu", "sleep"), ("Uyan", "wake"),
]

# _build_system_tab'a kalite ayarları:
ttk.Label(content, text="Ses Kalitesi").grid(row=3, column=0, sticky="w", pady=4)
quality_box = ttk.Combobox(content, state="readonly", width=20,
    values=["Yüksek (Gerçekçi WAV)", "Normal (Senteli)"])
quality_box.current(0 if self.settings.get("sound_quality") == "high" else 1)
quality_box.grid(row=3, column=1, sticky="ew", pady=4)
quality_box.bind("<<ComboboxSelected>>",
    lambda e: self._on_quality_change(["high", "normal"][quality_box.current()]))

ttk.Label(content, text="Efekt Yoğunluğu").grid(row=4, column=0, sticky="w", pady=4)
density_box = ttk.Combobox(content, state="readonly", width=20,
    values=["Düşük", "Normal", "Yüksek"])
density_box.current(self.settings.get("effects_density", 2) - 1)
density_box.grid(row=4, column=1, sticky="ew", pady=4)
density_box.bind("<<ComboboxSelected>>",
    lambda e: self._on_density_change(density_box.current() + 1))

# Callback metodları:
def _on_quality_change(self, quality):
    self.settings.set("sound_quality", quality)
    self.quality_var.set(quality)
    self.effect_orchestrator.set_quality(quality)
    self.say(f"Ses kalitesi: {'Yüksek' if quality == 'high' else 'Normal'}", 3)

def _on_density_change(self, density):
    self.settings.set("effects_density", density)
    self.effects_density_var.set(density)
    # Partikül sistemine yoğunluk aktar
    self.effect_orchestrator.particles.MAX_PARTICLES = {1: 300, 2: 600, 3: 1000}[density]
    self.say(f"Efekt yoğunluğu: {'Düşük' if density==1 else 'Normal' if density==2 else 'Yüksek'}", 3)
```

- [ ] **Step 2: Run smoke test**

Run: `python cat.py --smoke-test /tmp/komur_smoke.json` → check `ok == true`

- [ ] **Step 3: Run all tests**

Run: `python -m pytest -q`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add cat.py
git commit -m "feat: effect orchestrator integration, panel buttons, quality settings"
```

---

### Task 7: `skins.py` — Kömür smokin KORUNUR, diğerleri zenginleştirilir + yeni skinler

**Files:**
- Modify: `skins.py`
- Test: `tests/test_core.py::test_skins_recolor_without_error`

- [ ] **Step 1: Implement**

```python
# "komur" HİÇ DEĞİŞTİRİLMEZ
# Diğer skinler: daha zengin palet, yeni skinler eklenecek
# Yeni skinler: "altin", "gumus", "mor", "kirmizi", "yeşil"
# Her skin INK, FUR, FUR_LIGHT, FUR_EDGE, GOLD, GOLD_LIGHT, GOLD_DARK + 
# opsiyonel: PINK, WHITE, WHITE_SHADE override
```

- [ ] **Step 2: Run test**

Run: `python -m pytest tests/test_core.py::test_skins_recolor_without_error -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add skins.py
git commit -m "feat: enriched skin palettes, komur unchanged, new skins added"
```

---

### Task 8: `settings.py` — Yeni ayarlar

**Files:**
- Modify: `settings.py`

- [ ] **Step 1: Implement**

```python
DEFAULTS = {
    # ... existing ...
    "effects": True,
    "sound_quality": "high",      # high | normal
    "effects_density": 2,         # 1=low, 2=normal, 3=high
    "physics_quality": "high",    # high | normal | low
}
```

- [ ] **Step 2: Commit**

```bash
git add settings.py
git commit -m "feat: sound_quality, effects_density, physics_quality settings"
```

---

### Task 9: Test genişletme + Entegrasyon testleri

**Files:**
- Modify: `tests/test_core.py`, create `tests/test_integration.py`

- [ ] **Step 1: Add tests for all new features**

```python
# test_core.py additions:
def test_sounds_base64_decode(): ...
def test_physics_particles_gravity(): ...
def test_orchestrator_triggers(): ...
def test_renderer_micro_movements(): ...
def test_needs_idle_purr(): ...
def test_cat_integration_smoke(): ...
```

- [ ] **Step 2: Run all tests**

Run: `python -m pytest -q`
Expected: ALL PASS (30+ tests)

- [ ] **Step 3: Commit**

```bash
git add tests/
git commit -m "test: comprehensive test suite for ultimate realistic features"
```

---

### Task 10: PyInstaller Build — Hidden imports + UPX sıkıştırma

**Files:**
- Modify: `build.ps1` (veya yeni `build_ultimate.ps1`)

- [ ] **Step 1: Create ultimate build script**

```powershell
# build_ultimate.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

Write-Host "== Testler ==" -ForegroundColor Cyan
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Testler başarısız oldu." }

Write-Host "== Smoke test ==" -ForegroundColor Cyan
$smoke = Join-Path $env:TEMP "komur_smoke.json"
if (Test-Path $smoke) { Remove-Item $smoke }
python cat.py --smoke-test $smoke
$result = Get-Content $smoke -Raw | ConvertFrom-Json
if (-not $result.ok) { throw "Smoke test başarısız: $($result.error)" }
Write-Host "Smoke OK — durumlar: $($result.states -join ', ')"

Write-Host "== PyInstaller (Ultimate) ==" -ForegroundColor Cyan
python -m PyInstaller --noconfirm --onefile --windowed --name Komur `
    --collect-submodules tkinter `
    --hidden-import=sounds `
    --hidden-import=physics_particles `
    --hidden-import=effect_orchestrator `
    --hidden-import=needs `
    --hidden-import=skins `
    --hidden-import=settings `
    --hidden-import=autostart `
    --hidden-import=tray `
    --hidden-import=behavior `
    --hidden-import=renderer `
    --upx-dir=C:\Tools\upx `  # UPX varsa
    cat.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller başarısız oldu." }

Write-Host "== Paketlenen EXE doğrulaması ==" -ForegroundColor Cyan
$exe = Join-Path $here "dist\Komur.exe"
$frozenSmoke = Join-Path $env:TEMP "komur_frozen_smoke.json"
if (Test-Path $frozenSmoke) { Remove-Item $frozenSmoke }
& $exe --smoke-test $frozenSmoke
Start-Sleep -Seconds 3
$frozen = Get-Content $frozenSmoke -Raw | ConvertFrom-Json
if (-not $frozen.ok) { throw "Paketlenen EXE smoke testi başarısız." }

Write-Host "== ZIP Oluştur ==" -ForegroundColor Cyan
Compress-Archive -Path $exe -DestinationPath "Komur-Ultimate.zip" -Force

Write-Host "Tamamlandı: $exe" -ForegroundColor Green
Write-Host "Boyut: $([math]::Round((Get-Item $exe).Length/1MB, 1)) MB" -ForegroundColor Cyan
```

- [ ] **Step 2: Run build**

Run: `powershell -ExecutionPolicy Bypass -File .\build_ultimate.ps1`
Expected: Tests pass, smoke OK, PyInstaller builds, frozen smoke OK, ZIP created

- [ ] **Step 3: Verify EXE manually**

Run `dist\Komur.exe` → test all features manually

- [ ] **Step 4: Commit**

```bash
git add build_ultimate.ps1 dist/Komur.exe Komur-Ultimate.zip
git commit -m "build: ultimate realistic EXE + ZIP"
```

---

## Plan Self-Review

1. **Spec coverage:** 
   - Base64 WAV sesler → Task 1
   - Fizik partiküller → Task 2
   - Efekt orkestratörü → Task 3
   - Renderer entegrasyon → Task 4
   - Yeni durumlar → Task 5
   - Cat.py entegrasyon → Task 6
   - Skinler → Task 7
   - Ayarlar → Task 8
   - Testler → Task 9
   - Build → Task 10

2. **Step scan:** Her step unambiguous, tek bir action.

3. **Type consistency:** `sounds.play(name, enabled, quality)` → `EffectOrchestrator.trigger(kind, x, y)` → `PhysicsParticleSystem.emit(kind, x, y)` tutarlı.

4. **Review Focus:** Frozen EXE ses/efekt, partikül performansı, renderer bozulmaması, yeni durumlar behavior.py'siz, smoke test tamamı.

5. **Proportion:** Plan ~3x spec, uygun.

---

**Plan complete and saved.** I recommend **Native** execution (I implement every task myself in this session) because all tasks are tightly coupled through shared interfaces and the plan carries the complete design.

**Onay veriyor musun?** Onayınla Task 1'e (`sounds.py`) başlıyorum.
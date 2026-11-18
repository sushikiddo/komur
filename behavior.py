"""Time-based, GUI-independent behavior for the desktop cat."""
from dataclasses import dataclass
import math
import random


@dataclass(frozen=True)
class Bounds:
    """Allowed inclusive range for the cat window's top-left corner."""
    left: float
    top: float
    right: float
    bottom: float


# Kendiliginden hareket profilleri. "normal" eski davranisa yakindir
# (tum ekranda gezinme); "sakin" yuvanin etrafinda seyrek ve yavas gezer.
ACTIVITY_PROFILES = {
    "sakin": {"radius": 250.0, "speed": 30.0, "wander": 50, "idle": 20.0},
    "normal": {"radius": None, "speed": 52.0, "wander": 30, "idle": 1.0},
    "hareketli": {"radius": None, "speed": 70.0, "wander": 40, "idle": 0.7},
}
IDLE_STATES = ("sit", "look", "groom")
HOME_RETURN_DISTANCE = 60.0
GOAL_SPEED = 150.0   # hedefli yuruyus (px/sn)
VERTICAL_SPEED = 400.0  # dikey fark ziplama gibi hizli kapanir


class CatBrain:
    STATES = ("wander", "sit", "look", "groom", "stretch", "sleep", "yawn", "play", "follow", "bored", "roll")

    def __init__(self, bounds, width=260, height=280, seed=None, activity="sakin"):
        self.width = max(1, width)
        self.height = max(1, height)
        self._rng = random.Random(seed)
        self.bounds = self._normalize_bounds(bounds)
        self.x = (self.bounds.left + self.bounds.right) / 2
        self.y = (self.bounds.top + self.bounds.bottom) / 2
        self.target_x = self.x
        self.target_y = self.y
        self.home_x, self.home_y = self.x, self.y
        self.activity = activity if activity in ACTIVITY_PROFILES else "sakin"
        self._free_roam = False
        self._goal = False
        self.state = "sit"
        self.elapsed = 0.0
        self.energy = 80.0
        self.happiness = 75.0
        self.paused = False
        self.facing = 1
        self.message = "Merhaba!"
        self.ball_x = self.width * 0.72
        self.ball_y = self.height * 0.78
        self._ball_vx, self._ball_vy = 100.0, -80.0
        self._duration = self._rng.uniform(2.0, 5.0)
        self._sleep_requested = False
        self._idle_seconds = 0.0

    @staticmethod
    def _normalize_bounds(bounds):
        return Bounds(
            min(bounds.left, bounds.right),
            min(bounds.top, bounds.bottom),
            max(bounds.left, bounds.right),
            max(bounds.top, bounds.bottom),
        )

    def _clamp(self, x, y):
        return (
            max(self.bounds.left, min(self.bounds.right, x)),
            max(self.bounds.top, min(self.bounds.bottom, y)),
        )

    def move_to(self, x, y):
        if math.isfinite(x) and math.isfinite(y):
            self.x, self.y = self._clamp(x, y)
            self.target_x, self.target_y = self.x, self.y
            self.home_x, self.home_y = self.x, self.y

    def set_activity(self, level):
        if level in ACTIVITY_PROFILES:
            self.activity = level

    def rest(self):
        """Dur ve otur (ornegin surukle-birak sonrasi): yeni yuvada dinlen."""
        self._sleep_requested = False
        self._change("sit")

    def settle(self, state):
        """Etkinlik tepkisi: kullanıcının açık komutunu (takip/oyun) bölmeden sakin bir duruma geç."""
        if state in self.STATES and state not in ("wander", "follow", "play") \
                and self.state not in ("follow", "play", state):
            self._sleep_requested = state == "sleep"
            self._change(state)

    def set_bounds(self, bounds):
        self.bounds = self._normalize_bounds(bounds)
        self.x, self.y = self._clamp(self.x, self.y)
        self.home_x, self.home_y = self._clamp(self.home_x, self.home_y)
        self.target_x, self.target_y = self._clamp(self.target_x, self.target_y)

    def _change(self, state, duration=None):
        self.state, self.elapsed = state, 0.0
        self._goal = False
        if state in ("bored", "roll"):
            self._idle_seconds = 0.0
        ranges = {
            "wander": (4, 10), "sit": (3, 8), "look": (2, 5),
            "groom": (4, 8), "stretch": (2, 4), "sleep": (20, 35),
            "yawn": (2, 4), "play": (10, 18), "follow": (float("inf"), float("inf")),
            "bored": (5, 9), "roll": (3, 5),
        }
        lo, hi = ranges[state]
        if duration is not None:
            self._duration = duration
        elif lo == hi:
            self._duration = lo
        else:
            self._duration = self._rng.uniform(lo, hi)
        if state in IDLE_STATES and duration is None:
            self._duration *= ACTIVITY_PROFILES[self.activity]["idle"]
        if state == "wander":
            self._pick_wander_target()

    def go_to(self, x, y, max_seconds=None):
        """Belirli bir noktaya yürü (oyuncak/kase); varınca oturur. Takip/oyun/uyku bölünmez."""
        if self.state in ("follow", "play", "sleep") or self.paused:
            return False
        self._sleep_requested = False
        tx, ty = self._clamp(x, y)
        if max_seconds is None:
            max_seconds = abs(tx - self.x) / GOAL_SPEED + 3.0
        self._change("wander", duration=max_seconds)
        self.target_x, self.target_y = tx, ty
        self._goal = True
        return True

    def _pick_wander_target(self):
        radius = ACTIVITY_PROFILES[self.activity]["radius"]
        if self._free_roam or radius is None:
            self.target_x = self._rng.uniform(self.bounds.left, self.bounds.right)
            self.target_y = self.y   # serbest gezinme de yalnız yatay
            return
        # kendiliginden gezinme: yuvadan uzaktaysa yuvaya don, degilse yakin bir nokta sec
        if math.hypot(self.x - self.home_x, self.y - self.home_y) > HOME_RETURN_DISTANCE:
            tx, ty = self.home_x, self.home_y
        else:
            angle = self._rng.uniform(0, 2 * math.pi)
            dist = self._rng.uniform(radius * 0.4, radius)
            tx = self.home_x + math.cos(angle) * dist
            ty = self.y
        self.target_x, self.target_y = self._clamp(tx, ty)

    def command(self, name):
        name = str(name).lower().strip()
        if name == "pause":
            self.paused = True
            self.message = "Duraklatıldı."
            return
        if name not in frozenset({"resume", "follow", "pet", "wake", "sleep", "play", "wander", "bored", "roll", "yawn"}):
            return
        self.paused = False
        self._free_roam = False
        if name == "resume":
            self.message = "Devam ediyorum!"
            return
        if name == "pet":
            self.happiness = min(100.0, self.happiness + 12)
            self._sleep_requested = False
            self._change("sit")
            self.message = "Mırıldıyorum!"
            return
        if name == "play":
            self._sleep_requested = False
            self._change("play")
            self.message = "Oynayalım!"
            return
        if name == "roll":
            self._sleep_requested = False
            self._change("roll")
            self.message = "Sırt üstü yuvarlanıyorum!"
            return
        if name == "bored":
            self._sleep_requested = False
            self._change("bored")
            self.message = "Biraz sıkıldım..."
            return
        if name == "yawn":
            self._sleep_requested = False
            self._change("yawn")
            self.message = "Esniyorum..."
            return
        if name == "follow":
            self._sleep_requested = False
            self._change("follow")
            self.message = "Seni takip ediyorum!"
            return
        if name == "sleep":
            self._sleep_requested = True
            self._change("sleep")
            self.message = "İyi geceler..."
            return
        if name == "wake":
            self._sleep_requested = False
            self._change("stretch")
            self.message = "Günaydın!"
            return
        if name == "wander":
            self._sleep_requested = False
            self._free_roam = True  # acik komut: tum ekranda gezinebilir
            self._change("wander")
            self.message = "Biraz dolaşayım."
            return

    def _move_towards(self, x, y, speed, dt):
        x, y = self._clamp(x, y)
        self.target_x, self.target_y = x, y
        dx = x - self.x
        dy = y - self.y
        distance = math.hypot(dx, dy)
        if distance > 1e-09:
            amount = min(distance, speed * dt)
            self.x += dx / distance * amount
            self.y += dy / distance * amount
            if abs(dx) > 1:
                self.facing = 1 if dx > 0 else -1
        self.x, self.y = self._clamp(self.x, self.y)
        return distance

    def _walk_towards(self, x, y, speed, dt):
        """Yatayda yuru, dikey farki hizla kapat (havada capraz yuruyus yok). Kalan mesafeyi dondurur."""
        x, y = self._clamp(x, y)
        self.target_x, self.target_y = x, y
        dx, dy = x - self.x, y - self.y
        if abs(dx) > 1:
            self.facing = 1 if dx > 0 else -1
        self.x += math.copysign(min(abs(dx), speed * dt), dx) if dx else 0.0
        self.y += math.copysign(min(abs(dy), VERTICAL_SPEED * dt), dy) if dy else 0.0
        self.x, self.y = self._clamp(self.x, self.y)
        return max(abs(x - self.x), abs(y - self.y))

    def _follow(self, pointer, dt):
        if pointer is None:
            return
        try:
            px, py = pointer
            if not (math.isfinite(px) and math.isfinite(py)):
                return
        except (TypeError, ValueError):
            return
        cx = self.x + self.width / 2
        cy = self.y + self.height / 2
        dx = px - cx
        dy = py - cy
        distance = math.hypot(dx, dy)
        if distance < 1e-09:
            dx, dy, distance = float(self.facing), 0.0, 1.0
        ux = dx / distance
        uy = dy / distance
        tx = (self.width / 2 + 105) / abs(ux) if ux else float("inf")
        ty = (self.height / 2 + 105) / abs(uy) if uy else float("inf")
        stand_off = min(tx, ty)
        if distance > stand_off + 8:
            self._move_towards(
                px - ux * stand_off - self.width / 2,
                py - uy * stand_off - self.height / 2,
                115, dt,
            )
            return
        self.target_x, self.target_y = self.x, self.y

    def _advance_ball(self, dt):
        radius = min(12.0, self.width / 2, self.height / 2)
        floor = self.height - radius
        self._ball_vy += self.height * 2.8 * dt
        self.ball_x += self._ball_vx * dt
        self.ball_y += self._ball_vy * dt
        if self.ball_x <= radius:
            self.ball_x, self._ball_vx = radius, abs(self._ball_vx) * .85
        elif self.ball_x >= self.width - radius:
            self.ball_x, self._ball_vx = self.width - radius, -abs(self._ball_vx) * .85
        if self.ball_y >= floor:
            self.ball_y = floor
            self._ball_vy = -abs(self._ball_vy) * .62
            self._ball_vx *= .90
            if abs(self._ball_vy) < 12:
                self._ball_vy = 0
        self.ball_y = max(radius, self.ball_y)
        phase = self.elapsed % 2.4
        self.pounce = max(0.0, 1.0 - abs(phase - 1.2) / .35)
        if phase >= 1.2 and phase - dt < 1.2:
            self._ball_vx = self._rng.choice((-1, 1)) * self.width * .65
            self._ball_vy = -self.height * self._rng.uniform(.55, .85)

    def _next_state(self):
        if self.state == "sleep":
            if self._sleep_requested and self.energy < 95:
                self._duration += 10
                return
            self._sleep_requested = False
            self._change("stretch")
            return
        if self.energy < 20:
            self._change("sleep" if self.state == "yawn" else "yawn")
            return
        if self._idle_seconds >= 30 and self.state in ("sit", "look", "groom", "yawn", "bored"):
            self._idle_seconds = 0.0
            self._change(self._rng.choices(("bored", "roll"), weights=(3, 2), k=1)[0])
            return
        self._free_roam = False
        choices = ["wander", "sit", "look", "groom", "stretch", "play"]
        weights = [ACTIVITY_PROFILES[self.activity]["wander"], 23, 15, 13, 8,
                   (11 if self.happiness < 65 else 5)]
        if self.energy < 35:
            choices.append("yawn")
            weights.append(30)
        self._change(self._rng.choices(choices, weights=weights, k=1)[0])

    def step(self, dt, pointer=None):
        if self.paused:
            return
        try:
            dt = float(dt)
            if not math.isfinite(dt) or dt <= 0:
                return
        except (TypeError, ValueError):
            return
        dt = min(dt, 0.1)
        self.elapsed += dt
        if self.state in ("sit", "look", "groom", "yawn", "bored"):
            self._idle_seconds += dt
        elif self.state not in ("roll",):
            self._idle_seconds = 0.0
        if self.state == "sleep":
            self.energy += 2.0 * dt
        elif self.state == "play":
            self.energy -= 0.7 * dt
            self.happiness += 0.9 * dt
            self._advance_ball(dt)
        else:
            self.energy -= (0.22 if self.state in ("wander", "follow") else 0.08) * dt
            self.happiness -= 0.025 * dt
        self.energy = max(0.0, min(100.0, self.energy))
        self.happiness = max(0.0, min(100.0, self.happiness))
        if self.state == "wander":
            if self._goal:
                speed = GOAL_SPEED
            else:
                speed = 52 if self._free_roam else ACTIVITY_PROFILES[self.activity]["speed"]
            remaining = self._walk_towards(self.target_x, self.target_y, speed, dt)
            if remaining <= 2:
                self._change("sit")
        elif self.state == "follow":
            self._follow(pointer, dt)
        if self.elapsed >= self._duration:
            self._next_state()

"""Logica di movimento (pura, senza Qt): passeggiate, pause, schivata del cursore."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass
class Step:
    x: float
    y: float
    vx: float
    vy: float
    moving: bool
    event: str | None = None  # "wave" quando decide di salutare


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _rect_distance(px: float, py: float, x: float, y: float, w: float, h: float) -> float:
    dx = max(x - px, 0.0, px - (x + w))
    dy = max(y - py, 0.0, py - (y + h))
    return math.hypot(dx, dy)


def _approach(pos: float, target: float, speed: float, dt: float) -> tuple[float, float, bool]:
    """Muove pos verso target. Ritorna (nuova_pos, velocità, arrivato)."""
    d = target - pos
    step = speed * dt
    if abs(d) <= step:
        return target, (d / dt if dt > 0 else 0.0), True
    s = 1.0 if d > 0 else -1.0
    return pos + s * step, s * speed, False


class Behavior:
    DODGE_SPEED_MULT = 3.5

    def __init__(self, cfg: dict, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.speed = float(cfg["walk_speed_px_s"])
        self.idle_min = float(cfg["idle_min_s"])
        self.idle_max = max(self.idle_min, float(cfg["idle_max_s"]))
        self.avoid = float(cfg["avoid_cursor_distance_px"])
        self.wave_chance = float(cfg["wave_chance"])
        self.paused = False
        self.mode = "idle"
        self.timer = self._idle_time()
        self.target_y = 0.0

    def _idle_time(self) -> float:
        return self.rng.uniform(self.idle_min, self.idle_max)

    def hold(self, seconds: float) -> None:
        """Resta ferma (in idle) per qualche secondo."""
        self.mode = "idle"
        self.timer = seconds

    def update(self, dt: float, x: float, y: float, w: float, h: float,
               rest_x: float, ymin: float, ymax: float,
               cursor: tuple[float, float], allow_dodge: bool = True) -> Step:
        cx, cy = cursor
        vx = vy = 0.0
        event = None

        # Torna al bordo destro (es. dopo essere stata trascinata altrove)
        if abs(rest_x - x) > 0.5:
            x, vx, _ = _approach(x, rest_x, self.speed * 1.5, dt)

        dist = _rect_distance(cx, cy, x, y, w, h)
        if allow_dodge and self.avoid > 0 and dist < self.avoid:
            self.mode = "dodge"

        if self.mode == "dodge":
            if not allow_dodge or dist > self.avoid * 1.4:
                self.hold(self.rng.uniform(1.5, 3.0))
            else:
                ty = self._dodge_target(cy, h, ymin, ymax, go_down=cy < y + h / 2)
                y, vy, _ = _approach(y, ty, self.speed * self.DODGE_SPEED_MULT, dt)
        elif self.mode == "walk":
            y, vy, arrived = _approach(y, self.target_y, self.speed, dt)
            if arrived:
                self.hold(self._idle_time())
        elif not self.paused:  # idle
            self.timer -= dt
            if self.timer <= 0:
                if self.rng.random() < self.wave_chance:
                    event = "wave"
                    self.timer = self._idle_time()
                else:
                    self._pick_walk_target(y, ymin, ymax)

        y = _clamp(y, ymin, max(ymin, ymax))
        moving = abs(vx) > 1 or abs(vy) > 1
        return Step(x, y, vx, vy, moving, event)

    def _pick_walk_target(self, y: float, ymin: float, ymax: float) -> None:
        span = ymax - ymin
        if span < 10:
            self.timer = self._idle_time()
            return
        min_d = min(120.0, span / 3)
        for _ in range(10):
            ty = self.rng.uniform(ymin, ymax)
            if abs(ty - y) >= min_d:
                break
        self.target_y = ty
        self.mode = "walk"

    def _dodge_target(self, cy: float, h: float, ymin: float, ymax: float, go_down: bool) -> float:
        gap = self.avoid + 12
        down = cy + gap
        up = cy - gap - h
        if go_down:
            return down if down <= ymax else (up if up >= ymin else ymax)
        return up if up >= ymin else (down if down <= ymax else ymin)

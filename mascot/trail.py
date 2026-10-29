"""Traccia del percorso recente della mascotte, per l'effetto "ritardo" delle perline.

Ogni perlina si disegna dove si trovava la mascotte qualche frazione di secondo
prima: più è lontana dalla testa, più è in ritardo, così la catena si allunga
seguendo il percorso (ad esempio quello del mouse durante il trascinamento).
"""
from __future__ import annotations

import math
from collections import deque


class Trail:
    def __init__(self, max_age: float = 1.0) -> None:
        self.max_age = max_age
        self._pts: deque[tuple[float, float, float]] = deque()

    def clear(self) -> None:
        self._pts.clear()

    def push(self, t: float, x: float, y: float) -> None:
        self._pts.append((t, x, y))
        # tieni un punto più vecchio di max_age, serve per interpolare
        while len(self._pts) > 2 and self._pts[1][0] < t - self.max_age:
            self._pts.popleft()

    def _at(self, t: float) -> tuple[float, float]:
        pts = self._pts
        if t <= pts[0][0]:
            return pts[0][1], pts[0][2]
        for i in range(len(pts) - 1, 0, -1):
            t0, x0, y0 = pts[i - 1]
            t1, x1, y1 = pts[i]
            if t0 <= t <= t1:
                k = (t - t0) / (t1 - t0) if t1 > t0 else 1.0
                return x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
        return pts[-1][1], pts[-1][2]

    def offset(self, delay: float) -> tuple[float, float]:
        """Dov'era la mascotte `delay` secondi fa, rispetto a ora (in pixel)."""
        if len(self._pts) < 2 or delay <= 0:
            return 0.0, 0.0
        now, x, y = self._pts[-1]
        px, py = self._at(now - delay)
        return px - x, py - y

    def lag_function(self, scale: float, max_delay: float, cap: float):
        """Funzione delay_relativo (0..1) -> offset in unità di progetto, con limite morbido `cap`."""
        def lag(rel: float) -> tuple[float, float]:
            dx, dy = self.offset(rel * max_delay)
            dx, dy = dx / scale, dy / scale
            mag = math.hypot(dx, dy)
            if mag > 1e-6:
                k = cap * math.tanh(mag / cap) / mag
                dx, dy = dx * k, dy * k
            return dx, dy
        return lag

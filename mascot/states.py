"""Macchina a stati delle animazioni di Elyca."""
from __future__ import annotations

import math
import random
from enum import Enum

from mascot.painter import Pose


class State(Enum):
    IDLE = "idle"
    WALK = "walk"
    WAVE = "wave"
    TALK = "talk"
    SLEEP = "sleep"
    THINK = "think"
    LISTEN = "listen"


class Animator:
    """Tiene il tempo e le fasi delle animazioni e produce una Pose per fotogramma.

    La finestra imposta lo stato "di base" (idle/walk/talk/sleep); il saluto
    (wave) è temporaneo e si sovrappone a idle/walk per la sua durata.
    """

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.state = State.IDLE
        self.base = State.IDLE
        self.t = 0.0
        self.state_t = 0.0
        self.helix_phase = 0.0
        self.step_phase = 0.0
        self.wave_left = 0.0
        self.look_x = self.look_y = 0.0
        self._look_tx = self._look_ty = 0.0
        self._blink_t = -1.0
        self._next_blink = self.rng.uniform(2.0, 5.0)

    # --- comandi -------------------------------------------------------------
    def set_base(self, state: State) -> None:
        self.base = state

    def wave(self, duration: float = 2.0) -> None:
        self.wave_left = max(self.wave_left, duration)

    @property
    def waving(self) -> bool:
        return self.wave_left > 0 and self.base in (State.IDLE, State.WALK)

    def set_look(self, x: float, y: float) -> None:
        self._look_tx, self._look_ty = x, y

    # --- avanzamento ---------------------------------------------------------
    def tick(self, dt: float, speed: float = 0.0, direction: float = 1.0) -> None:
        self.t += dt
        self.wave_left = max(0.0, self.wave_left - dt)
        state = State.WAVE if self.waving else self.base
        if state != self.state:
            self.state = state
            self.state_t = 0.0
        else:
            self.state_t += dt

        if state == State.WALK:
            # la doppia elica "ruota" facendo scorrere la fase
            self.helix_phase += dt * (3.0 + speed * 0.06) * (1 if direction >= 0 else -1)
            self.step_phase += dt * (6.0 + speed * 0.08)
        elif state == State.SLEEP:
            self.helix_phase += dt * 0.1
        elif state == State.THINK:
            self.helix_phase += dt * 1.6  # l'elica gira mentre "elabora"
        else:
            self.helix_phase += dt * 0.4

        # sbattere le palpebre
        if state != State.SLEEP:
            self._next_blink -= dt
            if self._next_blink <= 0:
                self._blink_t = 0.0
                self._next_blink = self.rng.uniform(2.5, 6.0)
            if self._blink_t >= 0:
                self._blink_t += dt
                if self._blink_t > 0.18:
                    self._blink_t = -1.0

        k = 1 - math.exp(-dt * 8)
        self.look_x += (self._look_tx - self.look_x) * k
        self.look_y += (self._look_ty - self.look_y) * k

    def pose(self) -> Pose:
        t, st = self.t, self.state
        blink = math.sin(self._blink_t / 0.18 * math.pi) if self._blink_t >= 0 else 0.0
        pose = Pose(t=t, helix_phase=self.helix_phase, step_phase=self.step_phase,
                    blink=blink, look_x=self.look_x, look_y=self.look_y)
        if st == State.IDLE:
            pose.sway_deg = 2.5 * math.sin(t * 1.3)
            pose.bob = 1.5 * math.sin(t * 2.6)
            pose.tail_swing = 3 * math.sin(t * 1.3 + 0.8)
        elif st == State.WALK:
            pose.walking = True
            pose.sway_deg = 4 * math.sin(self.step_phase)
            pose.bob = -2 * abs(math.sin(self.step_phase))
            pose.tail_swing = 5 * math.sin(self.step_phase + 1.0)
            pose.ripple = 0.6
        elif st == State.WAVE:
            pose.wave_t = self.state_t
            pose.sway_deg = 3 * math.sin(t * 2.0)
            pose.mouth_open = 0.85
        elif st == State.TALK:
            pose.sway_deg = 1.5 * math.sin(t * 1.6)
            pose.bob = 1.0 * math.sin(t * 3.0)
            pose.mouth_open = 0.2 + 0.7 * abs(math.sin(t * 11))
            pose.ripple = 0.7
        elif st == State.THINK:
            # "sto pensando": guarda in alto a destra, nuvoletta di pensiero a puntini
            pose.think_t = self.state_t
            pose.look_x, pose.look_y = 0.7, -0.9
            pose.mouth_open = 0.12
            pose.sway_deg = 2 * math.sin(t * 1.1)
            pose.bob = 1.0 * math.sin(t * 2.2)
            pose.ripple = 1.4
        elif st == State.LISTEN:
            # "ti ascolto": occhi verso l'utente, boccuccia a "o", onde sonore che arrivano
            pose.listen_t = self.state_t
            pose.look_x, pose.look_y = -0.6, 0.0
            pose.mouth_open = 0.3
            pose.sway_deg = 1.5 * math.sin(t * 2.0)
            pose.ripple = 0.5
        elif st == State.SLEEP:
            pose.eyes_closed = True
            pose.blink = 0.0
            pose.mouth_open = 0.0
            pose.sway_deg = 1.5 * math.sin(t * 0.7)
            pose.bob = 1.5 * math.sin(t * 0.9)
            pose.ripple = 0.3
            pose.zzz_t = self.state_t
            pose.look_x = pose.look_y = 0.0
        return pose

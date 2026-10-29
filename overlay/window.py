"""Finestra overlay della mascotte: trasparente, click-through, mai attiva.

La finestra è più grande della mascotte: attorno c'è un margine trasparente
in cui possono finire le perline "in ritardo" quando si muove o viene trascinata.
Le coordinate _fx/_fy sono quelle del canvas della mascotte, non della finestra.
"""
from __future__ import annotations

import logging
import math
from ctypes import wintypes

from PySide6.QtCore import QElapsedTimer, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

from brain import Brain
from i18n import t
from mascot.behavior import Behavior
from mascot.painter import CANVAS, HEAD_X, HEAD_Y, LAG_CAP, LAG_MARGIN, VISUAL_HEIGHT, draw_mascot
from mascot.states import Animator, State
from mascot.trail import Trail
from overlay import win32
from overlay.bubbles import InputBubble, SpeechBubble
from voice import Voice

log = logging.getLogger(__name__)

HOTKEY_CHAT = 1
HOTKEY_PTT = 2
SLEEP_FPS = 12


def _event_type_bytes(event_type) -> bytes:
    if isinstance(event_type, (bytes, bytearray)):
        return bytes(event_type)
    data = getattr(event_type, "data", None)
    return data() if callable(data) else bytes(event_type)


class MascotWindow(QWidget):
    notify = Signal(str, str)  # (titolo, messaggio) per il tray
    menu_requested = Signal(QPoint)  # Ctrl + tasto destro sulla mascotte: apre il menu del tray

    def __init__(self, cfg: dict) -> None:
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)
        self.setWindowTitle("Elyca")
        self.setCursor(Qt.OpenHandCursor)  # visibile solo con Ctrl premuto

        self.cfg = cfg
        m = cfg["mascot"]
        self.mcfg = m
        self.scale = float(m["height_px"]) / VISUAL_HEIGHT
        self.msize = math.ceil(CANVAS * self.scale)          # lato del canvas della mascotte
        self.trail_delay = max(0.0, float(m["trail_delay_s"]))
        self.margin = math.ceil(LAG_MARGIN * self.scale) if self.trail_delay > 0 else 0
        self.setFixedSize(self.msize + 2 * self.margin, self.msize + 2 * self.margin)
        self.fps = max(5, int(m["fps"]))

        self.animator = Animator()
        self.behavior = Behavior(m)
        self.trail = Trail(max_age=self.trail_delay + 0.2)
        self.brain = Brain(cfg["brain"])
        self.brain.chunk.connect(self._on_brain_chunk)
        self.brain.finished.connect(self._on_brain_finished)
        self.brain.failed.connect(self._on_brain_failed)
        self.brain.status.connect(self._on_brain_status)
        self._req_id = 0
        self._thinking = False

        self.voice = Voice(cfg["voice"])
        self.voice.transcribed.connect(self._on_transcribed)
        self.voice.failed.connect(self._on_voice_failed)
        self.voice.status.connect(self._on_voice_status)
        self.voice.speaking_changed.connect(self._on_speaking_changed)
        self._listening = False      # push-to-talk premuto, sto registrando
        self._transcribing = False
        self._speaking = False
        self._ptt_vk = 0
        self._ptt_ok = False
        self.bubble = SpeechBubble(cfg["bubble"])
        self.input = InputBubble(float(cfg["bubble"]["font_size_pt"]),
                                 float(cfg["bubble"]["conversation_timeout_s"]))
        self.input.closed.connect(lambda: self.bubble.set_sticky(False))
        self.bubble.revealed.connect(self._on_reveal_done)
        self.bubble.finished.connect(self._on_reveal_done)
        self.input.submitted.connect(self._on_submit)

        self._time = 0.0
        self._dragging = False
        self._drag_offset = QPoint()
        self._clickthrough = True
        self._talking = False
        self._user_hidden = False
        self._fs_hidden = False
        self._forced_sleep = False
        self._auto_sleep = False
        self._hotkey_ok = False

        # posizione iniziale: bordo destro del monitor principale, altezza casuale
        geom = QGuiApplication.primaryScreen().availableGeometry()
        self._fx = float(self._rest_x(geom))
        span = max(0, geom.height() - self.msize)
        self._fy = float(geom.top() + self.behavior.rng.uniform(0.3, 0.8) * span)
        self._place()

        self._clock = QElapsedTimer()
        self.frame_timer = QTimer(self)
        self.frame_timer.setTimerType(Qt.PreciseTimer)
        self.frame_timer.setInterval(1000 // self.fps)
        self.frame_timer.timeout.connect(self._on_frame)
        self.slow_timer = QTimer(self)
        self.slow_timer.setInterval(1000)
        self.slow_timer.timeout.connect(self._on_slow)

    # ------------------------------------------------------------------ avvio/stop
    def start(self) -> None:
        self.show()
        hwnd = self._hwnd()
        ex = win32.configure_overlay(hwnd, clickthrough=True)
        if not ex & win32.WS_EX_LAYERED:
            log.warning("La finestra non è layered: il click-through potrebbe non funzionare")
        log.info("Overlay pronto: finestra %dx%d px, mascotte %d px, scala %.2f, exstyle=0x%08X",
                 self.width(), self.height(), self.msize, self.scale, ex & 0xFFFFFFFF)
        spec = self.cfg["hotkeys"]["chat"]
        self._hotkey_ok = win32.register_hotkey(hwnd, HOTKEY_CHAT, spec)
        if not self._hotkey_ok:
            QTimer.singleShot(1500, lambda: self.notify.emit(
                "Elyca", t("hotkey_failed", spec=spec)))
        if self.voice.enabled:
            ptt = self.cfg["hotkeys"]["push_to_talk"]
            self._ptt_ok = win32.register_hotkey(hwnd, HOTKEY_PTT, ptt)
            if self._ptt_ok:
                self._ptt_vk = win32.parse_hotkey(ptt)[1]
            else:
                QTimer.singleShot(3000, lambda: self.notify.emit(
                    "Elyca", t("hotkey_failed", spec=ptt)))
        self._clock.start()
        self.frame_timer.start()
        self.slow_timer.start()
        self.animator.wave(2.0)

    def shutdown(self) -> None:
        self.frame_timer.stop()
        self.slow_timer.stop()
        if self._hotkey_ok:
            win32.unregister_hotkey(self._hwnd(), HOTKEY_CHAT)
        if self._ptt_ok:
            win32.unregister_hotkey(self._hwnd(), HOTKEY_PTT)
        if self._listening:
            self.voice.stop_recording()
        self.voice.stop_speaking()
        self.brain.cancel()
        self.input.cancel(restore_focus=False)
        self.bubble.dismiss()

    # ------------------------------------------------------------------ comandi (tray)
    @property
    def user_hidden(self) -> bool:
        return self._user_hidden

    def set_user_hidden(self, hidden: bool) -> None:
        self._user_hidden = hidden
        self._sync_visibility()

    @property
    def paused(self) -> bool:
        return self.behavior.paused

    def set_paused(self, paused: bool) -> None:
        self.behavior.paused = paused
        log.info("Movimento %s", "in pausa" if paused else "ripreso")

    @property
    def forced_sleep(self) -> bool:
        return self._forced_sleep

    def set_forced_sleep(self, sleep: bool) -> None:
        self._forced_sleep = sleep
        if sleep:
            self._cancel_request()
            self.input.cancel(restore_focus=False)
            self.bubble.dismiss()
        else:
            self._auto_sleep = False
            self.animator.wave(1.5)
        self._update_frame_rate()

    # ------------------------------------------------------------------ utilità
    def _hwnd(self) -> int:
        return int(self.winId())

    def _place(self) -> None:
        x, y = int(self._fx) - self.margin, int(self._fy) - self.margin
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

    def mascot_rect(self) -> QRect:
        """Area del canvas della mascotte in coordinate globali (senza il margine)."""
        return QRect(self.x() + self.margin, self.y() + self.margin, self.msize, self.msize)

    def _screen_geom(self) -> QRect:
        center = self.mascot_rect().center()
        screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
        return screen.availableGeometry()

    def _rest_x(self, geom: QRect) -> int:
        # il canvas ha un margine trasparente a destra: lo recuperiamo in parte
        pad = int(12 * self.scale)
        return geom.right() + 1 - self.msize + pad - int(self.mcfg["edge_margin_px"])

    def _head_y(self) -> int:
        return self.mascot_rect().top() + int(HEAD_Y * self.scale)

    def _bubble_inset(self) -> int:
        return int(30 * self.scale)

    @property
    def sleeping(self) -> bool:
        return self._forced_sleep or self._auto_sleep

    # ------------------------------------------------------------------ ciclo animazione
    def _on_frame(self) -> None:
        dt = min(self._clock.restart() / 1000.0, 0.1)
        self._time += dt
        cursor = QCursor.pos()
        ctrl = win32.is_ctrl_down()
        geom = self._screen_geom()
        size = self.msize
        ymin = geom.top() - int(40 * self.scale)  # la parte alta del canvas è vuota
        ymax = geom.bottom() + 1 - size

        self._update_clickthrough(ctrl, cursor)

        # push-to-talk: si registra finché il tasto resta premuto
        if self._listening and (not win32.is_key_down(self._ptt_vk) or self.voice.recording_full):
            self._end_listening()

        busy = (self._dragging or self.input.isVisible() or self.bubble.isVisible()
                or self._thinking or self._listening or self._transcribing or self._speaking
                or self.sleeping or self.animator.waving)
        speed, direction = 0.0, 1.0
        moving = False
        if not busy:
            step = self.behavior.update(dt, self._fx, self._fy, size, size, self._rest_x(geom),
                                        ymin, ymax, (cursor.x(), cursor.y()), allow_dodge=not ctrl)
            self._fx, self._fy = step.x, step.y
            moving = step.moving
            speed = math.hypot(step.vx, step.vy)
            direction = step.vy if abs(step.vy) > 0.1 else step.vx
            if step.event == "wave":
                self.animator.wave(2.0)
        if not self._dragging:
            # resta nello schermo anche se cambia risoluzione o monitor
            self._fx = max(geom.left() - size / 2, min(geom.right() + 1 - size / 2, self._fx))
            self._fy = max(ymin, min(max(ymin, ymax), self._fy))
        old_pos = self.pos()
        self._place()
        if self.pos() != old_pos and self.bubble.isVisible():
            self.bubble.follow(self.mascot_rect(), self._head_y(), geom, self._bubble_inset())
        if self.input.isVisible() and self.bubble.isVisible():
            # risposta lunga: la casella scende sotto il fumetto invece di esserne coperta
            bottom = self.bubble.frameGeometry().bottom() + 6
            if self.input.y() < bottom:
                self.input.move_top_to(bottom, geom)
        self.trail.push(self._time, self._fx, self._fy)

        if self.sleeping:
            base = State.SLEEP
        elif self._listening:
            base = State.LISTEN
        elif self._thinking or self._transcribing:
            base = State.THINK
        elif self._talking or self._speaking:
            base = State.TALK
        elif moving:
            base = State.WALK
        else:
            base = State.IDLE
        self.animator.set_base(base)

        # gli occhi seguono il cursore
        hx = self._fx + HEAD_X * self.scale
        hy = self._fy + HEAD_Y * self.scale
        dx, dy = cursor.x() - hx, cursor.y() - hy
        dist = math.hypot(dx, dy) or 1.0
        k = min(1.0, dist / 150.0) / dist
        self.animator.set_look(dx * k, dy * k)

        self.animator.tick(dt, speed, direction)
        self.update()

    def _on_slow(self) -> None:
        hwnd = self._hwnd()
        if self.cfg["overlay"]["hide_on_fullscreen"]:
            fs = win32.foreground_is_fullscreen(hwnd)
            if fs != self._fs_hidden:
                self._fs_hidden = fs
                log.info("App a schermo intero %s", "rilevata: mi nascondo" if fs else "chiusa: ricompaio")
                self._sync_visibility()

        minutes = float(self.mcfg["sleep_after_minutes"])
        if minutes > 0 and not self._forced_sleep:
            idle = win32.idle_seconds()
            chatting = (self.input.isVisible() or self._thinking or self.bubble.isVisible()
                        or self._listening or self._transcribing or self._speaking)
            if not self._auto_sleep and idle >= minutes * 60 and not chatting:
                self._auto_sleep = True
                self.bubble.dismiss()
                log.info("Nessuna attività da %.0f min: Elyca si addormenta", minutes)
                self._update_frame_rate()
            elif self._auto_sleep and idle < 2:
                self._auto_sleep = False
                self.animator.wave(1.5)
                self._update_frame_rate()

        if self.isVisible():
            win32.configure_overlay(hwnd, self._clickthrough)

    def _update_frame_rate(self) -> None:
        fps = SLEEP_FPS if self.sleeping else self.fps
        self.frame_timer.setInterval(1000 // fps)

    def _sync_visibility(self) -> None:
        should_show = not self._user_hidden and not self._fs_hidden
        if should_show and not self.isVisible():
            self.trail.clear()
            self.show()
            win32.configure_overlay(self._hwnd(), self._clickthrough)
            self._clock.restart()
            self.frame_timer.start()
        elif not should_show and self.isVisible():
            self.frame_timer.stop()
            self._cancel_request()
            self.input.cancel(restore_focus=False)
            self.bubble.dismiss()
            self.hide()

    # ------------------------------------------------------------------ click-through e drag
    def _update_clickthrough(self, ctrl: bool, cursor: QPoint) -> None:
        interactive = self._dragging or (ctrl and self.mascot_rect().contains(cursor))
        clickthrough = not interactive
        if clickthrough != self._clickthrough:
            self._clickthrough = clickthrough
            win32.configure_overlay(self._hwnd(), clickthrough)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.RightButton and win32.is_ctrl_down():
            # accesso al menu anche quando l'icona del tray è nascosta da Windows
            self.menu_requested.emit(event.globalPosition().toPoint())
            event.accept()
            return
        if event.button() == Qt.LeftButton and win32.is_ctrl_down():
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - QPoint(int(self._fx), int(self._fy))
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if not self._dragging:
            return
        if not win32.is_ctrl_down():
            self._end_drag()
            return
        pos = event.globalPosition().toPoint() - self._drag_offset
        self._fx, self._fy = float(pos.x()), float(pos.y())
        self._place()

    def mouseReleaseEvent(self, event) -> None:
        if self._dragging and event.button() == Qt.LeftButton:
            self._end_drag()

    def _end_drag(self) -> None:
        self._dragging = False
        self.setCursor(Qt.OpenHandCursor)
        self.behavior.hold(2.5)  # poi torna camminando verso il bordo destro
        log.info("Trascinata in (%d, %d)", int(self._fx), int(self._fy))

    # ------------------------------------------------------------------ hotkey e fumetti
    def nativeEvent(self, event_type, message):
        try:
            if _event_type_bytes(event_type) == b"windows_generic_MSG":
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == win32.WM_HOTKEY and msg.wParam == HOTKEY_CHAT:
                    self._on_chat_hotkey()
                    return True, 0
                if msg.message == win32.WM_HOTKEY and msg.wParam == HOTKEY_PTT:
                    self._on_ptt_hotkey()
                    return True, 0
        except Exception:
            log.exception("Errore gestendo un messaggio nativo")
        return super().nativeEvent(event_type, message)

    def _on_chat_hotkey(self) -> None:
        if self.input.isVisible():
            self.input.cancel(restore_focus=True)
            return
        if self._fs_hidden:
            log.info("Hotkey ignorata: app a schermo intero in primo piano")
            return
        if self._user_hidden:
            self.set_user_hidden(False)
        prev = win32.get_foreground_window()
        if self.sleeping:
            self._forced_sleep = self._auto_sleep = False
            self._update_frame_rate()
        self._cancel_request()
        self.bubble.dismiss()
        self.animator.wave(1.2)
        self.input.open_beside(self.mascot_rect(), self._head_y(), self._screen_geom(),
                               self._bubble_inset(), prev)

    def _on_submit(self, text: str) -> None:
        log.info("Domanda: %s", text)
        self.voice.stop_speaking()
        self._req_id = self.brain.ask(text)
        self._thinking = True
        self._talking = False
        self.bubble.begin(self.mascot_rect(), self._head_y(), self._screen_geom(), self._bubble_inset(),
                          dock=self._bubble_dock(), sticky=self.input.isVisible())

    def _bubble_dock(self):
        """In conversazione il fumetto di risposta sta sopra la casella di testo."""
        return self.input.frameGeometry() if self.input.isVisible() else None

    def _cancel_request(self) -> None:
        if self._thinking or self.bubble.isVisible():
            self.brain.cancel()
        self.voice.stop_speaking()
        self._req_id = 0
        self._thinking = False

    def _on_brain_chunk(self, req_id: int, text: str) -> None:
        if req_id != self._req_id:
            return
        if self._thinking:
            self._thinking = False
            self._talking = True
        self.bubble.append(text)

    def _on_brain_finished(self, req_id: int, answer: str) -> None:
        if req_id != self._req_id:
            return
        log.info("Risposta (%d caratteri)", len(answer))
        self._thinking = False
        self.bubble.end()
        self.voice.speak(answer)

    def _on_brain_status(self, req_id: int, message: str) -> None:
        if req_id == self._req_id:
            self.bubble.set_status(message)

    def _on_brain_failed(self, req_id: int, message: str) -> None:
        if req_id != self._req_id:
            return
        log.warning("Risposta non riuscita: %s", message)
        self._thinking = False
        self._talking = True
        self.bubble.dismiss()
        self.say(message)

    def say(self, text: str) -> None:
        self._talking = True
        self.bubble.show_text(text, self.mascot_rect(), self._head_y(), self._screen_geom(),
                              self._bubble_inset(), dock=self._bubble_dock(),
                              sticky=self.input.isVisible())

    def _on_reveal_done(self) -> None:
        self._talking = False

    # ------------------------------------------------------------------ voce
    def _on_ptt_hotkey(self) -> None:
        if self._listening or self._fs_hidden or not self.voice.enabled:
            return
        if self._user_hidden:
            self.set_user_hidden(False)
        if self.sleeping:
            self._forced_sleep = self._auto_sleep = False
            self._update_frame_rate()
        # una nuova domanda vocale interrompe la risposta in corso
        self.voice.stop_speaking()
        if self._thinking:
            self._cancel_request()
        if not self.input.isVisible():
            self.bubble.dismiss()
        if self.voice.start_recording():
            self._listening = True

    def _end_listening(self) -> None:
        self._listening = False
        if self.voice.stop_recording():
            self._transcribing = True

    def _on_transcribed(self, text: str) -> None:
        self._transcribing = False
        text = text.strip()
        if not text:
            self.say(t("voice_not_understood"))
            return
        log.info("Dettato: %s", text)
        if self.input.isVisible():
            self.input.set_hint(t("input_heard", text=text))
            self.input.submit_text(text)
        else:
            self._on_submit(text)

    def _on_voice_failed(self, message: str) -> None:
        self._listening = self._transcribing = False
        self.say(message)

    def _on_voice_status(self, message: str) -> None:
        self.say(message)

    def _on_speaking_changed(self, speaking: bool) -> None:
        self._speaking = speaking

    # ------------------------------------------------------------------ disegno
    def paintEvent(self, _event) -> None:
        pose = self.animator.pose()
        if self.trail_delay > 0:
            pose.lag = self.trail.lag_function(self.scale, self.trail_delay, LAG_CAP)
        p = QPainter(self)
        p.translate(self.margin, self.margin)
        draw_mascot(p, pose, self.scale)
        p.end()

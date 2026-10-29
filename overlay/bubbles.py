"""Fumetti accanto alla mascotte: uno di sola lettura (click-through) e uno con
la casella di testo (l'unica finestra che prende il focus, solo su richiesta)."""
from __future__ import annotations

from PySide6.QtCore import QElapsedTimer, QEvent, QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLineEdit, QWidget

from i18n import t
from overlay import win32

TAIL = 14     # lunghezza della punta del fumetto
PAD_X = 14
PAD_Y = 10
RADIUS = 14
SHADOW = 3
EDGE = 2      # spazio per il bordo
OUTLINE = QColor(34, 34, 34)


def _body_rect(widget_rect: QRect, side: str) -> QRectF:
    r = QRectF(widget_rect).adjusted(EDGE, EDGE, -EDGE - SHADOW, -EDGE - SHADOW)
    if side == "right":
        return QRectF(r.left(), r.top(), r.width() - TAIL, r.height())
    return QRectF(r.left() + TAIL, r.top(), r.width() - TAIL, r.height())


def _paint_bubble(p: QPainter, widget_rect: QRect, side: str, tail_y: float) -> QRectF:
    body = _body_rect(widget_rect, side)
    path = QPainterPath()
    path.addRoundedRect(body, RADIUS, RADIUS)
    ty = max(body.top() + RADIUS, min(body.bottom() - RADIUS, tail_y))
    tail = QPainterPath()
    if side == "right":
        tip_x = body.right() + TAIL
        tail.moveTo(body.right() - 2, ty - 8)
        tail.lineTo(tip_x, ty + 1)
        tail.lineTo(body.right() - 2, ty + 7)
    else:
        tip_x = body.left() - TAIL
        tail.moveTo(body.left() + 2, ty - 8)
        tail.lineTo(tip_x, ty + 1)
        tail.lineTo(body.left() + 2, ty + 7)
    tail.closeSubpath()
    path = path.united(tail)

    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0, 45))
    p.drawPath(path.translated(SHADOW, SHADOW))
    p.setPen(QPen(OUTLINE, 2))
    p.setBrush(QColor(255, 255, 255))
    p.drawPath(path)
    return body


def place_beside(size: QSize, anchor: QRect, head_y: int, screen: QRect,
                 inset: int) -> tuple[QPoint, str, int]:
    """Posiziona un fumetto a lato della mascotte, verso il centro dello schermo.
    Ritorna (posizione, lato della punta, y della punta in coordinate locali)."""
    w, h = size.width(), size.height()
    if anchor.center().x() >= screen.center().x():
        side, x = "right", anchor.left() + inset - w
    else:
        side, x = "left", anchor.right() - inset
    y = head_y - h // 2
    x = max(screen.left(), min(screen.right() - w + 1, x))
    y = max(screen.top(), min(screen.bottom() - h + 1, y))
    return QPoint(x, y), side, head_y - y


class SpeechBubble(QWidget):
    """Fumetto di sola lettura: click-through, non prende mai il focus.

    Riceve il testo anche a pezzi (streaming): begin() -> append()... -> end().
    Il testo compare progressivamente; quando è tutto visibile e lo streaming è
    finito, il fumetto resta aperto per un tempo proporzionale alla lunghezza.
    """

    revealed = Signal()   # tutto il testo è visibile
    finished = Signal()   # il fumetto si è chiuso

    def __init__(self, cfg: dict) -> None:
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput
                         | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)
        self.cfg = cfg
        self.text_font = QFont("Segoe UI")
        self.text_font.setPointSizeF(float(cfg["font_size_pt"]))
        self._text = ""
        self._shown = 0.0
        self._streaming = False
        self._side = "right"
        self._tail_y = 0
        self._place_args: tuple | None = None
        self._dock: QRect | None = None   # se impostato: il fumetto sta appena sopra questo rettangolo
        self._sticky = False              # se True non si chiude da solo (conversazione aperta)
        self._done = False                # tutto il testo è stato mostrato
        self._is_status = False           # il testo attuale è un messaggio di stato provvisorio
        self._clock = QElapsedTimer()
        self._reveal = QTimer(self)
        self._reveal.setInterval(33)
        self._reveal.timeout.connect(self._on_reveal)
        self._hold = QTimer(self)
        self._hold.setSingleShot(True)
        self._hold.timeout.connect(self._close)

    # --- API ---------------------------------------------------------------
    def begin(self, anchor: QRect, head_y: int, screen: QRect, inset: int,
              dock: QRect | None = None, sticky: bool = False) -> None:
        """Prepara un nuovo fumetto vuoto; compare al primo testo ricevuto."""
        self._hold.stop()
        if self.isVisible():
            self.hide()  # via la risposta precedente: la nuova compare al primo testo
        self._dock, self._sticky, self._done = dock, sticky, False
        self._is_status = False
        self._text, self._shown, self._streaming = "", 0.0, True
        self._place_args = (anchor, head_y, screen, inset)
        self._clock.start()
        self._reveal.start()

    def set_status(self, text: str) -> None:
        """Mostra subito un messaggio provvisorio; il primo testo vero lo sostituisce."""
        self._text, self._shown, self._is_status = text, float(len(text)), True
        self._relayout()
        if not self.isVisible():
            self.show()
            win32.configure_overlay(int(self.winId()), clickthrough=True)

    def append(self, chunk: str) -> None:
        if self._is_status:
            self._text, self._shown, self._is_status = "", 0.0, False
        if not self._text:
            chunk = chunk.lstrip()
            if not chunk:
                return
        self._text += chunk
        self._relayout()
        if not self.isVisible():
            self.show()
            win32.configure_overlay(int(self.winId()), clickthrough=True)
        if not self._reveal.isActive():
            self._clock.restart()
            self._reveal.start()

    def end(self) -> None:
        self._streaming = False
        if not self._text:
            self._close()

    def show_text(self, text: str, anchor: QRect, head_y: int, screen: QRect, inset: int,
                  dock: QRect | None = None, sticky: bool = False) -> None:
        self.begin(anchor, head_y, screen, inset, dock, sticky)
        self.append(text)
        self.end()

    def set_sticky(self, sticky: bool) -> None:
        """Con la conversazione chiusa, il fumetto torna a chiudersi da solo."""
        self._sticky = sticky
        if not sticky:
            self._dock = None
            if self._done and self.isVisible() and not self._hold.isActive():
                self._start_hold()

    def follow(self, anchor: QRect, head_y: int, screen: QRect, inset: int) -> None:
        self._place_args = (anchor, head_y, screen, inset)
        if self.isVisible():
            self._relayout()

    def dismiss(self) -> None:
        if self.isVisible() or self._reveal.isActive() or self._streaming:
            self._close()

    # --- interni -----------------------------------------------------------
    def _relayout(self) -> None:
        if self._place_args is None:
            return
        anchor, head_y, screen, inset = self._place_args
        fm = QFontMetrics(self.text_font)
        max_w = int(self.cfg["max_width_px"])
        br = fm.boundingRect(QRect(0, 0, max_w, 100000), Qt.TextWordWrap, self._text)
        w = br.width() + 2 * PAD_X + TAIL + 2 * EDGE + SHADOW + 2
        h = min(br.height(), screen.height() - 40) + 2 * PAD_Y + 2 * EDGE + SHADOW
        if (w, h) != (self.width(), self.height()):
            self.setFixedSize(w, h)
        pos, self._side, self._tail_y = place_beside(self.size(), anchor, head_y, screen, inset)
        if self._dock is not None:
            # in conversazione: appena sopra la casella di testo, allineato al suo lato
            x = self._dock.right() - w + 1 if self._side == "right" else self._dock.left()
            y = max(screen.top(), self._dock.top() - 6 - h)
            pos = QPoint(max(screen.left(), min(screen.right() - w + 1, x)), y)
            self._tail_y = head_y - y
        if pos != self.pos():
            self.move(pos)
        self.update()

    def _on_reveal(self) -> None:
        dt = self._clock.restart() / 1000.0
        cps = max(1.0, float(self.cfg["chars_per_second"]))
        before = int(self._shown)
        self._shown = min(float(len(self._text)), self._shown + cps * dt)
        if int(self._shown) != before:
            self.update()
        if not self._streaming and self._text and int(self._shown) >= len(self._text):
            self._reveal.stop()
            self._done = True
            self.revealed.emit()
            if not self._sticky:
                self._start_hold()

    def _start_hold(self) -> None:
        hold = float(self.cfg["min_display_s"]) + float(self.cfg["seconds_per_char"]) * len(self._text)
        self._hold.start(int(hold * 1000))

    def _close(self) -> None:
        was_open = self._reveal.isActive() or self._streaming
        self._reveal.stop()
        self._hold.stop()
        self._streaming = False
        self._done = False
        self.hide()
        if was_open:
            self.revealed.emit()
        self.finished.emit()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        body = _paint_bubble(p, self.rect(), self._side, self._tail_y)
        p.setFont(self.text_font)
        p.setPen(OUTLINE)
        p.drawText(body.adjusted(PAD_X, PAD_Y, -PAD_X, -PAD_Y),
                   Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, self._text[: int(self._shown)])
        p.end()


class InputBubble(QWidget):
    """Fumetto con casella di testo. Prende il focus SOLO quando aperto con la hotkey;
    Invio invia, Esc chiude e restituisce il focus all'app precedente."""

    submitted = Signal(str)
    closed = Signal()

    def __init__(self, font_pt: float, idle_timeout_s: float = 120.0) -> None:
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(340, 58)
        font = QFont("Segoe UI")
        font.setPointSizeF(font_pt)
        self.edit = QLineEdit(self)
        self.edit.setFont(font)
        self.edit.setFrame(False)
        self.edit.setPlaceholderText(t("input_placeholder"))
        self.edit.setStyleSheet("QLineEdit { background: transparent; border: none; color: #222; }")
        self.edit.returnPressed.connect(self._submit)
        self.edit.installEventFilter(self)
        self._prev_fg = 0
        self._armed = False
        self._side = "right"
        self._tail_y = self.height() // 2
        # la conversazione si chiude da sola dopo un po' che non scrivi
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle_ms = int(max(0.0, idle_timeout_s) * 1000)
        self._idle.timeout.connect(self._on_idle)
        self.edit.textEdited.connect(lambda _t: self._restart_idle())

    def _restart_idle(self) -> None:
        if self._idle_ms > 0:
            self._idle.start(self._idle_ms)

    def _on_idle(self) -> None:
        # ridà il focus solo se la casella lo ha ancora (l'utente non è andato altrove)
        self._close(restore_focus=self.isActiveWindow())

    def set_hint(self, text: str) -> None:
        self.edit.setPlaceholderText(text or t("input_placeholder"))

    def move_top_to(self, y: int, screen: QRect) -> None:
        """Sposta la casella in verticale (usato per non sovrapporla al fumetto di risposta)."""
        y = max(screen.top(), min(screen.bottom() - self.height() + 1, y))
        if y != self.y():
            self._tail_y += self.y() - y
            self.move(self.x(), y)
            self.update()

    def open_beside(self, anchor: QRect, head_y: int, screen: QRect, inset: int, prev_fg: int) -> None:
        self._prev_fg = prev_fg
        self.edit.clear()
        self.set_hint("")
        self._restart_idle()
        pos, self._side, self._tail_y = place_beside(self.size(), anchor, head_y, screen, inset)
        self.edit.setGeometry(_body_rect(self.rect(), self._side).adjusted(PAD_X, 6, -PAD_X, -6).toRect())
        self.move(pos)
        self.show()
        self.raise_()
        self.activateWindow()
        win32.force_foreground(int(self.winId()))
        self.edit.setFocus(Qt.ActiveWindowFocusReason)
        QTimer.singleShot(80, self._ensure_focus)

    def _ensure_focus(self) -> None:
        if self.isVisible() and not self.isActiveWindow():
            win32.force_foreground(int(self.winId()))
            self.activateWindow()
        if self.isVisible():
            self.edit.setFocus(Qt.ActiveWindowFocusReason)

    def cancel(self, restore_focus: bool = True) -> None:
        self._close(restore_focus)

    def _submit(self) -> None:
        text = self.edit.text().strip()
        if not text:
            return
        # la casella resta aperta: si può rispondere subito, senza ripremere la hotkey
        self.edit.clear()
        self.set_hint(t("input_reply"))
        self._restart_idle()
        self.submitted.emit(text)

    def submit_text(self, text: str) -> None:
        """Invia un testo come se fosse stato scritto (es. dalla dettatura vocale)."""
        self._restart_idle()
        self.submitted.emit(text)

    def _close(self, restore_focus: bool) -> None:
        if not self.isVisible():
            return
        self._armed = False
        self._idle.stop()
        self.hide()
        if restore_focus and self._prev_fg:
            win32.set_foreground(self._prev_fg)
        self._prev_fg = 0
        self.closed.emit()

    def eventFilter(self, obj, event) -> bool:
        if obj is self.edit and event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self._close(restore_focus=True)
            return True
        return super().eventFilter(obj, event)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.ActivationChange:
            if self.isActiveWindow():
                self._armed = True
            elif self._armed and self.isVisible():
                # l'utente ha cliccato altrove: chiudi senza rubargli il focus
                self._close(restore_focus=False)
        super().changeEvent(event)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        _paint_bubble(p, self.rect(), self._side, self._tail_y)
        p.end()

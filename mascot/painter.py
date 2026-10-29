"""Disegno di Elyca interamente con QPainter (nessun file immagine).

Tutto è disegnato in un "canvas di progetto" di 300x300 unità, poi scalato.
La figura occupa circa 250 unità in altezza (dai ciuffi ai piedi).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap

CANVAS = 300.0          # lato del canvas di progetto
VISUAL_HEIGHT = 250.0   # altezza visibile della mascotte nel canvas
HEAD_X, HEAD_Y = 150.0, 100.0
PIVOT = QPointF(150, 285)  # punto attorno a cui ondeggia (i piedi)
HEAD_RX, HEAD_RY = 47.0, 45.0
LAG_CAP = 140.0     # massimo spostamento "in ritardo" di una perlina (unità di progetto)
LAG_MARGIN = 150.0  # margine attorno al canvas per contenere le perline in ritardo

OUTLINE = QColor(34, 34, 34)
WHITE = QColor(255, 255, 255)
TEAL = QColor(52, 140, 168)
PINK = QColor(226, 50, 122)
YELLOW = QColor(247, 186, 44)
HAIR = QColor(168, 168, 168)
HAIR_LINE = QColor(70, 70, 70)
MOUTH = QColor(70, 18, 30)
TONGUE = QColor(240, 108, 140)
RUNG = QColor(150, 150, 150)
BEAD_COLORS = (WHITE, TEAL, PINK, YELLOW)


@dataclass
class Pose:
    """Tutto ciò che serve per disegnare un fotogramma."""
    t: float = 0.0               # tempo globale (s)
    sway_deg: float = 0.0        # ondeggiamento del corpo
    bob: float = 0.0             # su/giù del corpo
    ripple: float = 1.0          # ampiezza dell'oscillazione delle perline
    helix_phase: float = 0.0     # fase della doppia elica
    tail_swing: float = 0.0      # spostamento laterale della coda
    walking: bool = False
    step_phase: float = 0.0
    wave_t: float | None = None  # tempo del saluto (None = non saluta)
    mouth_open: float = 0.65     # 0 = chiusa, 1 = spalancata
    blink: float = 0.0           # 0 = occhi aperti, 1 = chiusi
    eyes_closed: bool = False    # sonno
    look_x: float = 0.0          # direzione dello sguardo [-1, 1]
    look_y: float = 0.0
    zzz_t: float | None = None   # tempo delle "z" del sonno
    think_t: float | None = None  # tempo dell'animazione "sto pensando"
    listen_t: float | None = None  # tempo dell'animazione "ti ascolto"
    # ritardo relativo (0..1) -> offset (dx, dy): dov'era la mascotte poco fa
    lag: Callable[[float], tuple[float, float]] | None = None


# --------------------------------------------------------------------------- utilità

def _pen(width: float, color: QColor = OUTLINE) -> QPen:
    pen = QPen(color, width)
    pen.setJoinStyle(Qt.RoundJoin)
    pen.setCapStyle(Qt.RoundCap)
    return pen


def _bezier(p0, p1, p2, s):
    """Punto e tangente su una Bézier quadratica."""
    u = 1 - s
    x = u * u * p0[0] + 2 * u * s * p1[0] + s * s * p2[0]
    y = u * u * p0[1] + 2 * u * s * p1[1] + s * s * p2[1]
    tx = 2 * u * (p1[0] - p0[0]) + 2 * s * (p2[0] - p1[0])
    ty = 2 * u * (p1[1] - p0[1]) + 2 * s * (p2[1] - p1[1])
    n = math.hypot(tx, ty) or 1.0
    return x, y, tx / n, ty / n


def _lag(pose: Pose, rel: float) -> tuple[float, float]:
    return pose.lag(rel) if pose.lag else (0.0, 0.0)


def _stretch(base: list, lagged: list) -> list:
    """Le perline possono allontanarsi tra loro (la catena si allunga) ma non
    avvicinarsi più della distanza di riposo, misurata lungo la direzione base."""
    out = [lagged[0]]
    for i in range(1, len(base)):
        bx, by = base[i][0] - base[i - 1][0], base[i][1] - base[i - 1][1]
        seg = math.hypot(bx, by) or 1.0
        ux, uy = bx / seg, by / seg
        px, py = lagged[i]
        along = (px - out[-1][0]) * ux + (py - out[-1][1]) * uy
        if along < seg:
            px += ux * (seg - along)
            py += uy * (seg - along)
        out.append((px, py))
    return out


# --------------------------------------------------------------------------- parti

def _draw_body(p: QPainter, pose: Pose) -> None:
    """Doppia elica di perline che si assottiglia verso il basso."""
    n, top, bottom = 13, 138.0, 266.0
    base, lagged = [], []
    for i in range(n):
        s = i / (n - 1)
        y = top + s * (bottom - top)
        wobble = pose.ripple * 3.0 * s * math.sin(pose.t * 3.0 - i * 0.6)
        cx = 150 + pose.tail_swing * s * s + wobble
        dx, dy = _lag(pose, s)
        base.append((cx, y))
        lagged.append((cx + dx, y + dy))
    centers = _stretch(base, lagged)

    beads = []
    p.setPen(_pen(1.3, RUNG))
    for i, (cx, y) in enumerate(centers):
        s = i / (n - 1)
        amp = 14.0 * (1 - 0.55 * s)
        r = 7.2 * (1 - 0.5 * s)
        th = pose.helix_phase + s * math.tau * 1.3
        x1 = cx + amp * math.sin(th)
        x2 = cx - amp * math.sin(th)
        z = math.cos(th)
        p.drawLine(QPointF(x1, y), QPointF(x2, y))  # "pioli" della doppia elica
        beads.append((z, x1, y, r, BEAD_COLORS[i % 4]))
        beads.append((-z, x2, y, r, BEAD_COLORS[(i + 2) % 4]))
    pose._tail_end = centers[-1]  # usato dai piedi

    p.setPen(_pen(1.5))
    for z, x, y, r, color in sorted(beads, key=lambda b: b[0]):
        depth = (z + 1) / 2  # 0 = dietro, 1 = davanti
        p.setBrush(color.darker(int(100 + 35 * (1 - depth))))
        rr = r * (0.8 + 0.2 * depth)
        p.drawEllipse(QPointF(x, y), rr, rr)


def _draw_feet(p: QPainter, pose: Pose) -> None:
    lift_l = lift_r = 0.0
    if pose.walking:
        s = math.sin(pose.step_phase)
        lift_l, lift_r = 6 * max(0.0, s), 6 * max(0.0, -s)
    tx, ty = getattr(pose, "_tail_end", (150.0 + pose.tail_swing, 266.0))
    for fx, lift, dx in ((-9.0, lift_l, -1), (9.0, lift_r, 1)):
        fx += tx
        fy = ty + 15.0 - lift
        p.setPen(_pen(2.0))
        p.drawLine(QPointF(tx, ty - 2), QPointF(fx, fy - 3))
        p.setBrush(YELLOW)
        p.drawEllipse(QRectF(fx - 9 + dx * 3, fy - 5, 18, 9))


def _draw_hand(p: QPainter, cx: float, cy: float, ang: float) -> None:
    p.setPen(_pen(1.8))
    p.setBrush(YELLOW)
    for k, da in enumerate((-64, -24, 12, 48)):
        a = ang + math.radians(da)
        length = 15.0 if k in (1, 2) else 12.5
        dist = 11 + length * 0.35
        p.save()
        p.translate(cx + math.cos(a) * dist, cy + math.sin(a) * dist)
        p.rotate(math.degrees(a))
        p.drawRoundedRect(QRectF(-length / 2, -3.3, length, 6.6), 3.3, 3.3)
        p.restore()
    p.drawEllipse(QPointF(cx, cy), 14, 14)


def _draw_arm(p: QPainter, pose: Pose, shoulder, ctrl, hand, color_offset: int, phase: float) -> None:
    # numero di perline in base alla lunghezza del braccio, così restano a contatto
    length = sum(
        math.dist(_bezier(shoulder, ctrl, hand, k / 10)[:2], _bezier(shoulder, ctrl, hand, (k + 1) / 10)[:2])
        for k in range(10)
    )
    n = max(6, round(length * 0.8 / 13.5) + 1)
    base, lagged, normals, sizes = [], [], [], []
    for i in range(n):
        s = 0.06 + 0.8 * i / (n - 1)
        x, y, tx, ty = _bezier(shoulder, ctrl, hand, s)
        dx, dy = _lag(pose, 0.15 + 0.85 * s)
        base.append((x, y))
        lagged.append((x + dx, y + dy))
        normals.append((-ty, tx))
        sizes.append(4.2 + 5.0 * s)
    dx, dy = _lag(pose, 1.0)
    base.append(hand)
    lagged.append((hand[0] + dx, hand[1] + dy))
    pts = _stretch(base, lagged)

    p.setPen(_pen(1.5))
    for i in range(n):
        rip = pose.ripple * 1.8 * math.sin(pose.t * 3.2 - i * 0.7 + phase)
        x = pts[i][0] + normals[i][0] * rip
        y = pts[i][1] + normals[i][1] * rip
        p.setBrush(BEAD_COLORS[(i + color_offset) % 4])
        p.drawEllipse(QPointF(x, y), sizes[i], sizes[i])
    hx, hy = pts[-1]
    ang = math.atan2(hy - pts[-2][1], hx - pts[-2][0])
    _draw_hand(p, hx, hy, ang)


def _draw_arms(p: QPainter, pose: Pose) -> None:
    swing = 5 * math.sin(pose.step_phase) if pose.walking else 0.0
    # braccio sinistro (alla nostra sinistra)
    _draw_arm(p, pose, (138, 142), (88, 190), (44, 150 + swing), 0, 0.0)
    # braccio destro: normale o che saluta
    shoulder = (162.0, 142.0)
    if pose.wave_t is not None:
        a = math.radians(-45 + 20 * math.sin(pose.wave_t * 9))
        hand = (shoulder[0] + 105 * math.cos(a), shoulder[1] + 105 * math.sin(a))
        ctrl = (shoulder[0] + 70, shoulder[1] + 25)
    else:
        hand = (254.0, 120.0 - swing)
        ctrl = (220.0, 172.0)
    _draw_arm(p, pose, shoulder, ctrl, hand, 1, 1.5)


def _draw_tuft(p: QPainter, x: float, y: float, angle: float) -> None:
    """Ciuffo/sopracciglio grigio "a spazzola"."""
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    path = QPainterPath()
    path.moveTo(-15, 0)
    path.cubicTo(-15, -23, 15, -23, 15, 0)
    path.closeSubpath()
    p.setPen(_pen(2.0))
    p.setBrush(HAIR)
    p.drawPath(path)
    p.setPen(_pen(1.5, HAIR_LINE))
    for k in range(7):
        bx = -10.5 + k * 3.5
        top = -15.5 + (bx / 15.0) ** 2 * 9
        p.drawLine(QPointF(bx * 0.45, -3), QPointF(bx, top))
    p.restore()


def _draw_eyes(p: QPainter, pose: Pose) -> None:
    openness = 0.0 if pose.eyes_closed else 1.0 - pose.blink
    for ex, ey, inward in ((134.0, 94.0, 1), (166.0, 92.0, -1)):
        if openness < 0.15:
            path = QPainterPath()
            path.moveTo(ex - 10, ey + 2)
            path.quadTo(ex, ey + 10, ex + 10, ey + 2)
            p.setPen(_pen(2.4))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
            continue
        ry = 16.5 * openness
        p.setPen(_pen(2.4))
        p.setBrush(WHITE)
        p.drawEllipse(QPointF(ex, ey), 12.5, ry)
        px = ex + inward * 3 + pose.look_x * 4.5
        py = ey + (4 + pose.look_y * 5) * openness
        pr = 6.5
        p.setPen(Qt.NoPen)
        p.setBrush(OUTLINE)
        p.drawEllipse(QPointF(px, py), pr, pr * min(1.0, openness * 1.3))
        p.setBrush(WHITE)
        p.drawEllipse(QPointF(px - 2.2, py - 2.4 * openness), 2.0, 2.0 * openness)


def _draw_mouth(p: QPainter, pose: Pose) -> None:
    lx, ly, rx, ry = 125.0, 119.0, 178.0, 115.0
    o = max(0.0, min(1.0, pose.mouth_open))
    if o < 0.06:  # bocca chiusa: un sorriso
        path = QPainterPath()
        path.moveTo(lx + 8, ly)
        path.quadTo(151, ly + 10, rx - 8, ry)
        p.setPen(_pen(2.4))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        return
    depth = 6 + 34 * o
    mouth = QPainterPath()
    mouth.moveTo(lx, ly)
    mouth.quadTo(152, ly + 5, rx, ry)
    mouth.cubicTo(rx - 2, ry + depth, lx + 4, ly + depth, lx, ly)
    mouth.closeSubpath()

    p.setPen(Qt.NoPen)
    p.setBrush(MOUTH)
    p.drawPath(mouth)
    p.save()
    p.setClipPath(mouth)
    p.setBrush(TONGUE)
    p.drawEllipse(QPointF(146, ly + depth * 0.85), 17, 5 + 7 * o)
    p.setBrush(WHITE)
    p.setPen(_pen(1.2))
    p.drawRect(QRectF(150, 112, 10, 9))  # dentino
    p.restore()
    p.setPen(_pen(2.6))
    p.setBrush(Qt.NoBrush)
    p.drawPath(mouth)


def _draw_head(p: QPainter, pose: Pose) -> None:
    _draw_tuft(p, 126, 64, -28)
    _draw_tuft(p, 176, 65, 30)
    # faccia trasparente: cancella tutto ciò che è stato disegnato dentro la testa
    # (ciuffi, perline del collo e delle braccia che ci passano dietro)
    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Clear)
    p.setPen(Qt.NoPen)
    p.setBrush(OUTLINE)
    p.drawEllipse(QPointF(HEAD_X, HEAD_Y), HEAD_RX, HEAD_RY)
    p.restore()
    # faccia trasparente e senza bordo: alfa 1/255 è invisibile ma tiene la testa
    # "afferrabile" con Ctrl
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 1))
    p.drawEllipse(QPointF(HEAD_X, HEAD_Y), HEAD_RX, HEAD_RY)
    _draw_eyes(p, pose)
    _draw_mouth(p, pose)


def _draw_thinking(p: QPainter, t: float) -> None:
    """Tre bollicine di pensiero che si accendono in sequenza sopra la testa."""
    p.setPen(_pen(1.8))
    for k, (x, y, r) in enumerate(((196.0, 62.0, 3.5), (208.0, 47.0, 5.0), (224.0, 28.0, 7.5))):
        ph = (t * 1.6 - k * 0.33) % 1.0
        glow = max(0.0, math.sin(ph * math.pi))
        color = QColor(BEAD_COLORS[(k + 1) % 4])
        color.setAlpha(int(90 + 165 * glow))
        p.setBrush(color)
        rr = r * (0.85 + 0.3 * glow)
        p.drawEllipse(QPointF(x, y), rr, rr)


def _draw_listening(p: QPainter, t: float) -> None:
    """Onde sonore che arrivano verso la testa da sinistra (dove di solito c'è l'utente)."""
    for k in range(3):
        ph = (t * 1.2 + k / 3) % 1.0           # 0 = lontana, 1 = vicina alla testa
        radius = 34 + 30 * (1 - ph)
        alpha = int(230 * math.sin(ph * math.pi))
        color = QColor(TEAL.red(), TEAL.green(), TEAL.blue(), alpha)
        p.setPen(_pen(3.2, color))
        p.setBrush(Qt.NoBrush)
        rect = QRectF(HEAD_X - 40 - radius, HEAD_Y - radius, 2 * radius, 2 * radius)
        p.drawArc(rect, 150 * 16, 60 * 16)   # arco aperto verso la testa


def _draw_zzz(p: QPainter, t: float) -> None:
    font = QFont("Segoe UI")
    font.setBold(True)
    for k in range(3):
        ph = (t * 0.45 + k / 3) % 1.0
        x = 198 + 26 * ph + 4 * math.sin(ph * 6)
        y = 78 - 50 * ph
        size = 11 + 12 * ph
        alpha = int(255 * math.sin(ph * math.pi))
        font.setPixelSize(int(size))
        p.setFont(font)
        p.setPen(QColor(TEAL.red(), TEAL.green(), TEAL.blue(), alpha))
        p.drawText(QPointF(x, y), "z")


# --------------------------------------------------------------------------- API

def draw_mascot(p: QPainter, pose: Pose, scale: float) -> None:
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    p.scale(scale, scale)
    p.save()
    p.translate(PIVOT)
    p.rotate(pose.sway_deg)
    p.translate(-PIVOT.x(), -PIVOT.y() + pose.bob)
    _draw_body(p, pose)
    _draw_feet(p, pose)
    _draw_arms(p, pose)
    _draw_head(p, pose)
    p.restore()
    if pose.zzz_t is not None:
        _draw_zzz(p, pose.zzz_t)
    if pose.think_t is not None:
        _draw_thinking(p, pose.think_t)
    if pose.listen_t is not None:
        _draw_listening(p, pose.listen_t)
    p.restore()


def render_icon(size: int = 64) -> QIcon:
    """Icona per il system tray: solo la testa."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = size / 112.0
    p.scale(s, s)
    p.translate(-94, -38)
    _draw_head(p, Pose())
    p.end()
    return QIcon(pm)

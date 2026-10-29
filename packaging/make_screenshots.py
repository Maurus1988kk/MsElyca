"""Generate the README images in docs/ using the same drawing code as the app.

Usage: python packaging/make_screenshots.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRect, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QBrush, QColor, QFont, QGuiApplication, QImage,  # noqa: E402
                           QLinearGradient, QPainter)

from mascot.painter import LAG_CAP, draw_mascot  # noqa: E402
from mascot.states import Animator, State  # noqa: E402
from mascot.trail import Trail  # noqa: E402
from overlay.bubbles import PAD_X, PAD_Y, _paint_bubble  # noqa: E402

DOCS = ROOT / "docs"
SCALE = 0.75
CELL = int(300 * SCALE)


def background(p: QPainter, w: int, h: int) -> None:
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor(46, 86, 140))
    g.setColorAt(1, QColor(196, 120, 72))
    p.fillRect(0, 0, w, h, QBrush(g))


def mascot_layer(state: State, frames: int = 20, wave: bool = False, trail: Trail | None = None) -> QImage:
    """Draw the mascot on a transparent layer (the transparent face needs real compositing)."""
    a = Animator()
    a.set_base(state)
    if wave:
        a.wave(10)
    for _ in range(frames):
        a.tick(1 / 30, 45, 1)
    pose = a.pose()
    if state == State.IDLE:
        pose.look_x, pose.look_y = -0.5, 0.2
    if trail is not None:
        pose.lag = trail.lag_function(SCALE, 0.3, LAG_CAP)
    margin = 150 if trail is not None else 0
    size = int((300 + 2 * margin) * SCALE)
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.translate(margin * SCALE, margin * SCALE)
    draw_mascot(p, pose, SCALE)
    p.end()
    return img


def label(p: QPainter, rect: QRect, text: str) -> None:
    font = QFont("Segoe UI", 11)
    font.setBold(True)
    p.setFont(font)
    p.setPen(QColor(255, 255, 255, 230))
    p.drawText(rect, Qt.AlignHCenter | Qt.AlignBottom, text)


def states_image() -> None:
    states = [("Idle", State.IDLE, False), ("Walking", State.WALK, False), ("Waving", State.IDLE, True),
              ("Thinking", State.THINK, False), ("Listening", State.LISTEN, False), ("Sleeping", State.SLEEP, False)]
    w, h = CELL * len(states), CELL + 30
    img = QImage(w, h, QImage.Format_ARGB32)
    p = QPainter(img)
    background(p, w, h)
    for i, (name, st, wave) in enumerate(states):
        p.drawImage(i * CELL, 0, mascot_layer(st, frames=24, wave=wave))
        label(p, QRect(i * CELL, 0, CELL, h - 8), name)
    p.end()
    img.save(str(DOCS / "states.png"))


def chat_image() -> None:
    w, h = 760, 300
    img = QImage(w, h, QImage.Format_ARGB32)
    p = QPainter(img)
    background(p, w, h)
    p.drawImage(w - CELL - 10, 30, mascot_layer(State.TALK, frames=7))
    font = QFont("Segoe UI", 10)
    p.setFont(font)
    answer = ("Sure! Take a 5-minute break every hour: stand up, stretch and look "
              "at something far away to rest your eyes.")
    text_w = 300
    br = p.fontMetrics().boundingRect(QRect(0, 0, text_w, 1000), Qt.TextWordWrap, answer)
    bw, bh = br.width() + 2 * PAD_X + 14 + 9, br.height() + 2 * PAD_Y + 9
    bx, by = w - CELL - bw + 10, 40
    p.save()
    p.translate(bx, by)
    body = _paint_bubble(p, QRect(0, 0, bw, bh), "right", 75)
    p.setPen(QColor(34, 34, 34))
    p.drawText(body.adjusted(PAD_X, PAD_Y, -PAD_X, -PAD_Y), Qt.TextWordWrap, answer)
    p.restore()
    p.save()
    p.translate(w - CELL - 340 + 10, by + bh + 6)
    body = _paint_bubble(p, QRect(0, 0, 340, 58), "right", 20)
    p.setPen(QColor(130, 130, 130))
    p.drawText(body.adjusted(PAD_X, 0, -PAD_X, 0), Qt.AlignVCenter, "Reply…  (Esc to close)")
    p.restore()
    p.end()
    img.save(str(DOCS / "chat.png"))


def trail_image() -> None:
    trail = Trail(0.5)
    x = y = 0.0
    for k in range(30):  # dragged quickly up and to the right
        x += 700 / 30
        y -= 500 / 30
        trail.push(k / 30, x, y)
    layer = mascot_layer(State.IDLE, trail=trail)
    img = QImage(layer.width(), layer.height(), QImage.Format_ARGB32)
    p = QPainter(img)
    background(p, img.width(), img.height())
    p.drawImage(0, 0, layer)
    label(p, QRect(0, 0, img.width(), img.height() - 8), "Ctrl + drag: the beads follow the mouse path")
    p.end()
    img.save(str(DOCS / "trail.png"))


def main() -> None:
    app = QGuiApplication([])  # noqa: F841
    DOCS.mkdir(exist_ok=True)
    states_image()
    chat_image()
    trail_image()
    print("Images saved in", DOCS)


if __name__ == "__main__":
    main()

"""Genera packaging/elyca.ico (la faccina di Elyca) disegnandola con lo stesso codice della mascotte.

L'.ico contiene più dimensioni (16-256 px) in formato PNG, così Windows la mostra nitida ovunque.
Uso: python packaging/make_icon.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from mascot.painter import render_icon  # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)


def main() -> None:
    app = QGuiApplication([])  # noqa: F841 - serve per disegnare
    icon = render_icon(256)
    images = []
    for size in SIZES:
        pm = icon.pixmap(size, size)
        data = QByteArray()
        buf = QBuffer(data)
        buf.open(QIODevice.WriteOnly)
        pm.save(buf, "PNG")
        images.append((size, bytes(data)))

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for size, png in images:
        dim = 0 if size >= 256 else size  # 0 significa 256 nel formato ICO
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        blobs += png
        offset += len(png)
    out = Path(__file__).resolve().parent / "elyca.ico"
    out.write_bytes(header + entries + blobs)
    print(f"Creato {out} ({len(images)} dimensioni)")


if __name__ == "__main__":
    main()

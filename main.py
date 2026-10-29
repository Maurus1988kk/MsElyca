"""Elyca — mascotte desktop per Windows. Avvio: python main.py"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from config import CONFIG_PATH, LOG_DIR, load_config


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fh = RotatingFileHandler(LOG_DIR / "elyca.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    if sys.stderr is not None:  # con PyInstaller --noconsole non c'è stderr
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)

    def excepthook(exc_type, exc, tb):
        logging.getLogger("elyca").critical("Eccezione non gestita", exc_info=(exc_type, exc, tb))
    sys.excepthook = excepthook


def main() -> int:
    setup_logging()
    log = logging.getLogger("elyca")
    if sys.platform != "win32":
        log.error("Elyca funziona solo su Windows")
        return 1
    if "--selftest" in sys.argv:
        from selftest import run
        return run()

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon

    from overlay import win32
    from overlay.tray import Tray
    from overlay.window import MascotWindow

    cfg = load_config()
    from i18n import set_language, t
    set_language(cfg["general"]["ui_language"])

    if not win32.acquire_single_instance("Local\\ElycaDesktopMascot"):
        log.info("Elyca è già in esecuzione")
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None, t("already_running"),
            "Elyca", 0x40)  # MB_ICONINFORMATION
        return 0

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Elyca")
    app.setQuitOnLastWindowClosed(False)

    win = MascotWindow(cfg)
    tray = Tray(win, CONFIG_PATH)
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray.show()
        if cfg["overlay"]["startup_notice"]:
            QTimer.singleShot(1500, lambda: tray.showMessage(
                t("startup_title"), t("startup_body", hotkey=cfg["hotkeys"]["chat"])))
    else:
        log.warning("System tray non disponibile")
    app.aboutToQuit.connect(win.shutdown)
    win.start()
    log.info("Elyca avviata")
    code = app.exec()
    log.info("Elyca chiusa")
    return code


if __name__ == "__main__":
    sys.exit(main())

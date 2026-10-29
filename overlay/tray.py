"""Icona nel system tray con il menu di controllo."""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from i18n import t
from mascot.painter import render_icon
from overlay.window import MascotWindow

log = logging.getLogger(__name__)


class Tray(QSystemTrayIcon):
    def __init__(self, win: MascotWindow, config_path: Path) -> None:
        super().__init__(render_icon(64), win)
        self.win = win
        self.config_path = config_path
        self.setToolTip(t("tray_tooltip", hotkey=win.cfg["hotkeys"]["chat"]))

        self.menu = QMenu()
        self.act_show = self.menu.addAction(t("menu_hide"))
        self.act_show.triggered.connect(self._toggle_show)
        self.act_pause = self.menu.addAction(t("menu_pause"))
        self.act_pause.setCheckable(True)
        self.act_pause.toggled.connect(win.set_paused)
        self.act_sleep = self.menu.addAction(t("menu_sleep"))
        self.act_sleep.setCheckable(True)
        self.act_sleep.toggled.connect(win.set_forced_sleep)
        self.menu.addAction(t("menu_forget")).triggered.connect(win.brain.clear_history)
        self.act_tts = self.menu.addAction(t("menu_tts"))
        self.act_tts.setCheckable(True)
        self.act_tts.setVisible(win.voice.enabled)
        self.act_tts.toggled.connect(self._set_tts)
        self.menu.addSeparator()
        self.menu.addAction(t("menu_config")).triggered.connect(self._open_config)
        self.menu.addSeparator()
        self.menu.addAction(t("menu_quit")).triggered.connect(QApplication.quit)
        self.menu.aboutToShow.connect(self._refresh)
        self.setContextMenu(self.menu)

        win.notify.connect(lambda title, msg: self.showMessage(title, msg))
        win.menu_requested.connect(self.menu.popup)

    def _set_tts(self, on: bool) -> None:
        self.win.voice.tts_enabled = on
        if not on:
            self.win.voice.stop_speaking()

    def _refresh(self) -> None:
        self.act_show.setText(t("menu_show") if self.win.user_hidden else t("menu_hide"))
        for act, value in ((self.act_pause, self.win.paused), (self.act_sleep, self.win.forced_sleep),
                           (self.act_tts, self.win.voice.tts_enabled)):
            act.blockSignals(True)
            act.setChecked(value)
            act.blockSignals(False)

    def _toggle_show(self) -> None:
        self.win.set_user_hidden(not self.win.user_hidden)

    def _open_config(self) -> None:
        try:
            subprocess.Popen(["notepad.exe", str(self.config_path)])
        except OSError:
            os.startfile(self.config_path)  # type: ignore[attr-defined]
        self.showMessage("Elyca", t("config_restart"))

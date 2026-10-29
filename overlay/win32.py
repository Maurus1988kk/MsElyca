"""Funzioni Win32 via ctypes: stili finestra, focus, hotkey, inattività, schermo intero."""
from __future__ import annotations

import ctypes
import logging
import os
from ctypes import wintypes

log = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_CAPTION = 0x00C00000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
VK_CONTROL = 0x11
MONITOR_DEFAULTTONEAREST = 2
ERROR_ALREADY_EXISTS = 183

LONG_PTR = ctypes.c_ssize_t
if ctypes.sizeof(ctypes.c_void_p) == 8:
    _GetWindowLong = user32.GetWindowLongPtrW
    _SetWindowLong = user32.SetWindowLongPtrW
else:
    _GetWindowLong = user32.GetWindowLongW
    _SetWindowLong = user32.SetWindowLongW
_GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
_GetWindowLong.restype = LONG_PTR
_SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
_SetWindowLong.restype = LONG_PTR


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromWindow.restype = wintypes.HMONITOR
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
user32.GetMonitorInfoW.restype = wintypes.BOOL
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
for _fn in (user32.IsWindowVisible, user32.IsIconic, user32.IsZoomed, user32.IsWindow):
    _fn.argtypes = [wintypes.HWND]
    _fn.restype = wintypes.BOOL
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
user32.GetLastInputInfo.restype = wintypes.BOOL
kernel32.GetTickCount.argtypes = []
kernel32.GetTickCount.restype = wintypes.DWORD
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE

_OWN_PID = os.getpid()
_SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}


# --------------------------------------------------------------------------- stili

def configure_overlay(hwnd: int, clickthrough: bool) -> int:
    """Applica gli stili "non disturbare": niente attivazione, niente taskbar,
    e (se clickthrough) clic che passano alle finestre sotto. Idempotente.

    Il click-through richiede WS_EX_LAYERED + WS_EX_TRANSPARENT: Qt imposta
    già WS_EX_LAYERED sulle finestre frameless con sfondo trasparente."""
    ex = _GetWindowLong(hwnd, GWL_EXSTYLE)
    new = (ex | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
    if clickthrough:
        new |= WS_EX_TRANSPARENT
    else:
        new &= ~WS_EX_TRANSPARENT
    if new != ex:
        _SetWindowLong(hwnd, GWL_EXSTYLE, new)
    return new


def get_exstyle(hwnd: int) -> int:
    return _GetWindowLong(hwnd, GWL_EXSTYLE)


# --------------------------------------------------------------------------- input

def is_ctrl_down() -> bool:
    return bool(user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)


def is_key_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def idle_seconds() -> float:
    """Secondi trascorsi dall'ultimo input di mouse/tastiera (di sistema)."""
    info = LASTINPUTINFO(cbSize=ctypes.sizeof(LASTINPUTINFO))
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    return ((kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0


# --------------------------------------------------------------------------- focus

def get_foreground_window() -> int:
    return user32.GetForegroundWindow() or 0


def set_foreground(hwnd: int) -> bool:
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    return bool(user32.SetForegroundWindow(hwnd))


def force_foreground(hwnd: int) -> bool:
    """Porta in primo piano una nostra finestra (solo su richiesta esplicita
    dell'utente, cioè dopo la hotkey). Usa AttachThreadInput come ripiego."""
    if user32.SetForegroundWindow(hwnd) and get_foreground_window() == hwnd:
        return True
    fg = get_foreground_window()
    cur_tid = kernel32.GetCurrentThreadId()
    fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    attached = False
    try:
        if fg_tid and fg_tid != cur_tid:
            attached = bool(user32.AttachThreadInput(cur_tid, fg_tid, True))
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(cur_tid, fg_tid, False)
    return get_foreground_window() == hwnd


# --------------------------------------------------------------------------- schermo intero

def _class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def foreground_is_fullscreen(own_hwnd: int) -> bool:
    """True se l'app in primo piano copre tutto il monitor su cui si trova la mascotte."""
    fg = get_foreground_window()
    if not fg:
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
    if pid.value == _OWN_PID:
        return False
    if _class_name(fg) in _SHELL_CLASSES:
        return False
    if not user32.IsWindowVisible(fg) or user32.IsIconic(fg):
        return False
    style = _GetWindowLong(fg, GWL_STYLE)
    if user32.IsZoomed(fg) and (style & WS_CAPTION) == WS_CAPTION:
        return False  # finestra semplicemente massimizzata
    rect = wintypes.RECT()
    if not user32.GetWindowRect(fg, ctypes.byref(rect)):
        return False
    mon = user32.MonitorFromWindow(fg, MONITOR_DEFAULTTONEAREST)
    info = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
    if not mon or not user32.GetMonitorInfoW(mon, ctypes.byref(info)):
        return False
    m = info.rcMonitor
    covers = rect.left <= m.left and rect.top <= m.top and rect.right >= m.right and rect.bottom >= m.bottom
    if not covers:
        return False
    if own_hwnd and user32.MonitorFromWindow(own_hwnd, MONITOR_DEFAULTTONEAREST) != mon:
        return False  # schermo intero su un altro monitor: non serve nascondersi
    return True


# --------------------------------------------------------------------------- hotkey

_NAMED_KEYS = {
    "space": 0x20, "enter": 0x0D, "return": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B,
    "backspace": 0x08, "insert": 0x2D, "ins": 0x2D, "delete": 0x2E, "del": 0x2E,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28, "pause": 0x13,
}
_MODIFIERS = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT,
              "shift": MOD_SHIFT, "win": MOD_WIN}


def parse_hotkey(spec: str) -> tuple[int, int]:
    """'Ctrl+Alt+E' -> (modificatori, virtual key). Solleva ValueError se non valida."""
    parts = [x.strip().lower() for x in spec.split("+") if x.strip()]
    if not parts:
        raise ValueError(f"hotkey vuota: {spec!r}")
    mods = 0
    for m in parts[:-1]:
        if m not in _MODIFIERS:
            raise ValueError(f"modificatore sconosciuto {m!r} in {spec!r}")
        mods |= _MODIFIERS[m]
    key = parts[-1]
    if len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    elif key in _NAMED_KEYS:
        vk = _NAMED_KEYS[key]
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    else:
        raise ValueError(f"tasto sconosciuto {key!r} in {spec!r}")
    return mods, vk


def register_hotkey(hwnd: int, hotkey_id: int, spec: str) -> bool:
    try:
        mods, vk = parse_hotkey(spec)
    except ValueError as e:
        log.error("Hotkey non valida: %s", e)
        return False
    if not user32.RegisterHotKey(hwnd, hotkey_id, mods | MOD_NOREPEAT, vk):
        log.error("RegisterHotKey(%s) fallita (errore %d): forse è già usata da un'altra app",
                  spec, ctypes.get_last_error())
        return False
    log.info("Hotkey %s registrata", spec)
    return True


def unregister_hotkey(hwnd: int, hotkey_id: int) -> None:
    user32.UnregisterHotKey(hwnd, hotkey_id)


# --------------------------------------------------------------------------- istanza singola

_mutex = None


def acquire_single_instance(name: str) -> bool:
    global _mutex
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, False, name)
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        return False
    _mutex = handle
    return True

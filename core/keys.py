"""Pulsaciones de teclado y ratón que Star Citizen sí recibe.

Star Citizen lee el teclado por códigos de exploración (scan codes), no por
teclas virtuales, así que usamos SendInput con KEYEVENTF_SCANCODE, igual que
VoiceAttack. No se toca la memoria del juego: solo se "pulsa" como lo harías tú.
"""
from __future__ import annotations

import ctypes
import logging
import sys
import time

log = logging.getLogger("nova.keys")
IS_WINDOWS = sys.platform == "win32"

# Scan codes (set 1). (código, extendida)
_BASE = {
    "esc": 0x01, "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06, "6": 0x07,
    "7": 0x08, "8": 0x09, "9": 0x0A, "0": 0x0B, "minus": 0x0C, "equals": 0x0D,
    "backspace": 0x0E, "tab": 0x0F,
    "q": 0x10, "w": 0x11, "e": 0x12, "r": 0x13, "t": 0x14, "y": 0x15, "u": 0x16,
    "i": 0x17, "o": 0x18, "p": 0x19, "lbracket": 0x1A, "rbracket": 0x1B, "enter": 0x1C,
    "lctrl": 0x1D, "a": 0x1E, "s": 0x1F, "d": 0x20, "f": 0x21, "g": 0x22, "h": 0x23,
    "j": 0x24, "k": 0x25, "l": 0x26, "semicolon": 0x27, "apostrophe": 0x28, "grave": 0x29,
    "lshift": 0x2A, "backslash": 0x2B, "z": 0x2C, "x": 0x2D, "c": 0x2E, "v": 0x2F,
    "b": 0x30, "n": 0x31, "m": 0x32, "comma": 0x33, "period": 0x34, "slash": 0x35,
    "rshift": 0x36, "multiply": 0x37, "lalt": 0x38, "space": 0x39, "capslock": 0x3A,
    "f1": 0x3B, "f2": 0x3C, "f3": 0x3D, "f4": 0x3E, "f5": 0x3F, "f6": 0x40, "f7": 0x41,
    "f8": 0x42, "f9": 0x43, "f10": 0x44, "numlock": 0x45, "scrolllock": 0x46,
    "num7": 0x47, "num8": 0x48, "num9": 0x49, "subtract": 0x4A, "num4": 0x4B,
    "num5": 0x4C, "num6": 0x4D, "add": 0x4E, "num1": 0x4F, "num2": 0x50, "num3": 0x51,
    "num0": 0x52, "decimal": 0x53, "intlbackslash": 0x56, "f11": 0x57, "f12": 0x58,
}
_EXTENDED = {
    "ralt": 0x38, "rctrl": 0x1D, "insert": 0x52, "delete": 0x53, "home": 0x47,
    "end": 0x4F, "pageup": 0x49, "pagedown": 0x51, "up": 0x48, "down": 0x50,
    "left": 0x4B, "right": 0x4D, "numenter": 0x1C, "divide": 0x35,
    "lwin": 0x5B, "rwin": 0x5C, "apps": 0x5D, "print": 0x37,
}
_ALIASES = {
    "alt": "lalt", "ctrl": "lctrl", "control": "lctrl", "shift": "lshift",
    "altgr": "ralt", "alt gr": "ralt", "right alt": "ralt", "left alt": "lalt",
    "espacio": "space", "intro": "enter", "return": "enter", "tabulador": "tab",
    "escape": "esc", "supr": "delete", "del": "delete", "ins": "insert",
    "inicio": "home", "fin": "end", "repag": "pageup", "avpag": "pagedown",
    "pgup": "pageup", "pgdn": "pagedown", "arriba": "up", "abajo": "down",
    "izquierda": "left", "derecha": "right", "-": "minus", "=": "equals",
    ",": "comma", ".": "period", "/": "slash", ";": "semicolon", "'": "apostrophe",
    "`": "grave", "[": "lbracket", "]": "rbracket", "\\": "backslash", "<": "intlbackslash",
    "oem102": "intlbackslash", "rwin": "rwin", "lwin": "lwin", "pause": "pause", "print": "print",
    "num +": "add", "num+": "add", "num -": "subtract", "num-": "subtract",
    "num *": "multiply", "num*": "multiply", "num /": "divide", "num/": "divide",
    "num .": "decimal", "num enter": "numenter",
}
for _d in range(10):
    _ALIASES[f"num {_d}"] = f"num{_d}"
    _ALIASES[f"numpad{_d}"] = f"num{_d}"
    _ALIASES[f"numpad {_d}"] = f"num{_d}"


def resolve_key(name: str) -> tuple[int, bool]:
    """'n' -> (0x31, False); 'ralt' -> (0x38, True). Lanza KeyError si no existe."""
    k = name.strip().lower()
    k = _ALIASES.get(k, k)
    if k in _EXTENDED:
        return _EXTENDED[k], True
    if k in _BASE:
        return _BASE[k], False
    raise KeyError(f"Tecla desconocida: '{name}'")


def parse_combo(combo: str) -> list[tuple[int, bool]]:
    """'lalt+n' -> [(lalt), (n)]. El '+' del teclado numérico se escribe 'add'."""
    parts = [p for p in combo.replace(" + ", "+").split("+") if p.strip()]
    return [resolve_key(p) for p in parts]


def valid_combo(combo: str) -> bool:
    try:
        return bool(parse_combo(combo))
    except KeyError:
        return False


# --------------------------------------------------------------------------- #
#  SendInput (solo Windows)
# --------------------------------------------------------------------------- #
if IS_WINDOWS:
    from ctypes import wintypes

    ULONG_PTR = ctypes.c_size_t

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)

    INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
    KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE = 0x1, 0x2, 0x8
    MOUSE_FLAGS = {
        "left": (0x0002, 0x0004, 0), "right": (0x0008, 0x0010, 0),
        "middle": (0x0020, 0x0040, 0), "x1": (0x0080, 0x0100, 1), "x2": (0x0080, 0x0100, 2),
    }
    MOUSEEVENTF_WHEEL = 0x0800

    def _send(inp: "INPUT") -> None:
        if _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) != 1:
            log.warning("SendInput falló (error %s). ¿El juego se ejecuta como administrador?",
                        ctypes.get_last_error())

    def _key(scan: int, extended: bool, up: bool) -> None:
        flags = KEYEVENTF_SCANCODE | (KEYEVENTF_EXTENDEDKEY if extended else 0) | (KEYEVENTF_KEYUP if up else 0)
        _send(INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=KEYBDINPUT(0, scan, flags, 0, 0))))

    def _mouse(flags: int, data: int = 0) -> None:
        _send(INPUT(type=INPUT_MOUSE, u=_INPUTUNION(mi=MOUSEINPUT(0, 0, data, flags, 0, 0))))

    def foreground_title() -> str:
        hwnd = _user32.GetForegroundWindow()
        length = _user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
else:  # En Linux/Mac solo se registra (útil para pruebas).
    def _key(scan: int, extended: bool, up: bool) -> None:
        log.debug("tecla %s%s %s", hex(scan), " ext" if extended else "", "up" if up else "down")

    def _mouse(flags: int, data: int = 0) -> None:
        log.debug("ratón %s %s", flags, data)

    MOUSE_FLAGS = {"left": (1, 2, 0), "right": (3, 4, 0), "middle": (5, 6, 0), "x1": (7, 8, 1), "x2": (7, 8, 2)}
    MOUSEEVENTF_WHEEL = 0

    def foreground_title() -> str:
        return ""


def game_in_foreground() -> bool:
    return "star citizen" in foreground_title().lower()


def press_combo(combo: str, hold: float = 0.0, gap: float = 0.05) -> None:
    """Pulsa una combinación ('lalt+n') manteniéndola `hold` segundos."""
    keys = parse_combo(combo)
    for scan, ext in keys:
        _key(scan, ext, up=False)
        time.sleep(gap)
    time.sleep(max(hold, 0.06))
    for scan, ext in reversed(keys):
        _key(scan, ext, up=True)
        time.sleep(gap / 2)


def key_down(combo: str) -> None:
    for scan, ext in parse_combo(combo):
        _key(scan, ext, up=False)


def key_up(combo: str) -> None:
    for scan, ext in reversed(parse_combo(combo)):
        _key(scan, ext, up=True)


def mouse_click(button: str = "left", hold: float = 0.0) -> None:
    down, up, data = MOUSE_FLAGS[button]
    _mouse(down, data)
    time.sleep(max(hold, 0.05))
    _mouse(up, data)


def mouse_scroll(clicks: int) -> None:
    for _ in range(abs(clicks)):
        _mouse(MOUSEEVENTF_WHEEL, (120 if clicks > 0 else -120) & 0xFFFFFFFF)
        time.sleep(0.03)

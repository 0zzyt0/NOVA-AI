"""«Envía mensaje al chat»: lo que dices, traducido al inglés y escrito en el chat de Star Citizen.

Cómo se escribe en Star Citizen: F12 (abre el chat) + Intro (para escribir), las letras tecla a tecla,
Intro (envía) + F12 (cierra el chat). Las teclas se pueden cambiar en Juego › Chat del juego."""
from __future__ import annotations

import logging
import re
import sys
import time
import unicodedata

from . import keys

log = logging.getLogger("nova.chat")

MAX_LEN = 240  # el chat del juego corta los mensajes largos
CHAT_WAIT_S = 120  # tras «envía mensaje al chat», lo siguiente que digas es el mensaje (2 min)

_VERB = r"(?:envia(?:me|le)?|manda(?:me|le)?|escribe(?:me)?|pon|publica|di)"
_INTENT = re.compile(
    rf"^\s*(?:por favor\s+)?{_VERB}\s+(?:(?:un|el|este|otro)\s+)?(?:mensaje|texto)\s+(?:(?:al|en el|por el|en)\s+)?"
    rf"chat(?:\s+(?:del|de)\s+(?:juego|star citizen))?(?:\s+(?:que\s+(?:diga|ponga)|diciendo|con))?\s*[:,;.\-]?\s*",
    re.I)
_INTENT_SHORT = re.compile(rf"^\s*{_VERB}\s+(?:(?:al|en el|por el)\s+)?chat\s*(?:(?:que\s+(?:diga|ponga)|diciendo)\s*)?[:,;.\-]?\s*",
                           re.I)
CANCEL = {"cancela", "cancelar", "olvidalo", "nada", "no", "dejalo", "da igual", "ninguno"}


def _plain(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in t if not unicodedata.combining(c))


def parse(text: str) -> tuple[bool, str]:
    """¿Es la orden de enviar al chat? -> (sí/no, mensaje que venía en la misma frase o '')."""
    from .i18n import lang
    from .lang_data import CHAT_RX
    plain = _plain(text)
    extra = (CHAT_RX[lang()],) if lang() in CHAT_RX else ()
    for rx in (_INTENT, _INTENT_SHORT) + extra:
        m = rx.match(plain)
        if m:
            return True, clean(text[m.end():])  # mismo largo: quitar tildes no cambia las posiciones
    return False, ""


def clean(text: str) -> str:
    t = (text or "").strip().strip("«»\"'“”").strip()
    t = re.sub(r"\s+", " ", t)
    return t[:MAX_LEN]


def is_cancel(text: str) -> bool:
    from .i18n import lang
    from .lang_data import CANCEL as MORE
    t = _plain(text).lower()
    if re.sub(r"[^a-z ]", "", t).strip() in CANCEL:
        return True
    return " ".join(re.findall(r"[a-z]+", t)) in MORE.get(lang(), set())


# --------------------------------------------------------------------- escribir en el juego
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    KEYEVENTF_UNICODE = 0x0004
    _u32 = ctypes.WinDLL("user32", use_last_error=True)
    _u32.VkKeyScanExW.restype = ctypes.c_short
    _u32.VkKeyScanExW.argtypes = (ctypes.c_wchar, ctypes.c_void_p)
    _u32.MapVirtualKeyExW.restype = ctypes.c_uint
    _u32.MapVirtualKeyExW.argtypes = (ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p)
    _u32.GetKeyboardLayout.restype = ctypes.c_void_p
    _u32.GetKeyboardLayout.argtypes = (wintypes.DWORD,)
    _u32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.c_void_p)
    _u32.GetForegroundWindow.restype = wintypes.HWND
    SC_SHIFT, SC_CTRL, SC_ALT = 0x2A, 0x1D, 0x38

    def _layout():
        tid = _u32.GetWindowThreadProcessId(_u32.GetForegroundWindow(), None)
        return _u32.GetKeyboardLayout(tid)

    def _scan_for(ch: str, hkl) -> tuple[int, int] | None:
        """(código de tecla, modificadores 1=Mayús 2=Ctrl 4=Alt) para escribir ese carácter con tu teclado."""
        r = _u32.VkKeyScanExW(ch, hkl)
        if r == -1:
            return None
        vk, mods = r & 0xFF, (r >> 8) & 0xFF
        sc = _u32.MapVirtualKeyExW(vk, 0, hkl)  # MAPVK_VK_TO_VSC
        return (sc, mods) if sc else None

    def _tap(sc: int, mods: int, gap: float) -> None:
        held = []
        if (mods & 6) == 6:  # AltGr (Ctrl+Alt) en teclados como el español: @ # [ ] { } €
            held = [(SC_CTRL, False), (SC_ALT, True)]
        else:
            if mods & 2:
                held.append((SC_CTRL, False))
            if mods & 4:
                held.append((SC_ALT, False))
        if mods & 1:
            held.append((SC_SHIFT, False))
        for code, ext in held:
            keys._key(code, ext, up=False)
        keys._key(sc, False, up=False)
        time.sleep(gap)
        keys._key(sc, False, up=True)
        for code, ext in reversed(held):
            keys._key(code, ext, up=True)
        time.sleep(gap)

    DEAD = {"\u0301": "´", "\u0300": "`", "\u0308": "¨", "\u0302": "^", "\u0303": "~"}

    def _type_keys(text: str, gap: float) -> None:
        """Pulsa las teclas de verdad (como si escribieras tú): el chat de Star Citizen no acepta otra cosa."""
        hkl = _layout()
        for ch in text:
            hit = _scan_for(ch, hkl)
            if hit:
                _tap(*hit, gap)
                continue
            dec = unicodedata.normalize("NFD", ch)  # á = tecla muerta ´ + a
            base, marks = dec[:1], dec[1:]
            dead = _scan_for(DEAD.get(marks[:1], ""), hkl) if marks[:1] in DEAD else None
            if dead:
                _tap(*dead, gap)
            hit = _scan_for(base, hkl) if base and base != ch else None
            if hit:
                _tap(*hit, gap)
            else:
                log.info("No sé escribir «%s» con este teclado", ch)

    def _type_unicode(text: str, gap: float) -> None:
        for ch in text:
            code = ord(ch)
            units = [code] if code <= 0xFFFF else [0xD800 + ((code - 0x10000) >> 10), 0xDC00 + ((code - 0x10000) & 0x3FF)]
            for u in units:
                for up in (False, True):
                    flags = KEYEVENTF_UNICODE | (keys.KEYEVENTF_KEYUP if up else 0)
                    keys._send(keys.INPUT(type=keys.INPUT_KEYBOARD,
                                          u=keys._INPUTUNION(ki=keys.KEYBDINPUT(0, u, flags, 0, 0))))
            time.sleep(gap)

    def _set_clipboard(text: str) -> bool:
        u32, k32 = ctypes.WinDLL("user32"), ctypes.WinDLL("kernel32")
        k32.GlobalAlloc.restype = wintypes.HGLOBAL
        k32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
        k32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
        k32.GlobalLock.restype = ctypes.c_void_p
        k32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
        u32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
        data = (text + "\0").encode("utf-16-le")
        if not u32.OpenClipboard(None):
            return False
        try:
            u32.EmptyClipboard()
            h = k32.GlobalAlloc(0x0042, len(data))
            p = k32.GlobalLock(h)
            ctypes.memmove(p, data, len(data))
            k32.GlobalUnlock(h)
            return bool(u32.SetClipboardData(13, h))  # CF_UNICODETEXT
        finally:
            u32.CloseClipboard()
else:  # fuera de Windows solo se registra (pruebas)
    TYPED: list[str] = []

    def _type_keys(text: str, gap: float) -> None:
        TYPED.append(text)
        log.debug("chat (teclas): %s", text)

    def _type_unicode(text: str, gap: float) -> None:
        TYPED.append(text)
        log.debug("chat: %s", text)

    def _set_clipboard(text: str) -> bool:
        TYPED.append("[portapapeles] " + text)
        return True


def send_to_game(text: str, settings) -> str:
    """Abre el chat, escribe y envía. Devuelve '' si fue bien o el motivo si no se pudo."""
    text = clean(text)
    if not text:
        return "No hay nada que enviar."
    if settings.get("solo_si_juego_activo") and not keys.game_in_foreground():
        return "Star Citizen no está en primer plano."
    open_key = (settings.get("chat_tecla") or "f12").strip().lower()
    if not keys.valid_combo(open_key):
        return f"La tecla del chat «{open_key}» no es válida."
    wait = max(0.1, min(3.0, float(settings.get("chat_espera_ms", 450)) / 1000))
    keys.press_combo(open_key)  # F12: abre el chat
    time.sleep(wait)
    focus = (settings.get("chat_tecla_foco") or "").strip().lower()
    if focus and keys.valid_combo(focus):
        keys.press_combo(focus)  # Intro: el cursor en la línea de escribir
        time.sleep(max(0.15, wait / 2))
    method = settings.get("chat_metodo", "escribir")
    if method == "pegar" and _set_clipboard(text):
        keys.press_combo("lctrl+v")
    elif method == "unicode":
        _type_unicode(text, 0.012)
    else:  # «escribir»: tecla a tecla, con tu distribución de teclado
        gap = max(0.004, min(0.08, float(settings.get("chat_tecla_ms", 12)) / 1000))
        _type_keys(text, gap)
    time.sleep(0.15)
    keys.press_combo("enter")  # Intro: envía
    after = (settings.get("chat_tecla_cerrar") or "").strip().lower()
    if after and keys.valid_combo(after):
        time.sleep(0.3)
        keys.press_combo(after)  # F12: cierra el chat y vuelves a los mandos
    return ""

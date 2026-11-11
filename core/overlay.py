"""Overlay del logo de Nova sobre el juego.

Ventana de Windows 'por capas' (transparente píxel a píxel), siempre encima,
que no recibe clics ni roba el foco: el ratón la atraviesa y el juego sigue
recibiendo todo. Se ve con Star Citizen en modo «Ventana sin bordes»
(Borderless); en «Pantalla completa» exclusiva Windows no deja dibujar encima.

Se adapta a la resolución: detecta la ventana del juego (o su monitor) y escala
el logo respecto a 1080p. También se puede fijar una resolución a mano.

Colores:   azul (tu color)  escuchando / pensando / hablando
           verde            ha entendido tu orden
           amarillo         buscando información en internet
           rojo             en pausa (apagada) o no te ha entendido
Solo parpadea mientras la IA está hablando.
"""
from __future__ import annotations

import logging
import math
import random
import sys
import threading
import time
from pathlib import Path
from typing import Callable

import numpy as np

from .config import APP_DIR

log = logging.getLogger("nova.overlay")
IS_WINDOWS = sys.platform == "win32"
LOGO = APP_DIR / "recursos" / "nova.png"

RESOLUTIONS = ["640x480", "800x600", "1024x768", "1280x720", "1280x1024", "1366x768", "1440x900", "1600x900",
               "1680x1050", "1920x1080", "1920x1200", "2560x1080", "2560x1440", "3440x1440", "3840x1600", "3840x2160"]
TINT_KEYS = {"green": "overlay_color_ok", "yellow": "overlay_color_busca", "red": "overlay_color_error",
             "purple": "overlay_color_memoria", "white": "overlay_color_memoriza"}


def _hex(color: str) -> tuple[int, int, int]:
    c = (color or "").lstrip("#")
    try:
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except (ValueError, IndexError):
        return 32, 184, 232


def tint_rgb(settings, tint: str) -> np.ndarray:
    key = TINT_KEYS.get(tint, "overlay_color")
    return np.array(_hex(settings.get(key)), dtype=np.float32) / 255.0


def parse_resolution(value: str) -> tuple[int, int] | None:
    try:
        w, h = (int(x) for x in str(value).lower().replace("×", "x").split("x"))
        if 320 <= w <= 7680 and 240 <= h <= 4320:
            return w, h
    except ValueError:
        pass
    return None


def scale_for(height: int) -> float:
    """Escala respecto a 1080p, para que el logo ocupe lo mismo a cualquier resolución."""
    return max(0.35, min(height / 1080.0, 2.6))


class FrameMaker:
    """Prepara el logo y su halo una vez; luego compone cada fotograma con numpy."""

    def __init__(self, size: int, logo_path: Path = LOGO) -> None:
        from PIL import Image, ImageFilter

        self.size = size
        self.canvas = int(size * 1.8) // 2 * 2
        logo = Image.open(logo_path).convert("RGBA").resize((size, size), Image.LANCZOS)
        layer = Image.new("RGBA", (self.canvas, self.canvas), (0, 0, 0, 0))
        off = (self.canvas - size) // 2
        layer.paste(logo, (off, off), logo)
        a = np.asarray(layer, dtype=np.float32) / 255.0
        self.logo_rgb = a[..., :3]
        self.logo_a = a[..., 3:4]
        self.logo_lum = (0.3 * a[..., 0] + 0.59 * a[..., 1] + 0.11 * a[..., 2])[..., None]

        alpha = layer.getchannel("A")
        near = np.asarray(alpha.filter(ImageFilter.GaussianBlur(size * 0.07)), dtype=np.float32) / 255.0
        far = np.asarray(alpha.filter(ImageFilter.GaussianBlur(size * 0.22)), dtype=np.float32) / 255.0
        self.glow_a = np.clip(near * 1.4 + far * 1.1, 0, 1)[..., None]
        # v1.3 «cinematográfico»: un anillo de luz discontinuo que gira alrededor del logo
        c = (self.canvas - 1) / 2
        yy, xx = np.mgrid[0:self.canvas, 0:self.canvas].astype(np.float32)
        dist = np.sqrt((xx - c) ** 2 + (yy - c) ** 2)
        self.ring_d = np.exp(-((dist - size * 0.62) / (size * 0.018 + 0.6)) ** 2)
        self.ring_ang = np.arctan2(yy - c, xx - c)

    def ring(self, now: float, strength: float) -> np.ndarray:
        arcs = (np.cos(self.ring_ang * 3 - now * 2.4) > 0.35).astype(np.float32)
        return (self.ring_d * arcs * strength)[..., None]

    def render(self, logo_alpha: float, glow: float, boost: float, color: np.ndarray, tint: float,
               ring: np.ndarray | None = None) -> np.ndarray:
        """Devuelve BGRA premultiplicado (uint8) listo para UpdateLayeredWindow.
        color: RGB 0..1 del brillo · tint: 0 = logo original, 1 = logo teñido de ese color."""
        la = self.logo_a * logo_alpha
        tinted = np.clip(self.logo_lum * color * 1.9, 0, 1)
        lc = self.logo_rgb * (1 - tint) + tinted * tint
        lc = np.clip(lc * (1.0 + boost) + boost * 0.25, 0, 1)
        ga = np.clip(self.glow_a * glow + (ring if ring is not None else 0), 0, 1)
        out_a = la + ga * (1 - la)
        out_c = lc * la + color * ga * (1 - la)
        bgra = np.empty(out_c.shape[:2] + (4,), dtype=np.uint8)
        bgra[..., 0] = (out_c[..., 2] * 255).astype(np.uint8)
        bgra[..., 1] = (out_c[..., 1] * 255).astype(np.uint8)
        bgra[..., 2] = (out_c[..., 0] * 255).astype(np.uint8)
        bgra[..., 3] = (out_a[..., 0] * 255).astype(np.uint8)
        return bgra


class Animator:
    """Convierte (estado, color, nivel de voz, tiempo) en opacidad, halo, brillo, color y tinte.
    Solo hay parpadeo cuando la IA habla; el resto de estados son luz fija."""

    def __init__(self) -> None:
        self.glow = 0.0
        self.alpha = 0.0
        self.tint = 0.0
        self.color = np.array([32, 184, 232], dtype=np.float32) / 255.0
        self._blink_until = 0.0
        self._next_blink = 0.0

    def step(self, mode: str, tint_key: str, level: float, now: float, idle_alpha: float, idle_hidden: bool,
             intensity: float, color: np.ndarray, fx: str = "cine") -> tuple[float, float, float, np.ndarray, float]:
        boost = 0.0
        target_t = 0.0 if tint_key == "base" else 0.85
        if mode == "speaking":
            target_a = 1.0
            target_g = 0.45 + 0.9 * min(1.0, level * 1.6)
            boost = 0.15 + 0.35 * min(1.0, level * 1.6)
            if fx != "cine":  # «ligero» y «sin efectos»: sin parpadeo, brillo según la voz
                self._blink_until = 0.0
                if fx == "ninguno":
                    target_g, boost = 0.6, 0.15
            elif now >= self._next_blink:  # parpadeos rápidos tipo holograma
                self._blink_until = now + random.uniform(0.04, 0.09)
                self._next_blink = now + random.uniform(0.25, 0.9)
            if now < self._blink_until:
                target_a, target_g, boost = 0.55, 0.25, 0.0
            k = 0.6
        elif mode == "off":
            target_a, target_g, k = 0.85, 0.5, 0.2
        elif mode == "searching":
            target_a, target_g, boost, k = 1.0, 0.7, 0.08, 0.25
        elif mode in ("listening", "thinking"):
            target_a, target_g, boost, k = 1.0, 0.55, 0.08, 0.3
        elif tint_key != "base":  # en reposo pero con un color que mostrar (entendido / no entendido)
            target_a, target_g, boost, k = 1.0, 0.65, 0.1, 0.3
        else:
            target_a, target_g, k = (0.0 if idle_hidden else idle_alpha), 0.0, 0.12
        if fx == "ninguno":
            k = 1.0  # cambios de estado al instante
        elif fx == "cine" and mode in ("speaking", "listening", "thinking", "searching"):
            target_g *= 1.0 + 0.18 * np.sin(now * 3.2)  # el halo «respira»
        self.alpha += (target_a - self.alpha) * k
        self.glow += (target_g * intensity - self.glow) * k
        self.tint += (target_t - self.tint) * 0.25
        self.color += (color - self.color) * 0.25
        return self.alpha, self.glow, boost, self.color, self.tint


POSITIONS = ("arriba-izquierda", "arriba-centro", "arriba-derecha", "centro-derecha", "abajo-izquierda", "abajo-derecha")


def place(pos: str, rect: tuple[int, int, int, int], w: int, margin: int) -> tuple[int, int]:
    left, top, right, bottom = rect
    xs = {"izquierda": left + margin, "centro": (left + right - w) // 2, "derecha": right - w - margin}
    ys = {"arriba": top + margin, "centro": (top + bottom - w) // 2, "abajo": bottom - w - margin}
    v, _, h = (pos if pos in POSITIONS else "arriba-derecha").partition("-")
    return xs[h], ys[v]


def list_monitors() -> list[dict]:
    """Monitores con el principal primero: [{'id': '1', 'rect': (l,t,r,b), 'label': 'Monitor 1 · principal · 2560×1440'}]."""
    out = []
    for i, (rect, primary) in enumerate(_monitors(), 1):
        w, h = rect[2] - rect[0], rect[3] - rect[1]
        out.append({"id": str(i), "rect": rect, "primary": primary,
                    "label": f"Monitor {i}{' · principal' if primary else ''} · {w}×{h}"})
    return out


def _inside(rect, mon) -> bool:
    cx, cy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
    return mon[0] <= cx < mon[2] and mon[1] <= cy < mon[3]


def target_area(settings) -> tuple[tuple[int, int, int, int], str]:
    """Zona donde va el overlay. Nunca sigue al ratón ni a la ventana activa:
    usa el monitor elegido (el principal por defecto) o el del juego."""
    game = _game_window_rect()
    mons = list_monitors()
    choice = str(settings.get("overlay_monitor") or "1")
    if choice == "juego" and game:
        mon = next((m for m in mons if _inside(game, m["rect"])), mons[0])
    else:
        mon = next((m for m in mons if m["id"] == choice), mons[0])
    on_this = game if game and _inside(game, mon["rect"]) else None
    manual = parse_resolution(settings.get("overlay_resolucion"))
    base = on_this or mon["rect"]
    label = f"Monitor {mon['id']}"
    if manual:
        return (base[0], base[1], base[0] + manual[0], base[1] + manual[1]), f"manual · {label}"
    if on_this:
        return on_this, f"ventana del juego · {label}"
    return mon["rect"], label


def layout(settings, rect: tuple[int, int, int, int]) -> tuple[int, int]:
    """(tamaño del logo, margen) en píxeles reales para esa zona."""
    k = scale_for(rect[3] - rect[1])
    size = int(max(32, min(float(settings.get("overlay_tamano")) * k, 600)))
    return size, int(float(settings.get("overlay_margen")) * k)


DEMO = [("listening", "base", 1.3), ("searching", "purple", 1.3), ("searching", "yellow", 1.3),
        ("searching", "white", 1.0), ("idle", "green", 1.3),
        ("speaking", "green", 1.8), ("idle", "red", 1.3), ("off", "red", 1.0)]


class Overlay(threading.Thread):
    def __init__(self, settings, state_fn: Callable[[], tuple[str, float, str]]) -> None:
        super().__init__(daemon=True, name="overlay")
        self.settings = settings
        self.state_fn = state_fn
        self.anim = Animator()
        self.test_until = 0.0
        self.test_start = 0.0
        self.status = "inactivo"
        self.resolution = (0, 0)
        self.source = ""
        self._stop = threading.Event()
        self._maker: FrameMaker | None = None

    def test(self, seconds: float = 9.0) -> None:
        """Lo enseña aunque el juego no esté delante, recorriendo los estados y colores."""
        self.test_start = time.time()
        self.test_until = self.test_start + seconds

    def stop(self) -> None:
        self._stop.set()

    def info(self) -> dict:
        w, h = self.resolution
        return {"status": self.status, "res": f"{w}×{h}" if w else "", "source": self.source,
                "game": bool(_game_window_rect())}

    def _frame_maker(self, size: int) -> FrameMaker:
        if self._maker is None or self._maker.size != size:
            self._maker = FrameMaker(size)
        return self._maker

    def _demo_state(self, now: float) -> tuple[str, float, str]:
        t = now - self.test_start
        total = sum(d for *_, d in DEMO)
        t = t % total
        for mode, tint, dur in DEMO:
            if t < dur:
                return mode, abs(math.sin(now * 9)) * 0.8 if mode == "speaking" else 0.0, tint
            t -= dur
        return "idle", 0.0, "base"

    def run(self) -> None:
        if not IS_WINDOWS:
            self.status = "solo disponible en Windows"
            return
        try:
            win = _LayeredWindow()
        except Exception as e:
            log.exception("Overlay")
            self.status = f"error: {e}"
            return
        self.status = "activo"
        shown = False
        last_top = 0.0
        while not self._stop.is_set():
            win.pump()
            now = time.time()
            testing = now < self.test_until
            game_rect = _game_window_rect()
            visible = bool(self.settings.get("overlay_activo")) and (
                testing or not self.settings.get("overlay_solo_juego") or game_rect is not None and _game_foreground())
            if not visible:
                if shown:
                    win.hide()
                    shown = False
                    self.anim.alpha = self.anim.glow = 0.0
                time.sleep(0.25)
                continue
            try:
                mode, level, tint = self._demo_state(now) if testing else self.state_fn()
                rect, self.source = target_area(self.settings)
                self.resolution = (rect[2] - rect[0], rect[3] - rect[1])
                size, margin = layout(self.settings, rect)
                alpha, glow, boost, color, tint_amount = self.anim.step(
                    mode, tint, level, now, float(self.settings.get("overlay_opacidad_reposo")),
                    self.settings.get("overlay_reposo") == "oculto", float(self.settings.get("overlay_intensidad")),
                    tint_rgb(self.settings, tint), fx=self.settings.get("efectos_nivel", "cine"))
                maker = self._frame_maker(size)
                fx = self.settings.get("efectos_nivel", "cine")
                ring = maker.ring(now, 0.55 * min(1.0, glow)) if fx == "cine" and glow > 0.05 else None
                x, y = place(self.settings.get("overlay_posicion"), rect, maker.canvas,
                             margin - (maker.canvas - maker.size) // 2)
                win.update(maker.render(alpha, glow, boost, color, tint_amount, ring), x, y)
                self.status = "activo"
            except Exception as e:  # un fotograma roto no debe matar el overlay
                if self.status != f"error: {e}":
                    log.exception("Overlay")
                self.status = f"error: {e}"
                time.sleep(2)
                continue
            if not shown:
                win.show()
                shown = True
            if now - last_top > 2:  # algunos juegos se ponen encima: recuperar la posición
                win.keep_on_top()
                last_top = now
            time.sleep(1 / 30)
        win.destroy()


# =========================================================== Win32 (ctypes)
if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    class WNDCLASSEXW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                    ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                    ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)]

    class BLENDFUNCTION(ctypes.Structure):
        _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                    ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    class MSG(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("message", wintypes.UINT), ("wParam", wintypes.WPARAM),
                    ("lParam", wintypes.LPARAM), ("time", wintypes.DWORD), ("pt", wintypes.POINT)]

    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = LRESULT
    user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
    user32.RegisterClassExW.restype = wintypes.ATOM
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.UpdateLayeredWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                           ctypes.POINTER(wintypes.SIZE), wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                           wintypes.COLORREF, ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD]
    user32.UpdateLayeredWindow.restype = wintypes.BOOL
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, wintypes.UINT]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.PeekMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
    user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.IsIconic.argtypes = [wintypes.HWND]
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
                                       ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
    gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE

    WS_POPUP = 0x80000000
    WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOPMOST = 0x00080000, 0x00000020, 0x00000008
    WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x00000080, 0x08000000
    HWND_TOPMOST = wintypes.HWND(-1)
    SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x1, 0x2, 0x10
    SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
    ULW_ALPHA, AC_SRC_OVER, AC_SRC_ALPHA = 0x2, 0x0, 0x1
    PM_REMOVE = 0x1

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                         ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)]

    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), MONITORENUMPROC, wintypes.LPARAM]
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                    ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _GAME = {"hwnd": None, "checked": 0.0}
    _EXCLUDE = ("launcher", "easyanticheat", "eac_", "crashhandler", "setup")

    def _text(fn, hwnd) -> str:
        buf = ctypes.create_unicode_buffer(256)
        fn(hwnd, buf, 256)
        return buf.value

    def _exe_of(hwnd) -> str:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(520)
            size = wintypes.DWORD(520)
            if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return Path(buf.value).name.lower()
            return ""
        finally:
            kernel32.CloseHandle(h)

    def _client_rect(hwnd):
        r = wintypes.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(r)):
            return None
        p = wintypes.POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(p))
        return p.x, p.y, p.x + r.right, p.y + r.bottom

    def _find_game_window():
        """La ventana real del juego: proceso StarCitizen.exe / clase CryENGINE, visible y grande.
        Descarta la ventana de EasyAntiCheat y el lanzador, aunque se llamen igual."""
        found = []

        def cb(hwnd, _):
            if user32.IsWindowVisible(hwnd) and "star citizen" in _text(user32.GetWindowTextW, hwnd).lower():
                found.append(hwnd)
            return True
        user32.EnumWindows(WNDENUMPROC(cb), 0)
        best, best_score = None, -1.0
        for hwnd in found:
            cls = _text(user32.GetClassNameW, hwnd).lower()
            title = _text(user32.GetWindowTextW, hwnd).lower()
            exe = _exe_of(hwnd)
            if any(x in cls or x in title or x in exe for x in _EXCLUDE) or "anticheat" in title:
                continue
            rect = _client_rect(hwnd)
            if not rect or user32.IsIconic(hwnd):
                continue
            w, h = rect[2] - rect[0], rect[3] - rect[1]
            if w < 640 or h < 400:
                continue
            score = (4 if cls == "cryengine" else 0) + (3 if exe == "starcitizen.exe" else 0) + w * h / 1e8
            if score > best_score:
                best, best_score = hwnd, score
        return best

    def _game_hwnd():
        now = time.time()
        hwnd = _GAME["hwnd"]
        valid = bool(hwnd) and user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd)
        if not valid or now - _GAME["checked"] > 3.0:  # se vuelve a buscar: primero sale EAC, luego el juego
            _GAME["hwnd"], _GAME["checked"] = _find_game_window(), now
        return _GAME["hwnd"]

    def _game_window_rect():
        hwnd = _game_hwnd()
        if not hwnd or user32.IsIconic(hwnd):
            return None
        rect = _client_rect(hwnd)
        if not rect or rect[2] - rect[0] < 640:
            return None
        return rect

    def _game_foreground() -> bool:
        hwnd = _game_hwnd()
        return bool(hwnd) and user32.GetForegroundWindow() == hwnd

    def _monitors():
        mons = []

        def cb(hmon, hdc, lprect, _):
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                r = mi.rcMonitor
                mons.append(((r.left, r.top, r.right, r.bottom), bool(mi.dwFlags & 1)))
            return True
        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(cb), 0)
        if not mons:
            mons = [((0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)), True)]
        mons.sort(key=lambda m: (not m[1], m[0][0], m[0][1]))  # principal primero, luego de izquierda a derecha
        return mons

    # El procedimiento de ventana vive todo el programa (si se liberase, Windows llamaría a memoria muerta).
    _WNDPROC_KEEP = WNDPROC(lambda h, m, w, l: user32.DefWindowProcW(h, m, w, l))

    class _LayeredWindow:
        _class_registered = False

        _class_lock = threading.Lock()

        def __init__(self) -> None:
            hinst = kernel32.GetModuleHandleW(None)
            with _LayeredWindow._class_lock:  # una sola clase para el logo y los hologramas (hilos distintos)
                self._register(hinst)
            ex = WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            self.hwnd = user32.CreateWindowExW(ex, "NovaOverlay", "Nova Overlay", WS_POPUP,
                                               0, 0, 1, 1, None, None, hinst, None)
            if not self.hwnd:
                raise OSError(f"CreateWindowEx falló ({ctypes.get_last_error()})")
            self.screen_dc = user32.GetDC(None)
            self.mem_dc = gdi32.CreateCompatibleDC(self.screen_dc)
            self.bmp = None
            self.bits = ctypes.c_void_p()
            self.size = (0, 0)
            self.old = None

        @staticmethod
        def _register(hinst) -> None:
            if not _LayeredWindow._class_registered:
                wc = WNDCLASSEXW()
                wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
                wc.lpfnWndProc = _WNDPROC_KEEP
                wc.hInstance = hinst
                wc.lpszClassName = "NovaOverlay"
                if not user32.RegisterClassExW(ctypes.byref(wc)):
                    raise OSError(f"RegisterClassEx falló ({ctypes.get_last_error()})")
                _LayeredWindow._class_registered = True

        def _ensure_bitmap(self, w: int, h: int) -> None:
            if (w, h) == self.size:
                return
            if self.bmp:
                gdi32.SelectObject(self.mem_dc, self.old)
                gdi32.DeleteObject(self.bmp)
            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = w
            bmi.bmiHeader.biHeight = -h  # de arriba abajo
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            self.bmp = gdi32.CreateDIBSection(self.screen_dc, ctypes.byref(bmi), 0, ctypes.byref(self.bits), None, 0)
            if not self.bmp:
                raise OSError("CreateDIBSection falló")
            self.old = gdi32.SelectObject(self.mem_dc, self.bmp)
            self.size = (w, h)

        def update(self, bgra: np.ndarray, x: int, y: int) -> None:
            h, w = bgra.shape[:2]
            self._ensure_bitmap(w, h)
            data = np.ascontiguousarray(bgra).tobytes()
            ctypes.memmove(self.bits, data, len(data))
            blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
            user32.UpdateLayeredWindow(self.hwnd, self.screen_dc, ctypes.byref(wintypes.POINT(x, y)),
                                       ctypes.byref(wintypes.SIZE(w, h)), self.mem_dc,
                                       ctypes.byref(wintypes.POINT(0, 0)), 0, ctypes.byref(blend), ULW_ALPHA)

        def show(self) -> None:
            user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            self.keep_on_top()

        def hide(self) -> None:
            user32.ShowWindow(self.hwnd, SW_HIDE)

        def keep_on_top(self) -> None:
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)

        def pump(self) -> None:
            msg = MSG()
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        def destroy(self) -> None:
            try:
                if self.bmp:
                    gdi32.SelectObject(self.mem_dc, self.old)
                    gdi32.DeleteObject(self.bmp)
                gdi32.DeleteDC(self.mem_dc)
                user32.ReleaseDC(None, self.screen_dc)
                user32.DestroyWindow(self.hwnd)
            except Exception:
                pass
else:
    def _game_window_rect():
        return None

    def _game_foreground() -> bool:
        return False

    def _monitors():
        return [((0, 0, 1920, 1080), True), ((1920, 0, 3840, 1080), False)]


def preview_frames(settings, path: Path, height: int = 1080) -> None:
    """Genera una tira de fotogramas de ejemplo de todos los estados (para pruebas)."""
    from PIL import Image

    size, _ = layout(settings, (0, 0, int(height * 16 / 9), height))
    maker = FrameMaker(size)
    anim = Animator()
    frames = []
    t = 1000.0
    states = (("idle", "base", 0), ("listening", "base", 0.4), ("searching", "yellow", 0),
              ("idle", "green", 0), ("speaking", "green", 0.9), ("speaking", "base", 0.5),
              ("idle", "red", 0), ("off", "red", 0))
    for mode, tint, level in states:
        for _ in range(40):
            t += 1 / 30
            anim._next_blink = t + 10  # sin parpadeo en la foto
            a, g, b, c, ti = anim.step(mode, tint, level, t, 0.35, False, 1.0, tint_rgb(settings, tint))
        bgra = maker.render(a, g, b, c, ti)
        rgba = bgra[..., [2, 1, 0, 3]].astype(np.float32)
        alpha = rgba[..., 3:4] / 255.0
        rgba[..., :3] = np.where(alpha > 0, rgba[..., :3] / np.maximum(alpha, 1e-6), 0)
        frames.append(Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA"))
    w = frames[0].width
    strip = Image.new("RGBA", (w * len(frames), w), (8, 14, 24, 255))
    for i, f in enumerate(frames):
        strip.alpha_composite(f, (i * w, 0))
    strip.save(path)

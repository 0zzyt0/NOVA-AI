"""Tecla / botón para hablar: teclado, ratón o joystick/HOTAS.

El teclado y el ratón se leen con GetAsyncKeyState (sin ganchos globales:
funciona con el juego en primer plano y no interfiere con él). Los joysticks
se leen con pygame.
"""
from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import time
from typing import Callable

log = logging.getLogger("nova.triggers")
IS_WINDOWS = sys.platform == "win32"

VK = {
    "lbutton": 0x01, "rbutton": 0x02, "mbutton": 0x04, "xbutton1": 0x05, "xbutton2": 0x06,
    "backspace": 0x08, "tab": 0x09, "enter": 0x0D, "pause": 0x13, "capslock": 0x14,
    "space": 0x20, "pageup": 0x21, "pagedown": 0x22, "end": 0x23, "home": 0x24,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28, "insert": 0x2D, "delete": 0x2E,
    "lshift": 0xA0, "rshift": 0xA1, "lctrl": 0xA2, "rctrl": 0xA3, "lalt": 0xA4, "ralt": 0xA5,
    "num0": 0x60, "num1": 0x61, "num2": 0x62, "num3": 0x63, "num4": 0x64, "num5": 0x65,
    "num6": 0x66, "num7": 0x67, "num8": 0x68, "num9": 0x69, "multiply": 0x6A, "add": 0x6B,
    "subtract": 0x6D, "decimal": 0x6E, "divide": 0x6F, "numlock": 0x90, "scrolllock": 0x91,
    "grave": 0xC0, "minus": 0xBD, "equals": 0xBB, "comma": 0xBC, "period": 0xBE,
}
for i in range(1, 25):
    VK[f"f{i}"] = 0x6F + i
for c in "abcdefghijklmnopqrstuvwxyz0123456789":
    VK[c] = ord(c.upper())
VK_NAMES = {v: k for k, v in VK.items()}
# Nombres legibles para la ventana
PRETTY = {"xbutton1": "Ratón lateral 1", "xbutton2": "Ratón lateral 2", "mbutton": "Rueda del ratón (clic)",
          "insert": "Insert", "ralt": "Alt Gr", "rctrl": "Ctrl derecho", "capslock": "Bloq Mayús"}

if IS_WINDOWS:
    _user32 = ctypes.WinDLL("user32")

    def _down(vk: int) -> bool:
        return bool(_user32.GetAsyncKeyState(vk) & 0x8000)
else:
    def _down(vk: int) -> bool:
        return False


def key_pressed(name: str | None) -> bool:
    """Admite combinaciones: 'rctrl+space'."""
    if not name:
        return False
    try:
        return all(_down(VK[p.strip().lower()]) for p in name.split("+"))
    except KeyError:
        return False


class Joysticks:
    """Lectura de botones de joysticks/HOTAS con pygame (opcional)."""

    def __init__(self) -> None:
        self.ok = False
        self._pg = None
        self._sticks: list = []
        self._lock = threading.Lock()
        try:
            os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
            os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
            import pygame  # noqa: WPS433

            # Solo vídeo (sin ventana) y joystick: pygame.init() abriría también el audio
            # y competiría con la voz de Nova por la tarjeta de sonido.
            pygame.display.init()
            pygame.joystick.init()
            self._pg = pygame
            self.refresh()
            self.ok = True
        except Exception as e:  # pygame es opcional
            log.info("Joystick no disponible: %s", e)

    def refresh(self) -> None:
        if not self._pg:
            return
        with self._lock:
            self._sticks = []
            for i in range(self._pg.joystick.get_count()):
                j = self._pg.joystick.Joystick(i)
                j.init()
                self._sticks.append(j)

    def names(self) -> list[str]:
        return [j.get_name() for j in self._sticks]

    def pressed(self, name: str, button: int) -> bool:
        if not self.ok:
            return False
        with self._lock:
            self._pg.event.pump()
            for j in self._sticks:
                if j.get_name() == name and button < j.get_numbuttons():
                    return bool(j.get_button(button))
        return False

    def any_pressed(self) -> tuple[str, int] | None:
        if not self.ok:
            return None
        with self._lock:
            self._pg.event.pump()
            for j in self._sticks:
                for b in range(j.get_numbuttons()):
                    if j.get_button(b):
                        return j.get_name(), b
        return None


class PushToTalk(threading.Thread):
    """Vigila la tecla/botón y llama a on_press / on_release."""

    def __init__(self, settings, on_press: Callable[[], None], on_release: Callable[[], None]) -> None:
        super().__init__(daemon=True, name="ptt")
        self.settings = settings
        self.on_press, self.on_release = on_press, on_release
        self.joysticks = Joysticks()
        self.paused = False
        self._held = False

    def is_held(self) -> bool:
        key = self.settings.get("ptt_tecla")
        js = self.settings.get("ptt_joystick")
        if key_pressed(key):
            return True
        if js and self.joysticks.ok:
            return self.joysticks.pressed(js.get("nombre", ""), int(js.get("boton", -1)))
        return False

    def run(self) -> None:
        while True:
            held = False if self.paused else self.is_held()
            if held and not self._held:
                self._held = True
                self.on_press()
            elif not held and self._held:
                self._held = False
                self.on_release()
            time.sleep(0.02)


def capture_next_input(joysticks: Joysticks, timeout: float = 6.0) -> dict | None:
    """Para el botón 'Asignar': espera a que el usuario pulse algo."""
    end = time.time() + timeout
    time.sleep(0.3)  # que suelte el clic del botón de la ventana
    while time.time() < end:
        for vk, name in VK_NAMES.items():
            if vk in (0x01, 0x02):  # clic izquierdo/derecho: no sirven
                continue
            if _down(vk):
                return {"tipo": "tecla", "tecla": name}
        hit = joysticks.any_pressed()
        if hit:
            return {"tipo": "joystick", "nombre": hit[0], "boton": hit[1]}
        time.sleep(0.02)
    return None


def pretty(name: str | None) -> str:
    if not name:
        return "—"
    return " + ".join(PRETTY.get(p, p.upper() if len(p) <= 3 else p.capitalize()) for p in name.split("+"))

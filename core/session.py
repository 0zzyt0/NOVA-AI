"""Dónde lo dejaste: chat, sección abierta, tamaño de la ventana y última ubicación.

Se guarda en datos/sesion.json al cerrar Nova y cada 30 s (por si se va la luz).
Los ajustes y la memoria tienen sus propios archivos y se guardan al momento.
"""
from __future__ import annotations

import json
import os
import threading
import time

from .config import SESSION_FILE

MAX_CHAT = 80


class Session:
    def __init__(self, path=SESSION_FILE) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.data: dict = {}
        self.dirty = False
        self.load()

    def load(self) -> None:
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            self.data = d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            self.data = {}

    def save(self) -> None:
        with self._lock:
            self.data["guardado"] = time.strftime("%Y-%m-%d %H:%M")
            self.data["chat"] = (self.data.get("chat") or [])[-MAX_CHAT:]
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
                os.replace(tmp, self.path)
                self.dirty = False
            except OSError:
                pass

    def save_if_dirty(self) -> None:
        if self.dirty:
            self.save()

    def get(self, key, default=None):
        with self._lock:
            return self.data.get(key, default)

    def update(self, **kw) -> None:
        with self._lock:
            for k, v in kw.items():
                if self.data.get(k) != v:
                    self.data[k] = v
                    self.dirty = True

    # ------------------------------------------------------------ ventana
    def window_bounds(self) -> dict | None:
        """Posición y tamaño de la ventana la última vez, si son razonables."""
        b = self.get("ventana") or {}
        try:
            x, y, w, h = (int(b[k]) for k in ("x", "y", "w", "h"))
        except (KeyError, TypeError, ValueError):
            return None
        if not (800 <= w <= 8000 and 560 <= h <= 5000 and -2000 <= x <= 12000 and -200 <= y <= 6000):
            return None
        return {"x": x, "y": max(y, 0), "w": w, "h": h}

    # --------------------------------------------------------------- chat
    def previous_chat(self) -> list[dict]:
        """Mensajes de la sesión anterior con una línea separadora al final."""
        chat = [m for m in (self.get("chat") or []) if isinstance(m, dict) and m.get("t") == "msg"]
        if not chat:
            return []
        for m in chat:
            if m.get("who") not in ("tú", "sistema", "juego"):
                m["ai"] = True
        when = self.get("guardado") or ""
        try:
            d = time.strptime(when, "%Y-%m-%d %H:%M")
            when = time.strftime("%d/%m %H:%M", d)
        except ValueError:
            pass
        sep = {"t": "msg", "who": "sistema", "ts": "", "text": f"── Sesión anterior · {when} ── continúas donde lo dejaste ──"}
        return chat[-(MAX_CHAT - 1):] + [sep]

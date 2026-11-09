"""Temporizadores de Nova: refinados, contratos o lo que quieras («avísame en 2 horas»).
Se guardan en la carpeta de datos, así que siguen contando aunque cierres Nova o el juego:
al volver a abrirla te avisa de los que terminaron mientras no estabas."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Callable

from .config import DATA_DIR

log = logging.getLogger("nova.timers")
TIMERS_FILE = DATA_DIR / "temporizadores.json"
KINDS = {"refinado": "⚗", "contrato": "📜", "general": "⏰"}


def human(seconds: float) -> str:
    """3725 -> '1 h 2 min'; 40 -> '40 s'."""
    s = int(max(0, seconds))
    if s < 60:
        return f"{s} s"
    m = (s + 30) // 60
    d, m = divmod(m, 1440)
    h, m = divmod(m, 60)
    parts = [f"{d} d"] if d else []
    if h:
        parts.append(f"{h} h")
    if m and not d:
        parts.append(f"{m} min")
    return " ".join(parts) or "1 min"


class Timers:
    def __init__(self, path: Path = TIMERS_FILE, on_due: Callable[[dict, bool], None] | None = None) -> None:
        self.path = path
        self.on_due = on_due or (lambda t, late: None)  # late=True: terminó mientras Nova estaba cerrada
        self.on_change: Callable[[], None] = lambda: None
        self._lock = threading.RLock()
        self.items: list[dict] = []
        self._load()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------ archivo
    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.items = [t for t in data if isinstance(t, dict) and t.get("fin")]
        except (OSError, ValueError):
            self.items = []

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.items, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as e:
            log.warning("Temporizadores: %s", e)

    # ------------------------------------------------------------ uso
    def add(self, minutos: float, motivo: str, lugar: str = "", tipo: str = "general") -> dict:
        minutos = float(minutos)
        if not (0 < minutos <= 60 * 24 * 14):
            raise ValueError("La duración tiene que estar entre unos segundos y 14 días.")
        now = time.time()
        t = {"id": uuid.uuid4().hex[:8], "motivo": (motivo or "Temporizador").strip()[:120],
             "lugar": (lugar or "").strip()[:80], "tipo": tipo if tipo in KINDS else "general",
             "inicio": now, "fin": now + minutos * 60}
        with self._lock:
            self.items.append(t)
            self.items.sort(key=lambda x: x["fin"])
            self._save()
        self.on_change()
        return t

    def cancel(self, ref: str) -> list[dict]:
        """Cancela por id o por texto del motivo/lugar ('todos' = todos)."""
        ref = (ref or "").strip().lower()
        with self._lock:
            if ref in ("todos", "todo", "all", "*"):
                gone, self.items = self.items, []
            else:
                gone = [t for t in self.items if t["id"] == ref or (ref and (ref in t["motivo"].lower() or ref in t["lugar"].lower()))]
                self.items = [t for t in self.items if t not in gone]
            if gone:
                self._save()
        if gone:
            self.on_change()
        return gone

    def active(self) -> list[dict]:
        now = time.time()
        with self._lock:
            return [dict(t, queda=t["fin"] - now) for t in self.items]

    def describe(self) -> str:
        items = self.active()
        if not items:
            return "No hay temporizadores en marcha."
        return "Temporizadores en marcha:\n" + "\n".join(
            f"- {t['motivo']}" + (f" ({t['lugar']})" if t["lugar"] else "") +
            f": quedan {human(t['queda'])} (termina a las {time.strftime('%H:%M', time.localtime(t['fin']))}"
            + (f" del {time.strftime('%d/%m', time.localtime(t['fin']))}" if t["queda"] > 20 * 3600 else "") + ")"
            for t in items)

    # ------------------------------------------------------------ vigilancia
    def check(self, late: bool = False) -> list[dict]:
        now = time.time()
        with self._lock:
            due = [t for t in self.items if t["fin"] <= now]
            if due:
                self.items = [t for t in self.items if t["fin"] > now]
                self._save()
        for t in due:
            try:
                self.on_due(t, late)
            except Exception:
                log.exception("Aviso de temporizador")
        if due:
            self.on_change()
        return due

    def start(self) -> None:
        """Avisa de los que terminaron con Nova cerrada y vigila el resto."""
        if self._thread:
            return
        self.check(late=True)

        def loop() -> None:
            while not self._stop.wait(2.0):
                self.check()
        self._thread = threading.Thread(target=loop, daemon=True, name="nova-timers")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

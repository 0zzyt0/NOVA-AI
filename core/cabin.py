"""2.1.7 · Copia de la última sesión de la Cabina (las transmisiones entre el piloto y Nova).

Se guarda en datos/diario/ultima_sesion_cabina.txt al cerrar NOVA AI (y cada 30 s, por si se va la luz),
aunque hayas limpiado la Cabina con 🧹. Solo se sustituye la copia anterior cuando en esta sesión
ha habido conversación de verdad (abrir y cerrar NOVA sin hablarle no borra la última).
La ves en ADN y Memoria › Bitácora y estadísticas, y Nova la puede consultar («¿de qué hablamos la última vez?»).
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from .config import DATA_DIR
from .i18n import tr as _

CABIN_FILE = DATA_DIR / "diario" / "ultima_sesion_cabina.txt"
MAX_LINES = 3000  # una sesión muy larga se queda con lo último
HEADER = "NOVA AI · ÚLTIMA SESIÓN DE CABINA"


class CabinLog:
    def __init__(self, path: Path = CABIN_FILE) -> None:
        self.path = path
        self.started = time.time()
        self.lines: list[str] = []
        self.talk = 0  # mensajes tuyos o de Nova (los avisos del sistema solos no cuentan como sesión)
        self.dirty = False
        self._lock = threading.Lock()

    def record(self, who: str, text: str, ai: bool = False, ai_name: str = "Nova") -> None:
        text = " ".join(str(text or "").split())
        if not text:
            return
        label = ai_name if ai else {"tú": _("Tú"), "sistema": _("Sistema"), "juego": _("Juego")}.get(who, who or "?")
        with self._lock:
            self.lines.append(f"[{time.strftime('%H:%M:%S')}] {label}: {text}")
            if len(self.lines) > MAX_LINES:
                self.lines = self.lines[-MAX_LINES:]
            if ai or who == "tú":
                self.talk += 1
            self.dirty = True

    def text(self) -> str:
        start = time.strftime("%d/%m/%Y %H:%M", time.localtime(self.started))
        end = time.strftime("%d/%m/%Y %H:%M")
        with self._lock:
            body = "\n".join(self.lines)
            n = len(self.lines)
        return (_(HEADER) + "\n" + _("Desde {a} hasta {b} · {n} transmisiones", a=start, b=end, n=n)
                + f"\n\n{body}\n")

    def save(self, force: bool = False) -> bool:
        """Escribe la copia si ha habido conversación en esta sesión. Devuelve True si la ha escrito."""
        if not self.talk or not (self.dirty or force):
            return False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(self.text(), encoding="utf-8")
            os.replace(tmp, self.path)
            self.dirty = False
            return True
        except OSError:
            return False

    def save_if_dirty(self) -> bool:
        return self.save() if self.dirty else False


def read_last(path: Path = CABIN_FILE, max_chars: int = 0) -> dict:
    """La copia guardada: {'existe', 'texto', 'fecha', 'ruta'}; con max_chars, solo el final."""
    try:
        txt = path.read_text(encoding="utf-8")
    except OSError:
        return {"existe": False, "texto": "", "fecha": "", "ruta": str(path)}
    head, _, body = txt.partition("\n\n")
    body = body.strip()
    info = head.split("\n", 1)[1] if "\n" in head else ""
    if max_chars and len(body) > max_chars:
        cut = body[-max_chars:]
        body = "…\n" + cut[cut.find("\n") + 1:]
    return {"existe": True, "texto": body.strip(), "fecha": info.strip(), "ruta": str(path)}

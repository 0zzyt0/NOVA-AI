"""Memoria entre sesiones: lo que sabe del piloto (en datos/lo_que_sabe_de_ti.txt, v2.0.1) y las últimas conversaciones."""
from __future__ import annotations

import json
import os
import threading
import time

from .config import MEMORY_FILE, PROFILE_FILE
from .profile import Profile


class Memory:
    MAX_FACTS = 60
    MAX_HISTORY = 30  # mensajes guardados para retomar la charla

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.facts: list[dict] = []
        self.history: list[dict] = []
        self.dirty = False
        self.profile = Profile(PROFILE_FILE)
        self.load()

    def load(self) -> None:
        try:
            d = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            self.facts = d.get("datos", [])
            self.history = d.get("historial", [])
        except (OSError, ValueError):
            pass
        # v2.0.1: los datos pasan al archivo de texto (una sola vez)
        old = [f.get("texto", "") for f in self.facts if isinstance(f, dict)]
        if not self.profile.exists():
            self.profile.ensure(facts=old)
        else:  # p. ej. una copia de seguridad anterior a la 2.0.1
            for f in old:
                self.profile.add_item("otros", f)
        if self.facts:
            self.facts = []
            try:
                self.save()
            except OSError:
                pass

    def wipe(self) -> None:
        """Olvidarlo todo (datos y conversación)."""
        with self._lock:
            self.facts, self.history = [], []
        self.profile.delete()
        self.save()

    def save(self) -> None:
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            tmp = MEMORY_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps({"datos": self.facts, "historial": self.history[-self.MAX_HISTORY:]},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, MEMORY_FILE)
            self.dirty = False

    # ----------------------------------------------------------------- datos
    def remember(self, fact: str, seccion: str = "otros") -> str:
        fact = " ".join((fact or "").split())
        if not fact:
            return "Nada que recordar."
        sec = seccion if seccion in ("naves", "otros", "misiones", "planos") else "otros"
        if sec == "naves":
            self.profile.add_item("naves", fact, key=fact)
        else:
            self.profile.add_item(sec, fact)
        return f"Recordado: {fact}"

    def forget(self, query: str) -> str:
        removed = self.profile.forget(query)
        return f"Olvidados {removed} datos." if removed else "No encontré nada parecido en la memoria."

    def facts_text(self) -> str:
        return self.profile.for_ai()

    # ------------------------------------------------------------- historial
    def add_turn(self, role: str, content: str) -> None:
        with self._lock:
            self.history.append({"role": role, "content": content})
            self.dirty = True
            self.history = self.history[-self.MAX_HISTORY:]

    def recent(self, n_turns: int) -> list[dict]:
        with self._lock:
            return list(self.history[-n_turns * 2:])

    def clear_history(self) -> None:
        with self._lock:
            self.history = []
        self.save()

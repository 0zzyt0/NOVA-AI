"""Memoria entre sesiones: datos sobre el piloto y las últimas conversaciones."""
from __future__ import annotations

import json
import os
import threading
import time

from .config import MEMORY_FILE


class Memory:
    MAX_FACTS = 60
    MAX_HISTORY = 30  # mensajes guardados para retomar la charla

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.facts: list[dict] = []
        self.history: list[dict] = []
        self.dirty = False
        self.load()

    def load(self) -> None:
        try:
            d = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            self.facts = d.get("datos", [])
            self.history = d.get("historial", [])
        except (OSError, ValueError):
            pass

    def wipe(self) -> None:
        """Olvidarlo todo (datos y conversación)."""
        with self._lock:
            self.facts, self.history = [], []
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
    def remember(self, fact: str) -> str:
        fact = fact.strip()
        if not fact:
            return "Nada que recordar."
        with self._lock:
            low = fact.lower()
            self.facts = [f for f in self.facts if f["texto"].lower() != low]
            self.facts.append({"texto": fact, "fecha": time.strftime("%Y-%m-%d")})
            self.facts = self.facts[-self.MAX_FACTS:]
        self.save()
        return f"Recordado: {fact}"

    def forget(self, query: str) -> str:
        q = query.lower().strip()
        with self._lock:
            before = len(self.facts)
            self.facts = [f for f in self.facts if q not in f["texto"].lower()]
            removed = before - len(self.facts)
        self.save()
        return f"Olvidados {removed} datos." if removed else "No encontré nada parecido en la memoria."

    def facts_text(self) -> str:
        if not self.facts:
            return "(todavía no sabes nada del piloto)"
        return "\n".join(f"- {f['texto']}" for f in self.facts)

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

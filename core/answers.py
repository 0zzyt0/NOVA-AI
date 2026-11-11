"""Ahorro de tokens: respuestas guardadas para preguntas sobre datos que no cambian
(planetas, lugares, naves, armas, armaduras y ropa, componentes, minerales, planos…).

Si la IA contestó usando SOLO la enciclopedia local, la wiki o VerseGuide (nada de precios, comandos,
internet ni tu partida), la respuesta se guarda. La próxima vez que preguntes lo mismo, Nova la repite
sin gastar cuota. Caducan a los 14 días o cuando cambia el parche del juego."""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import unicodedata
from pathlib import Path

log = logging.getLogger("nova.answers")

STABLE_TOOLS = {"buscar_datos_juego", "buscar_wiki_star_citizen", "plano_fabricacion", "donde_minar", "ficha_lugar"}
TTL_S = 14 * 86400
MAX_ITEMS = 800

# Palabras que no cambian lo que se pregunta («háblame de la Cutlass» = «qué es la Cutlass»)
FILLER = set("""
a al algo acerca como cual cuales cuentame cuenta de del describe describeme di dime donde el ella en es esta
explica explicame favor habla hablame hay info informacion la las le lo los me mas mucho nova oye para podrias
por puedes que quien quiero saber sabes se sobre son su sus te tienes todo un una unas uno unos y datos dato ficha
""".split())
# Si aparece alguna, la pregunta depende de la conversación, de ti o del momento: no se guarda.
CONTEXT = set("""
eso esa ese esos esas esto este estos estas aquel aquella aquello anterior antes despues luego ahora hoy ayer
manana mi mis mio mia tengo llevo estoy voy vamos nuestro nuestra precio precios cuesta cuestan vale valen
comprar vender venta compra barato caro ruta rutas beneficio dinero auec stock cerca aqui alli ahi mismo misma
tambien entonces otra otro ultimo ultima recuerdas recuerda dijiste parche noticias nuevo nueva actual actualmente
""".split())


def _plain(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9ñ\-]+", t))


def key_for(question: str, wake: tuple[str, ...] = ()) -> str:
    """Clave de la pregunta, o '' si no se debe guardar (depende del contexto o es demasiado vaga)."""
    words = _plain(question).split()
    wake_plain = {_plain(w) for w in wake}
    words = [w for w in words if w not in wake_plain]
    if not words or any(w in CONTEXT for w in words) or words[0] in ("y", "pero", "entonces"):
        return ""
    content = sorted({w for w in words if w not in FILLER})
    if not content or len(" ".join(content)) < 4:
        return ""
    return " ".join(content)


class AnswerCache:
    def __init__(self, path: Path | None = None, version_fn=lambda: "") -> None:
        self.path = path
        self.version_fn = version_fn
        self.items: dict[str, dict] = {}
        self._lock = threading.Lock()
        if path and path.exists():
            try:
                self.items = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.items = {}

    def _save(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.items, ensure_ascii=False), encoding="utf-8")
        except OSError:
            log.debug("No pude guardar las respuestas", exc_info=True)

    def get(self, question: str, wake: tuple[str, ...] = ()) -> str:
        k = key_for(question, wake)
        if not k:
            return ""
        with self._lock:
            it = self.items.get(k)
            if not it:
                return ""
            version = self.version_fn() or ""
            if time.time() - it.get("t", 0) > TTL_S or (version and it.get("v") and it["v"] != version):
                self.items.pop(k, None)
                self._save()
                return ""
            it["usos"] = int(it.get("usos", 0)) + 1
            self._save()
            return it.get("a", "")

    def put(self, question: str, answer: str, tools_used: list[str], wake: tuple[str, ...] = ()) -> bool:
        """Guarda la respuesta si es de datos fijos. True si se guardó."""
        if not answer or len(answer) < 20 or not tools_used or not set(tools_used) <= STABLE_TOOLS:
            return False
        k = key_for(question, wake)
        if not k:
            return False
        with self._lock:
            self.items[k] = {"q": question.strip()[:200], "a": answer.strip(), "t": time.time(),
                             "v": self.version_fn() or "", "h": sorted(set(tools_used)), "usos": 0}
            if len(self.items) > MAX_ITEMS:  # fuera las más antiguas
                for old in sorted(self.items, key=lambda x: self.items[x].get("t", 0))[:len(self.items) - MAX_ITEMS]:
                    self.items.pop(old, None)
            self._save()
        return True

    def forget(self, question: str, wake: tuple[str, ...] = ()) -> bool:
        k = key_for(question, wake)
        with self._lock:
            hit = self.items.pop(k, None) is not None
            if hit:
                self._save()
        return hit

    def clear(self) -> int:
        with self._lock:
            n = len(self.items)
            self.items = {}
            self._save()
        return n

    def count(self) -> int:
        return len(self.items)

    def recent(self, n: int = 30) -> list[dict]:
        with self._lock:
            rows = sorted(self.items.values(), key=lambda x: -x.get("t", 0))[:n]
        return [{"pregunta": r.get("q", ""), "usos": r.get("usos", 0),
                 "fecha": time.strftime("%d/%m/%Y", time.localtime(r.get("t", 0)))} for r in rows]

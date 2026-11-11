"""Traducciones sin gastar cuota de IA: Google Translate (el mismo servicio gratuito que usa
translate.google.es) y, solo si falla, la IA como respaldo. Lo traducido se guarda en tu equipo,
así que el mismo texto no se vuelve a pedir nunca."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from pathlib import Path

import requests

log = logging.getLogger("nova.translate")

GT_URL = "https://translate.googleapis.com/translate_a/single"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NOVA-AI"}
LANG_NAMES = {"es": "español de España", "en": "inglés"}
MAX_CHUNK = 1800  # caracteres por petición (la dirección no debe ser demasiado larga)


def _chunks(text: str, size: int = MAX_CHUNK) -> list[str]:
    if len(text) <= size:
        return [text]
    out, cur = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if len(cur) + len(sentence) + 1 > size and cur:
            out.append(cur)
            cur = ""
        while len(sentence) > size:  # una frase enorme: se corta a lo bruto
            out.append(sentence[:size])
            sentence = sentence[size:]
        cur = f"{cur} {sentence}".strip()
    if cur:
        out.append(cur)
    return out


def parse_google(data) -> str:
    """[[["Hello","Hola",…], …], …] -> 'Hello…'"""
    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError("Respuesta de Google Translate no reconocida")
    return "".join(seg[0] for seg in data[0] if isinstance(seg, list) and seg and isinstance(seg[0], str))


def google(text: str, target: str = "en", source: str = "auto", http=None, timeout: float = 8) -> str:
    """Traduce con Google Translate (gratis, sin clave). Lanza una excepción si no puede."""
    http = http or requests
    out = []
    for part in _chunks(text):
        r = http.get(GT_URL, params={"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": part},
                     headers=UA, timeout=timeout)
        if getattr(r, "status_code", 200) >= 400:
            raise RuntimeError(f"Google Translate respondió {r.status_code}")
        out.append(parse_google(r.json()))
    result = " ".join(x.strip() for x in out).strip()
    if not result:
        raise RuntimeError("Google Translate no devolvió nada")
    return result


class Translator:
    """translate(texto, 'en') -> (traducción, motor). motor: 'guardada' | 'google' | 'ia' | ''."""

    def __init__(self, settings, brain=None, cache_file: Path | None = None, http=None) -> None:
        self.settings, self.brain, self.http = settings, brain, http
        self.cache_file = cache_file
        self._cache: dict[str, str] = {}
        self._lock = threading.Lock()
        self._loaded = False
        self.on_saved = lambda motor: None  # para contar lo que se ahorra

    # ------------------------------------------------------------------ caché
    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if self.cache_file and self.cache_file.exists():
            try:
                self._cache = json.loads(self.cache_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._cache = {}

    def _save(self) -> None:
        if not self.cache_file:
            return
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            items = list(self._cache.items())[-3000:]  # tope: las 3000 más recientes
            self._cache = dict(items)
            self.cache_file.write_text(json.dumps(self._cache, ensure_ascii=False), encoding="utf-8")
        except OSError:
            log.debug("No pude guardar las traducciones", exc_info=True)

    @staticmethod
    def _key(text: str, target: str) -> str:
        return target + ":" + hashlib.sha1(text.strip().encode("utf-8")).hexdigest()

    def clear(self) -> int:
        with self._lock:
            self._load()
            n = len(self._cache)
            self._cache = {}
            self._save()
        return n

    def count(self) -> int:
        with self._lock:
            self._load()
            return len(self._cache)

    # ---------------------------------------------------------------- traducir
    def translate(self, text: str, target: str = "es", source: str = "auto", use_cache: bool = True,
                  allow_ai: bool | None = None) -> tuple[str, str]:
        text = (text or "").strip()
        if not text:
            return "", ""
        key = self._key(text, target)
        if use_cache:
            with self._lock:
                self._load()
                hit = self._cache.get(key)
            if hit:
                self.on_saved("guardada")
                return hit, "guardada"
        result, motor = "", ""
        if self.settings.get("traduccion_motor", "google") == "google":
            try:
                result, motor = google(text, target, source, http=self.http), "google"
                self.on_saved("google")
            except Exception as e:  # noqa: BLE001 — sin conexión, bloqueado…: respaldo con la IA
                log.info("Google Translate: %s", e)
        if allow_ai is None:
            allow_ai = self.settings.get("traduccion_respaldo_ia", True) or \
                self.settings.get("traduccion_motor", "google") == "ia"
        if not result and allow_ai and self.brain is not None:
            lang = LANG_NAMES.get(target, target)
            result = self.brain.quick(f"Traduce al {lang} este texto de Star Citizen. Mantén los nombres propios. "
                                      f"Responde solo con la traducción:\n\n{text[:1500]}")
            result = (result or "").strip().strip('"').strip("«»")
            motor = "ia" if result else ""
        if result and use_cache:
            with self._lock:
                self._cache[key] = result
                self._save()
        return result, motor


class Savings:
    """Cuenta lo que se ha hecho sin gastar cuota de IA (se ve en Inteligencia › Ahorro de tokens)."""

    FIELDS = ("respuestas_guardadas", "respuestas_locales", "traducciones_google", "traducciones_guardadas")

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.data = {k: 0 for k in self.FIELDS}
        self.data["desde"] = time.time()
        if path and path.exists():
            try:
                self.data.update(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass
        self._lock = threading.Lock()

    def add(self, field: str, n: int = 1) -> None:
        if field not in self.FIELDS:
            return
        with self._lock:
            self.data[field] = int(self.data.get(field, 0)) + n
            if self.path:
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    self.path.write_text(json.dumps(self.data), encoding="utf-8")
                except OSError:
                    pass

    def total(self) -> int:
        return sum(int(self.data.get(k, 0)) for k in self.FIELDS)

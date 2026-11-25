"""2.1.5: los motores de IA de Nova y el cambio inteligente entre ellos.

Antes Nova probaba una lista corta de motores y, si fallaban, se rendía. Ahora:
- Lista automática: con tu clave de un servicio, se prueban TODOS sus modelos gratuitos (en Groq y en Gemini
  cada modelo tiene su propio cupo, así que si uno se llena el siguiente suele estar libre).
- Cada fallo se trata según su causa:
    · límite por minuto  → si el servicio dice «reintenta en 3 s», se espera y se reintenta; si es más, ese
                           modelo descansa justo ese tiempo y se pasa al siguiente;
    · cupo del día       → ese modelo (o todo el servicio, en OpenRouter) se aparta hasta que se renueva el cupo;
    · servidor saturado  → pausa corta de ese modelo (30 s, 1 min, 2 min… hasta 5 min);
    · no responde / red  → se salta el servicio entero un rato (1, 2, 4… hasta 10 min);
    · clave no válida    → el servicio queda marcado hasta que cambies la clave;
    · modelo retirado    → ese modelo se aparta un día.
- Si no queda ninguno libre, Nova dice cuál falla y cuándo vuelve.
- `status()` da el semáforo de cada servicio para la ventana.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from . import i18n
from .config import PROVIDERS

log = logging.getLogger("nova.engines")

# Servicios gratuitos que se ofrecen en la ventana (en este orden)
MAIN = ("gemini", "groq", "openrouter")
DEFAULT_ORDER = ("gemini", "groq", "openrouter", "mistral", "deepseek")
SHORT_WAIT = 8.0  # segundos que merece la pena esperar a un motor en vez de saltar al siguiente

REASONS = {
    "minuto": "límite por minuto",
    "dia": "cupo del día gastado",
    "saturado": "servidor saturado",
    "red": "no responde",
    "clave": "clave no válida",
    "modelo": "modelo no disponible",
    "rechazo": "rechazó la petición",
    "grande": "pregunta demasiado larga para este motor",
}

# Cómo empieza la clave de cada servicio (para reconocerla al pegarla)
KEY_PREFIXES = (("sk-or-", "openrouter"), ("gsk_", "groq"), ("AIza", "gemini"), ("AQ.", "gemini"))


def detect_provider(key: str) -> str:
    """De qué servicio es una clave, por cómo empieza. '' si no se reconoce."""
    k = (key or "").strip()
    for prefix, prov in KEY_PREFIXES:
        if k.startswith(prefix):
            return prov
    return ""


def fingerprint(key: str) -> str:
    return hashlib.sha256((key or "").strip().encode("utf-8")).hexdigest()[:16]


def provider_name(prov: str) -> str:
    """Nombre corto: «Google Gemini (gratis)» → «Google Gemini»."""
    name = (PROVIDERS.get(prov) or {}).get("nombre") or prov
    return re.sub(r"\s*\(.*?\)\s*$", "", name)


# ------------------------------------------------------------------ horas de reinicio de los cupos
def _pacific_offset(now_utc: datetime) -> timedelta:
    """Hora del Pacífico (los cupos diarios de Gemini se renuevan a medianoche de allí)."""
    try:
        from zoneinfo import ZoneInfo
        off = now_utc.astimezone(ZoneInfo("America/Los_Angeles")).utcoffset()
        if off is not None:
            return off
    except Exception:  # noqa: BLE001 — Windows sin tzdata: regla de horario de verano de EE. UU.
        pass
    y = now_utc.year
    mar = datetime(y, 3, 8, 10, tzinfo=timezone.utc)  # 2.º domingo de marzo, 2:00 PST = 10:00 UTC
    mar += timedelta(days=(6 - mar.weekday()) % 7)
    nov = datetime(y, 11, 1, 9, tzinfo=timezone.utc)  # 1.er domingo de noviembre, 2:00 PDT = 9:00 UTC
    nov += timedelta(days=(6 - nov.weekday()) % 7)
    return timedelta(hours=-7) if mar <= now_utc < nov else timedelta(hours=-8)


def next_pacific_midnight(now: float | None = None) -> float:
    now_utc = datetime.fromtimestamp(now or time.time(), timezone.utc)
    off = _pacific_offset(now_utc)
    local = now_utc + off
    nxt = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (nxt - off).timestamp() + 60


def next_utc_midnight(now: float | None = None) -> float:
    d = datetime.fromtimestamp(now or time.time(), timezone.utc)
    return (d + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp() + 60


_DUR = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")


def parse_duration(text: str) -> float | None:
    """«7.66s», «2m30.5s», «1h2m3s», «450ms» → segundos."""
    if not text:
        return None
    total, hit = 0.0, False
    for num, unit in _DUR.findall(text):
        hit = True
        total += float(num) * {"ms": 0.001, "s": 1, "m": 60, "h": 3600}[unit]
    return total if hit else None


def _retry_after(e: Exception, text: str) -> float | None:
    """Cuánto pide esperar el servicio (cabecera retry-after, «retry in 34s», «retryDelay»)."""
    resp = getattr(e, "response", None)
    headers = getattr(resp, "headers", None) or {}
    try:
        ra = headers.get("retry-after")
        if ra:
            return max(0.0, float(ra))
    except (TypeError, ValueError):
        pass
    m = re.search(r"(?:try again|retry) in\s+((?:\d+(?:\.\d+)?(?:ms|h|m|s))+)", text, re.I)
    if m:
        return parse_duration(m.group(1))
    m = re.search(r'retryDelay["\']?\s*:\s*["\']([\d.]+s)', text)
    if m:
        return parse_duration(m.group(1))
    return None


def _reset_header(e: Exception) -> float | None:
    """OpenRouter: X-RateLimit-Reset en milisegundos desde 1970."""
    headers = getattr(getattr(e, "response", None), "headers", None) or {}
    try:
        v = float(headers.get("x-ratelimit-reset") or 0)
    except (TypeError, ValueError):
        return None
    if v > 1e12:
        v /= 1000
    return v if v > time.time() else None


@dataclass
class Pause:
    until: float
    reason: str
    detail: str = ""


@dataclass
class Verdict:
    scope: str  # "model" | "prov"
    reason: str
    until: float
    wait: float | None = None  # lo que pide esperar el servicio (para un reintento corto)
    detail: str = ""


def classify(prov: str, e: Exception, strikes: int = 0, now: float | None = None) -> Verdict:
    """Qué significa un fallo y cuánto apartar el motor."""
    now = now or time.time()
    status = getattr(e, "status_code", None)
    body = getattr(e, "body", None)
    try:
        text = f"{e} {json.dumps(body, default=str, ensure_ascii=False) if body else ''}"
    except Exception:  # noqa: BLE001
        text = str(e)
    low = text.lower()
    detail = str(e)[:300]
    name = type(e).__name__
    if status is None and (name in ("APITimeoutError", "APIConnectionError", "Timeout", "ConnectError")
                           or "timed out" in low or "timeout" in low or "connection" in low):
        pause = min(600, 60 * 2 ** min(strikes, 4))
        return Verdict("prov", "red", now + pause, detail=detail)
    if status == 401:
        return Verdict("prov", "clave", now + 365 * 86400, detail=detail)
    if status == 402:  # OpenRouter: sin saldo / cupo gratuito agotado
        return Verdict("prov", "dia", _reset_header(e) or next_utc_midnight(now), detail=detail)
    if status == 403:
        return Verdict("model", "clave", now + 3600, detail=detail)
    if status == 404:
        return Verdict("model", "modelo", now + 86400, detail=detail)
    if status == 413 or "context length" in low or "context_length" in low or "too large" in low:
        return Verdict("model", "grande", now + 600, detail=detail)
    if status == 429 or "resource_exhausted" in low or "rate limit" in low or "quota" in low:
        wait = _retry_after(e, text)
        daily = any(k in low for k in ("perday", "per day", "per_day", "(rpd)", "(tpd)", "free-models-per-day",
                                       "daily", "requests per day", "tokens per day"))
        if daily:
            if prov == "gemini":
                until = next_pacific_midnight(now)
            elif prov == "openrouter":
                until = _reset_header(e) or next_utc_midnight(now)
            else:
                until = now + (wait if wait and wait > 60 else 3600)
            return Verdict("prov" if prov == "openrouter" else "model", "dia", until, wait, detail)
        m = re.search(r"limit\s*:?\s*(\d+),\s*used\s*:?\s*(\d+),\s*requested\s*:?\s*(\d+)", low)
        if m and int(m.group(3)) > int(m.group(1)):  # la pregunta sola ya no cabe en su límite por minuto
            return Verdict("model", "grande", now + 600, detail=detail)
        return Verdict("model", "minuto", now + max(2.0, wait or 60.0), wait, detail)
    if status == 400:
        return Verdict("model", "rechazo", now + 300, detail=detail)
    if status is not None and status >= 500:
        pause = min(300, 30 * 2 ** min(strikes, 3))
        return Verdict("model", "saturado", now + pause, detail=detail)
    return Verdict("model", "rechazo", now + 120, detail=detail)


def _clock(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def when_text(until: float, now: float | None = None) -> str:
    """«en 40 s», «en 3 min», «a las 09:00»."""
    left = until - (now or time.time())
    if left <= 0:
        return i18n.tr("enseguida")
    if left < 90:
        return i18n.tr("en {n} s", n=int(left + 0.99))
    if left < 3600:
        return i18n.tr("en {n} min", n=int(left / 60 + 0.99))
    if left > 300 * 86400:
        return ""
    return i18n.tr("a las {h}", h=_clock(until))


class Engines:
    """Estado de cada motor (servicio:modelo) y la lista que se prueba en cada pregunta."""

    def __init__(self, settings) -> None:
        self.settings = settings
        self._lock = threading.RLock()
        self.model: dict[str, Pause] = {}
        self.prov: dict[str, Pause] = {}
        self.strikes: dict[str, int] = {}
        self.key_fp: dict[str, str] = {}  # huella de la clave con la que se marcó «clave no válida»
        self.last_ok: dict[str, float] = {}
        self.last_used = ""

    # ---------------------------------------------------------------- lista de motores
    def has_key(self, prov: str) -> bool:
        return prov == "ollama" or bool(self.settings.key_for(prov))

    def order(self) -> list[str]:
        order = [p for p in (self.settings.get("ia_orden") or DEFAULT_ORDER) if p in PROVIDERS and p != "ollama"]
        for p in DEFAULT_ORDER:
            if p not in order:
                order.append(p)
        if self.settings.get("ia_ollama"):
            order.append("ollama")
        return order

    def configured(self) -> list[dict]:
        """Todos los motores con clave, en el orden en que se prueban."""
        if self.settings.get("ia_auto", True):
            out = []
            for p in self.order():
                if not self.has_key(p):
                    continue
                for m in PROVIDERS[p]["modelos"]:
                    out.append({"proveedor": p, "modelo": m})
            return out
        return [dict(e) for e in (self.settings.get("ia_cadena") or [])
                if e.get("proveedor") in PROVIDERS and e.get("modelo") and self.has_key(e["proveedor"])]

    def pause_of(self, entry: dict, now: float | None = None) -> Pause | None:
        """La pausa que afecta a un motor ahora mismo (la más larga), o None si está libre."""
        now = now or time.time()
        p = entry["proveedor"]
        tag = f"{p}:{entry['modelo']}"
        with self._lock:
            pp = self.prov.get(p)
            if pp and pp.reason == "clave" and self.key_fp.get(p) != fingerprint(self.settings.key_for(p)):
                self.prov.pop(p, None)  # la clave ha cambiado: se vuelve a probar
                pp = None
            mp = self.model.get(tag)
        live = [x for x in (pp, mp) if x and x.until > now]
        return max(live, key=lambda x: x.until) if live else None

    def available(self, now: float | None = None) -> list[dict]:
        now = now or time.time()
        return [e for e in self.configured() if not self.pause_of(e, now)]

    def soonest(self, now: float | None = None, exclude: set | None = None) -> tuple[dict, Pause] | None:
        """El motor en pausa que antes vuelve (sin contar claves no válidas)."""
        now = now or time.time()
        best = None
        for e in self.configured():
            if exclude and f"{e['proveedor']}:{e['modelo']}" in exclude:
                continue
            pz = self.pause_of(e, now)
            if pz and pz.reason not in ("clave", "modelo") and (best is None or pz.until < best[1].until):
                best = (e, pz)
        return best

    # ---------------------------------------------------------------- lo que pasa en cada llamada
    def ok(self, entry: dict) -> None:
        tag = f"{entry['proveedor']}:{entry['modelo']}"
        with self._lock:
            self.strikes.pop(tag, None)
            self.strikes.pop(entry["proveedor"], None)
            self.model.pop(tag, None)
            pp = self.prov.get(entry["proveedor"])
            if pp and pp.reason in ("red", "saturado"):
                self.prov.pop(entry["proveedor"], None)
            self.last_ok[tag] = time.time()
            self.last_used = tag

    def failed(self, entry: dict, e: Exception) -> Verdict:
        p = entry["proveedor"]
        tag = f"{p}:{entry['modelo']}"
        with self._lock:
            key = p if classify(p, e).scope == "prov" else tag
            n = self.strikes.get(key, 0)
            v = classify(p, e, n)
            if v.reason in ("red", "saturado"):
                self.strikes[key] = n + 1
            pause = Pause(v.until, v.reason, v.detail)
            if v.scope == "prov":
                self.prov[p] = pause
                if v.reason == "clave":
                    self.key_fp[p] = fingerprint(self.settings.key_for(p))
            else:
                self.model[tag] = pause
        log.warning("%s: %s (%s) %s", tag, REASONS.get(v.reason, v.reason),
                    when_text(v.until) or "hasta que cambies la clave", v.detail[:160].replace("\n", " "))
        return v

    def reset(self, prov: str | None = None) -> None:
        with self._lock:
            if prov is None:
                self.model.clear(), self.prov.clear(), self.strikes.clear(), self.key_fp.clear()
                return
            self.prov.pop(prov, None)
            self.key_fp.pop(prov, None)
            for d in (self.model, self.strikes):
                for k in [k for k in d if k == prov or k.startswith(prov + ":")]:
                    d.pop(k, None)

    # ---------------------------------------------------------------- explicaciones
    def explain(self) -> str:
        """Por qué no hay motor libre, en una frase para decirla en voz alta."""
        now = time.time()
        conf = self.configured()
        if not conf:
            return ""
        parts = []
        for p in dict.fromkeys(e["proveedor"] for e in conf):
            pauses = [self.pause_of(e, now) for e in conf if e["proveedor"] == p]
            if any(x is None for x in pauses):
                continue
            first = min(pauses, key=lambda x: x.until)
            if first.reason == "clave":
                parts.append(i18n.tr("{n} dice que la clave no es válida", n=provider_name(p)))
            elif first.reason == "modelo":
                parts.append(i18n.tr("{n} no tiene modelos disponibles", n=provider_name(p)))
            else:
                parts.append(i18n.tr("{n}: {r}, vuelve {w}", n=provider_name(p), r=i18n.tr(REASONS[first.reason]),
                                     w=when_text(first.until, now)))
        return "; ".join(parts)

    def status(self) -> dict:
        """Semáforo de cada servicio para la ventana."""
        now = time.time()
        out = {}
        conf = self.configured()
        for p in PROVIDERS:
            models = PROVIDERS[p]["modelos"] if self.settings.get("ia_auto", True) else \
                [e["modelo"] for e in conf if e["proveedor"] == p]
            rows = []
            for m in models:
                pz = self.pause_of({"proveedor": p, "modelo": m}, now) if self.has_key(p) else None
                rows.append({"modelo": m, "libre": pz is None,
                             "motivo": pz.reason if pz else "", "texto": self._pause_text(pz, now) if pz else "",
                             "detalle": (pz.detail if pz else "")[:300],
                             "ultimo_ok": self.last_ok.get(f"{p}:{m}", 0)})
            if not self.has_key(p):
                estado, texto = "sin_clave", i18n.tr("Sin clave")
            elif p in [e["proveedor"] for e in conf] or not rows:
                free = [r for r in rows if r["libre"]]
                if free:
                    estado, texto = "listo", i18n.tr("Listo · {n} de {t} modelos libres", n=len(free), t=len(rows))
                else:
                    pz = min((self.pause_of({"proveedor": p, "modelo": r["modelo"]}, now) for r in rows),
                             key=lambda x: x.until)
                    estado = "clave_mal" if pz.reason == "clave" else "pausa"
                    texto = self._pause_text(pz, now)
            else:
                estado, texto = "fuera", i18n.tr("Con clave, pero fuera de tu lista de motores")
            out[p] = {"estado": estado, "texto": texto, "modelos": rows, "nombre": provider_name(p)}
        return {"servicios": out, "ultimo": self.last_used, "listos": sum(1 for p in MAIN if out[p]["estado"] == "listo"),
                "auto": bool(self.settings.get("ia_auto", True))}

    @staticmethod
    def _pause_text(pz: Pause, now: float) -> str:
        if pz.reason == "clave":
            return i18n.tr("La clave no es válida: pega otra")
        w = when_text(pz.until, now)
        return i18n.tr("En pausa ({r}) · vuelve {w}", r=i18n.tr(REASONS.get(pz.reason, pz.reason)), w=w) if w \
            else i18n.tr(REASONS.get(pz.reason, pz.reason))

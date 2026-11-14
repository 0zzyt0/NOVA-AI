"""NOVA AI 1.4 · cuestionario anónimo de valoración.

Se envía a un pequeño servicio intermedio (un Cloudflare Worker del autor, ver servicios/cuestionario en el
repositorio) que lo publica como issue de GitHub. Así el programa no lleva dentro ningún token de GitHub.

Qué se envía: las notas del 1 al 10, el texto que escribas, la versión de NOVA AI y el idioma. Nada más:
ni tu nombre, ni tu gametag, ni datos del equipo.

Recordatorio: a los 3 días de usar esta versión se pregunta UNA vez al iniciar. Si dices «ahora no», se
pregunta si quieres otro aviso en 3 días; si dices que no, no se vuelve a preguntar.
"""
from __future__ import annotations

import logging
import re
import time

from .config import VERSION

log = logging.getLogger("nova.survey")

# Dirección del servicio intermedio. Vacía = el cuestionario no aparece (por ejemplo, en una versión compilada
# por otra persona sin su propio servicio).
URL = ""

QUESTIONS = ("reconocimiento", "comandos", "respuestas", "voz", "configuracion", "overlay", "ventana",
             "recomendarias")
IDEA_MAX = 2000
DAYS = 3 * 24 * 3600
UA = {"User-Agent": f"NOVA-AI/{VERSION} (cuestionario anonimo; +https://github.com/0zzyt0/NOVA-AI)"}


def available() -> bool:
    return bool(URL)


def clean_answers(raw) -> dict:
    """Solo las preguntas conocidas, con notas enteras del 1 al 10 (o None = «no lo uso / no sé»)."""
    if not isinstance(raw, dict):
        raise ValueError("Respuestas no válidas")
    out = {}
    for k in QUESTIONS:
        v = raw.get(k)
        if v in (None, "", "ns"):
            out[k] = None
            continue
        try:
            n = int(v)
        except (TypeError, ValueError):
            raise ValueError("Respuestas no válidas") from None
        if not 1 <= n <= 10:
            raise ValueError("Las notas van del 1 al 10")
        out[k] = n
    if all(v is None for v in out.values()):
        raise ValueError("Puntúa al menos una pregunta")
    return out


def clean_idea(text) -> str:
    text = str(text or "").replace("\r\n", "\n")
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text).strip()
    return text[:IDEA_MAX]


def payload(answers: dict, idea: str, lang: str) -> dict:
    return {"version": VERSION, "idioma": str(lang or "es")[:5], "respuestas": answers, "idea": idea}


def send(answers, idea, lang: str, http=None) -> str:
    """Envía el cuestionario. Devuelve un texto para el usuario; lanza ValueError con el motivo si falla."""
    if not URL:
        raise ValueError("El envío del cuestionario no está disponible en esta versión.")
    body = payload(clean_answers(answers), clean_idea(idea), lang)
    if http is None:
        import requests as http
    try:
        r = http.post(URL, json=body, timeout=20, headers=UA)
    except Exception as e:  # noqa: BLE001
        log.warning("Cuestionario: sin conexión (%s)", e)
        raise ValueError("No he podido conectar. Comprueba tu conexión e inténtalo más tarde.") from None
    if r.status_code == 429:
        raise ValueError("Se han enviado muchos cuestionarios en poco tiempo. Inténtalo en un rato.")
    if r.status_code >= 400:
        log.warning("Cuestionario: respuesta %s", r.status_code)
        raise ValueError(f"El servicio no ha aceptado el cuestionario (error {r.status_code}). Inténtalo más tarde.")
    return "¡Gracias! Cuestionario enviado de forma anónima."


# ------------------------------------------------------------------------------------- recordatorio
def ensure_clock(settings, now: float | None = None) -> None:
    """La primera vez que se usa esta versión, programa el aviso para dentro de 3 días."""
    now = now or time.time()
    if settings.get("cuestionario_version") != VERSION:
        settings.set("cuestionario_version", VERSION)
        if settings.get("cuestionario_estado") != "no_recordar":  # quien dijo «no» no vuelve a ser preguntado
            settings.set("cuestionario_estado", "pendiente")
            settings.set("cuestionario_recordar_en", now + DAYS)


def due(settings, now: float | None = None) -> bool:
    """¿Toca preguntar al iniciar?"""
    if not available() or not settings.get("asistente_completado"):
        return False
    now = now or time.time()
    return (settings.get("cuestionario_estado") == "pendiente"
            and now >= float(settings.get("cuestionario_recordar_en") or 0))


def later(settings, remind: bool, now: float | None = None) -> None:
    """«Ahora no»: con remind=True, otro aviso en 3 días; si no, no se vuelve a preguntar."""
    now = now or time.time()
    if remind:
        settings.set("cuestionario_recordar_en", now + DAYS)
    else:
        settings.set("cuestionario_estado", "no_recordar")


def sent(settings) -> None:
    settings.set("cuestionario_estado", "enviado")

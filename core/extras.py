"""Funciones de la v1.1 que usa el asistente: buscar jugadores en la web de RSI, temporizadores,
estado de los servidores, perfiles por nave y anotar objetivos en la bitácora."""
from __future__ import annotations

import logging
import re
import threading
import time

from . import discord
from .rsi import HANDLE_RE, NOT_FOUND, RSI, Citizen, NotFound, es_date, es_langs, status_text

log = logging.getLogger("nova.extras")

# «localízame a un jugador», «búscame a un jugador», «encuentra al jugador…», «ficha del jugador…»
LOOKUP_RE = re.compile(r"\b(localiza\w*|busca\w*|encuentra\w*|investiga\w*|ficha)\b.{0,25}\bjugador(a|es)?\b")
HANDLE_AFTER = re.compile(r"jugador(?:a|es)?\s*(?:[:,\-]|llamad[oa]|que se llama|con (?:el )?apodo)?\s*"
                          r"[«\"']?([A-Za-z0-9_\-]{2,60})[»\"']?\s*[.!?]?\s*$", re.I)
WAIT_HANDLE_S = 180  # tras pedirte el apodo, el siguiente texto escrito se toma como apodo durante 3 min
FILLERS = {"un", "una", "uno", "el", "la", "al", "por", "favor", "porfa", "ahora", "ya"}


def is_lookup(norm: str) -> bool:
    return bool(LOOKUP_RE.search(norm or ""))


def handle_in(text: str) -> str:
    """Apodo escrito en la misma frase («búscame al jugador 0zzyt0»), o ''."""
    m = HANDLE_AFTER.search(text or "")
    if not m:
        return ""
    h = m.group(1)
    return "" if h.lower() in FILLERS else h


def looks_like_handle(text: str) -> bool:
    return bool(HANDLE_RE.match((text or "").strip().strip("«»\"'@")))


def clean_handle(text: str) -> str:
    return (text or "").strip().strip("«»\"'@")


def spoken(c: Citizen, t: str) -> str:
    """Resumen corto para decir en voz alta (la ficha completa va al chat)."""
    who = c.apodo_juego or c.handle
    parts = [f"Ficha de {who}" + (f", handle {c.handle}" if c.handle and c.handle != who else "")]
    if c.alta:
        parts.append(f"alta en {es_date(c.alta)}")
    if c.idiomas:
        from .rsi import LANGS
        langs = [LANGS.get(x.strip().lower(), x.strip()) for x in c.idiomas.split(",") if x.strip()]
        parts.append("habla " + (" y ".join([", ".join(langs[:-1]), langs[-1]]) if len(langs) > 1 else langs[0]))
    o = c.org
    if o.oculta:
        parts.append("organización principal oculta")
    elif o.nombre or o.sid:
        parts.append(f"organización {o.nombre or o.sid}" + (f", {o.miembros} miembros" if o.miembros else ""))
    else:
        parts.append("sin organización principal")
    return parts[0] + (": " + ", ".join(parts[1:]) if len(parts) > 1 else "") + f". Tiene la ficha completa en pantalla, {t}."


def diary_detail(c: Citizen) -> str:
    vals = dict(c.lines())
    return " · ".join(f"{k}: {v}" for k, v in vals.items()) + f" · {c.url}"


def org_detail(c: Citizen) -> str:
    return " · ".join(f"{k}: {v}" for k, v in c.org_lines() if k not in ("Descripción",))


def discord_fields(c: Citizen) -> list[tuple[str, str]]:
    fields = list(c.lines())
    for k, v in c.org_lines():
        if k in ("Organización", "Página de la org"):
            continue
        fields.append((f"Org · {k}", v[:300]))
    return fields


def send_player_to_discord(settings, c: Citizen, http=None) -> str:
    """Devuelve '' si no toca mandar nada, o un texto con el resultado para el chat."""
    url = (settings.get("discord_webhook") or "").strip()
    if not url or not settings.get("discord_enviar_jugadores", True):
        return ""
    try:
        discord.send(url, f"Ficha de jugador: {c.apodo_juego or c.handle}", discord_fields(c), link=c.url,
                     footer=f"NOVA AI · consultado {time.strftime('%d/%m/%Y %H:%M')}", http=http)
        return "📨 Ficha enviada a Discord."
    except Exception as e:  # noqa: BLE001 - cualquier fallo se cuenta, no tumba a Nova
        log.warning("Discord: %s", e)
        return f"⚠ No pude mandarla a Discord: {e}"


def lookup(handle: str, rsi: RSI | None = None) -> Citizen:
    """Busca la ficha (y su organización). Lanza NotFound ante cualquier problema."""
    try:
        return (rsi or RSI()).citizen(clean_handle(handle))
    except NotFound:
        raise
    except Exception as e:  # noqa: BLE001
        log.warning("RSI %s: %s", handle, e)
        raise NotFound(NOT_FOUND) from e


def ship_alerts(settings, ship: str) -> dict:
    """Avisos activos para la nave actual: los generales con lo que cambie su perfil."""
    base = dict(settings.get("gamelog_avisos") or {})
    profiles = settings.get("perfiles_nave") or {}
    if ship and profiles:
        key = _key(ship)
        for name, prof in profiles.items():
            k = _key(name)
            if k and (k == key or k in key or key in k) and isinstance(prof, dict):
                base.update({c: bool(v) for c, v in prof.items()})
                break
    return base


def remember_ship(settings, ship: str) -> None:
    if not ship:
        return
    known = list(settings.get("naves_conocidas") or [])
    if any(_key(x) == _key(ship) for x in known):
        return
    known.append(ship)
    settings.set("naves_conocidas", known[-40:])


def _key(name: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", (name or "").lower())
    return re.sub(r"[^a-z0-9]", "", s)


class StatusCheck:
    """Mira el estado de los servidores de RSI (en un hilo; no bloquea el arranque)."""

    def __init__(self) -> None:
        self.last: dict = {}
        self.when = 0.0
        self._lock = threading.Lock()

    def run(self, rsi: RSI | None = None) -> dict:
        with self._lock:
            try:
                st = (rsi or RSI()).status()
            except Exception as e:  # noqa: BLE001
                st = {"ok": None, "componentes": {}, "avisos": [], "error": str(e)}
            self.last, self.when = st, time.time()
            return st

    def text(self) -> str:
        if not self.last:
            return "Todavía no he comprobado el estado de los servidores."
        if self.last.get("error"):
            return f"No pude consultar la página de estado de RSI ({self.last['error']})."
        return status_text(self.last)

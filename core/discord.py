"""Envío a un canal de Discord mediante un webhook (Ajustes del canal › Integraciones › Webhooks).
Solo se usa para lo que tú actives: de momento, las fichas de jugadores que busques."""
from __future__ import annotations

import re

import requests

WEBHOOK_RE = re.compile(r"^https://(?:(?:canary|ptb)\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+$")
COLOR = 0x20B8E8


def valid(url: str) -> bool:
    return bool(WEBHOOK_RE.match((url or "").strip()))


def send(url: str, title: str, fields: list[tuple[str, str]], link: str = "", footer: str = "NOVA AI",
         thumb: str = "", http=None) -> None:
    """Manda un mensaje con formato (embed). Lanza ValueError/RuntimeError si no se puede."""
    url = (url or "").strip()
    if not valid(url):
        raise ValueError("El webhook de Discord no es válido (debe empezar por https://discord.com/api/webhooks/…).")
    embed = {"title": title[:256], "color": COLOR,
             "fields": [{"name": k[:256], "value": (v or "—")[:1024], "inline": len(v or "") < 40} for k, v in fields][:25],
             "footer": {"text": footer[:2048]}}
    if link:
        embed["url"] = link
    if thumb:
        embed["thumbnail"] = {"url": thumb}
    payload = {"username": "NOVA AI", "embeds": [embed], "allowed_mentions": {"parse": []}}
    r = (http or requests).post(url, json=payload, timeout=10)
    if r.status_code == 429:
        raise RuntimeError("Discord pide esperar un poco (demasiados mensajes).")
    if r.status_code >= 400:
        raise RuntimeError(f"Discord respondió {r.status_code}.")

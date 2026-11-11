"""Envío a un canal de Discord mediante un webhook (Ajustes del canal › Integraciones › Webhooks).
Solo se usa para lo que tú actives: de momento, las fichas de jugadores que busques."""
from __future__ import annotations

import re

import requests

WEBHOOK_RE = re.compile(r"^https://(?:(?:canary|ptb)\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+$")
COLOR = 0x20B8E8


def valid(url: str) -> bool:
    return bool(WEBHOOK_RE.match((url or "").strip()))


RED = 0xFF4040
UA = {"User-Agent": "DiscordBot (https://github.com/0zzyt0/NOVA-AI, 1.2) NOVA-AI"}


def _clean(text, limit: int) -> str:
    text = " ".join(str(text or "").split()) if limit <= 256 else str(text or "").strip()
    return text[:limit]


def payload(title: str, fields: list[tuple[str, str]], link: str = "", footer: str = "NOVA AI",
            thumb: str = "", color: int = COLOR, author: str = "", author_icon: str = "") -> dict:
    """El mensaje con formato (embed) que acepta Discord: sin campos vacíos y dentro de sus límites."""
    out_fields, total = [], 0
    for k, v in fields:
        name, value = _clean(k, 256), _clean(v, 1024)
        if not name:
            continue
        value = value or "—"
        total += len(name) + len(value)
        if total > 5000 or len(out_fields) >= 25:  # Discord rechaza embeds de más de 6000 caracteres
            break
        out_fields.append({"name": name, "value": value, "inline": len(value) < 40})
    embed = {"title": _clean(title, 256) or "NOVA AI", "color": int(color), "fields": out_fields,
             "footer": {"text": _clean(footer, 2048) or "NOVA AI"}}
    if link and link.startswith(("http://", "https://")):
        embed["url"] = link
    if thumb and thumb.startswith("https://"):
        embed["thumbnail"] = {"url": thumb}
    if author:
        embed["author"] = {"name": _clean(author, 256)}
        if author_icon and author_icon.startswith("https://"):
            embed["author"]["icon_url"] = author_icon
    return {"username": "NOVA AI", "embeds": [embed], "allowed_mentions": {"parse": []}}


def _error_text(r) -> str:
    try:
        d = r.json()
        msg = d.get("message") or ""
        if d.get("errors"):
            msg += " " + str(d["errors"])[:200]
        return msg.strip()
    except Exception:  # noqa: BLE001
        return (getattr(r, "text", "") or "")[:200]


def send(url: str, title: str, fields: list[tuple[str, str]], link: str = "", footer: str = "NOVA AI",
         thumb: str = "", http=None, color: int = COLOR, author: str = "", author_icon: str = "",
         retries: int = 2) -> None:
    """Manda un mensaje con formato (embed). Lanza ValueError/RuntimeError si no se puede."""
    import time

    url = (url or "").strip()
    if not valid(url):
        raise ValueError("El webhook de Discord no es válido (debe empezar por https://discord.com/api/webhooks/…).")
    body = payload(title, fields, link, footer, thumb, color, author, author_icon)
    http = http or requests
    for attempt in range(retries + 1):
        try:
            r = http.post(url, json=body, timeout=15, headers=UA)
        except TypeError:  # clientes de prueba sin «headers»
            r = http.post(url, json=body, timeout=15)
        code = getattr(r, "status_code", 0)
        if code == 429 and attempt < retries:  # demasiados mensajes: espera lo que pide Discord
            try:
                wait = float(r.json().get("retry_after", 1.5))
            except Exception:  # noqa: BLE001
                wait = 1.5
            time.sleep(min(max(wait, 0.5), 10))
            continue
        if code == 429:
            raise RuntimeError("Discord pide esperar un poco (demasiados mensajes).")
        if code in (401, 403, 404):
            raise RuntimeError(f"Discord respondió {code}: el webhook no existe o se borró. Crea uno nuevo y pégalo.")
        if code >= 400:
            detail = _error_text(r)
            raise RuntimeError(f"Discord respondió {code}" + (f" ({detail})" if detail else "") + ".")
        return

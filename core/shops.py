"""«¿Dónde compro un P4-AR?»: en qué tiendas se vende cada objeto y a qué precio, con la API pública
de UEX Corp (api.uexcorp.uk/2.0, sin clave). Los datos los aportan los jugadores de la comunidad.

1) items_prices_all (una vez al día, guardado en tu equipo): qué objeto es y en qué terminales está.
2) items_prices?id_item=…: de ese objeto, dónde está cada tienda (sistema, planeta, ciudad o estación)."""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import unicodedata
from pathlib import Path

import requests

log = logging.getLogger("nova.shops")

UEX = "https://api.uexcorp.uk/2.0"
UA = {"User-Agent": "NOVA-AI/1.3 (asistente de voz de Star Citizen; +https://github.com/0zzyt0/NOVA-AI)"}
TTL_ALL = 24 * 3600
TTL_ITEM = 6 * 3600
GENERIC = {"rifle", "pistola", "pistol", "smg", "escopeta", "shotgun", "sniper", "francotirador", "fusil", "arma",
           "armadura", "armor", "casco", "helmet", "de", "la", "el", "los", "las", "un", "una", "del", "the", "a"}


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _fmt(n) -> str:
    try:
        return f"{float(n):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "?"


class Shops:
    def __init__(self, cache_dir: Path | None = None, http=None) -> None:
        self.cache_dir = cache_dir
        self.http = http or requests
        self._lock = threading.Lock()
        self._all: tuple[float, list] | None = None
        self._items: dict[int, tuple[float, list]] = {}

    def _get(self, resource: str, params: dict | None = None) -> list:
        r = self.http.get(f"{UEX}/{resource}", params=params or {}, headers=UA, timeout=20)
        if getattr(r, "status_code", 200) >= 400:
            raise LookupError(f"UEX respondió {r.status_code}")
        d = r.json()
        if not isinstance(d, dict) or d.get("status") != "ok":
            raise LookupError((d or {}).get("message") or "UEX no respondió") if isinstance(d, dict) else LookupError("UEX")
        return d.get("data") or []

    def all_prices(self) -> list[dict]:
        now = time.time()
        with self._lock:
            if self._all and now - self._all[0] < TTL_ALL:
                return self._all[1]
        f = self.cache_dir / "uex_objetos.json" if self.cache_dir else None
        if f and f.exists() and now - f.stat().st_mtime < TTL_ALL:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                with self._lock:
                    self._all = (f.stat().st_mtime, data)
                return data
            except (OSError, ValueError):
                pass
        try:
            rows = self._get("items_prices_all")
        except Exception as e:  # noqa: BLE001 — sin conexión: la última copia
            if f and f.exists():
                try:
                    return json.loads(f.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    pass
            raise LookupError(f"No pude consultar UEX ({e})") from e
        slim = [{"id_item": r.get("id_item"), "item_name": r.get("item_name"), "id_terminal": r.get("id_terminal"),
                 "terminal_name": r.get("terminal_name"), "price_buy": r.get("price_buy")} for r in rows
                if r.get("item_name") and (r.get("price_buy") or 0) > 0]
        with self._lock:
            self._all = (now, slim)
        if f:
            try:
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(json.dumps(slim, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
        return slim

    def find_item(self, query: str) -> tuple[int, str] | None:
        """(id, nombre) del objeto que más se parece a lo que pides."""
        q = norm(query)
        if not q:
            return None
        names: dict[int, str] = {}
        for r in self.all_prices():
            names.setdefault(r["id_item"], r["item_name"])
        for i, n in names.items():
            if norm(n) == q:
                return i, n
        qw = set(q.split()) - GENERIC or set(q.split())
        best, score = None, 0.0
        for i, n in names.items():
            nw = set(norm(n).split())
            if qw <= nw:
                s = len(qw) / len(nw)
                if s > score:
                    best, score = (i, n), s
        if best:
            return best
        import difflib
        by = {norm(n): (i, n) for i, n in names.items()}
        hit = difflib.get_close_matches(q, list(by), n=1, cutoff=0.86)
        return by[hit[0]] if hit else None

    def where(self, item_id: int) -> list[dict]:
        """Tiendas de un objeto, de la más barata a la más cara."""
        now = time.time()
        hit = self._items.get(item_id)
        if hit and now - hit[0] < TTL_ITEM:
            return hit[1]
        rows = self._get("items_prices", {"id_item": item_id})
        out = []
        for r in rows:
            if not (r.get("price_buy") or 0) > 0:
                continue
            place = r.get("city_name") or r.get("space_station_name") or r.get("outpost_name") or ""
            body = r.get("moon_name") or r.get("planet_name") or r.get("orbit_name") or ""
            out.append({"tienda": r.get("terminal_name") or "?", "lugar": place, "cuerpo": body,
                        "sistema": r.get("star_system_name") or "", "precio": r.get("price_buy"),
                        "actualizado": r.get("date_modified") or r.get("date_added")})
        out.sort(key=lambda x: x["precio"])
        self._items[item_id] = (now, out)
        return out


def place_text(s: dict) -> str:
    bits = [s["tienda"]]
    where = ", ".join(x for x in (s["lugar"], s["cuerpo"], s["sistema"]) if x and x not in s["tienda"])
    return bits[0] + (f" ({where})" if where else "")


def summary(name: str, shops: list[dict], tratamiento: str, limit: int = 3) -> tuple[str, str]:
    """(texto para la cabina, frase para decir)."""
    if not shops:
        return (f"UEX no tiene tiendas registradas para {name}.",
                f"No tengo tiendas registradas para {name}, {tratamiento}. Puede que solo salga en misiones o "
                f"como botín. Si quiere, le abro el buscador de objetos de la comunidad.")
    lines = [f"DÓNDE COMPRAR · {name} (UEX Corp, datos de la comunidad)"]
    lines += [f"• {place_text(s)}: {_fmt(s['precio'])} aUEC" for s in shops[:12]]
    if len(shops) > 12:
        lines.append(f"… y {len(shops) - 12} tiendas más")
    first = shops[0]
    say = (f"{name} se vende en {len(shops)} tienda{'s' if len(shops) != 1 else ''}. La más barata: "
           f"{place_text(first)}, por {_fmt(first['precio'])} aUEC.")
    rest = shops[1:limit]
    if rest:
        say += " También en " + " y ".join(f"{place_text(s)}" for s in rest) + "."
    say += f" Tiene la lista en la cabina, {tratamiento}."
    return "\n".join(lines), say

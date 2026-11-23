"""2.0.3 · Motherlode (cryon.rocks): minería de Star Citizen por su API pública y documentada.

https://cryon.rocks/developers (OpenAPI 3.1). Los datos de juego piden una clave GRATUITA que cada piloto genera en
https://cryon.rocks/profile/developer y se envía como «Authorization: Bearer <clave>». Límite: 60 peticiones por
minuto y clave. Sus condiciones prohíben automatizar peticiones a la web fuera de la API, así que NOVA solo usa la API.

Los datos de referencia (minerales, lugares, rocas, láseres, refinerías) casi no cambian: se guardan en disco un día.
Los precios los aportan los jugadores: se guardan una hora. Con todo, NOVA hace muy pocas peticiones.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import unicodedata
from pathlib import Path

import requests

from . import i18n

log = logging.getLogger("nova.motherlode")

SITE = "https://cryon.rocks"
API = SITE + "/api/public/v1"
KEY_URL = SITE + "/profile/developer"
UA = {"User-Agent": "NOVA-AI (asistente de voz de Star Citizen; +https://github.com/0zzyt0/NOVA-AI)"}
TTL = {"commodities": 86400, "locations": 86400, "rock-types": 86400, "refineries": 86400, "mining-lasers": 86400,
       "mining-modules": 86400, "commodity-terminals": 86400, "market-prices": 3600}
MIN_GAP = 1.1  # s entre peticiones (60/min)


class MotherlodeError(RuntimeError):
    pass


class NoKey(MotherlodeError):
    pass


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip()


def slug(name: str) -> str:
    return _norm(name).replace(" ", "-")


def _num(v) -> str:
    if v is None or v == "":
        return "?"
    if isinstance(v, (int, float)):
        if abs(v) >= 1000:
            return f"{v:,.0f}".replace(",", ".")
        return f"{v:g}"
    return str(v)


def _range(r) -> str:
    """{min, max} (o parecido) -> «min–max»."""
    if isinstance(r, dict):
        lo = next((r[k] for k in ("min", "from", "low", "minimum") if k in r), None)
        hi = next((r[k] for k in ("max", "to", "high", "maximum") if k in r), None)
        if lo is not None or hi is not None:
            return f"{_num(lo)}–{_num(hi)}" if lo != hi else _num(lo)
        return ", ".join(f"{k} {_num(v)}" for k, v in r.items() if not isinstance(v, (dict, list)))
    if isinstance(r, (list, tuple)) and len(r) == 2:
        return f"{_num(r[0])}–{_num(r[1])}"
    return _num(r)


def _age(iso: str | None) -> str:
    """Antigüedad de un dato («hace 3 días»)."""
    if not iso:
        return ""
    try:
        from datetime import datetime, timezone
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        days = (datetime.now(timezone.utc) - t).total_seconds() / 86400
    except (ValueError, TypeError):
        return ""
    if days < 1:
        return i18n.tr("hoy")
    return i18n.tr("hace {n} días", n=int(days))


class Motherlode:
    def __init__(self, settings, base: Path, session: requests.Session | None = None) -> None:
        self.settings = settings
        self.dir = Path(base) / "motherlode"
        self.http = session or requests.Session()
        self._lock = threading.Lock()
        self._last = 0.0
        self._mem: dict[str, tuple[float, list]] = {}

    # ------------------------------------------------------------ peticiones
    def key(self) -> str:
        return (self.settings.get("motherlode_clave") or "").strip()

    def _request(self, path: str):
        key = self.key()
        if not key:
            raise NoKey("Falta la clave gratuita de Motherlode.")
        with self._lock:
            wait = MIN_GAP - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
        r = self.http.get(f"{API}/{path}", headers={**UA, "Authorization": f"Bearer {key}", "Accept": "application/json"},
                          timeout=15)
        if r.status_code == 401:
            raise MotherlodeError("Motherlode no acepta la clave (401): revisa que esté bien copiada.")
        if r.status_code == 429:
            raise MotherlodeError("Motherlode pide esperar un poco (límite de 60 consultas por minuto).")
        r.raise_for_status()
        return r.json()

    def get(self, name: str) -> list:
        """Un conjunto de datos, de la memoria, del disco o de la API (por este orden)."""
        ttl = TTL.get(name, 3600)
        now = time.time()
        hit = self._mem.get(name)
        if hit and now - hit[0] < ttl:
            return hit[1]
        f = self.dir / f"{name}.json"
        stale = None
        try:
            saved = json.loads(f.read_text(encoding="utf-8"))
            stale = saved
            if now - saved.get("t", 0) < ttl and isinstance(saved.get("data"), list):
                self._mem[name] = (saved["t"], saved["data"])
                return saved["data"]
        except (OSError, ValueError):
            pass
        try:
            data = self._request(name)
        except NoKey:
            raise
        except Exception as e:  # noqa: BLE001 — sin red o error del servidor: lo último guardado
            if stale and isinstance(stale.get("data"), list):
                log.info("Motherlode %s: uso lo guardado (%s)", name, e)
                return stale["data"]
            raise MotherlodeError(str(e)) from e
        if not isinstance(data, list):
            data = data.get("data") if isinstance(data, dict) and isinstance(data.get("data"), list) else []
        self._mem[name] = (now, data)
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps({"t": now, "data": data}, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        return data

    def test(self) -> dict:
        """Botón «Probar»: a quién pertenece la clave."""
        me = self._request("me")
        owner = {}
        if isinstance(me, dict):
            owner = me.get("owner") or me.get("user") or me
        name = ""
        if isinstance(owner, dict):
            name = owner.get("displayName") or owner.get("name") or owner.get("handle") or ""
        return {"ok": True, "nombre": str(name)}

    # ------------------------------------------------------------ búsquedas
    def _index(self, name: str) -> dict[str, dict]:
        return {str(x.get("id")): x for x in self.get(name) if isinstance(x, dict)}

    @staticmethod
    def _find(items, q: str, keys=("displayName", "name", "gameName", "id")) -> dict | None:
        qn = _norm(q)
        if not qn:
            return None
        best, score = None, 0
        for it in items:
            for k in keys:
                v = _norm(it.get(k) or "")
                if not v:
                    continue
                s = 4 if v == qn else 3 if v.startswith(qn) else 2 if qn in v.split() else 1 if qn in v else 0
                if s > score:
                    best, score = it, s
        if best is None:  # dictado o grafía de otra web («Quantanium»): por parecido
            import difflib
            for it in items:
                for k in keys:
                    v = _norm(it.get(k) or "")
                    r = difflib.SequenceMatcher(None, qn, v).ratio() if v else 0
                    if r >= 0.86 and r > score:
                        best, score = it, r
        return best

    @staticmethod
    def _comp(item: dict) -> tuple[str, str, str]:
        """(id del mineral, % en la roca, calidad) de un elemento de «composition», sea cual sea su forma."""
        oid = next((str(item[k]) for k in ("oreId", "commodityId", "materialId", "ore", "id") if item.get(k)), "")
        pct = ""
        for k in ("percentRange", "percentage", "percent", "share", "range"):
            if k in item:
                pct = _range(item[k])
                break
        if not pct:
            lo = next((item[k] for k in ("minPercent", "min", "minPct") if k in item), None)
            hi = next((item[k] for k in ("maxPercent", "max", "maxPct") if k in item), None)
            if lo is not None or hi is not None:
                pct = f"{_num(lo)}–{_num(hi)}"
        q = next((_range(item[k]) for k in ("qualityRange", "quality") if k in item), "")
        return oid, pct, q

    def _name(self, ores: dict, oid: str) -> str:
        o = ores.get(oid) or {}
        return o.get("displayName") or o.get("name") or oid

    def _place(self, locs: dict, lid: str | None) -> str:
        loc = locs.get(str(lid)) or {}
        name = loc.get("name") or (lid or "")
        sysname = (loc.get("system") or "").capitalize()
        return f"{name} ({sysname})" if sysname and sysname.lower() not in name.lower() else name

    def mineral(self, nombre: str) -> str:
        ores = self._index("commodities")
        ore = self._find([o for o in ores.values() if o.get("isMinable", True)], nombre) or self._find(ores.values(), nombre)
        if not ore:
            return f"SIN DATOS: Motherlode no conoce el mineral «{nombre}»."
        oid = str(ore["id"])
        name = ore.get("displayName") or ore.get("name") or oid
        locs = self._index("locations")
        out = [f"{name} (Motherlode · cryon.rocks):"]
        bits = [x for x in (ore.get("rarity"), ore.get("oreType"), i18n.tr("volátil") if ore.get("isVolatile") else "") if x]
        if bits:
            out.append(" · ".join(bits))
        if ore.get("refinedPrice"):
            out.append(i18n.tr("Precio de referencia refinado: {p} aUEC/SCU", p=_num(ore["refinedPrice"])))
        # dónde: tipos de roca que lo llevan
        where = []
        for rk in self.get("rock-types"):
            comp = [self._comp(c) for c in (rk.get("composition") or []) if isinstance(c, dict)]
            mine = [c for c in comp if c[0] == oid]
            if rk.get("primaryOreId") != oid and not mine:
                continue
            pct, q = (mine[0][1], mine[0][2]) if mine else ("", "")
            det = [x for x in (f"{pct}%" if pct and pct != "?" else "", f"Q {q}" if q else "",
                               i18n.tr("resistencia {r}", r=_range(rk["resistanceRange"])) if rk.get("resistanceRange") else "",
                               i18n.tr("inestabilidad {r}", r=_range(rk["instabilityRange"])) if rk.get("instabilityRange") else "")
                   if x]
            where.append(self._place(locs, rk.get("locationId")) + (f" [{', '.join(det)}]" if det else ""))
        if where:
            uniq = list(dict.fromkeys(where))
            out.append(i18n.tr("Dónde minarlo ({n} sitios): ", n=len(uniq)) + "; ".join(uniq[:12])
                       + (" …" if len(uniq) > 12 else ""))
        else:
            out.append(i18n.tr("Motherlode no tiene sitios registrados para este mineral."))
        # dónde venderlo
        sell = self.best_prices(oid)
        if sell:
            out.append(i18n.tr("Dónde venderlo mejor: ") + "; ".join(sell))
        out.append(i18n.tr("Ficha completa: {u}", u=f"{SITE}/data/ores/{oid}"))
        return "\n".join(out)

    def best_prices(self, oid: str, n: int = 4) -> list[str]:
        try:
            prices = [p for p in self.get("market-prices") if str(p.get("oreId")) == oid and p.get("sellPrice")]
        except MotherlodeError:
            return []
        if not prices:
            return []
        try:
            terms = self._index("commodity-terminals")
        except MotherlodeError:
            terms = {}
        locs = self._index("locations")
        rows = []
        for p in sorted(prices, key=lambda x: -(x.get("sellPrice") or 0))[:n]:
            t = terms.get(str(p.get("terminalId"))) or {}
            where = (f"{t.get('location')} - {t.get('name')}" if t.get("location") else "") or self._place(locs, p.get("locationId"))
            age = _age(p.get("updatedAt"))
            rows.append(f"{where} {_num(p['sellPrice'])} aUEC" + (f" ({age})" if age else ""))
        return rows

    def place(self, nombre: str) -> str:
        locs = self._index("locations")
        loc = self._find(locs.values(), nombre, ("name", "id"))
        if not loc:
            return f"SIN DATOS: Motherlode no conoce el lugar «{nombre}»."
        lid = str(loc["id"])
        ores = self._index("commodities")
        found: dict[str, str] = {}
        for rk in self.get("rock-types"):
            if str(rk.get("locationId")) != lid:
                continue
            for c in rk.get("composition") or []:
                if isinstance(c, dict):
                    oid, pct, _q = self._comp(c)
                    if oid and oid not in found:
                        found[oid] = pct
            if rk.get("primaryOreId") and str(rk["primaryOreId"]) not in found:
                found[str(rk["primaryOreId"])] = ""
        name = self._place(locs, lid)
        if not found:
            return i18n.tr("{l}: Motherlode no tiene minerales registrados aquí.", l=name)
        rank = {"legendary": 0, "epic": 1, "rare": 2, "uncommon": 3, "common": 4}
        items = sorted(found, key=lambda o: (rank.get((ores.get(o) or {}).get("rarity", ""), 5), self._name(ores, o)))
        txt = "; ".join(self._name(ores, o) + (f" ({found[o]}%)" if found[o] and found[o] != "?" else "") for o in items)
        return i18n.tr("Minerales en {l} (Motherlode): ", l=name) + txt + "\n" + \
            i18n.tr("Ficha completa: {u}", u=f"{SITE}/data/locations/{slug(loc.get('name') or lid)}")

    def lasers(self, size: str = "") -> str:
        rows = self.get("mining-lasers")
        if size not in ("", None):
            try:
                rows = [r for r in rows if int(r.get("size", -1)) == int(size)]
            except ValueError:
                pass
        if not rows:
            return "SIN DATOS: no hay láseres de minería con ese tamaño."
        out = [i18n.tr("Láseres de minería (Motherlode; tamaño 0 = ROC o vehículo):")]
        for r in sorted(rows, key=lambda r: (r.get("size", 0), r.get("name") or ""))[:20]:
            bits = [f"S{r.get('size')}"]
            if r.get("powerRange"):
                bits.append(i18n.tr("potencia {p}", p=_range(r["powerRange"])))
            if r.get("moduleSlots") is not None:
                bits.append(i18n.tr("{n} módulos", n=r["moduleSlots"]))
            if r.get("miningRange"):
                bits.append(f"{_num(r['miningRange'])} m")
            if r.get("price"):
                bits.append(f"{_num(r['price'])} aUEC")
            out.append(f"- {r.get('name')}" + (f" ({r.get('manufacturer')})" if r.get("manufacturer") else "")
                       + ": " + ", ".join(bits))
        return "\n".join(out)

    def refineries(self) -> str:
        locs = self._index("locations")
        rows = [r for r in self.get("refineries") if r.get("bonus") not in (None, 0)]
        if not rows:
            return "SIN DATOS: Motherlode no tiene bonificaciones de refinería."
        rows.sort(key=lambda r: -(r.get("bonus") or 0))
        # la web muestra «+5 %»; si la API lo da como fracción (0.05), se pasa a porcentaje
        scale = 100 if max(abs(float(r["bonus"])) for r in rows) <= 1 else 1
        txt = "; ".join(f"{r.get('name') or self._place(locs, r.get('locationId'))} {float(r['bonus']) * scale:+g}%"
                        for r in rows[:12])
        return i18n.tr("Refinerías con bonificación (Motherlode): ") + txt + "\n" + \
            i18n.tr("La bonificación de cada mineral está en su ficha: {u}", u=f"{SITE}/data/refineries")

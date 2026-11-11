"""StarMap (starmap.space): planetas, lunas, estaciones y lugares de Star Citizen con su API pública
de solo lectura (https://starmap.space/api/docs.php).

Uso respetuoso, como pide su documentación: se piden solo los datos que hacen falta (los lugares, de
un planeta cada vez), se guardan una semana en tu equipo y nunca se descargan imágenes en bloque."""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import unicodedata
from pathlib import Path

import requests

log = logging.getLogger("nova.starmap")

API = "https://starmap.space/api/v4"
SITE = "https://starmap.space"
# Su API rechaza los agentes que se presentan como «bot», «crawler»… NOVA es un asistente personal.
UA = {"User-Agent": "NOVA-AI/1.3 (asistente de voz de Star Citizen; +https://github.com/0zzyt0/NOVA-AI)"}
TTL = 7 * 86400

TYPE_ES = {"Star": "Estrella", "Planet": "Planeta", "Moon": "Luna", "Lagrange Point": "Punto de Lagrange",
           "Asteroid Belt": "Cinturón de asteroides", "Jump Point": "Punto de salto", "Station": "Estación",
           "Space Station": "Estación espacial", "Outpost": "Puesto avanzado", "Cave": "Cueva",
           "Landing Zone": "Zona de aterrizaje", "Wreck": "Restos de nave", "Derelict": "Abandonado",
           "Bunker": "Búnker", "Underground Facility": "Instalación subterránea", "Settlement": "Asentamiento",
           "Distribution Center": "Centro de distribución", "Mining Facility": "Instalación minera",
           "Scrapyard": "Desguace", "Racetrack": "Circuito de carreras", "Gas Cloud": "Nube de gas"}


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _yes(v) -> bool:
    return str(v).strip() in ("1", "true", "True")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fmt(n, dec: int = 1) -> str:
    if n is None:
        return ""
    s = f"{n:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s.rstrip("0").rstrip(",") if "," in s else s


class StarMap:
    def __init__(self, cache_dir: Path | None = None, http=None) -> None:
        self.cache_dir = cache_dir
        self.http = http or requests
        self._lock = threading.Lock()
        self._mem: dict[str, tuple[float, object]] = {}

    # ------------------------------------------------------------------ caché
    def _cached(self, key: str, url: str, params: dict) -> list:
        now = time.time()
        with self._lock:
            hit = self._mem.get(key)
            if hit and now - hit[0] < TTL:
                return hit[1]
        f = self.cache_dir / f"{key}.json" if self.cache_dir else None
        if f and f.exists() and now - f.stat().st_mtime < TTL:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                with self._lock:
                    self._mem[key] = (f.stat().st_mtime, data)
                return data
            except (OSError, ValueError):
                pass
        try:
            r = self.http.get(url, params=params, headers=UA, timeout=15)
            if getattr(r, "status_code", 200) >= 400:
                raise LookupError(f"starmap.space respondió {r.status_code}")
            data = r.json()
        except LookupError:
            raise
        except Exception as e:  # noqa: BLE001 — sin conexión: la última copia, aunque sea vieja
            if f and f.exists():
                try:
                    return json.loads(f.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    pass
            raise LookupError(f"No pude leer starmap.space ({type(e).__name__})") from e
        data = data if isinstance(data, list) else []  # sin coincidencias: {"response": "error"}
        with self._lock:
            self._mem[key] = (now, data)
        if f:
            try:
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
        return data

    def containers(self) -> list[dict]:
        """Estrellas, planetas, lunas, puntos de Lagrange, estaciones… (unas 230 entradas, una vez por semana)."""
        return self._cached("contenedores", f"{API}/oc/index.php", {})

    def pois(self, planet: str) -> list[dict]:
        """Lugares de un planeta o luna (cuevas, puestos, restos…), solo de ese cuerpo."""
        key = "lugares_" + re.sub(r"[^a-z0-9]+", "_", norm(planet))
        return self._cached(key, f"{API}/pois/index.php", {"planet": planet})

    # --------------------------------------------------------------- buscar
    def container(self, name: str) -> dict | None:
        q = norm(name)
        if not q:
            return None
        items = self.containers()
        for c in items:
            if norm(c.get("ObjectContainer", "")) == q:
                return c
        best = []
        for c in items:
            n = norm(c.get("ObjectContainer", ""))
            if n and (q in n or (len(n) >= 4 and n in q)):
                best.append(c)
        return min(best, key=lambda c: len(c.get("ObjectContainer", ""))) if best else None

    def poi(self, name: str, planet: str) -> dict | None:
        q = norm(name)
        if not q or not planet:
            return None
        items = self.pois(planet)
        for p in items:
            if norm(p.get("PoiName", "")) == q:
                return p
        cands = [p for p in items if q in norm(p.get("PoiName", ""))]
        if cands:
            return min(cands, key=lambda p: len(p.get("PoiName", "")))
        import difflib
        names = {norm(p.get("PoiName", "")): p for p in items}
        hit = difflib.get_close_matches(q, list(names), n=1, cutoff=0.85)
        return names[hit[0]] if hit else None


# --------------------------------------------------------------------- textos
def container_fields(c: dict) -> list[tuple[str, str]]:
    out = [("Tipo", TYPE_ES.get(c.get("Type", ""), c.get("Type", "") or "")), ("Sistema", c.get("System", ""))]
    r = _num(c.get("BodyRadius"))
    if r:
        out.append(("Radio", f"{_fmt(r / 1000, 0)} km"))
    g = _num(c.get("Gravitation"))
    if g:
        out.append(("Gravedad", f"{_fmt(g, 2)} g"))
    lo, hi = _num(c.get("SurfaceMinTemp")), _num(c.get("SurfaceMaxTemp"))
    if lo is not None and hi is not None:
        out.append(("Temperatura", f"{_fmt(lo, 0)} a {_fmt(hi, 0)} °C"))
    if c.get("AtmosphereBreathable") is not None:
        out.append(("Aire respirable", "sí" if _yes(c.get("AtmosphereBreathable")) else "no"))
    rot = _num(c.get("RotationSpeedX"))
    if rot:
        out.append(("Día", f"{_fmt(rot, 1)} h"))
    if c.get("LandingZones"):
        out.append(("Zonas de aterrizaje", str(c["LandingZones"])))
    if c.get("Jurisdiction"):
        out.append(("Jurisdicción", str(c["Jurisdiction"])))
    return [(k, v) for k, v in out if v]


def poi_fields(p: dict) -> list[tuple[str, str]]:
    out = [("Tipo", TYPE_ES.get(p.get("Type", ""), p.get("Type", "") or "")), ("Situado en", p.get("Planet", ""))]
    lat, lon = _num(p.get("Latitude")), _num(p.get("Longitude"))
    if lat is not None and lon is not None:
        out.append(("Coordenadas", f"{_fmt(lat, 2)}°, {_fmt(lon, 2)}°"))
    services = []
    for key, label in (("POI_MedBay", "enfermería"), ("POI_LandingPads", "plataformas de aterrizaje"),
                       ("POI_Terminals", "terminales"), ("POI_FreightElevator", "ascensor de carga")):
        v = p.get(key)
        if v not in (None, "", "0", 0, "-1", -1):
            services.append(label)
    if services:
        out.append(("Servicios", ", ".join(services)))
    if _yes(p.get("Zone_Armistice")):
        out.append(("Zona", "armisticio (sin armas)"))
    elif _yes(p.get("Zone_Trespassing")):
        out.append(("Zona", "prohibido el paso"))
    if p.get("POI_Faction"):
        out.append(("Facción", str(p["POI_Faction"])))
    for key, label in (("Minerals", "Minerales"), ("Harvestables", "Recolectables"), ("Missions", "Misiones")):
        if p.get(key):
            out.append((label, str(p[key])[:120]))
    return [(k, v) for k, v in out if v]


def describe(fields: list[tuple[str, str]], name: str) -> str:
    return f"{name} (starmap.space): " + " · ".join(f"{k}: {v}" for k, v in fields)

"""Comprueba que todas las páginas de consulta responden desde tu PC (botón «Comprobar páginas»).
Hace una consulta pequeña a cada una, a la vez, y dice si funciona y cuánto tarda. No abre el navegador."""
from __future__ import annotations

import concurrent.futures as cf
import time

import requests

UA = {"User-Agent": "NOVA-AI/1.3 (asistente de voz de Star Citizen; +https://github.com/0zzyt0/NOVA-AI)"}

# (id, nombre, url, parámetros, qué se comprueba en la respuesta: "json" | "html" | "lista")
CHECKS = [
    ("uex", "UEX Corp (API)", "https://api.uexcorp.uk/2.0/game_versions", None, "json"),
    ("uex_tiendas", "UEX Corp · tiendas", "https://api.uexcorp.uk/2.0/categories", None, "json"),
    ("wiki", "Star Citizen Wiki (API)", "https://starcitizen.tools/api.php",
     {"action": "query", "list": "search", "srsearch": "Daymar", "srlimit": 1, "format": "json"}, "json"),
    ("scmdb", "SCMDB", "https://scmdb.net/", None, "html"),
    ("verseguide", "VerseGuide", "https://verseguide.com/location/STANTON/2B", None, "html"),
    ("starmap", "StarMap (API)", "https://starmap.space/api/v4/oc/index.php", {"itemid": 1}, "lista"),
    ("spviewer", "SC Ships Performances Viewer", "https://www.spviewer.eu/", None, "html"),
    ("cstone", "Universal Item Finder (CStone)", "https://finder.cstone.space/", None, "html"),
    ("schaulers", "SC Haulers", "https://schaulers.com/tools", None, "html"),
    ("rsi", "Roberts Space Industries", "https://robertsspaceindustries.com/en/", None, "html"),
    ("rsi_estado", "Estado de los servidores de RSI", "https://status.robertsspaceindustries.com/", None, "html"),
    ("google", "Google Translate", "https://translate.googleapis.com/translate_a/single",
     {"client": "gtx", "sl": "es", "tl": "en", "dt": "t", "q": "hola"}, "lista"),
    ("github", "GitHub (actualizaciones)", "https://api.github.com/repos/0zzyt0/NOVA-AI", None, "json"),
]


def _one(check, http, timeout: float) -> dict:
    cid, name, url, params, kind = check
    t0 = time.time()
    try:
        r = http.get(url, params=params, headers=UA, timeout=timeout)
        ms = int((time.time() - t0) * 1000)
        code = getattr(r, "status_code", 0)
        if code >= 400:
            return {"id": cid, "nombre": name, "url": url, "ok": False, "ms": ms, "texto": f"respondió {code}"}
        if kind in ("json", "lista"):
            data = r.json()
            if kind == "lista" and not isinstance(data, list):
                return {"id": cid, "nombre": name, "url": url, "ok": False, "ms": ms, "texto": "respuesta inesperada"}
        return {"id": cid, "nombre": name, "url": url, "ok": True, "ms": ms, "texto": f"funciona ({ms} ms)"}
    except Exception as e:  # noqa: BLE001
        return {"id": cid, "nombre": name, "url": url, "ok": False, "ms": int((time.time() - t0) * 1000),
                "texto": f"sin respuesta ({type(e).__name__})"}


def run(http=None, timeout: float = 12) -> list[dict]:
    http = http or requests
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        return list(ex.map(lambda c: _one(c, http, timeout), CHECKS))

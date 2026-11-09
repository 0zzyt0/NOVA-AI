"""Al arrancar (antes de activar nada): ¿hay datos nuevos en las páginas de consulta?

  - scmdb.net: misiones, planos, fabricación, minería… de cada parche LIVE. Se mira su
    latest.json (primero en su espejo público para programas, luego en scmdb.net) y solo
    se descarga si la versión del juego ha cambiado. CC BY-NC-ND 4.0: se descarga en tu PC
    para tu uso, igual que haría tu navegador; Nova no lo redistribuye.
  - UEX Corp (uexcorp.space): versión del juego que siguen, mercancías con precios medios,
    naves y métodos de refinado. Los precios cambian a diario: se renuevan cada 24 h.
  - Star Citizen Wiki (starcitizen.tools): se comprueba que responde (se consulta en directo).
  - global.ini de tu juego: se recarga si un parche lo ha cambiado.

Sin internet no pasa nada: se usa la última copia descargada.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable

import requests

from .config import VERSION
from .knowledge import KNOW_DIR

log = logging.getLogger("nova.updater")

UA = {"User-Agent": f"NOVA-AI/{VERSION} (asistente de voz para Star Citizen; uso personal)"}
SCMDB_MIRROR = "https://raw.githubusercontent.com/KrovaxCode/SCMDB_DATA/main/data"
SCMDB = "https://scmdb.net/data"
SCMDB_FILES = ("merged", "crafting_blueprints", "crafting_items", "mining_data", "mining_equipment")
UEX_API = "https://api.uexcorp.uk/2.0"
UEX_SETS = ("commodities", "vehicles", "refineries_methods")
UEX_TTL = 24 * 3600
WIKI_API = "https://starcitizen.tools/api.php"

# Las páginas de consulta (también se enseñan en la ventana)
PAGES = [
    {"id": "scmdb", "nombre": "SCMDB", "url": "https://scmdb.net",
     "que": "Misiones, recompensas, planos (blueprints), fabricación y minería del parche LIVE"},
    {"id": "uex", "nombre": "UEX Corp", "url": "https://uexcorp.space/?set_lang=es_ES",
     "que": "Precios de mercancías, rutas comerciales, naves, objetos y refinerías"},
    {"id": "wiki", "nombre": "Star Citizen Wiki", "url": "https://starcitizen.tools",
     "que": "Lore, naves, armas, lugares y mecánicas"},
    {"id": "juego", "nombre": "Textos de tu juego", "url": "",
     "que": "global.ini: naves, objetos, planetas, minerales, consejos y avisos del HUD en tu idioma"},
]

Progress = Callable[[dict], None]


class Updater:
    def __init__(self, settings, gamelog=None, knowledge=None, base: Path = KNOW_DIR,
                 on_progress: Progress | None = None, session: requests.Session | None = None) -> None:
        self.settings = settings
        self.gamelog = gamelog
        self.knowledge = knowledge
        self.base = base
        self.on_progress = on_progress or (lambda ev: None)
        self.http = session or requests.Session()
        self.http.headers.update(UA)
        self.state_file = base / "estado.json"
        self.state: dict = self._load_state()
        self.running = threading.Event()
        self.done = threading.Event()
        self.report: dict[str, dict] = {}

    # ---------------------------------------------------------------- estado
    def _load_state(self) -> dict:
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_state(self) -> None:
        try:
            self.base.mkdir(parents=True, exist_ok=True)
            tmp = self.state_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.state_file)
        except OSError as e:
            log.warning("Estado de las fuentes: %s", e)

    def _step(self, source: str, status: str, text: str, pct: float | None = None, **extra) -> None:
        ev = {"fuente": source, "estado": status, "texto": text}
        if pct is not None:
            ev["pct"] = round(max(0.0, min(100.0, pct)), 1)
        ev.update(extra)
        if status in ("ok", "actualizado", "sin cambios", "error", "sin conexión", "omitido"):
            self.report[source] = ev
        try:
            self.on_progress(ev)
        except Exception:
            log.exception("Progreso")

    # ------------------------------------------------------------------ http
    def _json(self, url: str, timeout: float = 10) -> dict | list:
        r = self.http.get(url, timeout=(6, timeout))
        r.raise_for_status()
        return r.json()

    def _download(self, urls: list[str], dest: Path, source: str, label: str, done: float, share: float) -> None:
        """Descarga con progreso (prueba cada dirección en orden). Escribe a .part y renombra al terminar."""
        last_err: Exception | None = None
        for url in urls:
            try:
                with self.http.get(url, stream=True, timeout=(6, 60)) as r:
                    r.raise_for_status()
                    total = int(r.headers.get("Content-Length") or 0)
                    got = 0
                    tmp = dest.with_suffix(dest.suffix + ".part")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    tick = 0.0
                    with open(tmp, "wb") as f:
                        for chunk in r.iter_content(256 * 1024):
                            f.write(chunk)
                            got += len(chunk)
                            if time.time() - tick > 0.25:
                                tick = time.time()
                                frac = got / total if total else 0.5
                                self._step(source, "descargando", f"{label} · {got / 1e6:.1f} MB",
                                           (done + share * frac) * 100)
                    json.loads(tmp.read_text(encoding="utf-8"))  # que sea JSON válido antes de usarlo
                    os.replace(tmp, dest)
                    return
            except (requests.RequestException, ValueError, OSError) as e:
                last_err = e
                log.info("Descarga %s: %s", url, e)
        raise last_err or RuntimeError("sin direcciones")

    # ================================================================ fuentes
    def check_global_ini(self) -> None:
        if not self.gamelog:
            return
        self._step("juego", "comprobando", "Buscando los textos de tu juego…")
        self.gamelog.load_texts(force=True)
        t = self.gamelog.text
        if t.path:
            when = time.strftime("%d/%m/%Y", time.localtime(t.mtime))
            self._step("juego", "ok", f"{t.language} · {len(t.entries):,} textos · {when}".replace(",", "."),
                       version=t.language)
            self.state["juego"] = {"version": t.language, "ruta": str(t.path), "fecha": t.mtime,
                                   "comprobado": time.time()}
        else:
            self._step("juego", "omitido", "Juego en inglés o sin global.ini: uso los textos ingleses que trae Nova")

    def check_scmdb(self) -> None:
        channel = self.settings.get("datos_canal") or "live"
        self._step("scmdb", "comprobando", "Mirando si hay datos de un parche nuevo…")
        latest, base_used = None, ""
        for base in (SCMDB_MIRROR, SCMDB):
            try:
                latest = self._json(f"{base}/latest.json")
                base_used = base
                break
            except (requests.RequestException, ValueError) as e:
                log.info("scmdb %s: %s", base, e)
        info = (latest or {}).get("channels", {}).get(channel) if isinstance(latest, dict) else None
        old = self.state.get("scmdb") or {}
        if not info:
            have = old.get("version")
            self._step("scmdb", "sin conexión", f"No responde · uso la copia {have}" if have else "No responde y no hay copia todavía",
                       version=have or "")
            return
        version, files = info.get("version", ""), info.get("files") or {}
        folder = self.base / "scmdb"
        missing = [k for k in SCMDB_FILES if files.get(k) and not (folder / os.path.basename(files[k])).exists()]
        if version == old.get("version") and not missing:
            old["comprobado"] = time.time()
            self.state["scmdb"] = old
            self._step("scmdb", "sin cambios", f"Al día · {version}", 100, version=version)
            return
        wanted = [k for k in SCMDB_FILES if files.get(k)]
        for i, kind in enumerate(wanted):
            name = os.path.basename(files[kind])
            dest = folder / name
            if dest.exists():
                continue
            urls = [f"{b}/{name}" for b in ([base_used] + [x for x in (SCMDB_MIRROR, SCMDB) if x != base_used])]
            self._download(urls, dest, "scmdb", f"{kind.replace('_', ' ')} ({i + 1}/{len(wanted)})",
                           i / len(wanted), 1 / len(wanted))
        keep = {os.path.basename(files[k]) for k in wanted}
        for p in folder.glob("*.json"):  # fuera las versiones anteriores
            if p.name not in keep:
                try:
                    p.unlink()
                except OSError:
                    pass
        self.state["scmdb"] = {"version": version, "comprobado": time.time(), "actualizado": time.time(),
                               "generado": info.get("generated_at", "")}
        self._step("scmdb", "actualizado", f"Actualizado a {version}", 100, version=version)

    def check_uex(self) -> None:
        self._step("uex", "comprobando", "Consultando la versión del juego en UEX…")
        old = self.state.get("uex") or {}
        try:
            gv = self._json(f"{UEX_API}/game_versions")
            live = (gv.get("data") or {}).get("live", "") if isinstance(gv, dict) else ""
        except (requests.RequestException, ValueError) as e:
            log.info("UEX: %s", e)
            have = old.get("version")
            self._step("uex", "sin conexión", f"No responde · uso la copia {have}" if have else "No responde",
                       version=have or "")
            return
        folder = self.base / "uex"
        stale = time.time() - (old.get("actualizado") or 0) > UEX_TTL
        missing = [s for s in UEX_SETS if not (folder / f"{s}.json").exists()]
        if live == old.get("version") and not stale and not missing:
            old["comprobado"] = time.time()
            self.state["uex"] = old
            self._step("uex", "sin cambios", f"Al día · juego {live}", 100, version=live)
            return
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "game_versions.json").write_text(json.dumps(gv, ensure_ascii=False), encoding="utf-8")
        for i, name in enumerate(UEX_SETS):
            self._download([f"{UEX_API}/{name}"], folder / f"{name}.json", "uex",
                           f"{name.replace('_', ' ')} ({i + 1}/{len(UEX_SETS)})", i / len(UEX_SETS), 1 / len(UEX_SETS))
        self.state["uex"] = {"version": live, "comprobado": time.time(), "actualizado": time.time()}
        self._step("uex", "actualizado", f"Precios y naves actualizados · juego {live}", 100, version=live)

    def check_wiki(self) -> None:
        self._step("wiki", "comprobando", "Comprobando la wiki…")
        try:
            d = self._json(f"{WIKI_API}?action=query&meta=siteinfo&siprop=statistics&format=json", timeout=8)
            pages = ((d.get("query") or {}).get("statistics") or {}).get("articles") if isinstance(d, dict) else None
            self.state["wiki"] = {"comprobado": time.time(), "articulos": pages}
            self._step("wiki", "ok", f"En línea · {pages:,} artículos".replace(",", ".") if pages else "En línea")
        except (requests.RequestException, ValueError) as e:
            log.info("Wiki: %s", e)
            self._step("wiki", "sin conexión", "No responde ahora (se consultará cuando la necesite)")

    # ================================================================== todo
    def run(self) -> dict:
        """Comprueba todas las fuentes y prepara la enciclopedia. No lanza excepciones."""
        if self.running.is_set():
            self.done.wait(300)
            return self.report
        self.running.set()
        self.done.clear()
        self.report = {}
        t0 = time.time()
        try:
            self.check_global_ini()
            if self.settings.get("actualizar_al_iniciar", True):
                for fn, src in ((self.check_scmdb, "scmdb"), (self.check_uex, "uex"), (self.check_wiki, "wiki")):
                    try:
                        fn()
                    except Exception as e:
                        log.exception("Actualizando %s", src)
                        have = (self.state.get(src) or {}).get("version", "")
                        self._step(src, "error", f"Falló ({type(e).__name__}) · uso la copia {have}" if have
                                   else f"Falló ({type(e).__name__})", version=have)
            else:
                for src in ("scmdb", "uex", "wiki"):
                    self._step(src, "omitido", "Comprobación al iniciar desactivada")
            self._save_state()
            if self.knowledge is not None:
                self._step("indice", "comprobando", "Preparando la enciclopedia…")
                try:
                    self.knowledge.load()
                    s = self.knowledge.summary()
                    self._step("indice", "ok", f"{s['entradas']:,} entradas · {s['misiones']:,} misiones · "
                                               f"{s['planos']:,} planos".replace(",", "."))
                except Exception as e:
                    log.exception("Enciclopedia")
                    self._step("indice", "error", f"No se pudo preparar ({type(e).__name__})")
        finally:
            self.running.clear()
            self.done.set()
            self.on_progress({"fuente": "fin", "estado": "fin", "texto": f"Listo en {time.time() - t0:.0f} s",
                              "informe": self.report})
        return self.report

    def overview(self) -> list[dict]:
        """Para la ventana: cada página de consulta con su versión y la última comprobación."""
        out = []
        for p in PAGES:
            st = self.state.get(p["id"]) or {}
            rep = self.report.get(p["id"]) or {}
            out.append({**p, "version": st.get("version") or rep.get("version") or "",
                        "comprobado": st.get("comprobado"), "actualizado": st.get("actualizado"),
                        "estado": rep.get("estado", ""), "texto": rep.get("texto", "")})
        return out

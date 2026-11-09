"""Enciclopedia local de Star Citizen: rápida, sin internet y de TU versión del juego.

Junta tres fuentes (las descarga/actualiza updater.py al arrancar):
  - global.ini de tu juego: naves, objetos (fabricante, tipo, tamaño), planetas y lunas
    (minerales, recursos y criaturas), estaciones, fabricantes, delitos, diarios de lore, consejos.
  - scmdb.net (datos extraídos del juego en cada parche LIVE): misiones y contratos con pagos,
    reputación y PLANOS que dan; recetas de fabricación (blueprints); minería por ubicación,
    refinerías; estadísticas de armas, armaduras y componentes fabricables; equipo de minería.
    Licencia CC BY-NC-ND 4.0: Nova lo descarga en TU PC para uso personal y no lo redistribuye.
  - UEX Corp: mercancías con precio medio de compra y venta, naves (SCU, tripulación, plataforma),
    métodos de refinado.

Búsqueda por palabras (BM25) sin tildes ni mayúsculas, en español y en inglés.
"""
from __future__ import annotations

import json
import logging
import math
import pickle
import re
import threading
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from .config import DATA_DIR

log = logging.getLogger("nova.knowledge")

KNOW_DIR = DATA_DIR / "conocimiento"
SCMDB_DIR = KNOW_DIR / "scmdb"
UEX_DIR = KNOW_DIR / "uex"
INDEX_FILE = KNOW_DIR / "indice.pickle"
INDEX_VERSION = 5

STOP = set("""a al algo como con cual cuales de del donde el ella en es esa ese eso esta este esto hay la las le les lo los
mas me mi muy no o para pero por que se si sin sobre su sus te tu un una uno unos y ya yo the of and to in is for on with
at by an be it as from or this that are what which who how where cuanto cuanta cuantos cuantas cual quien""".split())

# Prefijos del global.ini que no aportan nada a la enciclopedia (textos de interfaz, diálogos sueltos…)
SKIP_PREFIX = ("ui_", "frontend", "input", "pause", "hud_", "mobiglas", "chat", "interaction", "ea_", "dfm", "mg_",
               "notification", "text_", "dlg", "pu_", "dxsm", "dxsh", "ph_", "starchitect", "commarray", "event_",
               "fw2022", "fw22", "soo2", "mission_", "missionmanager", "local_", "headhunters", "hockrow", "cfp_")

KIND_LABEL = {"nave": "Nave", "objeto": "Objeto", "lugar": "Lugar", "fabricante": "Fabricante", "mision": "Misión",
              "plano": "Plano", "mineral": "Minería", "lore": "Lore", "consejo": "Consejo", "mercancia": "Mercancía",
              "ley": "Ley", "equipo": "Equipo de minería", "refineria": "Refinería"}


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z0-9]+", norm(text)):
        if w in STOP or len(w) < 2:
            continue
        if len(w) > 4 and w.endswith("es") and not w.endswith("ses"):
            w = w[:-2]
        elif len(w) > 3 and w.endswith("s"):
            w = w[:-1]
        out.append(w)
    return out


def clean(text: str) -> str:
    t = (text or "").replace("\\n", "\n")
    t = re.sub(r"</?EM\d?>", "", t)
    t = re.sub(r"~\w+\((\w+)[^)]*\)", r"[\1]", t)
    return re.sub(r"[ \t]+", " ", t).strip()


def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _fmt(n) -> str:
    try:
        return f"{float(n):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


class Doc:
    __slots__ = ("title", "text", "kind", "source", "ref")

    def __init__(self, title: str, text: str, kind: str, source: str, ref=None) -> None:
        self.title, self.text, self.kind, self.source, self.ref = title, text, kind, source, ref


class Knowledge:
    def __init__(self, text=None, base: Path = KNOW_DIR) -> None:
        self.text = text  # GameText (global.ini)
        self.base = base
        self.ready = threading.Event()
        self.status = "sin cargar"
        self.versions: dict[str, str] = {}
        self._lock = threading.Lock()
        self._reset()

    def _reset(self) -> None:
        self.docs: list[Doc] = []
        self.index: dict[str, list[tuple[int, int]]] = {}
        self.doclen: list[int] = []
        self.avglen = 1.0
        self.contracts: list[dict] = []
        self.blueprints: list[dict] = []
        self.ores: dict[str, dict] = {}
        self.ore_places: dict[str, list[tuple[str, str, str, float, str]]] = defaultdict(list)
        self.refineries: list[dict] = []
        self.refinery_profiles: dict[str, dict] = {}
        self.items: dict[str, dict] = {}
        self.commodities: dict[str, dict] = {}
        self.vehicles: dict[str, dict] = {}

    # =================================================================== carga
    def load(self) -> None:
        """Lee todo lo descargado + el global.ini y construye el índice (con caché en disco)."""
        t0 = time.time()
        self.status = "preparando…"
        sig = self._signature()
        cached = self._load_cache(sig)
        if cached:
            with self._lock:
                self.__dict__.update(cached)
            self.status = f"lista · {len(self.docs):,} entradas".replace(",", ".")
            self.ready.set()
            log.info("Enciclopedia desde caché (%.1fs)", time.time() - t0)
            return
        new = Knowledge(self.text, self.base)
        try:
            new._load_scmdb()
        except Exception:
            log.exception("scmdb")
        try:
            new._load_uex()
        except Exception:
            log.exception("UEX")
        try:
            new._load_global_ini()
        except Exception:
            log.exception("global.ini")
        new._build_index()
        with self._lock:
            for k in ("docs", "index", "doclen", "avglen", "contracts", "blueprints", "ores", "ore_places",
                      "refineries", "refinery_profiles", "items", "commodities", "vehicles", "versions"):
                setattr(self, k, getattr(new, k))
        self._save_cache(sig)
        self.status = f"lista · {len(self.docs):,} entradas".replace(",", ".")
        self.ready.set()
        log.info("Enciclopedia: %d entradas en %.1fs", len(self.docs), time.time() - t0)

    def _signature(self) -> str:
        parts = [str(INDEX_VERSION)]
        for d in (SCMDB_DIR if self.base == KNOW_DIR else self.base / "scmdb",
                  UEX_DIR if self.base == KNOW_DIR else self.base / "uex"):
            if d.exists():
                parts += [f"{p.name}:{p.stat().st_size}:{int(p.stat().st_mtime)}" for p in sorted(d.glob("*.json"))]
        if self.text is not None and self.text.path:
            parts.append(f"{self.text.path}:{int(self.text.mtime)}")
        return "|".join(parts)

    def _cache_path(self) -> Path:
        return self.base / "indice.pickle"

    def _load_cache(self, sig: str) -> dict | None:
        try:
            with open(self._cache_path(), "rb") as f:
                data = pickle.load(f)
            if data.get("sig") == sig:
                data.pop("sig")
                return data
        except (OSError, pickle.PickleError, EOFError, AttributeError, ValueError):
            pass
        return None

    def _save_cache(self, sig: str) -> None:
        keep = ("docs", "index", "doclen", "avglen", "contracts", "blueprints", "ores", "ore_places",
                "refineries", "refinery_profiles", "items", "commodities", "vehicles", "versions")
        data = {k: getattr(self, k) for k in keep}
        data["ore_places"] = dict(data["ore_places"])
        data["sig"] = sig
        try:
            self.base.mkdir(parents=True, exist_ok=True)
            tmp = self._cache_path().with_suffix(".tmp")
            with open(tmp, "wb") as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            tmp.replace(self._cache_path())
        except OSError as e:
            log.warning("Caché de la enciclopedia: %s", e)

    def _local(self, key: str | None) -> str:
        if not key or self.text is None:
            return ""
        return self.text.local(str(key).lstrip("@")) or ""

    # ----------------------------------------------------------------- scmdb
    def _scmdb_file(self, kind: str) -> Path | None:
        d = self.base / "scmdb"
        found = sorted(d.glob(f"{kind}-*.json"), key=lambda p: p.stat().st_mtime) if d.exists() else []
        return found[-1] if found else None

    @staticmethod
    def _read(p: Path | None):
        if not p:
            return None
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def _load_scmdb(self) -> None:
        merged = self._read(self._scmdb_file("merged"))
        bps = self._read(self._scmdb_file("crafting_blueprints"))
        items = self._read(self._scmdb_file("crafting_items"))
        mining = self._read(self._scmdb_file("mining_data"))
        equip = self._read(self._scmdb_file("mining_equipment"))
        if merged:
            self.versions["scmdb"] = merged.get("version", "")
        bp_by_guid: dict[str, dict] = {}
        if bps:
            self._load_blueprints(bps, bp_by_guid)
        if merged:
            self._load_contracts(merged, bp_by_guid)
        if items:
            self._load_items(items)
        if mining:
            self._load_mining(mining)
        if equip:
            self._load_equipment(equip)

    def _load_blueprints(self, data: dict, by_guid: dict) -> None:
        for b in data.get("blueprints") or []:
            name = b.get("productName") or b.get("tag") or "?"
            tiers = []
            for t in b.get("tiers") or []:
                slots = []
                for s in t.get("slots") or []:
                    opts = []
                    for o in s.get("options") or []:
                        what = o.get("resourceName") or o.get("itemName") or "?"
                        qty = o.get("quantity")
                        unit = " SCU" if o.get("type") == "resource" else " ud."
                        q = f"{_num(qty):g}{unit}" if qty is not None else ""
                        mq = f" (calidad mín. {o['minQuality']})" if o.get("minQuality") else ""
                        opts.append(f"{q} de {what}{mq}".strip())
                    slots.append({"nombre": s.get("name") or "", "opciones": opts,
                                  "modificadores": bool(s.get("modifiers"))})
                tiers.append({"tiempo": t.get("craftTimeSeconds"), "huecos": slots})
            entry = {"guid": b.get("guid"), "producto": name, "tag": b.get("tag", ""),
                     "tipo": " ".join(x for x in (b.get("gear"), b.get("type"), b.get("subtype")) if x),
                     "fabricante": b.get("manufacturer") or "", "niveles": tiers, "misiones": []}
            self.blueprints.append(entry)
            if b.get("guid"):
                by_guid[b["guid"]] = entry

    def _load_contracts(self, data: dict, bp_by_guid: dict) -> None:
        pools = data.get("blueprintPools") or {}
        locs = data.get("locationPools") or {}
        frp = data.get("factionRewardsPools") or []
        for c in list(data.get("contracts") or []) + list(data.get("legacyContracts") or []):
            title_en = clean(c.get("title", ""))
            title = clean(self._local(c.get("titleLocKey"))) or title_en
            desc = clean(self._local(c.get("descriptionLocKey"))) or clean(c.get("description", ""))
            bps, chance = [], []
            for r in c.get("blueprintRewards") or []:
                pool = pools.get(r.get("blueprintPool")) or {}
                for b in pool.get("blueprints") or []:
                    nm = b.get("name") or ""
                    if nm and nm not in bps:
                        bps.append(nm)
                    entry = bp_by_guid.get(b.get("blueprintRecord"))
                    if entry is not None:
                        entry["misiones"].append({"titulo": title, "contratista": c.get("contractorName", ""),
                                                  "probabilidad": r.get("chance"), "sistemas": c.get("systems") or []})
                chance.append(r.get("chance"))
            places = []
            for lid in (c.get("locations") or [])[:6]:
                nm = (locs.get(lid) or {}).get("name")
                if nm and not nm.startswith("@") and nm not in places:
                    places.append(nm)
            for p in (c.get("prerequisites") or {}).get("location") or []:
                nm = p.get("name")
                if nm and nm not in places:
                    places.append(nm)
            rep = ""
            idx = c.get("factionRewardsIndex")
            if isinstance(idx, int) and 0 <= idx < len(frp) and frp[idx]:
                rep = sum(_num(x.get("amount")) for x in frp[idx])
            ms = c.get("minStanding") or {}
            entry = {
                "titulo": title, "titulo_en": title_en, "descripcion": desc[:900],
                "contratista": c.get("contractorName", ""), "tipo": c.get("missionType", ""),
                "categoria": c.get("category", ""), "pago": c.get("rewardUEC"), "sistemas": c.get("systems") or c.get("availableSystems") or [],
                "ilegal": bool(c.get("illegal")), "compartible": bool(c.get("canBeShared")),
                "rep_min": ms.get("name", ""), "rep_min_xp": ms.get("minReputation"), "rep_gana": rep,
                "planos": bps, "prob_plano": max([x for x in chance if isinstance(x, (int, float))], default=None),
                "objetos": [f"{i.get('amount', 1)}× {i.get('name')}" for i in (c.get("itemRewards") or []) if i.get("name")],
                "lugares": places, "jugadores": c.get("maxPlayersPerInstance"), "tiempo": c.get("timeToComplete"),
                "una_vez": bool(c.get("onceOnly")),
            }
            self.contracts.append(entry)

    def _load_items(self, data: dict) -> None:
        for it in data.get("items") or []:
            name = it.get("name")
            if not name:
                continue
            self.items[norm(name)] = {
                "nombre": name, "tipo": it.get("itemType") or it.get("cgItemType") or "", "tamano": it.get("size"),
                "grado": it.get("grade"), "fabricante": it.get("manufacturer") or "", "masa": it.get("mass"),
                "alcance": (it.get("combatRange") or {}).get("ideal"), "subtipo": it.get("attachSubType") or "",
            }

    def _load_mining(self, data: dict) -> None:
        comps = data.get("compositions") or {}
        for el in (data.get("mineableElements") or {}).values():
            name = el.get("materialName") or re.sub(r"\s*\((?:ore|raw)\)\s*$", "", el.get("name", ""), flags=re.I)
            if not name:
                continue
            self.ores.setdefault(norm(name), {
                "nombre": name, "rareza": el.get("rarity", ""), "firma_nave": el.get("scanSignature"),
                "firma_roc": el.get("groundScanSignature"), "firma_mano": el.get("fpsScanSignature"),
                "inestabilidad": el.get("instability"), "resistencia": el.get("resistance"),
            })
        kinds = {"SpaceShip_Mineables": "nave", "SpaceShip_Mineables_Rare": "nave (raro)",
                 "GroundVehicle_Mineables": "vehículo (ROC)", "FPS_Mineables": "a mano", "Harvestables": "recolección"}
        for loc in data.get("locations") or []:
            lname, system = loc.get("locationName", "?"), loc.get("system", "")
            for g in loc.get("groups") or []:
                how = kinds.get(g.get("groupName"))
                if not how:
                    continue
                deps = g.get("deposits") or []
                total = sum(_num(d.get("relativeProbability")) for d in deps) or 1.0
                share: Counter = Counter()
                for d in deps:
                    comp = comps.get(d.get("compositionGuid")) or {}
                    w = _num(g.get("groupProbability"), 1.0) * _num(d.get("relativeProbability")) / total
                    for part in comp.get("parts") or []:
                        el = re.sub(r"\s*\((?:ore|raw)\)\s*$", "", part.get("elementName", ""), flags=re.I)
                        share[el] += w * _num(part.get("probability"), 1.0)
                tot = sum(share.values()) or 1.0
                for el, s in share.items():  # % de los depósitos de ese tipo en ese sitio
                    self.ore_places[norm(el)].append((lname, system, how, round(100 * s / tot, 1), loc.get("locationType", "")))
        for k in self.ore_places:
            self.ore_places[k].sort(key=lambda x: -x[3])
        profiles = data.get("refineryProfiles") or {}
        self.refinery_profiles = profiles
        for r in data.get("refineries") or []:
            self.refineries.append({"nombre": r.get("name", ""), "sistema": r.get("system", ""),
                                    "perfil": profiles.get(r.get("profileId")) or {}})

    def _load_equipment(self, data: dict) -> None:
        for kind in ("lasers", "modules", "gadgets", "fpsTools"):
            for e in data.get(kind) or []:
                name = e.get("name")
                if not name:
                    continue
                bits = [f"{k}: {v}" for k, v in e.items() if k in ("size", "grade", "manufacturer", "type", "moduleSlots",
                                                                    "charges", "lifetime") and v not in (None, "")]
                mb = e.get("miningBeam") or {}
                if mb.get("damagePerSecond"):
                    bits.append(f"potencia de extracción {_fmt(mb['damagePerSecond'])}/s, alcance {mb.get('fullDamageRange')} m")
                mods = e.get("modifiers") or {}
                if mods:
                    bits.append("modificadores: " + ", ".join(f"{k} {v:+g}%" for k, v in mods.items()
                                                              if isinstance(v, (int, float)) and v))
                self.docs.append(Doc(name, "; ".join(bits), "equipo", "scmdb"))

    # -------------------------------------------------------------------- UEX
    def _load_uex(self) -> None:
        d = self.base / "uex"
        if not d.exists():
            return
        def rows(name):
            p = d / f"{name}.json"
            if not p.exists():
                return []
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                return []
            return data.get("data") if isinstance(data, dict) else data
        gv = rows("game_versions")
        if isinstance(gv, dict):
            self.versions["uex"] = gv.get("live", "")
        for c in rows("commodities") or []:
            if isinstance(c, dict) and c.get("name"):
                self.commodities[norm(c["name"])] = c
        for v in rows("vehicles") or []:
            if isinstance(v, dict) and (v.get("name_full") or v.get("name")):
                self.vehicles[norm(v.get("name_full") or v.get("name"))] = v
        self._uex_methods = rows("refineries_methods") or []

    # -------------------------------------------------------------- global.ini
    def _load_global_ini(self) -> None:
        if self.text is None or not self.text.entries:
            return
        e = self.text.entries
        self.versions["global.ini"] = self.text.language
        seen = set()
        for k, v in e.items():
            if k.startswith(SKIP_PREFIX) or "~mission(" in v:
                continue
            m = re.search(r"_desc(?:ription)?(?:_\d+)?$", k)
            if not m and not k.startswith(("item_desc", "vehicle_desc", "manufacturer_desc")):
                continue
            base = k[:m.start()] if m else k
            cands = [base, base + "_name", k.replace("_desc", "_name"), k.replace("desc", "name", 1)]
            name = next((e[c] for c in cands if c in e and c != k and len(e[c]) < 80), None)
            if not name or len(v) < 40:
                continue
            name = clean(name)
            if (name, v[:40]) in seen:
                continue
            seen.add((name, v[:40]))
            kind = ("nave" if k.startswith("vehicle_") else "objeto" if k.startswith(("item_", "items_", "nb_"))
                    else "fabricante" if k.startswith("manufacturer") else "ley" if k.startswith("infraction")
                    else "lugar")
            if k.startswith("items_commodities"):
                kind = "mercancia"
            self.docs.append(Doc(name, clean(v)[:1500], kind, "juego"))
        for k, v in e.items():
            if k.startswith("journal_") and k.endswith("_content"):
                title = e.get(k.replace("_content", "_title")) or k[8:-8].replace("_", " ")
                self.docs.append(Doc(clean(title), clean(v)[:2500], "lore", "juego"))
            elif k.startswith("hints_") and not k.endswith("_title") and len(v) > 40:
                title = e.get(k + "_title") or e.get(re.sub(r"\d+$", "", k) + "_title") or "Consejo"
                self.docs.append(Doc(clean(title), clean(v)[:800], "consejo", "juego"))

    # ------------------------------------------------------------------ índice
    def _structured_docs(self) -> None:
        for i, c in enumerate(self.contracts):
            bits = [c["contratista"], c["tipo"], ", ".join(c["sistemas"]), c["titulo_en"], " ".join(c["planos"]),
                    " ".join(c["lugares"]), c["descripcion"][:300]]
            self.docs.append(Doc(c["titulo"], " · ".join(b for b in bits if b), "mision", "scmdb", ("c", i)))
        for i, b in enumerate(self.blueprints):
            mats = " ".join(o for t in b["niveles"][:1] for s in t["huecos"] for o in s["opciones"])
            self.docs.append(Doc(f"Plano: {b['producto']}", f"{b['tipo']} {b['fabricante']} {mats}", "plano", "scmdb", ("b", i)))
        for key, o in self.ores.items():
            places = ", ".join(p[0] for p in self.ore_places.get(key, [])[:8])
            self.docs.append(Doc(o["nombre"], f"mineral {o['rareza']} se encuentra en {places}", "mineral", "scmdb", ("o", key)))
        for key, it in self.items.items():
            self.docs.append(Doc(it["nombre"], f"{it['tipo']} {it['subtipo']} tamaño {it['tamano']} grado {it['grado']} "
                                               f"{it['fabricante']}", "objeto", "scmdb"))
        for key, c in self.commodities.items():
            self.docs.append(Doc(c["name"], f"mercancía {c.get('kind', '')}; precio medio compra {_fmt(c.get('price_buy'))}, "
                                            f"venta {_fmt(c.get('price_sell'))} aUEC/SCU", "mercancia", "uex", ("m", key)))
        for key, v in self.vehicles.items():
            roles = ", ".join(k[3:] for k, val in v.items() if k.startswith("is_") and val == 1 and k not in
                              ("is_spaceship", "is_concept", "is_addon"))
            self.docs.append(Doc(v.get("name_full") or v.get("name"),
                                 f"{v.get('company_name', '')}; carga {v.get('scu')} SCU; tripulación {v.get('crew')}; "
                                 f"plataforma {v.get('pad_type')}; funciones: {roles}", "nave", "uex", ("v", key)))
        for r in self.refineries:
            bonus = ", ".join(f"{k.split(' (')[0]} {v:+d}%" for k, v in sorted(r["perfil"].items(), key=lambda kv: -kv[1])
                              if isinstance(v, int) and v > 0)
            self.docs.append(Doc(r["nombre"], f"refinería en {r['sistema']}; bonificaciones: {bonus}", "refineria", "scmdb"))

    def _build_index(self) -> None:
        self._structured_docs()
        index: dict[str, list[tuple[int, int]]] = defaultdict(list)
        lens = []
        for i, d in enumerate(self.docs):
            tf = Counter(tokens(d.text))
            for w in tokens(d.title):
                tf[w] += 3  # el título pesa más
            lens.append(sum(tf.values()) or 1)
            for w, n in tf.items():
                index[w].append((i, n))
        self.index, self.doclen = dict(index), lens
        self.avglen = (sum(lens) / len(lens)) if lens else 1.0

    # ================================================================ consultas
    def search(self, query: str, kinds: tuple[str, ...] | None = None, k: int = 6) -> list[Doc]:
        if not self.ready.is_set():
            self.ready.wait(20)
        q = tokens(query)
        if not q or not self.docs:
            return []
        n = len(self.docs)
        scores: dict[int, float] = defaultdict(float)
        k1, b = 1.4, 0.7
        for w in set(q):
            posting = self.index.get(w)
            if not posting:  # tolera plurales y erratas cortas: prefijo
                cands = [t for t in self.index if len(w) >= 5 and t.startswith(w[:5])][:5]
                posting = [p for t in cands for p in self.index[t]]
                if not posting:
                    continue
            idf = math.log(1 + (n - len(posting) + 0.5) / (len(posting) + 0.5))
            for i, f in posting:
                if kinds and self.docs[i].kind not in kinds:
                    continue
                scores[i] += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * self.doclen[i] / self.avglen))
        qn = norm(query)
        for i in list(scores):
            if norm(self.docs[i].title) in qn or qn in norm(self.docs[i].title):
                scores[i] *= 1.6  # nombre exacto
        best = sorted(scores, key=lambda i: -scores[i])[:k]
        return [self.docs[i] for i in best]

    def find_contracts(self, consulta: str = "", sistema: str = "", tipo: str = "", con_planos: bool = False,
                       legal: bool | None = None, k: int = 8) -> list[dict]:
        pool = self.contracts
        if sistema:
            s = norm(sistema)
            pool = [c for c in pool if any(norm(x) == s for x in c["sistemas"])]
        if tipo:
            t = norm(tipo)
            pool = [c for c in pool if t in norm(c["tipo"]) or t in norm(c["contratista"]) or t in norm(c["categoria"])]
        if con_planos:
            pool = [c for c in pool if c["planos"]]
        if legal is not None:
            pool = [c for c in pool if c["ilegal"] != legal]
        if consulta:
            ids = {id(c) for c in pool}
            hits = [d.ref[1] for d in self.search(consulta, ("mision", "plano"), k=60) if d.ref and d.ref[0] == "c"]
            ranked = [self.contracts[i] for i in hits if id(self.contracts[i]) in ids]
            if not ranked and con_planos:  # «¿qué misión da el plano X?»
                bp = self.find_blueprint(consulta)
                if bp:
                    titles = {m["titulo"] for m in bp["misiones"]}
                    ranked = [c for c in pool if c["titulo"] in titles]
            pool = ranked
        else:
            pool = sorted(pool, key=lambda c: -(_num(c["pago"])))
        # quitar duplicados (mismo título y pago)
        out, seen = [], set()
        for c in pool:
            key = (c["titulo"], c["pago"], c["contratista"])
            if key in seen:
                continue
            seen.add(key)
            out.append(c)
            if len(out) >= k:
                break
        return out

    def find_blueprints(self, name: str, k: int = 5) -> list[dict]:
        """Planos que encajan con el nombre: exactos primero; entre iguales, los que dan misiones y los más cortos."""
        q = norm(name)
        qt = set(tokens(q))
        scored = []
        for b in self.blueprints:
            p = norm(b["producto"])
            s = 3.0 if p == q else 2.0 if p.startswith(q) else 1.5 if q in p else 0.0
            if not s and qt:
                common = qt & set(tokens(p))
                s = len(common) / len(qt)
                s = s if s >= 0.6 else 0.0
            if s:
                scored.append((-s, -bool(b["misiones"]), len(p), b["producto"], b))
        scored.sort(key=lambda x: x[:4])
        return [x[4] for x in scored[:k]]

    def find_blueprint(self, name: str) -> dict | None:
        found = self.find_blueprints(name, 1)
        return found[0] if found else None

    def find_ore(self, name: str) -> tuple[dict | None, list]:
        q = norm(name)
        alias = {"quantanium": "quantainium", "cuantanio": "quantainium", "aluminio": "aluminum", "hierro": "iron",
                 "cobre": "copper", "oro": "gold", "titanio": "titanium", "estano": "tin", "cuarzo": "quartz",
                 "tungsteno": "tungsten", "silicio": "silicon", "berilo": "beryl", "corindon": "corundum",
                 "hielo": "pressurized ice"}
        q = alias.get(q, q)
        key = q if q in self.ores else next((k for k in self.ores if k.startswith(q) or q in k), None)
        if key is None:
            key = next((k for k in self.ore_places if k.startswith(q) or q in k), None)
        if key is None:
            return None, []
        return self.ores.get(key) or {"nombre": name}, self.ore_places.get(key, [])

    def best_refineries(self, ore: str, k: int = 5) -> list[tuple[str, str, int]]:
        q = norm(ore)
        out = []
        for r in self.refineries:
            for name, bonus in (r["perfil"] or {}).items():
                if isinstance(bonus, (int, float)) and norm(re.sub(r"\s*\(.*\)", "", name)) == q:
                    out.append((r["nombre"], r["sistema"], int(bonus)))
        return sorted(out, key=lambda x: -x[2])[:k]

    def commodity(self, name: str) -> dict | None:
        q = norm(name)
        if q in self.commodities:
            return self.commodities[q]
        return next((c for k, c in self.commodities.items() if k.startswith(q) or q in k), None)

    def summary(self) -> dict:
        kinds = Counter(d.kind for d in self.docs)
        return {"estado": self.status, "entradas": len(self.docs), "tipos": dict(kinds), "versiones": self.versions,
                "misiones": len(self.contracts), "planos": len(self.blueprints), "minerales": len(self.ores)}


def describe_doc(d: Doc, maxlen: int = 700) -> str:
    src = {"juego": "textos del juego", "scmdb": "scmdb.net", "uex": "UEX Corp"}.get(d.source, d.source)
    text = d.text if len(d.text) <= maxlen else d.text[:maxlen].rsplit(" ", 1)[0] + "…"
    return f"[{KIND_LABEL.get(d.kind, d.kind)} · {src}] {d.title}: {text}"

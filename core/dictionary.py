"""Diccionario de consultas: la «memoria física» de NOVA AI, un archivo de texto que no caduca nunca.

Diccionario_de_consultas.txt (en la carpeta de datos) guarda, por grupos y en orden alfabético, la
definición de planetas, lunas, estaciones, lugares, naves, armaduras, armas, componentes, recursos…
Se rellena al crearlo con los textos oficiales del juego (el global.ini de la traducción) y se completa
solo con lo que Nova aprende en internet. Nova lo consulta ANTES de gastar la IA o buscar en internet.

Formato (se puede editar a mano con el Bloc de notas; Nova respeta tus cambios):

    ==================== NAVES ====================
    * Anvil Paladin: definición…  ‹4.3.1 · 10/11/2026 · juego›
    * Attrition (6 variantes):
        - Attrition-1 Repetidor: definición…  ‹4.3.1 · 10/11/2026 · juego›
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("nova.dictionary")

FILE_NAME = "Diccionario_de_consultas.txt"
CREATED_MSG = ("Diccionario de consultas no encontrado, se creará uno. Para ahorrar tokens evite eliminarlo, "
               "NOVA AI lo usa como base offline de consultas.")

# Grupos de clase (se escriben en orden alfabético)
GROUPS = [
    "Accesorios de armas y munición", "Armaduras y trajes", "Armas de nave", "Armas personales",
    "Ciudades y zonas de aterrizaje", "Componentes de nave", "Equipo médico y utilidades", "Estaciones espaciales",
    "Estrellas y sistemas", "Fabricantes", "Leyes y delitos", "Lugares y puntos de interés", "Mercancías",
    "Naves y vehículos", "Objetos", "Pinturas y diseños", "Planetas y lunas", "Procesos de refinado",
    "Recursos y minerales", "Ropa", "Otros (aprendido en internet)",
]
OTHER = "Otros (aprendido en internet)"

META_RE = re.compile(r"\s*‹([^›]*)›\s*$")
ENTRY_RE = re.compile(r"^\*\s+(?P<name>[^:]+?)\s*:\s*(?P<text>.*)$")
FAMILY_RE = re.compile(r"^\*\s+(?P<name>.+?)\s*\((?P<n>\d+)\s+variantes?\)\s*:?\s*$")
VARIANT_RE = re.compile(r"^\s+-\s+(?P<name>[^:]+?)\s*:\s*(?P<text>.*)$")
GROUP_RE = re.compile(r"^=+\s*(?P<g>.+?)\s*=+\s*$")

# Palabras que no identifican al modelo (para agrupar variantes: «Torso Citadel» y «Brazos Citadel» = Citadel)
GENERIC = set("""
torso brazos piernas casco mochila core arms legs helmet backpack undersuit traje mono pintura diseno diseño
livery edicion edición edition modificado modified smg rifle fusil pistola escopeta lmg hmg ametralladora
lanzagranadas lanzador cuchillo granada francotirador asalto de del la el energia energía balistico balística
balistica laser láser repetidor cañon cañón canon gatling misil misiles cohetes rack soporte torreta
mascara máscara gafas guantes botas camisa camiseta chaqueta pantalones sombrero gorro abrigo sudadera
""".split())
MAKERS = {"anvil", "aegis", "drake", "rsi", "misc", "origin", "crusader", "banu", "esperia", "argo", "consolidated",
          "kruger", "gatac", "aopoa", "tumbril", "greycat", "mirai", "cnou", "c.o.", "vanduul", "xian", "xi'an",
          "roberts", "musashi"}
SIZE_CODE = re.compile(r"^(?:mil|ind|civ|cmp|stl|cmpt)/\d/[a-d]$", re.I)

LOOKUP_RE = re.compile(
    r"^(?:hablame|cuentame(?: algo)?|dime algo|dime que es|informacion|info|datos|ficha|que sabes|que es|que son|"
    r"quien es|quienes son|que hay en|como es|como son|describeme|describe|define|definicion|explicame que es)"
    r"(?: de| del| sobre| acerca de| de la| de los| de las)?(?: la| el| los| las| un| una)?\s+(?P<x>.+)$")
UPDATE_RE = re.compile(r"^(?:actualiza|refresca|renueva|vuelve a buscar)(?: la ficha| la definicion| la entrada| los datos"
                       r"| la informacion)?(?: de| del| de la| de los)?(?: la| el| los| las)?\s+(?P<x>.+)$")


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def one_line(text: str, limit: int = 1500) -> str:
    t = (text or "").replace("\\n", "\n")
    t = re.sub(r"</?EM\d?>", "", t)
    t = re.sub(r"~\w+\((\w+)[^)]*\)", r"[\1]", t)
    parts = [p.strip() for p in re.split(r"\n+", t) if p.strip()]
    out = " · ".join(parts)
    out = re.sub(r"\s+", " ", out).replace("‹", "<").replace("›", ">").strip()
    return out if len(out) <= limit else out[:limit].rsplit(" ", 1)[0] + "…"


def family_key(name: str) -> str:
    """«Attrition-3 Repetidor» -> «Attrition»; «Mil/2/A FR-76» -> «FR»; «Torso Citadel (Modificado)» -> «Citadel»;
    «Drake Cutlass Black» -> «Cutlass»."""
    n = re.sub(r"[\"“”«»].*?[\"“”«»]", " ", name or "")
    n = re.sub(r"\(.*?\)", " ", n)
    words = [w for w in re.split(r"\s+", n.strip()) if w]
    if len(words) > 1 and words[0].lower() in MAKERS:
        words = words[1:]
    for w in words:
        if SIZE_CODE.match(w):
            continue
        base = w.split("-")[0] if "-" in w and len(w.split("-")[0]) >= 2 else w
        if norm(base) in GENERIC or not re.search(r"[a-zA-Z]", base) or norm(base) in ("y", "con"):
            continue
        return base.strip(".,:;")
    return ""


@dataclass
class Entry:
    name: str
    text: str
    group: str
    patch: str = ""
    date: str = ""
    source: str = ""  # juego | internet | ia | verseguide | tú
    family: str = ""

    def meta(self) -> str:
        bits = [b for b in (self.patch, self.date, self.source) if b]
        return f"  ‹{' · '.join(bits)}›" if bits else ""


@dataclass
class Dictionary:
    path: Path
    meta_path: Path | None = None
    entries: dict[str, Entry] = field(default_factory=dict)  # norm(nombre) -> Entry
    notes: list[str] = field(default_factory=list)  # líneas que no son entradas (las respetamos)

    def __post_init__(self) -> None:
        self._lock = threading.RLock()
        self._mtime = 0.0
        self._written: dict[str, str] = {}  # huella de lo que escribió Nova (para notar tus cambios)
        self._loaded = False
        if self.meta_path and self.meta_path.exists():
            try:
                self._written = json.loads(self.meta_path.read_text(encoding="utf-8")).get("huellas", {})
            except (OSError, ValueError):
                self._written = {}

    # ----------------------------------------------------------------- archivo
    def exists(self) -> bool:
        return self.path.exists()

    def load(self, force: bool = False) -> None:
        """Lee el archivo (y lo vuelve a leer si lo has cambiado con el Bloc de notas)."""
        with self._lock:
            try:
                mtime = self.path.stat().st_mtime
            except OSError:
                self._loaded = True
                return
            if self._loaded and not force and mtime == self._mtime:
                return
            text = self.path.read_text(encoding="utf-8-sig", errors="replace")
            self.entries, self.notes = {}, []
            group, family = OTHER, ""
            for raw in text.splitlines():
                line = raw.rstrip()
                if not line.strip() or line.startswith("#"):
                    continue
                g = GROUP_RE.match(line)
                if g and not line.startswith("*"):
                    name = g.group("g").strip().capitalize()
                    group = next((x for x in GROUPS if norm(x) == norm(name)), g.group("g").strip())
                    family = ""
                    continue
                f = FAMILY_RE.match(line)
                if f:
                    family = f.group("name").strip()
                    continue
                v = VARIANT_RE.match(raw)
                if v and family:
                    self._parse_entry(v.group("name"), v.group("text"), group, family)
                    continue
                e = ENTRY_RE.match(line)
                if e:
                    family = ""
                    self._parse_entry(e.group("name"), e.group("text"), group, "")
                    continue
                if not line.startswith(("DICCIONARIO", "Base offline", "Puedes editar", "Formato", "Índice",
                                        "Actualizado", "  ·", "Grupos")):
                    self.notes.append(line.strip())
            self._mtime = mtime
            self._loaded = True

    def _parse_entry(self, name: str, text: str, group: str, family: str) -> None:
        meta = META_RE.search(text)
        patch = date = source = ""
        if meta:
            bits = [b.strip() for b in meta.group(1).split("·")]
            text = text[:meta.start()]
            for b in bits:
                if re.match(r"^\d{2}/\d{2}/\d{4}$", b):
                    date = b
                elif b in ("juego", "internet", "ia", "verseguide", "tú", "tu", "wiki"):
                    source = b
                elif b:
                    patch = b
        text = text.strip()
        key = norm(name)
        if not key:
            return
        written = self._written.get(key)
        if written and written != _hash(text) and source != "tú":
            source = "tú"  # la has cambiado a mano: Nova no la vuelve a tocar
        self.entries[key] = Entry(name.strip(), text, group, patch, date, source, family)

    def save(self) -> None:
        with self._lock:
            by_group: dict[str, list[Entry]] = {}
            for e in self.entries.values():
                by_group.setdefault(e.group if e.group in GROUPS else OTHER, []).append(e)
            total = len(self.entries)
            lines = [
                "DICCIONARIO DE CONSULTAS · NOVA AI",
                "Base offline de consultas: NOVA AI mira aquí antes de gastar la IA o buscar en internet.",
                "Puedes editar las definiciones con el Bloc de notas: NOVA AI respeta tus cambios. No lo borres.",
                "Formato: * Nombre: definición  ‹parche · fecha · origen›   (las variantes van debajo de su familia)",
                f"Actualizado el {time.strftime('%d/%m/%Y %H:%M')} · {total} entradas",
                "",
                "Grupos:",
            ]
            for g in GROUPS:
                if by_group.get(g):
                    lines.append(f"  · {g} ({len(by_group[g])})")
            lines.append("")
            for g in GROUPS:
                items = by_group.get(g)
                if not items:
                    continue
                lines += [f"==================== {g.upper()} ====================", ""]
                fams: dict[str, list[Entry]] = {}
                singles: list[Entry] = []
                for e in items:
                    if e.family:
                        fams.setdefault(e.family, []).append(e)
                    else:
                        singles.append(e)
                rows: list[tuple[str, object]] = [(norm(e.name), e) for e in singles]
                rows += [(norm(f), (f, v)) for f, v in fams.items()]
                for _k, it in sorted(rows, key=lambda r: r[0]):
                    if isinstance(it, Entry):
                        lines.append(f"* {it.name}: {it.text}{it.meta()}")
                    else:
                        fam, variants = it
                        lines.append(f"* {fam} ({len(variants)} variantes):")
                        for v in sorted(variants, key=lambda x: _natural(x.name)):
                            lines.append(f"    - {v.name}: {v.text}{v.meta()}")
                lines.append("")
            if self.notes:
                lines += ["==================== NOTAS ====================", ""] + self.notes + [""]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text("\n".join(lines), encoding="utf-8-sig")
            os.replace(tmp, self.path)
            self._mtime = self.path.stat().st_mtime
            self._written = {k: _hash(e.text) for k, e in self.entries.items() if e.source != "tú"}
            if self.meta_path:
                try:
                    self.meta_path.parent.mkdir(parents=True, exist_ok=True)
                    old = {}
                    if self.meta_path.exists():
                        old = json.loads(self.meta_path.read_text(encoding="utf-8"))
                    old["huellas"] = self._written
                    self.meta_path.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
                except (OSError, ValueError):
                    pass

    def meta_get(self, key: str, default=None):
        if not self.meta_path or not self.meta_path.exists():
            return default
        try:
            return json.loads(self.meta_path.read_text(encoding="utf-8")).get(key, default)
        except (OSError, ValueError):
            return default

    def meta_set(self, key: str, value) -> None:
        if not self.meta_path:
            return
        try:
            data = json.loads(self.meta_path.read_text(encoding="utf-8")) if self.meta_path.exists() else {}
        except (OSError, ValueError):
            data = {}
        data[key] = value
        self.meta_path.parent.mkdir(parents=True, exist_ok=True)
        self.meta_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    # --------------------------------------------------------------- escribir
    def put(self, name: str, text: str, group: str = OTHER, source: str = "internet", patch: str = "",
            family: str | None = None, overwrite: bool = True, save: bool = True) -> Entry | None:
        name, text = (name or "").strip(), one_line(text)
        if not name or len(text) < 8:
            return None
        key = norm(name)
        with self._lock:
            self.load()
            old = self.entries.get(key)
            if old and (old.source == "tú" or not overwrite):
                return old  # lo que tú has escrito manda
            if family is None:
                family = old.family if old else ""
            e = Entry(name, text, group if group in GROUPS else OTHER, patch, time.strftime("%d/%m/%Y"), source, family)
            self.entries[key] = e
            if save:
                self.save()
            return e

    def count(self) -> int:
        self.load()
        return len(self.entries)

    def groups_count(self) -> dict[str, int]:
        self.load()
        out: dict[str, int] = {}
        for e in self.entries.values():
            out[e.group] = out.get(e.group, 0) + 1
        return out

    # ----------------------------------------------------------------- buscar
    def find(self, query: str) -> tuple[Entry | None, list[Entry]]:
        """(entrada, variantes). Una entrada exacta; la familia entera si preguntas por ella («Attrition» ->
        sus 6 variantes); la mejor coincidencia razonable; o, si lo escribes con alguna errata, lo más parecido."""
        self.load()
        q = norm(query)
        if not q:
            return None, []
        with self._lock:
            if q in self.entries:
                return self.entries[q], []
            qw = [w for w in q.split() if w not in QUERY_FILLER] or q.split()
            qs = set(qw)
            best, score = None, 0.0
            for k, e in self.entries.items():
                kw = content_words(k)
                if not kw or not qs <= kw:
                    continue
                s = len(qs) / len(kw) + GROUP_BONUS.get(e.group, 0)
                if e.source in ("tú", "internet", "verseguide", "wiki"):
                    s += 0.02
                if s > score:
                    best, score = e, s
            fam = self._family(" ".join(qw))
            if fam and best and score >= 0.99 and _rank(best.group) < _rank(fam[0].group):
                return best, []  # «Paladin»: la nave, no sus pinturas
            if len(fam) >= 2:  # preguntas por la familia: todas sus variantes (y la base si la hay)
                base = next((e for e in fam if content_words(norm(e.name)) == qs), None)
                return base, fam
            if best and score >= 0.5:
                return best, []
            # erratas («Atrittion», «Jalanite»…): lo más parecido entre familias y nombres
            import difflib
            target = " ".join(qw)
            fams = {norm(e.family): e.family for e in self.entries.values() if e.family}
            hit = difflib.get_close_matches(target, list(fams), n=1, cutoff=0.8)
            if hit and len(self._family(hit[0])) >= 2:
                return None, self._family(hit[0])
            names = {k: e for k, e in self.entries.items() if len(k) <= len(target) + 12}
            hit = difflib.get_close_matches(target, list(names), n=1, cutoff=0.82)
            if hit:
                return names[hit[0]], []
        return None, []

    def _family(self, q: str) -> list[Entry]:
        """Variantes de una familia, del grupo más importante («Cutlass» -> las naves, no las pinturas)."""
        q = norm(q)
        if len(q) < 2:
            return []
        members = [e for e in self.entries.values() if e.family and norm(e.family) == q]
        if not members:
            return []
        top = min(members, key=lambda e: GROUP_PRIORITY.index(e.group) if e.group in GROUP_PRIORITY else 99).group
        return sorted([e for e in members if e.group == top], key=lambda x: _natural(x.name))

    def family_groups(self, family: str) -> dict[str, int]:
        q = norm(family)
        out: dict[str, int] = {}
        for e in self.entries.values():
            if e.family and norm(e.family) == q:
                out[e.group] = out.get(e.group, 0) + 1
        return out

    # ------------------------------------------------------------- relleno inicial
    def seed_from_game(self, entries: dict[str, str], patch: str = "", ores: dict | None = None,
                       ore_places: dict | None = None, save: bool = True) -> int:
        """Rellena con los textos oficiales del juego (global.ini de la traducción). Devuelve cuántas
        entradas nuevas o actualizadas hay. Lo que tú hayas editado no se toca."""
        found = list(game_entries(entries))
        names = {norm(n) for n, _t, _g, _k in found}
        n = 0
        this_run: dict[str, str] = {}
        with self._lock:
            self.load()
            for name, text, group, key in found:
                if group == "Mercancías" and (norm(name) + " bruto" in names or norm(name) + " mena" in names
                                              or norm(name) + " mineral" in names):
                    group = "Recursos y minerales"
                if ores is not None and norm(name) in ores and group == "Mercancías":
                    group = "Recursos y minerales"
                if group == "Recursos y minerales" and ore_places:
                    places = ore_places.get(norm(re.sub(r"\s*\((?:bruto|mena|mineral)\)\s*$", "", name, flags=re.I)))
                    if places:
                        text += " · Dónde encontrarlo: " + ", ".join(f"{p[0]} ({p[2]})" for p in places[:5])
                fam = family_key(name) if group in VARIANT_GROUPS else ""
                k = norm(name)
                if k in this_run and _rank(this_run[k]) <= _rank(group):
                    continue  # mismo nombre en dos sitios del juego: se queda el más importante (la nave, no el objeto)
                this_run[k] = group
                old = self.entries.get(k)
                if old and old.source == "tú":
                    continue
                if old and old.source not in ("juego", "") and old.source != "tú":
                    continue  # lo aprendido en internet o VerseGuide se queda
                text1 = one_line(text)
                if old and old.text == text1 and old.group == group and old.family == fam:
                    continue
                self.entries[k] = Entry(name, text1, group, patch, time.strftime("%d/%m/%Y"), "juego", fam)
                n += 1
            # una familia con un solo miembro no es familia
            counts: dict[tuple[str, str], int] = {}
            for e in self.entries.values():
                if e.family:
                    counts[(e.group, e.family)] = counts.get((e.group, e.family), 0) + 1
            for e in self.entries.values():
                if e.family and counts.get((e.group, e.family), 0) < 2:
                    e.family = ""
            if save and (n or not self.path.exists()):
                self.save()
        return n


GROUP_PRIORITY = ["Naves y vehículos", "Armaduras y trajes", "Armas personales", "Armas de nave", "Componentes de nave",
                  "Accesorios de armas y munición", "Equipo médico y utilidades", "Ropa", "Objetos", "Pinturas y diseños"]
GROUP_BONUS = {"Planetas y lunas": 0.03, "Estaciones espaciales": 0.02, "Naves y vehículos": 0.02,
               "Recursos y minerales": 0.02, "Pinturas y diseños": -0.05}
QUERY_FILLER = {"escudo", "escudos", "generador", "componente", "componentes", "nave", "naves", "armadura", "armaduras",
                "arma", "armas", "repeater", "cannon", "shield", "shields", "armor", "helmet", "ship", "the", "a", "de",
                "la", "el", "los", "las", "del", "un", "una", "planeta", "luna", "estacion", "mineral", "recurso"}


def _rank(group: str) -> int:
    order = ["Planetas y lunas", "Estaciones espaciales", "Ciudades y zonas de aterrizaje", "Estrellas y sistemas",
             "Naves y vehículos"] + GROUP_PRIORITY[1:] + ["Recursos y minerales", "Mercancías", "Fabricantes"]
    return order.index(group) if group in order else 50


def content_words(key: str) -> set[str]:
    """Palabras que identifican el nombre (sin fabricantes, códigos de clase ni palabras genéricas)."""
    key = re.sub(r"^(?:mil|ind|civ|cmp|stl|cmpt) \d [a-d] ", "", key)
    words = key.split()
    out = {w for w in words if w not in GENERIC and w not in MAKERS and (len(w) > 1 or w.isdigit())}
    return out or set(words)


VARIANT_GROUPS = {"Accesorios de armas y munición", "Armaduras y trajes", "Armas de nave", "Armas personales",
                  "Componentes de nave", "Equipo médico y utilidades", "Naves y vehículos", "Pinturas y diseños",
                  "Ropa", "Objetos"}


def _natural(name: str) -> list:
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", norm(name))]


def _hash(text: str) -> str:
    return hashlib.sha1((text or "").strip().encode("utf-8")).hexdigest()[:12]


# --------------------------------------------------------------------- clasificación
TYPE_GROUPS = [
    (r"armadura|casco|mochila|traje", "Armaduras y trajes"),
    (r"^mono$|ropa|undersuit", "Ropa"),
    (r"pistola|smg|rifle|fusil|escopeta|^lmg|^hmg|ametralladora|lanzagranadas|lanzador|ballesta|cuchillo|granada|"
     r"railgun|multiherramienta|multitool", "Armas personales"),
    (r"cargador|optica|óptica|proyecci|reflex|telesc|holograf|compensador|supresor|linterna|puntero|flash|"
     r"estabilizador|punto rojo|bater[ií]a de arma", "Accesorios de armas y munición"),
    (r"ca[nñ]on|repetidor|gatling|misil|bomba|cohete|torreta|scattergun|mass driver|montura de arma|portamunicion|"
     r"cañón", "Armas de nave"),
    (r"planta de energ|cooler|refrigerador|quantum|cu[aá]ntic|escudo|soporte vital|radar|ordenador|bater|"
     r"rayo tractor|salto|laser minero|láser minero|utilidad$|almacenamiento|señuelo|ruido|blade de vuelo|"
     r"hoja de vuelo|inhibidor|amortiguador", "Componentes de nave"),
    (r"m[eé]dic|utilitario|herramienta", "Equipo médico y utilidades"),
]
CLOTHES_WORDS = re.compile(r"\b(camisa|camiseta|chaqueta|pantal[oó]n|pantalones|botas|zapatos|guantes|gorro|gorra|"
                           r"sombrero|gafas|sudadera|abrigo|vestido|bufanda|jersey|chaleco|mono|uniforme|bandana|"
                           r"pañuelo|calcetines|shirt|pants|jacket|boots|gloves|hat|beanie)\b", re.I)
LANDING = {"lorville", "area18", "area 18", "new babbage", "orison"}
ASTEROID_STATIONS = {"levski", "grim hex", "grimhex", "ruin station", "estacion ruin", "checkmate", "orbituary"}


def classify(key: str, name: str, text: str, kind: str) -> str:
    k, n, t = key.lower(), norm(name), norm(text[:200])
    if kind == "nave":
        return "Naves y vehículos"
    if kind == "fabricante":
        return "Fabricantes"
    if kind == "ley":
        return "Leyes y delitos"
    if kind == "mercancia":
        if re.search(r"\((bruto|mena|mineral|ore|raw)\)\s*$", name, re.I):
            return "Recursos y minerales"
        return "Mercancías"
    if kind == "objeto" and re.search(r"(^|\\n|\n)\s*Enfoque:", text):
        return "Naves y vehículos"
    if kind == "objeto":
        if re.match(r"^(pintura|diseño|diseno|livery|paint)\b", name, re.I) or "_paint" in k or "livery" in k:
            return "Pinturas y diseños"
        m = re.search(r"Tipo(?: de objeto)?:\s*([^\\\n·]+)", text)
        typ = norm(m.group(1)) if m else ""
        if typ:
            for rx, g in TYPE_GROUPS:
                if re.search(rx, typ):
                    return g
        if CLOTHES_WORDS.search(name) or any(w in k for w in ("_clothing", "_shirt", "_pants", "_jacket", "_shoes",
                                                                "_gloves", "_hat_", "_glasses", "undersuit")):
            return "Ropa"
        return "Objetos"
    # lugares
    from .verseguide import BODY_TABLE
    bodies = {norm(b[2]) for b in BODY_TABLE}
    if n in bodies or re.match(r"^(una |un |la |el )?(luna|planeta|gigante gaseoso|planeta enano|mundo)\b", t):
        return "Planetas y lunas"
    if re.match(r"^(una |un |la |el )?(estrella|sistema)\b", t) or n in ("stanton", "pyro", "nyx", "magnus", "terra"):
        return "Estrellas y sistemas"
    if "proceso de refinado" in t or "refinado" in n and len(n.split()) <= 3 and "estacion" not in n:
        return "Procesos de refinado"
    if n in ASTEROID_STATIONS or re.search(r"\b(estacion|station|puerto|port|harbor|point|plataforma|"
                                           r"[a-z]{3} l\d)\b", n) or re.search(r"\b[a-z]{3}-l\d\b", name.lower()):
        return "Estaciones espaciales"
    if n in LANDING or re.search(r"\b(ciudad|zona de aterrizaje)\b", t):
        return "Ciudades y zonas de aterrizaje"
    return "Lugares y puntos de interés"


SKIP_PREFIX = ("ui_", "frontend", "input", "pause", "hud_", "mobiglas", "chat", "interaction", "ea_", "dfm", "mg_",
               "notification", "text_", "dlg", "pu_", "dxsm", "dxsh", "ph_", "starchitect", "commarray", "event_",
               "fw2022", "fw22", "soo2", "mission_", "missionmanager", "local_", "headhunters", "hockrow", "cfp_")


def game_entries(e: dict[str, str]):
    """(nombre, descripción, grupo, clave) de todo lo que tiene descripción en el global.ini."""
    seen = set()
    lower = {k.lower(): k for k in e}
    for k, v in e.items():
        kl = k.lower()
        if kl.startswith(SKIP_PREFIX) or "~mission(" in v:
            continue
        m = re.search(r"_desc(?:ription)?(?:_\d+)?$", kl)
        if not m and not kl.startswith(("item_desc", "vehicle_desc", "manufacturer_desc")):
            continue
        base = k[:m.start()] if m else k
        cands = [base, base + "_name", k.replace("_desc", "_name"), k.replace("desc", "name", 1),
                 k.replace("_Desc", "_Name"), k.replace("Desc", "Name", 1)]
        name = None
        for c in cands:
            real = c if c in e else lower.get(c.lower())
            if real and real != k and len(e[real]) < 80:
                name = e[real]
                break
        if not name or len(v) < 25:
            continue
        name = one_line(name, 120)
        if not name or name.startswith("@") or (norm(name), v[:40]) in seen:
            continue
        seen.add((norm(name), v[:40]))
        kind = ("nave" if kl.startswith("vehicle_") else "objeto" if kl.startswith(("item_", "items_", "nb_"))
                else "fabricante" if kl.startswith("manufacturer") else "ley" if kl.startswith("infraction")
                else "lugar")
        if kl.startswith("items_commodities"):
            kind = "mercancia"
        yield name, v, classify(k, name, v, kind), k


# --------------------------------------------------------------------- aprender en internet
WIKI_API = "https://starcitizen.tools/api.php"
WIKI_UA = {"User-Agent": "NovaCopiloto/1.0 (asistente de voz para Star Citizen; uso personal)"}
GROUP_HINTS = [
    (r"\b(moon|planet|gas giant|dwarf planet)\b", "Planetas y lunas"),
    (r"\b(space station|station|rest stop|lagrange)\b", "Estaciones espaciales"),
    (r"\b(landing zone|city)\b", "Ciudades y zonas de aterrizaje"),
    (r"\b(star system|star)\b", "Estrellas y sistemas"),
    (r"\b(armou?r|undersuit|helmet)\b", "Armaduras y trajes"),
    (r"\b(rifle|pistol|smg|shotgun|sniper|lmg|grenade launcher|knife|multi-tool|railgun)\b", "Armas personales"),
    (r"\b(repeater|cannon|gatling|missile|torpedo|scattergun|mass driver|turret)\b", "Armas de nave"),
    (r"\b(shield generator|power plant|cooler|quantum drive|jump module|radar|tractor beam|mining laser)\b",
     "Componentes de nave"),
    (r"\b(ore|mineral|gem|element|raw material)\b", "Recursos y minerales"),
    (r"\b(commodity|cargo)\b", "Mercancías"),
    (r"\b(spacecraft|starship|ship|vehicle|fighter|bomber|hauler|freighter|rover|ground vehicle)\b",
     "Naves y vehículos"),
    (r"\b(manufacturer|company|corporation)\b", "Fabricantes"),
    (r"\b(outpost|cave|bunker|settlement|facility|derelict)\b", "Lugares y puntos de interés"),
]


def guess_group(text_en: str) -> str:
    t = (text_en or "").lower()[:400]
    for rx, g in GROUP_HINTS:
        if re.search(rx, t):
            return g
    return OTHER


def title_matches(subject: str, title: str) -> bool:
    """¿El artículo de la wiki es de lo que has preguntado?"""
    import difflib
    a, b = norm(subject), norm(re.sub(r"\(.*?\)", "", title))
    if not a or not b:
        return False
    if a == b or difflib.SequenceMatcher(None, a, b).ratio() >= 0.82:
        return True
    aw, bw = content_words(a), content_words(b)
    return bool(aw) and aw <= bw and len(bw) - len(aw) <= 2


def wiki_definition(subject: str, http=None, timeout: float = 10) -> tuple[str, str, str] | None:
    """(título, definición en inglés, grupo) de starcitizen.tools, o None si no hay un artículo que encaje."""
    import requests
    http = http or requests
    r = http.get(WIKI_API, params={"action": "query", "list": "search", "srsearch": subject, "srlimit": 5,
                                   "format": "json"}, headers=WIKI_UA, timeout=timeout)
    hits = (r.json().get("query") or {}).get("search") or []
    title = next((h["title"] for h in hits if title_matches(subject, h.get("title", ""))), None)
    if not title:
        return None
    text = ""
    try:  # resumen (si la wiki tiene la extensión de extractos)
        r = http.get(WIKI_API, params={"action": "query", "prop": "extracts", "exintro": 1, "explaintext": 1,
                                       "exsentences": 5, "titles": title, "format": "json", "redirects": 1},
                     headers=WIKI_UA, timeout=timeout)
        pages = (r.json().get("query") or {}).get("pages") or {}
        text = next(iter(pages.values()), {}).get("extract", "") if pages else ""
    except Exception:  # noqa: BLE001
        text = ""
    if len((text or "").strip()) < 30:  # starcitizen.tools no siempre lo da: los párrafos de la introducción
        r = http.get(WIKI_API, params={"action": "parse", "page": title, "prop": "text", "section": 0,
                                       "format": "json", "redirects": 1}, headers=WIKI_UA, timeout=timeout)
        html = ((r.json().get("parse") or {}).get("text") or {}).get("*", "")
        text = intro_from_html(html)
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) < 30:
        return None
    text = _sentences_en(text, 5)
    return title, text, guess_group(text)


def intro_from_html(html: str) -> str:
    """Los primeros párrafos de texto de una página de la wiki (sin tablas, fichas ni referencias)."""
    import html as H
    html = re.sub(r"(?is)<(table|style|script|sup|figure|aside)\b.*?</\1>", " ", html or "")
    paras = []
    for m in re.finditer(r"(?is)<p\b[^>]*>(.*?)</p>", html):
        t = H.unescape(re.sub(r"<[^>]+>", "", m.group(1)))
        t = re.sub(r"\[\d+\]", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) > 40:
            paras.append(t)
        if sum(len(x) for x in paras) > 1200:
            break
    return " ".join(paras)


def _sentences_en(text: str, n: int) -> str:
    parts = re.findall(r"[^.!?]+[.!?]+(?:\s|$)|[^.!?]+$", text)
    return "".join(parts[:n]).strip() or text[:900]


# --------------------------------------------------------------------- para decirlo en voz alta
def _split(text: str) -> tuple[list[tuple[str, str]], str]:
    fields, prose = [], []
    for part in (text or "").split(" · "):
        m = re.match(r"^([A-Za-zÁÉÍÓÚáéíóúñÑ .()/]{2,32}):\s*(.{1,60})$", part.strip())
        if m and not prose:
            fields.append((m.group(1).strip(), m.group(2).strip()))
        else:
            prose.append(part.strip())
    return fields, " ".join(prose)


def _sentences(text: str, limit: int = 320) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    out = ""
    for s in re.findall(r"[^.!?]+[.!?]+|\S[^.!?]*$", text):
        if len(out) + len(s) > limit and out:
            break
        out += s
    out = out.strip() or text[:limit]
    return out if out[-1:] in ".!?…" else out + "."


SPOKEN_FIELDS = ("Fabricante", "Tipo de objeto", "Tipo", "Enfoque", "Tamaño", "Clase", "Grado")


def spoken(entry: Entry | None, family: list[Entry], tratamiento: str) -> str:
    if family and len(family) >= 2:
        fam = family[0].family or family[0].name
        names = [f.name for f in family]
        sizes = sorted({int(m.group(1)) for f in family for m in [re.search(r"Tama[ñn]o:\s*(\d+)", f.text)] if m})
        out = f"Tengo {len(family)} variantes de {fam}: "
        out += (", ".join(names[:-1]) + " y " + names[-1]) if len(names) <= 6 else \
            (", ".join(names[:4]) + f" y {len(names) - 4} más")
        out += "."
        if len(sizes) > 1:
            out += f" Van del tamaño {sizes[0]} al {sizes[-1]}."
        if entry is not None:
            out += " " + _sentences(_split(entry.text)[1], 220)
        return out + f" Tiene la lista completa en la cabina, {tratamiento}."
    if entry is None:
        return ""
    fields, prose = _split(entry.text)
    bits = [f"{k.lower()} {v}" for k, v in fields if k in SPOKEN_FIELDS][:3]
    out = entry.name + (": " + ", ".join(bits) + "." if bits else ".")
    if prose:
        out += " " + _sentences(prose)
    return out


def card_text(entry: Entry | None, family: list[Entry]) -> str:
    if family and len(family) >= 2:
        lines = [f"DICCIONARIO · {family[0].group}", f"{family[0].family or family[0].name} ({len(family)} variantes)"]
        if entry is not None:
            lines.append(f"{entry.name}: {entry.text[:500]}")
        lines += [f"• {f.name}: {f.text[:180]}{'…' if len(f.text) > 180 else ''}" for f in family[:30]]
        if len(family) > 30:
            lines.append(f"… y {len(family) - 30} más en Diccionario_de_consultas.txt")
        return "\n".join(lines)
    e = entry
    meta = " · ".join(b for b in (e.patch, e.date, e.source) if b)
    return f"DICCIONARIO · {e.group}\n{e.name}\n{e.text}" + (f"\n({meta})" if meta else "")


PLACE_GROUPS = {"Planetas y lunas", "Estaciones espaciales", "Ciudades y zonas de aterrizaje", "Estrellas y sistemas",
                "Lugares y puntos de interés"}


def holo_card(entry: Entry):
    """Holograma hecho solo con lo que dice el diccionario (cuando VerseGuide no responde)."""
    from .holo import Card
    fields, prose = _split(entry.text)
    planet = entry.group in ("Planetas y lunas", "Estrellas y sistemas")
    return Card(kind="planeta" if planet else "lugar", title=entry.name.upper(), subtitle=entry.group,
                header="DICCIONARIO DE CONSULTAS", fields=[(k.upper(), v) for k, v in fields[:4]],
                desc=prose or entry.text, footer="Fuente: Diccionario de consultas · NOVA AI", seed=entry.name)

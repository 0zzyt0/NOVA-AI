"""Fichas de planetas, lunas y lugares planetarios (cuevas, puestos, bases…) leídas de verseguide.com.

VerseGuide es una web de fans (no oficial) que sirve cada cuerpo celeste en una página pública,
por ejemplo https://verseguide.com/location/STANTON/2B (Daymar). La página trae sus datos
dentro del propio HTML (`window.__NUXT__=(function(a,b,…){…}(…))`). NOVA lee esa página igual que
la abriría tu navegador y la interpreta SIN ejecutar ningún código: aquí hay un pequeño lector de
literales de JavaScript (objetos, listas, textos y números) que sólo entiende datos.

Lo leído se guarda en caché unos días para no pedir la misma página una y otra vez.
"""
from __future__ import annotations

import json
import logging
import math
import re
import threading
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger("nova.verseguide")

BASE = "https://verseguide.com"
UA = "NOVA-AI/1.2 (asistente de voz de Star Citizen; +https://github.com/0zzyt0/NOVA-AI)"
CACHE_DAYS = 3

# (sistema, código de VerseGuide, nombre, alias)
BODY_TABLE = [
    ("STANTON", "I", "Hurston", ("stanton1", "hurston dynamics")),
    ("STANTON", "1A", "Arial", ("stanton1a", "ariel")),
    ("STANTON", "1B", "Aberdeen", ("stanton1b",)),
    ("STANTON", "1C", "Magda", ("stanton1c",)),
    ("STANTON", "1D", "Ita", ("stanton1d",)),
    ("STANTON", "II", "Crusader", ("stanton2", "crusader industries")),
    ("STANTON", "2A", "Cellin", ("stanton2a",)),
    ("STANTON", "2B", "Daymar", ("stanton2b",)),
    ("STANTON", "2C", "Yela", ("stanton2c",)),
    ("STANTON", "III", "ArcCorp", ("stanton3", "arc corp")),
    ("STANTON", "3A", "Lyria", ("stanton3a",)),
    ("STANTON", "3B", "Wala", ("stanton3b",)),
    ("STANTON", "IV", "microTech", ("stanton4", "micro tech")),
    ("STANTON", "4A", "Calliope", ("stanton4a",)),
    ("STANTON", "4B", "Clio", ("stanton4b",)),
    ("STANTON", "4C", "Euterpe", ("stanton4c",)),
    ("PYRO", "I", "Pyro I", ("pyro1",)),
    ("PYRO", "II", "Monox", ("pyro2", "pyro ii")),
    ("PYRO", "III", "Bloom", ("pyro3", "pyro iii")),
    ("PYRO", "IV", "Pyro IV", ("pyro4",)),
    ("PYRO", "V", "Pyro V", ("pyro5",)),
    ("PYRO", "5A", "Ignis", ("pyro5a",)),
    ("PYRO", "5B", "Vatra", ("pyro5b",)),
    ("PYRO", "5C", "Adir", ("pyro5c",)),
    ("PYRO", "5D", "Fairo", ("pyro5d",)),
    ("PYRO", "5E", "Fuego", ("pyro5e",)),
    ("PYRO", "5F", "Vuur", ("pyro5f",)),
    ("PYRO", "VI", "Terminus", ("pyro6", "pyro vi")),
    ("NYX", "I", "Nyx I", ("nyx1",)),
    ("NYX", "II", "Nyx II", ("nyx2",)),
    ("NYX", "III", "Nyx III", ("nyx3",)),
    ("NYX", "DELAMAR", "Delamar", ("levski",)),
    ("NYX", "GLACIEM.ALPHA", "Glaciem Alpha", ()),
    ("NYX", "GLACIEM.BRAVO", "Glaciem Bravo", ()),
    ("NYX", "GLACIEM.CHARLIE", "Glaciem Charlie", ()),
    ("NYX", "KEEGER.ALPHA", "Keeger Alpha", ()),
    ("NYX", "KEEGER.LAMBDA", "Keeger Lambda", ()),
    ("NYX", "KEEGER.THETA", "Keeger Theta", ()),
]
SYSTEM_ES = {"STANTON": "Stanton", "PYRO": "Pyro", "NYX": "Nyx"}
TAG_ES = {"outpost": "Puesto avanzado", "industrial": "Instalación industrial", "underground": "Subterráneo (cueva o búnker)",
          "settlement": "Asentamiento", "derelict": "Abandonado", "station": "Estación", "race": "Circuito de carreras",
          "city": "Ciudad", "cave": "Cueva", "landmark": "Lugar de interés", "wreck": "Restos de nave"}
SUBTAG_ES = {"security-post": "puesto de seguridad", "planetary-alignment-facility": "estación de alineación planetaria",
             "forward-operating-base": "base de operaciones avanzada", "mining": "minería", "salvage-yard": "desguace",
             "farm": "granja", "shelter": "refugio", "stash-house": "escondite", "race-track": "circuito",
             "orbital-laser-platform": "plataforma láser orbital", "shipping-hub": "centro de transporte",
             "cave": "cueva", "bunker": "búnker", "research": "investigación", "medical": "médico"}
TYPE_ES = {"Planetary Moon": "Luna", "Super-Earth": "Supertierra", "Gas Giant": "Gigante gaseoso",
           "Protoplanet": "Protoplaneta", "Terrestrial": "Planeta rocoso", "Smog Planet": "Planeta de niebla tóxica",
           "Ice Giant": "Gigante helado", "Desert Planet": "Planeta desértico", "Ice Planet": "Planeta helado",
           "Rocky Planet": "Planeta rocoso", "Lava Planet": "Planeta volcánico"}
COMPOUND_ES = {"N": "nitrógeno", "N2": "nitrógeno", "O2": "oxígeno", "CO2": "dióxido de carbono", "CH4": "metano",
               "H": "hidrógeno", "Ar": "argón", "H2O": "agua", "CO": "monóxido de carbono", "NH3": "amoníaco",
               "SO": "monóxido de azufre", "NaCl": "sal", "He": "helio", "SO2": "dióxido de azufre"}


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


BY_KEY: dict[str, tuple[str, str, str]] = {}
for _sys, _code, _name, _alias in BODY_TABLE:
    for _k in (_name, *_alias):
        BY_KEY[_norm(_k)] = (_sys, _code, _name)
        BY_KEY[_norm(_k).replace(" ", "")] = (_sys, _code, _name)
_RAW_BODY = re.compile(r"(?i)(?<![a-z])(stanton|pyro|nyx)[ _-]?(\d)([a-f])?(?![0-9])")


def resolve_body(text: str) -> tuple[str, str, str] | None:
    """Texto del juego o del piloto -> (sistema, código, nombre) del planeta/luna, o None.
    Entiende códigos internos (Stanton2b_Daymar, OOC_Stanton_1_Hurston, Pyro3_Outpost_…, pyro5a)
    y nombres (Daymar, «jurisdicción de Hurston Dynamics», «Lorville (Hurston)»)."""
    if not text:
        return None
    m = _RAW_BODY.search(text.replace("OOC_", "").replace("ooc_", ""))
    if m:
        key = (m.group(1) + m.group(2) + (m.group(3) or "")).lower()
        if key in BY_KEY:
            return BY_KEY[key]
    n = f" {_norm(text)} "
    best = None
    for key, val in BY_KEY.items():
        if " " in key or len(key) >= 3:
            if f" {key} " in n and (best is None or len(key) > len(best[0])):
                best = (key, val)
    return best[1] if best else None


# ===================================================== lector de literales JS (sin ejecutar nada)
class _Undefined:
    def __repr__(self) -> str:
        return "undefined"


UNDEFINED = _Undefined()


class JSParseError(ValueError):
    pass


class _Reader:
    IDENT = re.compile(r"[A-Za-z_$][\w$]*")
    NUMBER = re.compile(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")

    def __init__(self, src: str, env: dict | None = None) -> None:
        self.s, self.i, self.env = src, 0, env if env is not None else {}

    def ws(self) -> None:
        s, i = self.s, self.i
        while i < len(s) and s[i] in " \t\r\n":
            i += 1
        self.i = i

    def peek(self, text: str) -> bool:
        self.ws()
        return self.s.startswith(text, self.i)

    def eat(self, text: str) -> None:
        self.ws()
        if not self.s.startswith(text, self.i):
            raise JSParseError(f"se esperaba {text!r} en {self.i}: {self.s[self.i:self.i + 40]!r}")
        self.i += len(text)

    def ident(self) -> str:
        self.ws()
        m = self.IDENT.match(self.s, self.i)
        if not m:
            raise JSParseError(f"identificador esperado en {self.i}")
        self.i = m.end()
        return m.group(0)

    def string(self) -> str:
        q = self.s[self.i]
        self.i += 1
        out, s = [], self.s
        while True:
            if self.i >= len(s):
                raise JSParseError("texto sin cerrar")
            c = s[self.i]
            if c == q:
                self.i += 1
                return "".join(out)
            if c == "\\":
                n = s[self.i + 1]
                if n == "u":
                    out.append(chr(int(s[self.i + 2:self.i + 6], 16)))
                    self.i += 6
                    continue
                if n == "x":
                    out.append(chr(int(s[self.i + 2:self.i + 4], 16)))
                    self.i += 4
                    continue
                out.append({"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}.get(n, n))
                self.i += 2
                continue
            out.append(c)
            self.i += 1

    def value(self):
        self.ws()
        s, i = self.s, self.i
        if i >= len(s):
            raise JSParseError("fin inesperado")
        c = s[i]
        if c in "\"'":
            return self.string()
        if c == "{":
            return self.obj()
        if c == "[":
            return self.arr()
        if c in "-.0123456789":
            if s.startswith("-Infinity", i):
                self.i += 9
                return float("-inf")
            m = self.NUMBER.match(s, i)
            if not m:
                raise JSParseError(f"número mal formado en {i}")
            self.i = m.end()
            t = m.group(0)
            return float(t) if any(x in t for x in ".eE") else int(t)
        if s.startswith("void 0", i):
            self.i += 6
            return UNDEFINED
        name = self.ident()
        if name == "true":
            return True
        if name == "false":
            return False
        if name == "null":
            return None
        if name == "undefined":
            return UNDEFINED
        if name == "NaN":
            return float("nan")
        if name == "Infinity":
            return float("inf")
        if name in self.env:
            return self.env[name]
        raise JSParseError(f"nombre desconocido {name!r}")

    def key(self) -> str:
        self.ws()
        c = self.s[self.i]
        if c in "\"'":
            return self.string()
        m = self.NUMBER.match(self.s, self.i)
        if m and c not in "-":
            self.i = m.end()
            return m.group(0)
        return self.ident()

    def obj(self) -> dict:
        self.eat("{")
        out: dict = {}
        if self.peek("}"):
            self.i += 1
            return out
        while True:
            k = self.key()
            self.eat(":")
            out[k] = self.value()
            if self.peek(","):
                self.i += 1
                if self.peek("}"):
                    self.i += 1
                    return out
                continue
            self.eat("}")
            return out

    def arr(self) -> list:
        self.eat("[")
        out: list = []
        if self.peek("]"):
            self.i += 1
            return out
        while True:
            out.append(self.value())
            if self.peek(","):
                self.i += 1
                if self.peek("]"):
                    self.i += 1
                    return out
                continue
            self.eat("]")
            return out


def parse_nuxt(html: str) -> dict:
    """Saca los datos de `window.__NUXT__=(function(a,b,…){ x.k=…; return {…} }(v1,v2,…))`
    leyendo sólo literales: no se ejecuta nada de la página."""
    start = html.find("window.__NUXT__=")
    if start < 0:
        raise JSParseError("la página no trae datos")
    end = html.find("</script>", start)
    src = html[start + len("window.__NUXT__="):end if end > 0 else len(html)].strip().rstrip(";")
    r = _Reader(src)
    if r.peek("{"):  # formato sencillo: un objeto directo
        return r.obj()
    r.eat("(")
    r.eat("function")
    r.eat("(")
    params: list[str] = []
    while not r.peek(")"):
        params.append(r.ident())
        if r.peek(","):
            r.i += 1
    r.eat(")")
    r.eat("{")
    body_start = r.i
    # Los argumentos están al final: «}(v1,v2,…))». Se leen primero para conocer cada variable.
    tail = _matching_close(src, body_start)
    args_reader = _Reader(src[tail + 1:])
    args = args_reader.arr_like()
    env = {p: (args[n] if n < len(args) else UNDEFINED) for n, p in enumerate(params)}
    body = _Reader(src[body_start:tail], env)
    while True:
        body.ws()
        if body.s.startswith("return", body.i):
            body.i += 6
            return body.value()
        target = body.ident()
        path: list[str] = []
        while True:
            if body.peek("."):
                body.i += 1
                path.append(body.ident())
            elif body.peek("["):
                body.i += 1
                k = body.value()
                body.eat("]")
                path.append(str(k))
            else:
                break
        body.eat("=")
        val = body.value()
        body.eat(";")
        if not path:
            env[target] = val
            continue
        obj = env.get(target)
        if obj is UNDEFINED or obj is None:
            obj = env[target] = {}
        for k in path[:-1]:
            obj = obj.setdefault(k, {}) if isinstance(obj, dict) else obj
        if isinstance(obj, dict):
            obj[path[-1]] = val
        elif isinstance(obj, list) and path[-1].isdigit():
            idx = int(path[-1])
            while len(obj) <= idx:
                obj.append(UNDEFINED)
            obj[idx] = val


def _matching_close(src: str, i: int) -> int:
    """Posición de la «}» que cierra el cuerpo de la función (respetando textos y anidamiento)."""
    depth, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in "\"'":
            q = c
            i += 1
            while i < n and src[i] != q:
                i += 2 if src[i] == "\\" else 1
        elif c in "{[(":
            depth += 1
        elif c in "}])":
            if depth == 0:
                if c != "}":
                    raise JSParseError("estructura inesperada")
                return i
            depth -= 1
        i += 1
    raise JSParseError("no encuentro el final de los datos")


def _arr_like(self) -> list:
    """Lee «(v1, v2, …)» como lista."""
    self.eat("(")
    out = []
    if self.peek(")"):
        return out
    while True:
        out.append(self.value())
        if self.peek(","):
            self.i += 1
            continue
        self.eat(")")
        return out


_Reader.arr_like = _arr_like


# ================================================================ modelo de datos
@dataclass
class Place:
    nombre: str
    tipo: str = ""
    subtipo: str = ""
    descripcion: str = ""
    temp_media: float | None = None
    temp_max: float | None = None
    temp_min: float | None = None
    oculto: bool = False
    descripcion_es: str = ""

    def tipo_es(self) -> str:
        t = TAG_ES.get(self.tipo, self.tipo.replace("-", " ").capitalize())
        if self.subtipo:
            t += " · " + SUBTAG_ES.get(self.subtipo, self.subtipo.replace("-", " "))
        return t


@dataclass
class Body:
    sistema: str
    codigo: str
    nombre: str
    designacion: str = ""
    tipo: str = ""
    subtipo: str = ""
    radio_km: float | None = None
    gravedad_g: float | None = None
    atmosfera: float | None = None
    compuestos: dict = field(default_factory=dict)
    dia_h: float | None = None
    descripcion: str = ""
    descripcion_es: str = ""
    imagen: str = ""
    peligro: int | None = None
    economia: int | None = None
    poblacion: int | None = None
    afiliacion: str = ""
    habitable: bool | None = None
    color: list = field(default_factory=list)
    lugares: list[Place] = field(default_factory=list)
    url: str = ""
    leido: float = 0.0

    def tipo_es(self) -> str:
        return TYPE_ES.get(self.subtipo or self.tipo, TYPE_ES.get(self.tipo, self.subtipo or self.tipo or "Cuerpo celeste"))

    def resumen_lugares(self) -> list[tuple[str, int]]:
        count: dict[str, int] = {}
        for p in self.lugares:
            if p.oculto:
                continue
            k = TAG_ES.get(p.tipo, p.tipo or "otros")
            count[k] = count.get(k, 0) + 1
        return sorted(count.items(), key=lambda kv: -kv[1])

    def atmosfera_es(self) -> str:
        if not self.compuestos:
            return "sin atmósfera respirable registrada" if not self.atmosfera else ""
        parts = []
        for k, v in sorted(self.compuestos.items(), key=lambda kv: -_num(kv[1])):
            if _num(v) > 0:
                parts.append(f"{COMPOUND_ES.get(k, k)} {_fmt(_num(v), 1)} %")
        return ", ".join(parts[:3])

    def campos(self) -> list[tuple[str, str]]:
        out = [("Tipo", self.tipo_es()), ("Sistema", SYSTEM_ES.get(self.sistema, self.sistema))]
        if self.radio_km:
            out.append(("Radio", f"{_fmt(self.radio_km)} km"))
        if self.gravedad_g:
            out.append(("Gravedad", f"{_fmt(self.gravedad_g, 2)} g"))
        if self.dia_h:
            out.append(("Día", f"{_fmt(self.dia_h, 1)} h"))
        atm = self.atmosfera_es()
        if atm:
            out.append(("Atmósfera", atm))
        if self.afiliacion:
            out.append(("Afiliación", self.afiliacion))
        if self.peligro is not None or self.economia is not None:
            out.append(("Peligro · Economía · Población",
                        " · ".join(f"{v}/10" if v is not None else "?" for v in (self.peligro, self.economia, self.poblacion))))
        lug = self.resumen_lugares()
        if lug:
            out.append(("Lugares", ", ".join(f"{n} {k.lower()}" for k, n in lug[:4])))
        return out

    def texto(self) -> str:
        lines = [f"{self.nombre.upper()} ({self.designacion or self.codigo})"]
        lines += [f"• {k}: {v}" for k, v in self.campos()]
        desc = self.descripcion_es or self.descripcion
        if desc:
            lines += ["", desc]
        lines.append(f"Fuente: {self.url}")
        return "\n".join(lines)

    def find_place(self, name: str) -> Place | None:
        q = _norm(name)
        if not q:
            return None
        best, score = None, 0.0
        for p in self.lugares:
            n = _norm(p.nombre)
            if not n:
                continue
            if n == q:
                return p
            s = _sim(q, n)
            if s > score:
                best, score = p, s
        return best if score >= 0.82 else None


def _num(v) -> float:
    try:
        f = float(v)
        return 0.0 if math.isnan(f) else f
    except (TypeError, ValueError):
        return 0.0


def _fmt(v: float, dec: int = 0) -> str:
    if dec == 0 or abs(v - round(v)) < 1e-9:
        return f"{round(v):,}".replace(",", ".")
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _sim(a: str, b: str) -> float:
    try:
        from rapidfuzz import fuzz
        return max(fuzz.ratio(a, b), fuzz.token_set_ratio(a, b) * 0.97) / 100.0
    except ImportError:  # pragma: no cover
        import difflib
        sa, sb = " ".join(sorted(a.split())), " ".join(sorted(b.split()))
        return max(difflib.SequenceMatcher(None, a, b).ratio(), difflib.SequenceMatcher(None, sa, sb).ratio())


def _real(v):
    if v is UNDEFINED or v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def body_from_data(data: dict, sistema: str, codigo: str, url: str = "") -> Body:
    """Datos de la página -> Body."""
    d0 = (data.get("data") or [{}])[0] if isinstance(data.get("data"), list) else data
    p = d0.get("planet") or {}
    if not isinstance(p, dict) or not p.get("name"):
        raise JSParseError("la página no trae el cuerpo celeste")
    system = p.get("system") if isinstance(p.get("system"), dict) else d0.get("system") or {}
    co = {}
    for o in (system.get("celestial_objects") or []) if isinstance(system, dict) else []:
        if isinstance(o, dict) and str(o.get("id")) == str(p.get("id")):
            co = o
            break
    img = ""
    for k in ("texture", "thumbnail"):
        t = co.get(k)
        if isinstance(t, dict):
            images = t.get("images") or {}
            img = images.get("post") or images.get("product_thumb_large") or t.get("source") or ""
            if img:
                break

    def sensor(k):
        v = _real(co.get(k))
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    grav = _real(p.get("gravity"))
    ptype = p.get("type") or co.get("type") or ""
    grav_g = None
    if isinstance(grav, (int, float)) and grav > 0 and (abs(grav - 9.81) > 0.01 or ptype == "PLANET"):
        grav_g = grav / 9.81
    radius = _real(p.get("radius"))
    if not radius and _real(co.get("size")) and float(co.get("size")) > 50:
        radius = float(co["size"]) / 2
    sub = co.get("subtype") if isinstance(co.get("subtype"), dict) else {}
    aff = ", ".join(a.get("name", "") for a in (co.get("affiliation") or []) if isinstance(a, dict) and a.get("name"))
    compounds = {k: v for k, v in (p.get("compounds") or {}).items() if _num(v) > 0} \
        if isinstance(p.get("compounds"), dict) else {}
    color = p.get("atmosphericColor") if isinstance(p.get("atmosphericColor"), list) else []
    places = []
    for loc in d0.get("locations") or []:
        if not isinstance(loc, dict) or not loc.get("name"):
            continue
        w = loc.get("weather") if isinstance(loc.get("weather"), dict) else {}
        places.append(Place(nombre=str(loc.get("name")), tipo=str(_real(loc.get("tag")) or ""),
                            subtipo=str(_real(loc.get("subTag")) or ""), descripcion=str(_real(loc.get("desc")) or ""),
                            temp_media=_real(w.get("average")), temp_max=_real(w.get("high")), temp_min=_real(w.get("low")),
                            oculto=bool(loc.get("hidden"))))
    return Body(sistema=sistema, codigo=codigo, nombre=str(p.get("name")), designacion=str(_real(co.get("designation")) or ""),
                tipo=str(p.get("type_name") or ptype), subtipo=str(sub.get("name") or p.get("type_name") or ""),
                radio_km=float(radius) if radius else None, gravedad_g=grav_g,
                atmosfera=_real(p.get("atm")), compuestos=compounds, dia_h=_real(p.get("rotationSpeed")),
                descripcion=str(_real(co.get("description")) or "").strip(), imagen=img,
                peligro=sensor("sensor_danger"), economia=sensor("sensor_economy"), poblacion=sensor("sensor_population"),
                afiliacion=aff, habitable=_real(co.get("habitable")),
                color=[float(_num(x)) for x in color[:3]], lugares=places, url=url, leido=time.time())


# ================================================================ descarga + caché
class VerseGuide:
    def __init__(self, cache_dir: Path | None = None, http=None) -> None:
        if cache_dir is None:
            from .config import DATA_DIR
            cache_dir = DATA_DIR / "cache" / "verseguide"
        self.dir = Path(cache_dir)
        self.http = http
        self._lock = threading.Lock()
        self._mem: dict[str, Body] = {}

    def _file(self, sistema: str, codigo: str) -> Path:
        return self.dir / f"{sistema}_{codigo}.json"

    def url(self, sistema: str, codigo: str) -> str:
        return f"{BASE}/location/{sistema}/{codigo}"

    def _load_cache(self, sistema: str, codigo: str) -> Body | None:
        try:
            raw = json.loads(self._file(sistema, codigo).read_text(encoding="utf-8"))
            raw["lugares"] = [Place(**p) for p in raw.get("lugares", [])]
            return Body(**raw)
        except (OSError, ValueError, TypeError):
            return None

    def _save_cache(self, b: Body) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = self._file(b.sistema, b.codigo).with_suffix(".tmp")
            tmp.write_text(json.dumps(asdict(b), ensure_ascii=False), encoding="utf-8")
            tmp.replace(self._file(b.sistema, b.codigo))
        except OSError:
            log.exception("Caché de VerseGuide")

    def body(self, sistema: str, codigo: str, fresh: bool = False) -> Body:
        """Ficha del cuerpo. Lanza LookupError si no se puede leer y no hay caché."""
        key = f"{sistema}/{codigo}"
        with self._lock:
            b = self._mem.get(key) or self._load_cache(sistema, codigo)
            if b and not fresh and time.time() - b.leido < CACHE_DAYS * 86400:
                self._mem[key] = b
                return b
            url = self.url(sistema, codigo)
            try:
                http = self.http
                if http is None:
                    import requests as http
                r = http.get(url, headers={"User-Agent": UA, "Accept": "text/html"}, timeout=15)
                if r.status_code != 200:
                    raise LookupError(f"VerseGuide respondió {r.status_code}")
                nb = body_from_data(parse_nuxt(r.text), sistema, codigo, url)
                if b and b.descripcion == nb.descripcion:
                    nb.descripcion_es = b.descripcion_es  # conservar la traducción
                self._mem[key] = nb
                self._save_cache(nb)
                return nb
            except Exception as e:  # noqa: BLE001
                if b:
                    log.warning("VerseGuide %s: %s (uso la copia guardada)", key, e)
                    self._mem[key] = b
                    return b
                raise LookupError(f"No pude leer {url}: {e}") from e

    def save(self, b: Body) -> None:
        with self._lock:
            self._mem[f"{b.sistema}/{b.codigo}"] = b
            self._save_cache(b)

    def cached_bodies(self) -> list[Body]:
        out = []
        for _sys, code, _name, _alias in BODY_TABLE:
            b = self._mem.get(f"{_sys}/{code}") or self._load_cache(_sys, code)
            if b:
                out.append(b)
        return out

    def find(self, text: str, system_hint: str = "", allow_scan: bool = True) -> tuple[Body, Place | None] | None:
        """«Daymar», «Lorville», «Security Post Kareah», «la cueva X de Hurston»… -> (cuerpo, lugar)."""
        hit = resolve_body(text)
        if hit:
            b = self.body(hit[0], hit[1])
            rest = _norm(text).replace(_norm(hit[2]), " ").strip()
            place = b.find_place(rest) if len(rest) > 3 else None
            return b, place
        for b in self.cached_bodies():
            p = b.find_place(text)
            if p:
                return b, p
        if not allow_scan:
            return None
        system = (system_hint or "STANTON").upper()
        for _sys, code, _name, _alias in BODY_TABLE:
            if _sys != system:
                continue
            try:
                b = self.body(_sys, code)
            except LookupError:
                continue
            p = b.find_place(text)
            if p:
                return b, p
        return None


def place_text(b: Body, p: Place) -> str:
    lines = [f"{p.nombre.upper()}", f"• Tipo: {p.tipo_es()}", f"• Situado en: {b.nombre} ({SYSTEM_ES.get(b.sistema, b.sistema)})"]
    if p.temp_media is not None:
        t = f"{_fmt(p.temp_media)} °C"
        if p.temp_min is not None and p.temp_max is not None and p.temp_min != p.temp_max:
            t += f" (de {_fmt(p.temp_min)} a {_fmt(p.temp_max)} °C)"
        lines.append(f"• Temperatura: {t}")
    if p.descripcion_es or p.descripcion:
        lines += ["", p.descripcion_es or p.descripcion]
    lines.append(f"Fuente: {b.url}")
    return "\n".join(lines)

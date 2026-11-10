"""Los textos del juego (global.ini): para entender el Game.log en cualquier idioma
y para la enciclopedia local.

Star Citizen guarda las traducciones en …\\StarCitizen\\LIVE\\data\\Localization\\<idioma>\\global.ini
y el idioma elegido en …\\LIVE\\user.cfg (g_language = spanish_(spain)). El inglés va dentro
del Data.p4k y no se puede leer como archivo: para él Nova trae las frases que necesita
(game_text_en.py).
"""
from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path

from .game_text_en import EN
from .logrules import CONST, RULE_KEYS, TILDE_FIELDS

log = logging.getLogger("nova.localization")

HANDLE_LIKE = re.compile(r"[_\-\d]|[a-z][A-Z]|^[A-Z0-9]{4,}$")
GENERIC_TARGET = re.compile(r"(?i)(?:sospechos[oa]|suspect|criminal|objetivo|target|recompensa|bounty)\s*:\s*"
                            r"([A-Za-z0-9_\-]{3,60})\s*$")
TOKEN = re.compile(r"%(?:\.\d+)?(?:ls|hs|[lh]?[sSdiuf])|~(\w+)\(([^)]*)\)")
NUMERIC = set("diuf")


# ------------------------------------------------------------------ archivo
def game_root_from_log(game_log: Path | None) -> Path | None:
    """Carpeta del canal (LIVE, PTU…) a partir del Game.log."""
    return game_log.parent if game_log else None


def read_language(channel_dir: Path) -> str:
    """Idioma elegido en user.cfg (g_language = spanish_(spain)). Vacío = inglés."""
    cfg = channel_dir / "user.cfg"
    try:
        for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*g_language\s*=\s*([^\s;#]+)", line, re.I)
            if m:
                return m.group(1).strip()
    except OSError:
        pass
    return ""


def find_global_ini(channel_dir: Path | None, custom: str = "") -> tuple[Path | None, str]:
    """(ruta del global.ini, idioma). Prioridad: ruta indicada a mano > idioma de user.cfg >
    la traducción más reciente de data\\Localization."""
    if custom:
        p = Path(custom)
        if p.is_file():
            return p, p.parent.name
    if not channel_dir:
        return None, ""
    loc = channel_dir / "data" / "Localization"
    lang = read_language(channel_dir)
    if lang:
        p = loc / lang / "global.ini"
        if p.is_file():
            return p, lang
    try:
        found = [p for p in loc.glob("*/global.ini") if p.is_file()]
    except OSError:
        found = []
    if found:
        best = max(found, key=lambda p: p.stat().st_mtime)
        return best, best.parent.name
    return None, lang or "english"


def parse_ini(path: Path) -> dict[str, str]:
    """clave (en minúsculas, sin ',P') -> texto."""
    out: dict[str, str] = {}
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            if "=" not in line or line.startswith((";", "#")):
                continue
            k, v = line.rstrip("\r\n").split("=", 1)
            out[k.split(",")[0].strip().lower()] = v
    return out


# --------------------------------------------------------------- plantillas
def _literal(text: str) -> str:
    """Texto fijo de una plantilla -> regex que tolera saltos de línea y espacios."""
    text = text.replace("\\n", " ").replace("\xa0", " ")
    parts = [re.escape(p) for p in re.split(r"\s+", text.strip())]
    core = r"\s*".join(p for p in parts if p)
    lead = r"\s*" if text[:1].isspace() else ""
    trail = r"\s*" if text[-1:].isspace() else ""
    return lead + core + trail


def template_regex(template: str, fields: tuple[str, ...], shape: str = "tpl") -> tuple[re.Pattern | None, int]:
    """Plantilla del juego -> expresión regular con grupos con nombre. Devuelve (regex, nº de letras fijas)."""
    tpl = (template or "").strip()
    if shape in ("title", "name_title", "title_name"):
        tpl = TOKEN.sub(" ", tpl).split("\\n")[0].strip().rstrip(".:!¡ ")
        lit = _literal(tpl)
        if len(re.sub(r"\W", "", tpl)) < 4:
            return None, 0
        if shape == "name_title":
            rx = r"(?:^|\s)(?P<nombre>[\w.\-]{2,})\s+" + lit
        elif shape == "title_name":
            rx = lit + r"\s+(?P<nombre>[\w.\-]{2,})\s*$"
        else:
            rx = r"(?:^|\W)" + lit + r"(?:\W|$)"
        return re.compile(rx, re.I), len(tpl)
    tpl = tpl.rstrip(" .:")
    out, pos, used, n_lit = [], 0, set(), 0
    free = list(fields)

    def group(name: str, body: str) -> str:
        if not name or name in used:
            return f"(?:{body})"
        used.add(name)
        return f"(?P<{name}>{body})"

    for m in TOKEN.finditer(tpl):
        lit = tpl[pos:m.start()]
        n_lit += len(re.sub(r"\W", "", lit))
        out.append(_literal(lit) if lit.strip() else (r"\s*" if lit else ""))
        pos = m.end()
        if m.group(1):  # ~funcion(Var)
            name = TILDE_FIELDS.get(m.group(2).lower(), "")
            body = r"[\d.,]+" if name == "cantidad" else r".*?"
            out.append(group(name, body) if name else r".*?")
            continue
        spec = m.group(0)
        if spec == "%S":  # jugador (sin espacios)
            out.append(group("nombre", r"[\w.\-]+"))
            continue
        name = free.pop(0) if free else ""
        body = r"[\d.,]+" if spec[-1] in NUMERIC else r".+?"
        out.append(group(name, body))
    lit = tpl[pos:]
    n_lit += len(re.sub(r"\W", "", lit))
    out.append(_literal(lit))
    if n_lit < 5:
        return None, 0
    rx = "".join(out) + r"\s*[.!]?\s*$"
    if not tpl.startswith(("%", "~")):
        rx = r"(?:^|\W)" + rx
    try:
        return re.compile(rx, re.I | re.S), n_lit
    except re.error as e:
        log.debug("Plantilla no válida %r: %s", template, e)
        return None, 0


class GameText:
    """Textos del juego cargados del global.ini del jugador (si lo hay) + inglés de reserva."""

    def __init__(self) -> None:
        self.path: Path | None = None
        self.language = "english"
        self.entries: dict[str, str] = {}
        self.mtime = 0.0
        self.rules: list[tuple[str, str, re.Pattern, str, str, dict]] = []
        self._suffix_ship: re.Pattern | None = None
        self._lock = threading.Lock()
        self.build_rules()

    # ----------------------------------------------------------------- carga
    def load(self, path: Path | None, language: str = "") -> bool:
        """Carga (o recarga si ha cambiado) el global.ini. Devuelve True si hubo cambios."""
        if not path:
            changed = bool(self.entries)
            with self._lock:
                self.path, self.entries, self.mtime = None, {}, 0.0
                self.language = language or "english"
            if changed:
                self.build_rules()
            return changed
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return False
        if path == self.path and mtime == self.mtime:
            return False
        entries = parse_ini(path)
        with self._lock:
            self.path, self.entries, self.mtime = path, entries, mtime
            self.language = language or path.parent.name
        log.info("global.ini: %s (%d textos, %s)", path, len(entries), self.language)
        self.build_rules()
        return True

    def get(self, key: str, default: str | None = None) -> str | None:
        k = key.lower().lstrip("@")
        v = self.entries.get(k)
        if v is None:
            v = EN.get(key) or next((t for kk, t in EN.items() if kk.lower() == k), None)
        return v if v is not None else default

    def local(self, key: str) -> str | None:
        """Solo el texto de TU global.ini (sin inglés de reserva)."""
        return self.entries.get(key.lower().lstrip("@"))

    # ---------------------------------------------------------------- reglas
    def build_rules(self) -> None:
        rules = []
        en_lower = {k.lower(): v for k, v in EN.items()}
        for kind, cat, keys, fields, shape in RULE_KEYS:
            for key in keys:
                texts = []
                mine = self.entries.get(key.lower())
                if mine:
                    texts.append(mine)
                en = en_lower.get(key.lower())
                if en and en not in texts:
                    texts.append(en)
                for t in texts:
                    rx, weight = template_regex(t, fields, shape)
                    if rx:
                        rules.append((kind, cat, rx, key, shape, dict(CONST.get(key, {})), weight))
        # Primero las plantillas más largas (más específicas): «X se ha unido a canal…» antes que «Nuevo miembro unido».
        rules.sort(key=lambda r: -r[6])
        suffix = self.entries.get("comms_suffix_ship_channel") or en_lower.get("comms_suffix_ship_channel")
        ship_rx = None
        if suffix:
            body = _literal(suffix).replace("%S", "(?P<canal>.+)").replace(re.escape("%S"), "(?P<canal>.+)")
            try:
                ship_rx = re.compile(r"^\s*(?:the\s+|el\s+|al\s+|del\s+)?" + body.replace("'", "'?") + r"\s*$", re.I)
            except re.error:
                ship_rx = None
        titles = set()
        for src in (self.entries, en_lower):
            for k, v in src.items():
                if k.startswith("notification_") and k.endswith("_title") and v and "%" not in v:
                    titles.add(v.strip().lower())
        self._target_rx = None
        with self._lock:
            self.rules = [r[:6] for r in rules]
            self._suffix_ship = ship_rx
            self._titles = sorted(titles, key=len, reverse=True)

    def match(self, text: str) -> tuple[str, str, dict, str] | None:
        """Aviso del HUD -> (tipo, categoría, datos, clave) o None."""
        with self._lock:
            rules = self.rules
        for kind, cat, rx, key, shape, const in rules:
            m = rx.search(text)
            if not m:
                continue
            data = {k: (v.strip() if k == "donde" else v.strip(" '\"")) for k, v in m.groupdict().items() if v}
            data.update(const)
            name = data.get("nombre", "")
            if name:  # «Miembro ha salido · ha dejado el canal…»: el «nombre» sería parte del título
                low = text.lower()
                for title in getattr(self, "_titles", []):
                    if low.startswith(title) and title.endswith(name.lower()):
                        data["nombre"] = "alguien"
                        break
            if "donde" in data:
                kind, cat, data = self._classify_suffix(kind, cat, data)
            return kind, cat, data, key
        return None

    # ------------------------------------------------- objetivos de recompensas (cazarrecompensas)
    def bounty_target(self, text: str) -> str:
        """Título u objetivo de un contrato -> nombre del objetivo (~mission(TargetName)) si es un apodo
        sin espacios (como los de los jugadores). '' si no lo es o no se reconoce."""
        t = re.sub(r"</?EM\d>", "", text or "").strip()
        if not t:
            return ""
        rxs = getattr(self, "_target_rx", None)
        if rxs is None:
            rxs = self._build_target_rx()
        for rx, strong in rxs:
            m = rx.fullmatch(t)
            if m:
                name = m.group("t").strip(" '\"«»")
                # Contratos JcJ: siempre. Otros: solo si el nombre parece un apodo de jugador
                # (los PNJ suelen tener nombres normales, «Gonzo», «Wade Rocha»).
                return name if strong or HANDLE_LIKE.search(name) else ""
        m = GENERIC_TARGET.search(t)
        return m.group(1) if m and HANDLE_LIKE.search(m.group(1)) else ""

    def _build_target_rx(self) -> list:
        out, seen = [], set()
        for src in (self.entries, {k.lower(): v for k, v in EN.items()}):
            for k, v in src.items():
                if "~mission(targetname)" not in (v or "").lower() or len(v) > 160:
                    continue
                if not any(w in k for w in ("title", "_obj", "objective", "marker")):
                    continue
                tpl = re.sub(r"</?EM\d>", "", v)
                tpl = re.sub(r"\[[^\]]*\]\*?", "", tpl).strip().rstrip(" .:")
                if tpl in seen:
                    continue
                seen.add(tpl)
                parts, pos, has = [], 0, False
                for m in TOKEN.finditer(tpl):
                    parts.append(_literal(tpl[pos:m.start()]))
                    pos = m.end()
                    if m.group(1) and m.group(2).lower() == "targetname" and not has:
                        parts.append(r"(?P<t>[A-Za-z0-9_\-]{2,60})")
                        has = True
                    else:
                        parts.append(r".+?")
                parts.append(_literal(tpl[pos:]))
                if not has:
                    continue
                try:
                    out.append((re.compile(r"\s*" + "".join(parts) + r"\s*[.:]?\s*", re.I),
                                "pvp" in k or "player" in k))
                except re.error:
                    continue
        out.sort(key=lambda r: not r[1])  # primero las plantillas de contratos JcJ
        self._target_rx = out
        return out

    def ship_channel(self, where: str) -> str:
        """«canal 'Argo MOLE : 0zzyt0'» -> «Argo MOLE : 0zzyt0» (o "" si no es un canal de nave)."""
        if not where:
            return ""
        rx = self._suffix_ship
        if rx:
            m = rx.match(where)
            if m:
                return m.group("canal").strip(" '\"")
        m = re.search(r"'([^']+ : [^']+)'?", where)
        return m.group(1) if m else ""

    def _classify_suffix(self, kind: str, cat: str, data: dict) -> tuple[str, str, dict]:
        where = data.pop("donde", "")
        channel = self.ship_channel(where)
        if not channel:
            return kind, cat, data
        ship, _, owner = channel.partition(" : ")
        data["nave"] = ship.strip()
        data["dueno"] = owner.strip()
        mapping = {"grupo_entra": "nave_tripulante_entra", "grupo_sale": "nave_tripulante_sale",
                   "grupo_te_unes": "nave_subes", "grupo_dejas": "nave_bajas",
                   "grupo_expulsa": "nave_tripulante_sale", "grupo_expulsado": "nave_bajas"}
        return mapping.get(kind, kind), "nave", data


# ------------------------------------------------------------ nombres de naves
def ship_name(cls: str, text: GameText | None) -> str:
    """'ARGO_MOLE_912403050828' -> 'Argo MOLE' (con el global.ini) o 'Argo Mole' (sin él)."""
    base = re.sub(r"_\d{6,}$", "", cls or "").strip("_")
    if not base:
        return ""
    if text:
        for cand in (base, re.sub(r"_[A-Z]+$", "", base)):
            v = text.local("vehicle_Name" + cand)
            if v:
                return v
        man, _, rest = base.partition("_")
        mname = text.local("manufacturer_Name" + man)
        if mname and rest:
            first = mname.split()[0]
            return f"{first} {_split(rest)}"
    return _split(base)


def _split(s: str) -> str:
    s = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Za-z])(?=\d)", " ", s)
    return re.sub(r"[_\s]+", " ", s).strip()


TEXT = GameText()  # instancia compartida (la carga el lector del Game.log)


def env_override() -> str:
    return os.environ.get("NOVA_GLOBAL_INI", "")

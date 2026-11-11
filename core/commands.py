"""Comandos de la nave.

Tres fuentes, que se combinan cada vez que se cargan:
  1. datos/comandos.json            comandos de fábrica de Nova (se actualizan con Nova)
  2. datos/comandos_personales.json  los tuyos: nuevos, modificados o borrados desde la ventana
  3. tu actionmaps.xml de Star Citizen: si cambiaste una tecla en el juego, Nova la usa;
     y las acciones a las que diste tecla en el juego y Nova no tenía se añaden solas.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import random
import re
import threading
import time
import unicodedata
from dataclasses import asdict, dataclass, field

from . import keys, keybinds, sc_actions
from .config import COMMANDS_FILE, DATA_DIR

log = logging.getLogger("nova.commands")
PERSONAL_FILE = DATA_DIR / "comandos_personales.json"

try:
    from rapidfuzz import fuzz

    def _similarity(a: str, b: str) -> float:
        return fuzz.ratio(a, b)

    def _partial(a: str, b: str) -> float:
        return fuzz.partial_ratio(a, b)
except ImportError:  # pragma: no cover
    from difflib import SequenceMatcher

    def _similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio() * 100

    def _partial(a: str, b: str) -> float:
        short, long_ = sorted((a, b), key=len)
        if not short:
            return 0.0
        best = 0.0
        for i in range(0, max(1, len(long_) - len(short) + 1)):
            best = max(best, SequenceMatcher(None, short, long_[i:i + len(short)]).ratio())
        return best * 100

# Muletillas que no cambian la orden.
_FILLERS = {
    "por", "favor", "porfa", "oye", "hey", "eh", "venga", "vale", "ya", "ahora", "rapido",
    "inmediatamente", "ok", "okay", "bueno", "pues", "anda", "nova",
}


def simplify(text: str) -> str:
    """Minúsculas, sin tildes ni signos: '¡Oye, Nova!' -> 'oye nova'"""
    t = unicodedata.normalize("NFKD", text.lower().replace("ß", "ss"))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9ñ]+", t))


def _tr(text: str) -> str:
    from .i18n import tr
    return tr(text)


def _lang() -> str:
    from .i18n import lang
    return lang()


_OVERLAYS: dict = {}


def lang_overlay(lang: str) -> dict:
    """Comandos de fábrica traducidos: datos\\comandos.<idioma>.json (vacío en español)."""
    if lang == "es":
        return {}
    if lang not in _OVERLAYS:
        _OVERLAYS[lang] = _read_json(COMMANDS_FILE.with_name(f"comandos.{lang}.json"), {})
    return _OVERLAYS[lang]


def normalize(text: str, extra_names: tuple[str, ...] = ()) -> str:
    """Además quita muletillas y el nombre: '¡Oye Nova, BAJA el tren, por favor!' -> 'baja el tren'"""
    from .i18n import lang
    from .lang_data import FILLERS
    drop = _FILLERS | FILLERS.get(lang(), set()) | {w for n in extra_names for w in simplify(n).split()}
    return " ".join(w for w in simplify(text).split() if w not in drop)


@dataclass
class Command:
    id: str
    nombre: str
    descripcion: str = ""
    categoria: str = ""
    frases: list[str] = field(default_factory=list)
    respuestas: list[str] = field(default_factory=list)
    acciones: list[dict] = field(default_factory=list)
    solo_frase_exacta: bool = False
    naves: list[str] = field(default_factory=list)  # vacío = en todas; si no, solo en esas naves
    registrar: bool = False  # anotarlo en la bitácora (p. ej. fijar objetivo)
    origen: str = "base"  # base | modificado | personal | juego

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("origen", None)
        return d


def _read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def _write_json(path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _ship_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", simplify(name or ""))


def ship_ok(cmd: Command, ship: str) -> bool:
    """¿Vale este comando en la nave actual? Sin lista de naves, o sin saber la nave, sí."""
    if not cmd.naves or not ship:
        return True
    k = _ship_key(ship)
    return any(_ship_key(x) and (_ship_key(x) in k or k in _ship_key(x)) for x in cmd.naves)


def _ships_disjoint(a: Command, b: Command) -> bool:
    if not a.naves or not b.naves:
        return False
    ka, kb = {_ship_key(x) for x in a.naves}, {_ship_key(x) for x in b.naves}
    return not (ka & kb)


def _pick_for_ship(cands: list[Command], ship: str) -> Command | None:
    """Entre comandos con la misma frase: primero el de tu nave, luego el general."""
    if not cands:
        return None
    if ship:
        for c in cands:
            if c.naves and ship_ok(c, ship):
                return c
    for c in cands:
        if not c.naves:
            return c
    return cands[0] if not ship else None


class CommandBook:
    def __init__(self, settings, gamelog_path_fn=lambda: None) -> None:
        self.settings = settings
        self.gamelog_path_fn = gamelog_path_fn
        self.commands: dict[str, Command] = {}
        self._phrases: dict[str, str] = {}
        self._lock = threading.Lock()  # una secuencia de teclas a la vez
        self.sync: dict = {"estado": "sin sincronizar"}
        self.warnings: list[str] = []
        self.load()

    # ------------------------------------------------------------------ carga
    def load(self) -> list[str]:
        warnings: list[str] = []
        base = _read_json(COMMANDS_FILE, {}).get("comandos", [])
        personal = _read_json(PERSONAL_FILE, {"comandos": []}).get("comandos", [])
        merged: dict[str, Command] = {}
        fields_ = Command.__dataclass_fields__
        from .i18n import lang
        lg = lang()
        overlay = lang_overlay(lg)
        self._localized_ids = set()
        for item in base:
            c = Command(**{k: v for k, v in item.items() if k in fields_})
            c.origen = "base"
            ov = overlay.get("comandos", {}).get(c.id)
            if ov:  # v1.3: nombre, frases y respuestas en el idioma elegido (las de español siguen valiendo)
                c.nombre = ov.get("nombre") or c.nombre
                c.descripcion = ov.get("descripcion") or c.descripcion
                c.categoria = overlay.get("categorias", {}).get(c.categoria, c.categoria)
                c.frases = list(ov.get("frases") or []) or c.frases  # en su idioma (STT ya no oye español)
                if ov.get("respuestas"):
                    c.respuestas = list(ov["respuestas"])
                    self._localized_ids.add(c.id)
            merged[c.id] = c
        for item in personal:
            if item.get("borrado"):
                merged.pop(item.get("id"), None)
                continue
            c = Command(**{k: v for k, v in item.items() if k in fields_})
            c.origen = "modificado" if c.id in merged else "personal"
            ov = overlay.get("comandos", {}).get(c.id)
            if ov:  # comando de fábrica que cambiaste: se le suman las frases del idioma
                c.frases = list(dict.fromkeys(c.frases + list(ov.get("frases") or [])))
                c.categoria = overlay.get("categorias", {}).get(c.categoria, c.categoria)
                self._localized_ids.discard(c.id)
            merged[c.id] = c

        self._apply_game_keys(merged, warnings)

        phrases: dict[str, list[str]] = {}
        for c in merged.values():
            for a in c.acciones:
                combo = a.get("tecla")
                if combo and not keys.valid_combo(combo):
                    warnings.append(f"«{c.nombre}»: tecla '{combo}' no reconocida")
            for p in c.frases:
                n = normalize(p)
                if not n:
                    continue
                ids = phrases.setdefault(n, [])
                for other in ids:
                    if other != c.id and not _ships_disjoint(c, merged[other]):
                        warnings.append(f"Frase repetida «{p}» en «{c.nombre}» y «{merged[other].nombre}»")
                if c.id not in ids:
                    ids.append(c.id)
        with self._lock:
            self.commands, self._phrases = merged, phrases
        self.warnings = warnings
        for w in warnings:
            log.warning(w)
        log.info("%d comandos y %d frases cargados", len(merged), len(phrases))
        return warnings

    def _apply_game_keys(self, merged: dict[str, Command], warnings: list[str]) -> None:
        """Ajusta las teclas a las de tu actionmaps.xml y añade las acciones nuevas."""
        if not self.settings.get("teclas_juego_sync"):
            self.sync = {"estado": "desactivado"}
            return
        path = keybinds.find_actionmaps(self.settings.get("actionmaps_ruta"), self.gamelog_path_fn())
        if not path:
            self.sync = {"estado": "no encontrado", "ruta": "",
                         "detalle": _tr("No encuentro actionmaps.xml. Se usan las teclas por defecto del juego.")}
            return
        try:
            binds = keybinds.parse_actionmaps(path)
        except Exception as e:
            self.sync = {"estado": "error", "ruta": str(path), "detalle": f"No pude leer el archivo: {e}"}
            return
        applied, unbound, joystick_only, used = [], [], [], set()
        for c in merged.values():
            for step in c.acciones:
                game = step.get("juego")
                if not game:
                    continue
                for name in sc_actions.names_for(game):
                    used.add(name)
                b = next((binds[n] for n in sc_actions.names_for(game) if n in binds), None)
                if not b:
                    continue
                if b.tecla:
                    if b.tecla != step.get("tecla"):
                        applied.append(f"{c.nombre}: {step.get('tecla') or step.get('raton') or '—'} → {b.tecla}")
                    step["tecla"] = b.tecla
                    step.pop("raton", None)
                    if b.mantener and b.mantener > float(step.get("mantener", 0)):
                        step["mantener"] = b.mantener
                    if b.doble:
                        step["doble"] = True
                elif b.raton:
                    applied.append(f"{c.nombre}: → ratón {b.raton}")
                    step["raton"] = b.raton
                    step.pop("tecla", None)
                elif b.sin_tecla:
                    (joystick_only if b.otros else unbound).append(c.nombre)
        added = []
        if self.settings.get("comandos_auto_juego"):
            for name, b in binds.items():
                if name in used or not (b.tecla or b.raton) or sc_actions.is_dangerous(name):
                    continue
                cid = "juego_" + name
                if cid in merged:
                    continue
                cat = sc_actions.CATALOG.get(name)
                step = {"juego": name, "mantener": b.mantener}
                step.update({"tecla": b.tecla} if b.tecla else {"raton": b.raton})
                if b.doble:
                    step["doble"] = True
                acts = lang_overlay(_lang()).get("acciones", {})
                if name in acts and cat:
                    cat = (acts[name][0], cat[1], cat[2], list(acts[name][1]),
                           lang_overlay(_lang()).get("categorias", {}).get(cat[4], cat[4]))
                merged[cid] = Command(
                    id=cid, nombre=cat[0] if cat else sc_actions.label(name),
                    descripcion=f"Acción del juego '{name}' tal como la tienes configurada en Star Citizen.",
                    categoria="Del juego (automático)", frases=list(cat[3]) if cat else [],
                    respuestas=[], acciones=[step], origen="juego")
                added.append(sc_actions.label(name))
        self.sync = {
            "estado": "ok", "ruta": str(path), "fecha": time.strftime("%d/%m %H:%M"),
            "acciones_en_archivo": len(binds), "aplicadas": applied, "nuevas": added,
            "sin_tecla": unbound, "solo_joystick": joystick_only,
        }
        log.info("actionmaps.xml: %d teclas aplicadas, %d comandos nuevos", len(applied), len(added))

    # ------------------------------------------------- comandos personales
    def _personal(self) -> list[dict]:
        return _read_json(PERSONAL_FILE, {"comandos": []}).get("comandos", [])

    def reset_personal(self) -> None:
        """Borra tus comandos creados o modificados y vuelve a los de fábrica (+ los del juego)."""
        try:
            PERSONAL_FILE.unlink()
        except OSError:
            pass
        self.load()

    def _save_personal(self, items: list[dict]) -> None:
        _write_json(PERSONAL_FILE, {"_info": "Tus comandos de Nova (creados o modificados desde la ventana).",
                                    "comandos": items})

    def save_command(self, data: dict) -> Command:
        """Crea o modifica un comando. Lanza ValueError con un mensaje legible si algo no vale."""
        nombre = (data.get("nombre") or "").strip()
        if not nombre:
            raise ValueError("Ponle un nombre al comando.")
        acciones = []
        for a in data.get("acciones") or []:
            if "esperar" in a:
                acciones.append({"esperar": max(0.0, min(float(a["esperar"]), 60.0))})
                continue
            step: dict = {}
            if a.get("tecla"):
                if not keys.valid_combo(a["tecla"]):
                    raise ValueError(f"Tecla no reconocida: {a['tecla']}")
                step["tecla"] = a["tecla"]
            elif a.get("raton") in ("left", "right", "middle", "x1", "x2"):
                step["raton"] = a["raton"]
            else:
                raise ValueError("Hay un paso sin tecla. Grábala o bórralo.")
            if float(a.get("mantener") or 0) > 0:
                step["mantener"] = min(float(a["mantener"]), 30.0)
            if a.get("doble"):
                step["doble"] = True
            if a.get("juego"):
                step["juego"] = a["juego"]
            acciones.append(step)
        if not any("tecla" in a or "raton" in a for a in acciones):
            raise ValueError("El comando necesita al menos una tecla o clic.")
        frases = [f.strip() for f in data.get("frases") or [] if f.strip()]
        cid = data.get("id") or self._new_id(nombre)
        naves = [x.strip() for x in data.get("naves") or [] if str(x).strip()]
        probe = Command(id=cid, nombre=nombre, naves=naves)
        for f in frases:  # que no pise frases de otros comandos (salvo si son de naves distintas)
            for other in self._phrases.get(normalize(f), []):
                if other != cid and other in self.commands and not _ships_disjoint(probe, self.commands[other]):
                    raise ValueError(f"La frase «{f}» ya la usa «{self.commands[other].nombre}». "
                                     f"Si es para otra nave, indícalo en «Solo en estas naves».")
        cmd = Command(id=cid, nombre=nombre, descripcion=(data.get("descripcion") or "").strip(),
                      categoria=(data.get("categoria") or "Personales").strip(), frases=frases,
                      respuestas=[r.strip() for r in data.get("respuestas") or [] if r.strip()],
                      acciones=acciones, solo_frase_exacta=bool(data.get("solo_frase_exacta")),
                      naves=naves, registrar=bool(data.get("registrar")))
        items = [i for i in self._personal() if i.get("id") != cid]
        items.append(cmd.to_dict())
        self._save_personal(items)
        self.load()
        return self.commands[cid]

    def delete_command(self, cid: str) -> None:
        items = [i for i in self._personal() if i.get("id") != cid]
        base_ids = {c["id"] for c in _read_json(COMMANDS_FILE, {}).get("comandos", [])}
        if cid in base_ids or cid.startswith("juego_"):
            items.append({"id": cid, "borrado": True})
        self._save_personal(items)
        self.load()

    def restore_command(self, cid: str) -> None:
        """Vuelve a la versión de fábrica (o deja de ocultar un comando borrado)."""
        self._save_personal([i for i in self._personal() if i.get("id") != cid])
        self.load()

    def hidden_commands(self) -> list[str]:
        return [i["id"] for i in self._personal() if i.get("borrado")]

    def _new_id(self, nombre: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "_", simplify(nombre)).strip("_")[:30] or "comando"
        cid = base
        while cid in self.commands:
            cid = f"{base}_{random.randint(100, 999)}"
        return cid

    # ---------------------------------------------------- reconocimiento rápido
    def match(self, transcript: str, names: tuple[str, ...] = (), ship: str = "") -> Command | None:
        """Frase reconocida al instante (sin IA). Tolera pequeños errores de dictado.
        `ship`: nave en la que vas; los comandos con «naves» solo valen en esas."""
        n = normalize(transcript, names)
        if not n:
            return None
        with self._lock:
            phrases, commands = dict(self._phrases), dict(self.commands)
        if n in phrases:
            return _pick_for_ship([commands[c] for c in phrases[n]], ship)
        best, score = None, 0.0
        for phrase, ids in phrases.items():
            cand = _pick_for_ship([commands[c] for c in ids if not commands[c].solo_frase_exacta], ship)
            if not cand:
                continue
            # Nunca confundir "activa" con "desactiva" por parecido.
            if n.startswith("des") != phrase.startswith("des"):
                continue
            s = _similarity(n, phrase)
            if s > score:
                best, score = cand, s
        if best and score >= 90 and len(n.split()) <= 6:
            return best
        return None

    # ---------------------------------------------------------------- ejecución
    def localized(self, cmd: Command) -> bool:
        """¿Sus respuestas ya están en el idioma elegido (archivo comandos.<idioma>.json)?"""
        return cmd.id in getattr(self, "_localized_ids", set())

    def response_for(self, cmd: Command) -> str:
        t = self.settings.get("tratamiento")
        text = random.choice(cmd.respuestas) if cmd.respuestas else f"{cmd.nombre}. Hecho, {t}."
        return text.replace("{t}", t)

    def execute(self, cmd: Command) -> str:
        """Ejecuta las acciones. Devuelve un texto de resultado para la IA/registro."""
        if self.settings.get("solo_si_juego_activo") and not keys.game_in_foreground():
            return "No ejecutado: Star Citizen no está en primer plano."
        delay = self.settings.get("teclas_retardo_ms", 60) / 1000
        steps = copy.deepcopy(cmd.acciones)
        with self._lock:
            for a in steps:
                try:
                    times = 2 if a.get("doble") else 1
                    if "esperar" in a:
                        time.sleep(float(a["esperar"]))
                    elif "tecla" in a:
                        for _ in range(times):
                            keys.press_combo(a["tecla"], float(a.get("mantener", 0)), gap=delay)
                            if times > 1:
                                time.sleep(0.08)
                    elif "tecla_abajo" in a:
                        keys.key_down(a["tecla_abajo"])
                    elif "tecla_arriba" in a:
                        keys.key_up(a["tecla_arriba"])
                    elif "raton" in a:
                        for _ in range(times):
                            keys.mouse_click(a["raton"], float(a.get("mantener", 0)))
                    elif "rueda" in a:
                        keys.mouse_scroll(int(a["rueda"]))
                    time.sleep(delay)
                except KeyError as e:
                    log.error("%s: %s", cmd.id, e)
                    return f"Error: {e}"
        log.info("Ejecutado: %s", cmd.nombre)
        return f"Ejecutado: {cmd.nombre}"

    # ------------------------------------------------------------ para la IA
    def tool_catalog(self, ship: str = "") -> str:
        lines = []
        for c in self.commands.values():
            if c.solo_frase_exacta or not ship_ok(c, ship):
                continue
            only = f" (solo en: {', '.join(c.naves)})" if c.naves else ""
            lines.append(f"- {c.id}: {c.nombre}{only}. {c.descripcion}")
        return "\n".join(lines)

    def ai_ids(self, ship: str = "") -> list[str]:
        return [c.id for c in self.commands.values() if not c.solo_frase_exacta and ship_ok(c, ship)]

    # ------------------------------------------------------------ para la ventana
    def as_list(self) -> list[dict]:
        out = []
        for c in self.commands.values():
            d = c.to_dict()
            d["origen"] = c.origen
            out.append(d)
        return out

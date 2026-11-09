"""Lee las teclas que tienes configuradas en Star Citizen (actionmaps.xml).

El juego guarda en  ...\\StarCitizen\\LIVE\\user\\client\\0\\Profiles\\default\\actionmaps.xml
SOLO las teclas que has cambiado respecto a las de fábrica. Nova lo lee al arrancar
y ajusta sus comandos para pulsar siempre las teclas que tú usas.
Formato:  <action name="v_toggle_landing_system"><rebind input="kb1_lalt+n"/></action>
"""
from __future__ import annotations

import logging
import os
import string
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from . import keys

log = logging.getLogger("nova.keybinds")

# Nombres de tecla del juego -> nombres de Nova (core/keys.py)
SC_TO_NOVA = {
    "escape": "esc", "pgup": "pageup", "pgdn": "pagedown", "np_add": "add", "np_subtract": "subtract",
    "np_multiply": "multiply", "np_divide": "divide", "np_period": "decimal", "np_enter": "numenter",
    "enter": "enter", "backspace": "backspace", "capslock": "capslock", "numlock": "numlock",
    "scrolllock": "scrolllock", "space": "space", "tab": "tab",
}
for _d in range(10):
    SC_TO_NOVA[f"np_{_d}"] = f"num{_d}"
SC_MOUSE = {"mouse1": "left", "mouse2": "right", "mouse3": "middle", "mouse4": "x1", "mouse5": "x2"}
# Modos de activación del juego -> cómo pulsar
MODE_HOLD = {"hold": 0.8, "delayed_press": 0.35, "delayed_press_medium": 0.6, "delayed_press_long": 1.6,
             "delayed_hold": 0.6, "delayed_hold_long": 1.6, "hold_no_retrigger": 0.8, "smart_toggle": 0.0}


@dataclass
class Binding:
    action: str
    tecla: str = ""        # combinación de teclado para Nova ("lalt+n"); "" si no hay
    raton: str = ""        # botón de ratón si solo está en el ratón
    mantener: float = 0.0
    doble: bool = False
    sin_tecla: bool = False  # el jugador la dejó sin tecla de teclado
    otros: list[str] = field(default_factory=list)  # joystick/HOTAS (Nova no los puede pulsar)


def convert_input(sc_input: str) -> str | None:
    """'lalt+n' (formato del juego, sin 'kb1_') -> combinación de Nova, o None si no se reconoce."""
    parts = [p.strip().lower() for p in sc_input.split("+") if p.strip()]
    if not parts:
        return None
    out = [SC_TO_NOVA.get(p, p) for p in parts]
    combo = "+".join(out)
    return combo if keys.valid_combo(combo) else None


def find_actionmaps(custom: str = "", gamelog_path: Path | None = None) -> Path | None:
    if custom and Path(custom).exists():
        return Path(custom)
    rel = Path("user") / "client" / "0" / "Profiles" / "default" / "actionmaps.xml"
    candidates: list[Path] = []
    if gamelog_path:
        candidates.append(Path(gamelog_path).parent / rel)
    if os.name == "nt":
        drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
        roots = ["Program Files\\Roberts Space Industries\\StarCitizen", "Roberts Space Industries\\StarCitizen",
                 "Games\\Roberts Space Industries\\StarCitizen", "StarCitizen"]
        for d in drives:
            for r in roots:
                for ch in ("LIVE", "PTU", "EPTU", "HOTFIX", "TECH-PREVIEW"):
                    candidates.append(Path(d) / r / ch / rel)
    found = [p for p in candidates if p.exists()]
    return max(found, key=lambda p: p.stat().st_mtime) if found else None


def parse_actionmaps(path: Path) -> dict[str, Binding]:
    tree = ET.parse(path)
    result: dict[str, Binding] = {}
    for action in tree.getroot().iter("action"):
        name = action.get("name")
        if not name:
            continue
        b = result.setdefault(name, Binding(name))
        for rb in action.findall("rebind"):
            raw = rb.get("input") or ""
            mode = (rb.get("activationMode") or "").lower()
            dev, _, key = raw.partition("_")
            if dev.startswith("kb"):
                if not key.strip():
                    b.sin_tecla = not b.tecla
                    continue
                combo = convert_input(key)
                if combo:
                    b.tecla, b.sin_tecla = combo, False
                    b.mantener = MODE_HOLD.get(mode, 0.0)
                    b.doble = mode == "double_tap"
                else:
                    log.info("Tecla del juego no reconocida: %s (%s)", raw, name)
            elif dev.startswith("mo") and key in SC_MOUSE and not b.tecla:
                b.raton = SC_MOUSE[key]
                b.mantener = MODE_HOLD.get(mode, 0.0)
            elif raw.strip() and key.strip():
                b.otros.append(raw)
    return result

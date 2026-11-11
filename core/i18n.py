"""Idiomas de NOVA AI (v1.3): español, inglés, catalán, francés y alemán.

El texto original está en español y hace de «clave»: cada idioma tiene un
catálogo `recursos/idiomas/<código>.json` con {"texto en español": "traducción"}.
Lo que no esté en el catálogo se queda en español (nunca se rompe nada).

Una clave puede llevar huecos con nombre, «{n} comandos», y entonces también
sirve como patrón para textos ya rellenados («12 comandos» → «12 commands»).
"""
from __future__ import annotations

import json
import locale
import os
import re
import sys
import threading
from pathlib import Path

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
DIR = BASE / "recursos" / "idiomas"

# Código → datos de cada idioma
LANGS: dict[str, dict] = {
    "es": {"nombre": "Español", "stt": "es", "edge": "es-ES-XimenaNeural", "piper": "es_ES-davefx-medium",
           "tratamiento": "señor", "tratamientos": ["señor", "señora", "capitán", "capitana", "comandante"],
           "chat": "en", "windows": ("es", "spanish")},
    "en": {"nombre": "English", "stt": "en", "edge": "en-GB-SoniaNeural", "piper": "en_GB-alba-medium",
           "tratamiento": "sir", "tratamientos": ["sir", "ma'am", "captain", "captain", "commander"],
           "chat": "en", "windows": ("en", "english")},
    "ca": {"nombre": "Català", "stt": "ca", "edge": "ca-ES-JoanaNeural", "piper": "ca_ES-upc_ona-medium",
           "tratamiento": "senyor", "tratamientos": ["senyor", "senyora", "capità", "capitana", "comandant"],
           "chat": "en", "windows": ("ca", "catalan")},
    "fr": {"nombre": "Français", "stt": "fr", "edge": "fr-FR-DeniseNeural", "piper": "fr_FR-siwis-medium",
           "tratamiento": "monsieur", "tratamientos": ["monsieur", "madame", "capitaine", "capitaine", "commandant"],
           "chat": "en", "windows": ("fr", "french")},
    "de": {"nombre": "Deutsch", "stt": "de", "edge": "de-DE-KatjaNeural", "piper": "de_DE-thorsten-medium",
           "tratamiento": "Herr", "tratamientos": ["Herr", "Frau", "Kapitän", "Kapitänin", "Kommandant"],
           "chat": "en", "windows": ("de", "german")},
}
CODES = tuple(LANGS)

# Voces de Edge recomendadas en cada idioma (la primera es la de por defecto)
EDGE_VOICES = {
    "es": ["es-ES-XimenaNeural", "es-ES-ElviraNeural", "es-ES-AlvaroNeural", "es-ES-XimenaMultilingualNeural",
           "es-ES-ArabellaMultilingualNeural", "es-ES-IsidoraMultilingualNeural", "es-ES-TristanMultilingualNeural",
           "es-MX-DaliaNeural", "es-MX-JorgeNeural"],
    "en": ["en-GB-SoniaNeural", "en-GB-LibbyNeural", "en-GB-RyanNeural", "en-US-AvaNeural", "en-US-EmmaNeural",
           "en-US-AndrewNeural", "en-US-JennyNeural", "en-US-GuyNeural", "en-AU-NatashaNeural"],
    "ca": ["ca-ES-JoanaNeural", "ca-ES-EnricNeural", "ca-ES-AlbaNeural"],
    "fr": ["fr-FR-DeniseNeural", "fr-FR-EloiseNeural", "fr-FR-HenriNeural", "fr-FR-VivienneMultilingualNeural",
           "fr-FR-RemyMultilingualNeural", "fr-CA-SylvieNeural", "fr-CA-JeanNeural"],
    "de": ["de-DE-KatjaNeural", "de-DE-AmalaNeural", "de-DE-ConradNeural", "de-DE-SeraphinaMultilingualNeural",
           "de-DE-FlorianMultilingualNeural", "de-AT-IngridNeural", "de-CH-LeniNeural"],
}

# Nombre del idioma en el que ha de contestar la IA
AI_LANG = {"es": "español de España", "en": "British English", "ca": "català", "fr": "français", "de": "Deutsch"}

# Carpeta de Localization del juego y valor de g_language para cada idioma oficial de Star Citizen
GAME_LANG = {"es": "spanish_(spain)", "en": "english", "fr": "french_(france)", "de": "german_(germany)",
             "ca": "spanish_(latin_america)"}

_lock = threading.Lock()
_lang = "es"
_cat: dict[str, dict[str, str]] = {}
_pat: dict[str, list[tuple[re.Pattern, str, list[str]]]] = {}

HOLE = re.compile(r"\{(\w*)\}")


def norm(code: str | None) -> str:
    c = (code or "").strip().lower().replace("_", "-")[:2]
    return c if c in LANGS else "es"


def detect_windows() -> str:
    """Idioma del sistema (para el instalador y la primera vez)."""
    v = os.environ.get("NOVA_IDIOMA")
    if v:
        return norm(v)
    try:
        if sys.platform == "win32":
            import ctypes
            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            name = locale.windows_locale.get(lcid, "")
            return norm(name)
        return norm((locale.getlocale()[0] or ""))
    except Exception:  # noqa: BLE001
        return "es"


def catalog(code: str) -> dict[str, str]:
    code = norm(code)
    if code == "es":
        return {}
    with _lock:
        if code not in _cat:
            data: dict[str, str] = {}
            f = DIR / f"{code}.json"
            try:
                raw = json.loads(f.read_text(encoding="utf-8"))
                data = {k: v for k, v in raw.items() if isinstance(v, str) and v and not k.startswith("@")}
            except Exception:  # noqa: BLE001
                pass
            _cat[code] = data
            pats = []
            for k, v in data.items():
                names = HOLE.findall(k)
                if not names:
                    continue
                # HOLE.split intercala texto y nombres de hueco: el texto se escapa, los huecos son grupos
                parts = HOLE.split(k)
                rx = "^"
                for i, part in enumerate(parts):
                    rx += r"(.+?)" if i % 2 else re.escape(part)
                rx += "$"
                pats.append((re.compile(rx, re.S), v, names))
            pats.sort(key=lambda p: -len(p[0].pattern))
            _pat[code] = pats
        return _cat[code]


def set_lang(code: str) -> str:
    global _lang
    _lang = norm(code)
    catalog(_lang)
    return _lang


def lang() -> str:
    return _lang


def info(code: str | None = None) -> dict:
    return LANGS[norm(code or _lang)]


def tr(text: str, code: str | None = None, **kw) -> str:
    """Traduce un texto en español al idioma activo (o a `code`)."""
    code = norm(code or _lang)
    out = text
    if code != "es" and text:
        cat = catalog(code)
        hit = cat.get(text)
        if hit is None:
            stripped = text.strip()
            hit = cat.get(stripped)
            if hit is not None:
                lead = text[: len(text) - len(text.lstrip())]
                trail = text[len(text.rstrip()):]
                hit = lead + hit + trail
        if hit is None and not kw:
            for rx, target, names in _pat.get(code, []):
                m = rx.match(text)
                if m:
                    vals = dict(zip(names, m.groups()))
                    pos = iter(m.groups())
                    groups = m.groups()
                    hit = HOLE.sub(lambda mm: (groups[int(mm.group(1)) - 1] if mm.group(1).isdigit()
                                               and 0 < int(mm.group(1)) <= len(groups) else
                                               vals.get(mm.group(1), mm.group(0)) if mm.group(1) else next(pos, "")),
                                   target)
                    break
        if hit is not None:
            out = hit
    if kw:
        try:
            out = out.format(**kw)
        except (KeyError, IndexError, ValueError):
            pass
    return out


_ = tr


def has(text: str, code: str | None = None) -> bool:
    code = norm(code or _lang)
    return code == "es" or text in catalog(code)


def client_catalog(code: str | None = None) -> dict[str, str]:
    """Lo que se manda a la ventana (todo el catálogo)."""
    return dict(catalog(norm(code or _lang)))


FEMININE = {"señora", "capitana", "señorita", "comandante en jefe", "ma'am", "madam", "senyora", "madame",
            "mademoiselle", "frau", "kapitänin", "kommandantin"}


def is_feminine(tratamiento: str) -> bool:
    return str(tratamiento or "").strip().lower() in FEMININE


def apply_language(settings, new: str, old: str) -> dict:
    """Ajusta lo que depende del idioma (tratamiento, voz) al cambiarlo. Devuelve lo que cambió."""
    new, old = norm(new), norm(old)
    changes: dict = {}
    settings.set("idioma", new, save=False)
    if new == old:
        return changes
    t = str(settings.get("tratamiento") or "").strip()
    olds = [x.lower() for x in LANGS[old]["tratamientos"]]
    if not t or t.lower() in olds:
        i = olds.index(t.lower()) if t else 0
        nt = LANGS[new]["tratamientos"][i]
        settings.set("tratamiento", nt, save=False)
        changes["tratamiento"] = nt
    voice = str(settings.get("tts_voz_edge") or "")
    if not voice.lower().startswith(new + "-"):
        settings.set("tts_voz_edge", LANGS[new]["edge"], save=False)
        changes["tts_voz_edge"] = LANGS[new]["edge"]
    pv = str(settings.get("tts_voz_piper") or "")
    if not pv.lower().startswith(new + "_"):
        settings.set("tts_voz_piper", LANGS[new]["piper"], save=False)
        changes["tts_voz_piper"] = LANGS[new]["piper"]
    return changes

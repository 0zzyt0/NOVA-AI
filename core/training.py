"""Configuración inicial: entender las respuestas habladas y entrenar el oído con el nombre.

Cada respuesta se califica como:
  ok=True   ✓ verde  (entendido; puede traer una nota, p. ej. «lo he oído como "Noba": aprendido»)
  ok=False  ✗ roja   (no se ha entendido nada útil: hay que repetir)
"""
from __future__ import annotations

import re

from .commands import _partial, simplify
from .wake import COMMON, contains_name, good_variant, same_name, strip_wake

# «Me llamo Antonio», «Llámate Atenea»… -> lo que va detrás.
_PILOT_INTRO = re.compile(
    r"^.*?\b(?:me llamo|mi nombre es|puedes llamarme|llamame|llámame|soy el|soy la|soy)\s+", re.IGNORECASE)
_AI_INTRO = re.compile(
    r"^.*?\b(?:quiero que te llames|me gustaria que te llamaras|me gustaría que te llamaras|te vas a llamar|"
    r"te llamaras|te llamarás|llamate|llámate|tu nombre (?:sera|será|es)|te llamas|te llamare|te llamaré|"
    r"te pondre|te pondré|ponte)\s+", re.IGNORECASE)
_TRAILING = re.compile(r"\b(por favor|gracias|vale|y ya|please|thanks|thank you|si us plau|gràcies|s'il te pla[iî]t|merci|bitte|danke)\b.*$",
                       re.IGNORECASE)


def _titlecase(words: list[str]) -> str:
    small = {"de", "del", "la", "las", "los", "y"}
    out = []
    for i, w in enumerate(words):
        out.append(w if (i and w.lower() in small) else (w[:1].upper() + w[1:]))
    return " ".join(out)


def extract_name(text: str, who: str = "piloto") -> tuple[str, bool]:
    """Saca el nombre de una respuesta hablada. Devuelve (nombre, entendido)."""
    raw = (text or "").strip()
    if not raw:
        return "", False
    pattern = _PILOT_INTRO if who == "piloto" else _AI_INTRO
    m = pattern.match(raw)
    if not m:  # v1.3: «my name is…», «je m'appelle…», «ich heiße…», «em dic…»
        from .i18n import lang
        from .lang_data import AI_INTRO, PILOT_INTRO
        extra = (PILOT_INTRO if who == "piloto" else AI_INTRO).get(lang())
        if extra:
            m = re.match(rf"^.*?\b(?:{extra})\s+", raw, re.IGNORECASE)
    body = raw[m.end():] if m else raw
    body = _TRAILING.sub("", body)
    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ'-]+", body)
    if not words:
        return "", False
    if not m and len(words) > 3:  # una frase larga sin «me llamo…»: no sé cuál es el nombre
        return _titlecase(words[:3]), False
    words = words[:3]
    if all(simplify(w) in COMMON for w in words):
        return "", False
    return _titlecase(words), True


def check_exercise(heard: str, name: str, names: list[str]) -> dict:
    """Ejercicio de sonido: el piloto dice SOLO el nombre."""
    h = simplify(heard)
    if not h:
        return {"ok": False, "note": "No he oído nada. Acércate al micrófono y repite."}
    if any(same_name(h, n) for n in names):
        return {"ok": True, "note": "Perfecto, te he entendido a la primera."}
    words = h.split()
    rest = strip_wake(heard, names)
    if rest is not None and len(words) <= 4:
        return {"ok": True, "note": "Entendido."}
    if good_variant(h, name):
        return {"ok": True, "learn": h, "note": f"Lo he oído como «{h}». Apuntado: a partir de ahora también me sirve."}
    return {"ok": False, "note": "He oído otra cosa. Di solo mi nombre, despacio y claro."}


# ------------------------------------------------------------ frases del entrenamiento
# Se eligen al azar al empezar la configuración: una con muchas vocales seguidas (hiatos y diptongos,
# para que el oído capte bien la vocalización), otra con ñ, ll, y, b, v, g, j, n y m, y otra que mezcla las dos.
PHRASES_VOWELS = [
    "{nombre}, aún oigo el aeropuerto de Área Dieciocho y huelo a aceite.",
    "{nombre}, la euforia aérea aumenta cuando aterrizo la Aurora en Orison.",
    "{nombre}, ahí iba a aparecer una Idris aliada; oí su aviso en Euterpe.",
    "{nombre}, guía a la Aurora hacia el área de aduanas; oía ruidos en el aire.",
    "{nombre}, aquí el piloto: la Aquila aúlla al oeste de Daymar.",
    "{nombre}, ¿oíste? Hay oro e iones en la órbita; aeronave lista para aterrizar.",
    "{nombre}, aún huele a ozono; el cuántico aguanta hasta Hurston.",
]
PHRASES_CONSONANTS = [
    "{nombre}, mañana llevo mi Vanguard y un Gladius bajo la nieve de Yela.",
    "{nombre}, ya llegó mi compañero en la Vulture; viajamos juntos con la Banu Merchantman.",
    "{nombre}, la señal de ayuda llega de un jugador bajo el hielo de Yela; vamos ya en la Gladius.",
    "{nombre}, llevo un año viajando en mi Avenger bajo la lluvia de Magnus y nunca me engaña el radar.",
    "{nombre}, el viejo cañón ya brilla; baja y vigila la montaña de Hurston.",
    "{nombre}, mi pequeña Mustang lleva gemas y joyas bajo la nave; vigila y ayúdame.",
]
PHRASES_MIXED = [
    "{nombre}, aquel jugador iba hacia la montaña; llévame ya en la Cutlass Black.",
    "{nombre}, oye, ayúdame: llevo veinte cajas de oro bajo la niebla y mañana viajo a Pyro.",
    "{nombre}, aún huele a gasolina; ya llegué con la Avenger al hangar de Lorville.",
    "{nombre}, oía a mi compañero gritar: baja ya, el Vanduul nos aleja de la luna.",
    "{nombre}, la Reclaimer aguanta; mañana llevamos el botín y la joya al aeropuerto de New Babbage.",
]
OLD_DEFAULT_PHRASES = [  # las fijas de la 1.0: si siguen guardadas, se usan las nuevas al azar
    "{nombre}, mi nombre es {piloto}.",
    "{nombre}, mi nave favorita es la Anvil Paladin.",
    "{nombre}, pertenezco a la organización Espada del Alba de Star Citizen.",
]


def random_phrases(rng=None, lang: str | None = None) -> list[str]:
    import random

    from .i18n import lang as current
    from .lang_data import TRAINING
    r = rng or random.SystemRandom()
    sets = TRAINING.get(lang or current())
    if sets:  # v1.3: frases en el idioma de NOVA AI
        return [r.choice(sets[0]), r.choice(sets[1]), r.choice(sets[2])]
    return [r.choice(PHRASES_VOWELS), r.choice(PHRASES_CONSONANTS), r.choice(PHRASES_MIXED)]


def check_phrase(heard: str, expected: str, name: str, names: list[str]) -> dict:
    """Frase de entrenamiento: «{nombre}, mi nave favorita es…»."""
    h = simplify(heard)
    if not h:
        return {"ok": False, "note": "No he oído nada. Pulsa y lee la frase en voz alta."}
    body = simplify(strip_wake(expected, [simplify(name)]) or expected)
    rest = strip_wake(heard, names)
    if rest is not None:
        score = _partial(simplify(rest), body) if body else 100
        if score >= 60:
            return {"ok": True, "score": round(score), "note": "Nombre y frase reconocidos."}
        return {"ok": True, "score": round(score), "note": "He reconocido mi nombre; el resto lo he oído algo distinto."}
    if contains_name(heard, names):
        return {"ok": True, "score": 50, "note": "He reconocido mi nombre, aunque no al principio de la frase."}
    # ¿Ha dicho la frase pero Whisper escribió el nombre de otra forma? Lo que va delante es el nombre.
    hw = h.split()
    bw = body.split()
    if len(bw) >= 2:
        anchor = " ".join(bw[:2])
        joined = " ".join(hw)
        pos = joined.find(anchor)
        if pos > 0:
            before = joined[:pos].strip().split()[-3:]
            cand = " ".join(before)
            if good_variant(cand, name):
                return {"ok": True, "learn": cand, "score": 70,
                        "note": f"Lo he oído como «{cand}». Apuntado para reconocerte mejor."}
    if _partial(h, body) >= 70:
        return {"ok": False, "note": "He entendido la frase pero no mi nombre. Repite y dilo claro al principio."}
    return {"ok": False, "note": "No te he entendido. Repite la frase con calma."}


def calibrate(samples: list[dict]) -> float | None:
    """Sensibilidad del micrófono según el ruido de fondo y tu volumen de voz medidos.
    Devuelve None si no hay medidas suficientes."""
    voice = sorted(s["voz"] for s in samples if s.get("voz"))
    noise = sorted(s["ruido"] for s in samples if s.get("ruido"))
    if len(voice) < 2:
        return None
    v = voice[len(voice) // 2]
    n = noise[len(noise) // 2] if noise else 0.003
    target = 0.4 * v  # el umbral ha de quedar holgadamente por debajo de tu voz
    need_min = (0.012 - target) / 0.009  # EnergyVAD.min_level = 0.012 - 0.009·s
    need_factor = (3.5 - target / max(n, 1e-4)) / 2.3  # EnergyVAD.factor = 3.5 - 2.3·s
    s = max(need_min, need_factor, 0.2) + 0.1
    return round(min(max(s, 0.0), 1.0), 2)

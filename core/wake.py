"""El nombre de la IA: reconocerlo en lo que oye el micrófono, se llame como se llame.

Whisper no conoce los nombres inventados y los escribe como le suenan ("Nova" -> "Noba",
"Jarvis" -> "Yarvis"). Por eso se combinan tres cosas:
  1. comparación fonética en español (b/v, c/k/qu, z/s, ll/y, h muda…);
  2. parecido de letras para nombres de 4 o más letras;
  3. las «variantes» aprendidas en el entrenamiento: cómo ha escrito Whisper el nombre
     cuando TÚ lo dijiste.
"""
from __future__ import annotations

import re

from .commands import _similarity, simplify

# Palabras que nunca se aprenden como variante del nombre (darían falsos avisos).
COMMON = {
    "a", "al", "de", "del", "el", "la", "las", "los", "lo", "un", "una", "y", "o", "que", "en", "es", "se", "si",
    "no", "mi", "me", "tu", "te", "su", "yo", "con", "por", "para", "pero", "como", "ya", "ah", "eh", "oh",
    "hola", "vale", "bueno", "pues", "venga", "oye", "hey", "ok", "okay", "gracias", "nada", "esto", "eso",
    "nave", "nombre", "silencio", "basta", "stop", "calla",
}
MAX_VARIANTS = 12


def phonetic(text: str) -> str:
    """Clave fonética aproximada del español: 'Noba' y 'Nova' dan lo mismo."""
    t = simplify(text).replace(" ", "")
    for a, b in (("ch", "X"), ("sh", "X"), ("ll", "y"), ("qu", "k"), ("ñ", "ny"), ("ph", "f"),
                 ("ce", "se"), ("ci", "si"), ("ge", "je"), ("gi", "ji"), ("gue", "ge"), ("gui", "gi")):
        t = t.replace(a, b)
    t = t.replace("h", "")
    t = t.translate(str.maketrans({"v": "b", "w": "b", "z": "s", "c": "k", "q": "k", "x": "s", "j": "x"}))
    t = re.sub(r"y$", "i", t)
    t = re.sub(r"(.)\1+", r"\1", t)  # letras dobles
    return t


def same_name(heard: str, name: str) -> bool:
    """¿'heard' (texto ya simplificado) es el nombre 'name' (simplificado)?"""
    if not heard or not name:
        return False
    if heard == name:
        return True
    ph, pn = phonetic(heard), phonetic(name)
    if len(pn) >= 3 and ph == pn:
        return True
    if len(name) >= 4 and _similarity(heard, name) >= 75:
        return True
    return len(pn) >= 5 and _similarity(ph, pn) >= 82


def wake_names(settings) -> list[str]:
    """Todas las formas válidas de llamar a la IA, de la más larga a la más corta."""
    names = [settings.get("nombre_asistente") or ""]
    names += list(settings.get("nombre_variantes") or [])
    names += list(settings.get("palabras_clave") or [])
    out = {simplify(n) for n in names}
    return sorted((n for n in out if n), key=len, reverse=True)


def strip_wake(text: str, names: list[str]) -> str | None:
    """Si la frase empieza (o casi: «eh, oye Nova…») por el nombre, devuelve el resto; si no, None."""
    words = text.split()
    simple = [simplify(w) for w in words]
    for name in names:
        nwords = name.split()
        for start in range(0, 3):
            chunk = " ".join(s for s in simple[start:start + len(nwords)] if s)
            if not chunk:
                continue
            if same_name(chunk, name):
                return " ".join(words[start + len(nwords):]).lstrip(",.:;!¡¿? ")
    return None


def contains_name(text: str, names: list[str]) -> bool:
    """¿Aparece el nombre en cualquier parte de la frase?"""
    simple = [w for w in simplify(text).split() if w]
    for name in names:
        n = len(name.split())
        for i in range(0, max(1, len(simple) - n + 1)):
            if same_name(" ".join(simple[i:i + n]), name):
                return True
    return False


def good_variant(candidate: str, name: str) -> bool:
    """¿Merece la pena aprender 'candidate' como otra forma de oír el nombre?"""
    c = simplify(candidate)
    if not c or c == simplify(name):
        return False
    words = c.split()
    if len(words) > 3 or len(c) < 3 or all(w in COMMON for w in words):
        return False
    return not any(ch.isdigit() for ch in c)


def add_variant(settings, candidate: str) -> bool:
    """Guarda una variante nueva del nombre. Devuelve True si era nueva."""
    name = settings.get("nombre_asistente") or ""
    c = simplify(candidate)
    if not good_variant(c, name):
        return False
    current = list(settings.get("nombre_variantes") or [])
    if c in current:
        return False
    settings.set("nombre_variantes", (current + [c])[-MAX_VARIANTS:])
    return True


def rename(settings, new_name: str) -> str:
    """Cambia el nombre de la IA y olvida lo aprendido del nombre anterior."""
    new_name = " ".join((new_name or "").split())[:40] or "Nova"
    old = simplify(settings.get("nombre_asistente") or "")
    if simplify(new_name) != old:
        old_forms = {old, *(settings.get("nombre_variantes") or [])}
        extras = [w for w in (settings.get("palabras_clave") or [])
                  if not any(f and f in simplify(w) for f in old_forms)]
        settings.set("palabras_clave", extras, save=False)
        settings.set("nombre_variantes", [], save=False)
    settings.set("nombre_asistente", new_name)
    return new_name


def name_warning(name: str) -> str:
    """Consejo si el nombre elegido va a dar problemas al reconocerlo."""
    s = simplify(name)
    if not s:
        return "Escribe un nombre."
    if len(s.replace(" ", "")) < 3:
        return "Es muy corto: se confundirá con otras palabras. Mejor un nombre de 2 o 3 sílabas."
    if all(w in COMMON for w in s.split()):
        return "Es una palabra muy común: se activaría sin querer. Elige un nombre propio."
    if len(s.split()) > 2:
        return "Mejor un nombre de una o dos palabras: es más fácil de decir y de reconocer."
    return ""

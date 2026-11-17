"""v2.0: estilos de voz y pronunciación en inglés de los nombres del juego.

Estilos: combinaciones ya afinadas de voz neuronal de Edge + velocidad + tono + efecto de cabina, con el aire
de los asistentes de a bordo del cine. Son voces sintéticas genéricas de Microsoft: no imitan a ningún actor
ni personaje real.

Pronunciación: Edge lee «Crusader» o «Hurston» con las reglas de tu idioma («crusáder», «urston»). Como Edge no
admite marcas SSML de idioma, se cambia el nombre por cómo se escribiría en tu idioma para sonar en inglés
(«Cruséider», «Jérston»). El jugador puede añadir o corregir los suyos.
"""
from __future__ import annotations

import re

# ------------------------------------------------------------------ estilos
# id: (nombre, descripción, voces por idioma (la primera que exista), velocidad %, tono Hz, efecto de voz)
STYLES: dict[str, tuple[str, str, dict[str, list[str]], int, int, str]] = {
    "clasica": ("Clásica de NOVA", "La voz de siempre: clara y cercana.", {
        "es": ["es-ES-XimenaNeural"], "en": ["en-GB-SoniaNeural"], "ca": ["ca-ES-JoanaNeural"],
        "fr": ["fr-FR-DeniseNeural"], "de": ["de-DE-KatjaNeural"]}, 5, 0, "cabina"),
    "mayordomo": ("Mayordomo de a bordo", "Masculina, serena y formal, un punto más grave y pausada.", {
        "es": ["es-ES-AlvaroNeural"], "en": ["en-GB-RyanNeural", "en-GB-ThomasNeural"], "ca": ["ca-ES-EnricNeural"],
        "fr": ["fr-FR-HenriNeural"], "de": ["de-DE-ConradNeural"]}, -5, -5, "ninguno"),
    "ordenador": ("Ordenador de la nave", "Femenina y neutra, rápida, con sonido de altavoz de cabina.", {
        "es": ["es-ES-ElviraNeural"], "en": ["en-GB-LibbyNeural", "en-GB-SoniaNeural"], "ca": ["ca-ES-AlbaNeural", "ca-ES-JoanaNeural"],
        "fr": ["fr-FR-EloiseNeural", "fr-FR-DeniseNeural"], "de": ["de-DE-AmalaNeural", "de-DE-KatjaNeural"]}, 10, 0, "cabina"),
    "copiloto": ("Copiloto cercano", "Masculina y cálida, como un compañero de vuelo.", {
        "es": ["es-ES-TristanMultilingualNeural", "es-MX-JorgeNeural"], "en": ["en-US-AndrewMultilingualNeural", "en-US-AndrewNeural"],
        "ca": ["ca-ES-EnricNeural"], "fr": ["fr-FR-RemyMultilingualNeural", "fr-FR-HenriNeural"],
        "de": ["de-DE-FlorianMultilingualNeural", "de-DE-ConradNeural"]}, 5, 0, "casco"),
    "tactica": ("IA táctica", "Grave y seca, por radio: para combate.", {
        "es": ["es-ES-AlvaroNeural"], "en": ["en-US-GuyNeural", "en-GB-RyanNeural"], "ca": ["ca-ES-EnricNeural"],
        "fr": ["fr-FR-HenriNeural"], "de": ["de-DE-ConradNeural"]}, 0, -10, "radio"),
    "serena": ("Asistente serena", "Femenina, suave y expresiva.", {
        "es": ["es-ES-XimenaMultilingualNeural", "es-ES-IsidoraMultilingualNeural", "es-ES-XimenaNeural"],
        "en": ["en-US-EmmaMultilingualNeural", "en-US-AvaNeural"], "ca": ["ca-ES-JoanaNeural"],
        "fr": ["fr-FR-VivienneMultilingualNeural", "fr-FR-DeniseNeural"],
        "de": ["de-DE-SeraphinaMultilingualNeural", "de-DE-KatjaNeural"]}, -5, 0, "ninguno"),
    "internacional": ("Voz internacional", "Una voz inglesa que habla tu idioma con acento: los nombres del juego le salen en inglés.", {
        "es": ["en-US-BrianMultilingualNeural", "en-US-AndrewMultilingualNeural"],
        "en": ["en-US-BrianMultilingualNeural", "en-US-BrianNeural"],
        "ca": ["en-US-BrianMultilingualNeural"], "fr": ["en-US-BrianMultilingualNeural"],
        "de": ["en-US-BrianMultilingualNeural"]}, 0, 0, "ninguno"),
}


def resolve_voice(style: str, lang: str, available: list[str] | None = None) -> str:
    """La primera voz del estilo que existe en la lista de Edge (sin lista: la primera)."""
    voices = STYLES[style][2].get(lang) or STYLES[style][2]["es"]
    if available:
        for v in voices:
            if v in available:
                return v
    return voices[0]


def style_list(lang: str, available: list[str] | None = None) -> list[dict]:
    from .i18n import tr

    return [{"id": k, "nombre": tr(v[0]), "desc": tr(v[1]), "voz": resolve_voice(k, lang, available),
             "velocidad": v[3], "tono": v[4], "efecto": v[5]} for k, v in STYLES.items()]


def apply_style(settings, style: str, lang: str, available: list[str] | None = None) -> dict:
    if style not in STYLES:
        raise ValueError(f"Estilo de voz desconocido: {style}")
    _n, _d, _v, rate, pitch, fx = STYLES[style]
    voice = resolve_voice(style, lang, available)
    settings.set("tts_motor", "edge")
    settings.set("tts_voz_edge", voice)
    settings.set("tts_velocidad", rate)
    settings.set("tts_tono", pitch)
    settings.set("tts_efecto", fx)
    settings.set("tts_efecto_radio", fx != "ninguno")
    settings.set("tts_estilo", style)
    return {"voz": voice, "velocidad": rate, "tono": pitch, "efecto": fx}


# ------------------------------------------------------------------ pronunciación
# Nombre del juego -> cómo escribirlo para que suene en inglés. Solo nombres que se leen claramente mal.
_ES = {
    "Hurston": "Jérston", "Crusader": "Cruséider", "ArcCorp": "Arc Corp", "microTech": "máicro tek", "Stanton": "Stánton",
    "Pyro": "Páiro", "Nyx": "Nix", "Lorville": "Lórvil", "New Babbage": "Niú Bábich", "Orison": "Órison",
    "Port Tressler": "Port Trésler", "Everus Harbor": "Éverus Járbor", "Seraphim Station": "Sérafim Stéishon",
    "Baijini Point": "Baiyíni Point", "Grim HEX": "Grim Jex", "Checkmate": "Chékmeit", "Ruin Station": "Rúin Stéishon",
    "Daymar": "Déimar", "Cellin": "Sélin", "Aberdeen": "Áberdin", "Arial": "Érial", "Calliope": "Calaiopi",
    "Euterpe": "Iutérpi", "Bloom": "Blum",
    "Drake": "Dréik", "Anvil": "Ánvil", "Aegis": "Íyis", "Origin": "Óriyin", "Crusader Industries": "Cruséider Índustris",
    "Hornet": "Jórnet", "Cutlass": "Cátlas", "Freelancer": "Frilánser", "Constellation": "Consteléishon",
    "Caterpillar": "Cáterpilar", "Prospector": "Prospéctor", "Vulture": "Vólcher", "Avenger": "Avénller",
    "Sabre": "Séiber", "Hammerhead": "Jámerjed", "Retaliator": "Ritáliéitor",
    "Starfarer": "Stárferer", "Mercury Star Runner": "Mércuri Star Ráner", "Corsair": "Córser", "Valkyrie": "Válkiri",
    "Arrow": "Árrou", "Hawk": "Jok", "Buccaneer": "Bucanír", "Herald": "Jérald", "Pisces": "Páisis",
    "Starlancer": "Starlánser",
    "Behring": "Béring", "Klaus & Werner": "Klaus and Uérner", "Gallenson": "Gálenson", "Kastak Arms": "Kástak Arms",
    "Hurston Dynamics": "Jérston Daináimics", "Shubin": "Shúbin", "Rough and Ready": "Raf and Rédi",
}
# El catalán no tiene «j» aspirada: la h inglesa se deja muda; el resto se lee igual que en castellano.
_CA = {k: v.replace("J", "").replace("j", "") if ("J" in v or "j" in v) and k not in ("Grim HEX",) else v for k, v in _ES.items()}
_CA.update({"Grim HEX": "Grim Ex", "Baijini Point": "Baiyíni Point", "Hurston": "Hérston", "Hurston Dynamics": "Hérston Daináimics"})
_FR = {
    "Hurston": "Heurstonne", "Crusader": "Crouzéïdeur", "ArcCorp": "Arc Corp", "microTech": "maïcro tèk", "Stanton": "Stanntonne",
    "Pyro": "Païro", "Lorville": "Lorvil", "New Babbage": "Niou Babidje", "Orison": "Orissonne", "Port Tressler": "Port Tresseleur",
    "Everus Harbor": "Évereus Harbeur", "Grim HEX": "Grim Hèx", "Daymar": "Déïmar", "Drake": "Dréïk", "Anvil": "Anvil",
    "Aegis": "Idjis", "Hornet": "Hornète", "Cutlass": "Keutlass", "Freelancer": "Frilanceur", "Constellation": "Consteléïchone",
    "Caterpillar": "Kateurpilar", "Vulture": "Veultcheur", "Avenger": "Avéndjeur", "Starfarer": "Starfèreur",
}
_DE = {
    "Crusader": "Kruhsäider", "microTech": "maikro Tek", "Pyro": "Pairo", "Lorville": "Lorwill", "New Babbage": "Nju Bäbbitsch",
    "Orison": "Orissen", "Everus Harbor": "Ewerus Harbor", "Grim HEX": "Grimm Hex", "Daymar": "Däimar", "Drake": "Dräik",
    "Aegis": "Idschis", "Origin": "Oridschin", "Freelancer": "Frielänser", "Constellation": "Konstelläischen",
    "Caterpillar": "Kätterpiller", "Vulture": "Waltscher", "Avenger": "Äwendscher", "Starfarer": "Starfärer",
    "Cutlass": "Kattläss", "Hammerhead": "Hämmerhed",
}
RESPELL = {"es": _ES, "ca": _CA, "fr": _FR, "de": _DE, "en": {}}


def parse_custom(text: str) -> dict[str, str]:
    """«Nombre = cómo decirlo», uno por línea (lo que escribe el jugador en Nova › Voz)."""
    out = {}
    for line in (text or "").splitlines():
        if "=" in line:
            a, b = (x.strip() for x in line.split("=", 1))
            if a and b:
                out[a] = b
    return out


def pronounce(text: str, lang: str, english_names: bool = True, custom: str = "") -> str:
    """Cambia los nombres del juego por su pronunciación en inglés escrita en tu idioma."""
    table = dict(RESPELL.get(lang, {})) if english_names else {}
    table.update(parse_custom(custom))
    if not table or not text:
        return text
    keys = sorted(table, key=len, reverse=True)  # «Hurston Dynamics» antes que «Hurston»
    rx = re.compile(r"(?<![\w-])(" + "|".join(re.escape(k) for k in keys) + r")(?![\w-])", re.I)
    low = {k.lower(): v for k, v in table.items()}
    return rx.sub(lambda m: low.get(m.group(1).lower(), m.group(1)), text)

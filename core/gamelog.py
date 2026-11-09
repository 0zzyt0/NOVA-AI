"""Lector del Game.log de Star Citizen (solo lectura; no toca el juego).

Desde las versiones 4.5 el juego escribe en el log las notificaciones del HUD
(contratos, grupo, dinero, amigos, hangar, zonas...). Con eso Nova sabe dónde
estás y qué te está pasando, y lo comenta en voz. Los kills y el saldo ya no
aparecen en el log, ni las frases habladas de la torre de control (ATC).

Patrones de notificaciones verificados por la comunidad en 4.x (gracias a
sc-log-tracker de DefaultHahn, licencia MIT, y al lector de Wingman AI).
"""
from __future__ import annotations

import calendar
import collections
import logging
import os
import random
import re
import string
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .localization import TEXT, find_global_ini, ship_name

log = logging.getLogger("nova.gamelog")

RECORD_START = re.compile(r"^<\d{4}-\d\d-\d\dT")
NOTIFICATION = re.compile(r'Added notification\s+"(.*?)(?:"\s*\[\d+\]|"\s*MissionId\b|"\s*$|$)', re.S)
LOCINV = re.compile(r"requested inventory for Location\[([^\]]+)\]")
LOCATION = re.compile(r"Location\[([^\]]+)\]")
SHARD = re.compile(r"shard\[([^\]]+)\]")
QT_DEST = re.compile(r"selected point (\S+) as their destination")
TIMESTAMP = re.compile(r"^<(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d+))?Z?>")
CHARACTER = re.compile(r"\bname\s+(\S+)\s+-\s+state\s+STATE_CURRENT")
VEHICLE_ID = re.compile(r"\b([A-Z]{3,5}_[A-Za-z0-9_]+?)_(\d{9,})\b")
CONTROL_TOKEN = re.compile(r"(releasing|requesting|granted|granting|acquir\w*|taking)\s+control token for '([^']+)'", re.I)
SPAWN_INFO = re.compile(r"VehicleEntityId:\s*\[(\d+)\],\s*LandingArea:\s*(.+?)\s*\[Team_", re.S)
# Formatos de la comunidad (sc-assistant, MIT); en 4.10 el cliente casi nunca los escribe.
ACTOR_KILL = re.compile(
    r"CActor::Kill:\s*'(?P<victim>[^']+)'\s+\[\d+\]\s+in\s+zone\s+'[^']*'\s+killed\s+by\s+'(?P<killer>[^']+)'"
    r"\s+\[\d+\]\s+using\s+'(?P<weapon>[^']*)'(?:.*?with\s+damage\s+type\s+'(?P<damage>[^']*)')?", re.I | re.S)
VEHICLE_DESTROY = re.compile(
    r"Vehicle\s+'(?P<vehicle>[^']+)'\s+\[\d+\]\s+in\s+zone\s+'[^']*'(?:\s+\[pos[^\]]*\])?\s+driven\s+by\s+'(?P<driver>[^']*)'"
    r"\s+\[\d+\]\s+advanced\s+from\s+destroy\s+level\s+\d+\s+to\s+(?P<to>\d+)(?:\s+caused\s+by\s+'(?P<attacker>[^']*)')?", re.I | re.S)
# Combate, reapariciones, carga y camilla médica: formatos tomados de all-slain (DimmaDont, licencia MIT),
# comprobados con Star Citizen 4.x. Desde 4.0.2 el cliente solo escribe los eventos en los que participas tú.
INCAP = re.compile(r"Logged an incap\.! nickname: (?P<who>[\w-]+), causes: \[(?P<causes>.*?)\]")
INCAP_CAUSE = re.compile(r"([\w]+) \(([\d.]+) damage\)")
CORPSE_HOSPITAL = re.compile(r"Player '(?P<who>[\w-]+)' <(?:remote|local) client>: DoesLocationContainHospital: "
                             r"Searching landing zone location \"(?P<loc>[^\"]*)\"")
MED_BED = re.compile(r"<MED BED HEAL> Actor: (?P<who>[\w-]+).*?Perform surgery event (?P<ok>\w+), med bed name: (?P<bed>[\w-]+), "
                     r"vehicle name: (?P<veh>[@\w-]+), head: (?P<head>\w+) torso: (?P<torso>\w+) leftArm: (?P<larm>\w+) "
                     r"rightArm: (?P<rarm>\w+) leftLeg: (?P<lleg>\w+) rightLeg: (?P<rleg>\w+)", re.S)
LOADED = re.compile(r"Loading screen for (?P<what>\w+) : \w+ closed after (?P<secs>[\d.]+) seconds")
CET_SLOW = re.compile(r"<C?ContextEstablisherTask(?P<st>LongWait|Failed)> .*?taskname=\"(?P<task>[\w.]+)\".*?runningTime=(?P<secs>[\d.]+)")
ACTOR_STALL = re.compile(r"<Actor stall> Actor stall detected, Player: (?P<who>[\w-]+), Type: \w+, Length: (?P<secs>\d+(?:\.\d+)?)")
DAMAGE_ES = {
    "bullet": "disparos", "explosion": "una explosión", "crash": "un choque", "collision": "una colisión",
    "vehicledestruction": "la destrucción de la nave", "suicide": "suicidio", "bleedout": "desangrado",
    "suffocation": "asfixia", "suffocationdamage": "asfixia", "depressurization": "despresurización",
    "depressurizationdamage": "despresurización", "bleed": "hemorragia", "fall": "una caída", "falldamage": "una caída",
    "melee": "cuerpo a cuerpo", "fire": "fuego", "electrical": "una descarga eléctrica", "hazard": "un peligro del entorno",
    "drowning": "ahogamiento", "temperature": "la temperatura", "radiation": "radiación", "physical": "un golpe",
    "combat": "combate", "debug": "depuración", "selfdestruct": "autodestrucción", "gameRules".lower(): "las reglas del juego",
    "overdose": "sobredosis", "distortion": "distorsión", "energy": "energía",
}
LOAD_WHAT = {"pu": "el universo persistente", "frontend_main": "el menú principal", "pyro": "Pyro", "stanton": "Stanton"}
NPC_PREFIX = ("pu_", "npc_", "ai_", "aimodule", "kopion", "marok", "quasigrazer", "valakkar", "vlk_", "irradiated",
              "vanduul", "creature", "animal", "hdmn_", "nt_", "ninetails", "pir_", "civ_")


def damage_es(dmg: str) -> str:
    key = re.sub(r"[^a-z]", "", (dmg or "").lower())
    return DAMAGE_ES.get(key, split_camel(dmg or "").lower())


def is_npc(name: str) -> bool:
    n = (name or "").lower()
    return n.startswith(NPC_PREFIX) or bool(re.search(r"_\d{9,}$", n)) or n in ("unknown", "")


def actor_name(name: str) -> str:
    """'PU_Human-NineTails-Grunt-Male-Grunt_10_123456789012' -> 'NPC (NineTails, Grunt)'; un jugador queda igual."""
    if not is_npc(name):
        return name
    n = re.sub(r"_\d{6,}$", "", name or "")
    if not n or n.lower() == "unknown":
        return "alguien desconocido"
    parts = [p for p in re.split(r"[-_]", n) if p and not p.isdigit()]
    drop = {"pu", "npc", "ai", "human", "male", "female", "archetypes", "pilots", "civilians", "light", "medium", "heavy"}
    words = [p for p in parts if p.lower() not in drop]
    first = (parts[0].lower() if parts else "")
    if first in ("kopion", "marok", "quasigrazer", "valakkar"):
        return parts[0].capitalize()
    tag = ", ".join(dict.fromkeys(words[:2]))
    return f"NPC ({tag})" if tag else "NPC"


NOTIF_END = re.compile(r'"\s*\[\d+\]')
TIMESTAMP_PREFIX = re.compile(r"^<[^>]+>\s?")
QT_ARRIVE = ("Quantum Drive Arrived - Arrived at Final Destination", "Quantum Drive has arrived at final destination")

# ------------------------------------------------------------ nombres de sitios
BODIES = {
    "stanton1": "Hurston", "stanton1a": "Arial", "stanton1b": "Aberdeen", "stanton1c": "Magda", "stanton1d": "Ita",
    "stanton2": "Crusader", "stanton2a": "Cellin", "stanton2b": "Daymar", "stanton2c": "Yela",
    "stanton3": "ArcCorp", "stanton3a": "Lyria", "stanton3b": "Wala",
    "stanton4": "microTech", "stanton4a": "Calliope", "stanton4b": "Clio", "stanton4c": "Euterpe",
    "pyro1": "Pyro I", "pyro2": "Monox", "pyro3": "Bloom", "pyro4": "Pyro IV", "pyro5": "Pyro V",
    "pyro5a": "Ignis", "pyro5b": "Vatra", "pyro5c": "Adir", "pyro5d": "Fairo", "pyro5e": "Fuego",
    "pyro5f": "Vuur", "pyro6": "Terminus",
}
STATIONS = {"hur_leo": "Everus Harbor", "cru_leo": "Seraphim Station", "arc_leo": "Baijini Point",
            "mic_leo": "Port Tressler", "p2_l4": "Checkmate", "p3_leo": "Orbituary", "p3_l1": "Starlight Service Station"}
PLANETS = {"hur": "Hurston", "cru": "Crusader", "arc": "ArcCorp", "mic": "microTech"}
CITIES = {"grimhex": "Grim HEX", "newbabbage": "New Babbage", "area18": "Área 18", "lorville": "Lorville",
          "orison": "Orison", "levski": "Levski", "kaboos": "Kaboos"}
SYSTEMS = {"stanton": "Stanton", "pyro": "Pyro", "nyx": "Nyx", "castra": "Castra", "magnus": "Magnus", "terra": "Terra"}


def split_camel(text: str) -> str:
    text = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", text)
    return re.sub(r"\s+", " ", text.replace("_", " ")).strip()


JUMP = re.compile(r"(?i)^(?:loc_)?rs_ext_([a-z]+)-([a-z]+)_jp\d*$")
JUMP_STATION = re.compile(r"(?i)^rr_jp_([a-z]+?)(stanton|pyro|nyx|castra|magnus|terra)$")
SYS_SHORT = {"stan": "Stanton", "pyro": "Pyro", "nyx": "Nyx", "cast": "Castra", "magn": "Magnus", "terr": "Terra"}


def pretty_loc(raw: str, text=None) -> str:
    """Códigos internos -> nombres: RR_CRU_LEO -> Seraphim Station, Stanton1_Lorville -> Lorville (Hurston).
    Con el global.ini del juego se usan además los nombres oficiales en tu idioma."""
    if not raw:
        return ""
    t = re.sub(r"_?\{[0-9A-Fa-f-]{36}\}", "", raw.strip()).replace(".socpak", "")
    t = re.sub(r"(_\d{6,})+$", "", t)
    low = t.lower()
    m = JUMP.match(t)
    if m:
        a, b = (SYS_SHORT.get(x[:4], x.capitalize()) for x in m.groups())
        return f"punto de salto {a} → {b}"
    m = JUMP_STATION.match(t)
    if m:
        a, b = (SYS_SHORT.get(x[:4], x.capitalize()) for x in m.groups())
        return f"estación del salto {a}-{b} (lado {a})"
    if text is not None:
        local = text.local(t) or text.local(re.sub(r"^(?:LOC_|OOC_)", "", t))
        if local and len(local) <= 60 and "%" not in local:
            return local
    if low in BODIES:
        return BODIES[low]
    m = re.fullmatch(r"rr_(hur|cru|arc|mic|p\d)_(leo|l\d)", low)
    if m:
        name = STATIONS.get(f"{m.group(1)}_{m.group(2)}")
        if name:
            return name
        body = PLANETS.get(m.group(1), m.group(1).upper())
        return f"estación de descanso de {body}" if m.group(2) == "leo" else f"{m.group(1).upper()}-{m.group(2).upper()}"
    m = re.fullmatch(r"rr_jp_\w+?(stanton|pyro|nyx|castra|magnus|terra)", low)
    if m:
        return f"puerta de salto a {SYSTEMS[m.group(1)]}"
    for key, name in CITIES.items():
        if key in low.replace("_", ""):
            body = next((b for code, b in BODIES.items() if code in low), "")
            return f"{name} ({body})" if body and body not in name else name
    t = re.sub(r"^(OOC_|ObjectContainer_)", "", t)
    m = re.fullmatch(r"(?i)(stanton|pyro|nyx)_(\d[a-f]?)_(.+)", t)
    if m:
        return split_camel(m.group(3))
    m = re.search(r"(?i)(stanton\d[a-f]?|pyro\d[a-f]?)", t)
    if m and m.group(1).lower() in BODIES:
        body = BODIES[m.group(1).lower()]
        rest = (t[:m.start()] + t[m.end():]).strip("_ ")
        rest = re.sub(r"(?i)^(outpost_[a-z]{3}_|asd_monorail_)", "", rest)
        rest = re.sub(r"_\d+$", "", rest)
        return f"{split_camel(rest)} ({body})" if rest else body
    return split_camel(re.sub(r"[-_]\d{1,3}$", "", t))


def pretty_dest(raw: str, text=None) -> str:
    low = (raw or "").lower()
    if low.startswith("partymembermarker"):
        return "un miembro del grupo"
    if low.startswith(("navpoint_dynamic", "mission_qt")) or re.search(r"final|_encounter|_dungeon|_cluster_", low):
        return ""
    m = re.fullmatch(r"(?i)loc_rr_s([1-4])_l(\d)", raw or "")
    if m:
        return f"{['HUR', 'CRU', 'ARC', 'MIC'][int(m.group(1)) - 1]}-L{m.group(2)}"
    return pretty_loc(raw, text)


def clean_notification(text: str) -> str:
    t = re.sub(r"</?EM\d>", "", text or "").replace("\xa0", " ")
    t = re.sub(r"\[[^\]]*\bRep\]\*?|\[BP\]\*?", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t.rstrip(": ").strip()


def money(n: str) -> str:
    try:
        v = int(re.sub(r"[.,]", "", n))
        return f"{v:,}".replace(",", ".")
    except ValueError:
        return n


# ---------------------------------------------------------- tipos de evento
# (tipo, categoría, regex sobre el texto de la notificación, campos)
# Categorías (se activan/desactivan en la ventana): ubicacion, grupo, dinero, amistad,
# atc, contratos, salud, ley, avisos
RULES: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("contrato_aceptado", "contratos", r"^Contract Accepted:\s*(.*)", ("x",)),
    ("contrato_completado", "contratos", r"^Contract Complete:\s*(.*)", ("x",)),
    ("contrato_fallido", "contratos", r"^Contract Failed:\s*(.*)", ("x",)),
    ("contrato_retirado", "", r"^Contract Withdrawn:\s*(.*)", ("x",)),
    ("contrato_disponible", "", r"^Contract Available:\s*(.*)", ("x",)),
    ("contrato_compartido", "grupo", r"^Contract Shared:\s*(.*)", ("x",)),
    ("objetivo_nuevo", "", r"^New Objective:\s*(.*)", ("x",)),
    ("objetivo_completado", "", r"^Objective Complete:\s*(.*)", ("x",)),
    ("recompensa", "contratos", r"^(?:You've earned:|Awarded)\s*(.*)", ("x",)),
    # --- grupo (party)
    ("grupo_invitacion", "grupo", r"^(\S+) Party Invite Received", ("nombre",)),
    ("grupo_entra", "grupo", r"^(?:New Member Joined )?(\S+) has joined the party", ("nombre",)),
    ("grupo_sale", "grupo", r"^(?:Member Left )?(\S+) has left the party", ("nombre",)),
    ("grupo_conectado", "grupo", r"^Party (\S+) connected\.?$", ("nombre",)),
    ("grupo_desconectado", "grupo", r"^Party (\S+) disconnected\.?$", ("nombre",)),
    ("grupo_te_unes", "grupo", r"^You have joined party", ()),
    ("grupo_creado", "grupo", r"^You have created party", ()),
    ("grupo_dejas", "grupo", r"^You have left the party", ()),
    ("grupo_expulsado", "grupo", r"^You have been kicked from the party", ()),
    ("grupo_disuelto", "grupo", r"^Party Disbanded", ()),
    ("grupo_lider", "grupo", r"^New Party Leader (\S+)", ("nombre",)),
    ("grupo_rechaza", "grupo", r"^Invitation Declined (\S+) has declined", ("nombre",)),
    ("grupo_salto_hacia_ti", "grupo", r"^(\S+) has started to QT to your current location", ("nombre",)),
    ("grupo_lanzamiento", "grupo", r"^(?:Initiated by (\S+) Party Launching|Party Launch Initiated by party leader (\S+?)\.?$)", ("nombre", "nombre2")),
    ("grupo_calibracion", "grupo", r"^Quantum Travel Calibration Complete By (\S+)", ("nombre",)),
    # --- dinero
    ("dinero_recibido", "dinero", r"^(\S+) has sent you:?\s*([\d.,]+)\s*a?UEC", ("nombre", "cantidad")),
    ("dinero_ofrecido", "dinero", r"^(\S+) wants to send you ([\d.,]+)\s*a?UEC", ("nombre", "cantidad")),
    ("dinero_enviado", "dinero", r"^You sent (.+?):\s*([\d.,]+)\s*a?UEC", ("nombre", "cantidad")),
    ("multa", "ley", r"^Fined ([\d.,]+) UEC", ("cantidad",)),
    ("transaccion", "", r"^Transaction Complete", ()),
    # --- amistad
    ("amistad_peticion", "amistad", r"^(\S+) Friend Request", ("nombre",)),
    ("amistad_aceptada", "amistad", r"^Friend Added (\S+)", ("nombre",)),
    ("llamada", "amistad", r"^Incoming call:\s*(.*)", ("nombre",)),
    # --- torre / hangar (ATC)
    ("atc_hangar_listo", "atc", r"^Hangar Request Completed", ()),
    ("atc_cola_hangar", "atc", r"^Joined hangar queue\.?\s*(?:Your place:\s*(\d+))?", ("puesto",)),
    ("atc_incautada", "atc", r"^Vehicle Impounded:\s*(.*)", ("x",)),
    # --- zonas y ley
    ("zona_armisticio_entra", "ubicacion", r"^(?:Entering|Entered) Armistice Zone", ()),
    ("zona_armisticio_sale", "ubicacion", r"^(?:Leaving|Exiting|Exited) Armistice Zone", ()),
    ("jurisdiccion", "ubicacion", r"^Entered (.+?) Jurisdiction", ("x",)),
    ("propiedad_privada", "ubicacion", r"^Entering Private Property", ()),
    ("zona_restringida", "ley", r"^Restricted Area", ()),
    ("espacio_vigilado_sale", "", r"^Exited Monitored Space", ()),
    ("comms_caidas", "ley", r"^Monitored Space Down", ()),
    ("crimestat", "ley", r"^CrimeStat Rating Increased", ()),
    ("crimen_contra_ti", "ley", r"^(\S+) committed (.+?) against you", ("nombre", "x")),
    # --- salud y nave
    ("herida", "salud", r"^(\w+) Injury Detected(?: - (.+?) -)?", ("x", "parte")),
    ("sangrando", "salud", r"^Bleeding", ()),
    ("incapacitado", "salud", r"^Incapacitated", ()),
    ("emergencias", "salud", r"^(?:Standby, Local )?Emergency Services", ()),
    ("combustible_bajo", "avisos", r"^Low Fuel", ()),
    ("cuantico_calibrado", "", r"^Quantum Travel Calibration Complete$", ()),
    ("plano_recibido", "avisos", r"^Received Blueprint:\s*(.*)", ("x",)),
    ("refineria_lista", "avisos", r"^(?:A )?Refinery Work Order has been Completed at (.+)", ("lugar",)),
]
RULES_RX = [(k, c, re.compile(p, re.I), f) for k, c, p, f in RULES]
CATEGORIES = {
    "ubicacion": "Llegadas y cambios de ubicación",
    "grupo": "Grupo: invitaciones, quién entra y sale",
    "dinero": "Dinero recibido y enviado",
    "amistad": "Peticiones de amistad y llamadas",
    "atc": "Torre de control y hangar",
    "contratos": "Contratos y recompensas",
    "salud": "Heridas y emergencias",
    "ley": "CrimeStat, multas y zonas restringidas",
    "avisos": "Combustible, refinería, planos y llamaradas solares",
    "nave": "Tu nave: quién sube y baja, daños",
}

# Comentarios (se elige uno al azar). {t} = tratamiento; {nombre}, {cantidad}, {lugar}, {x}, {puesto}, {parte}
COMMENTS = {
    "ubicacion": ["Hemos llegado a {lugar}, {t}.", "Bienvenido a {lugar}, {t}.", "{lugar}. Recuerde dónde ha aparcado esta vez."],
    "llegada_cuantica": ["Salto completado. Llegamos a {lugar}.", "Destino alcanzado: {lugar}, {t}.", "Hemos llegado a {lugar}. Ni un rasguño… esta vez."],
    "llegada_cuantica_sin_destino": ["Salto completado, {t}."],
    "zona_armisticio_entra": ["Entramos en zona de armisticio. Armas bloqueadas, {t}.", "Zona de armisticio: aquí toca portarse bien."],
    "zona_armisticio_sale": ["Salimos de la zona de armisticio. Ojos abiertos, {t}."],
    "jurisdiccion": ["Entramos en la jurisdicción de {x}.", "Ahora mandan los de {x}, {t}."],
    "propiedad_privada": ["Propiedad privada a la vista, {t}. Llame antes de entrar."],
    "grupo_invitacion": ["{t}, {nombre} le invita a su grupo.", "Invitación de grupo de {nombre}. ¿Le hacemos un hueco?"],
    "grupo_entra": ["{nombre} se ha unido al grupo.", "Tenemos compañía: {nombre} entra en el grupo."],
    "grupo_sale": ["{nombre} ha dejado el grupo.", "{nombre} se ha ido del grupo. No ha dicho adiós."],
    "grupo_conectado": ["{nombre} se ha conectado."],
    "grupo_desconectado": ["{nombre} se ha desconectado.", "Perdemos a {nombre}: desconectado."],
    "grupo_te_unes": ["Se ha unido al grupo, {t}."],
    "grupo_creado": ["Grupo creado, {t}. Ahora solo falta gente."],
    "grupo_dejas": ["Ha dejado el grupo, {t}."],
    "grupo_expulsado": ["Le han echado del grupo, {t}. Ellos se lo pierden."],
    "grupo_disuelto": ["El grupo se ha disuelto."],
    "grupo_lider": ["{nombre} es el nuevo líder del grupo."],
    "grupo_rechaza": ["{nombre} ha rechazado la invitación. Peor para {nombre}."],
    "grupo_salto_hacia_ti": ["{nombre} está saltando hacia nuestra posición."],
    "grupo_lanzamiento": ["{nombre} inicia un lanzamiento de grupo."],
    "grupo_calibracion": ["{nombre} tiene el cuántico calibrado."],
    "contrato_compartido": ["Le han compartido un contrato: {x}."],
    "dinero_recibido": ["{nombre} le ha enviado {cantidad} aUEC, {t}.", "¡Ingreso! {cantidad} aUEC de {nombre}. Invite usted a la próxima."],
    "dinero_ofrecido": ["{nombre} quiere enviarle {cantidad} aUEC, {t}."],
    "dinero_enviado": ["Enviados {cantidad} aUEC a {nombre}.", "{cantidad} aUEC para {nombre}. Qué generoso, {t}."],
    "amistad_peticion": ["{nombre} quiere ser su amigo, {t}.", "Petición de amistad de {nombre}. Parece majo… o no."],
    "amistad_aceptada": ["{nombre} ya está en su lista de amigos."],
    "llamada": ["Llamada entrante de {nombre}, {t}."],
    "atc_hangar_listo": ["Control confirma: hangar asignado, {t}.", "La torre nos ha dado hangar. Puede ir a por la nave."],
    "atc_cola_hangar": ["La torre nos pone en cola para el hangar. Puesto {puesto}.", "En cola para el hangar, {t}."],
    "atc_incautada": ["Nos han incautado la nave: {x}. Qué vergüenza, {t}."],
    "contrato_aceptado": ["Contrato aceptado: {x}. A trabajar, {t}.", "Nuevo contrato: {x}. Otro día, otro aUEC."],
    "contrato_completado": ["Contrato completado: {x}. Bien hecho, {t}.", "¡Contrato cumplido! Esto se celebra con un café de máquina."],
    "contrato_fallido": ["Contrato fallido: {x}. Haremos como que no ha pasado, {t}."],
    "recompensa": ["Recompensa recibida, {t}. Me debe una cerveza."],
    "multa": ["Nos han multado con {cantidad} UEC, {t}."],
    "zona_restringida": ["{t}, zona restringida. Le aconsejo dar media vuelta antes de que nos disparen."],
    "comms_caidas": ["Las comunicaciones del sector han caído. Aquí no hay seguridad que valga, {t}."],
    "crimestat": ["{t}, nos acaban de subir el CrimeStat. Discreción, por favor."],
    "crimen_contra_ti": ["{nombre} ha cometido un delito contra usted, {t}: {x}."],
    "herida": ["Detecto una herida {x}, {t}. Busque un médico o al menos una tirita."],
    "sangrando": ["{t}, está sangrando. Use un medpen, por favor."],
    "incapacitado": ["{t}, está incapacitado. Pidiendo ayuda… o rezando, lo que llegue antes."],
    "emergencias": ["Los servicios de emergencia van de camino, {t}. Aguante."],
    "combustible_bajo": ["Atención, {t}: combustible bajo.", "Nos quedamos secos de combustible. Sugiero repostar antes de empujar la nave."],
    "plano_recibido": ["Nuevo plano recibido: {x}."],
    "refineria_lista": ["La orden de refinería está lista en {lugar}, {t}."],
    # --- nave y tripulación (canal de la nave)
    "nave_subes": ["A bordo de la {nave}, {t}.", "Bienvenido a la {nave}. Abróchese el cinturón."],
    "nave_tripulante_entra": ["{nombre} ha subido a la {nave}.", "Tenemos a {nombre} a bordo de la {nave}, {t}."],
    "nave_tripulante_sale": ["{nombre} ha bajado de la {nave}.", "{nombre} abandona la {nave}. Uno menos para el café."],
    "nave_destruida": ["{t}, hemos perdido la {nave}. Toca reclamar el seguro."],
    "nave_inutilizada": ["{t}, la {nave} está inutilizada. Hay que salir de aquí."],
    # --- más avisos (cualquier idioma, gracias al global.ini)
    "grupo_calibracion_inicio": ["{nombre} está calibrando el salto cuántico del grupo."],
    "grupo_calibracion_fallo": ["{nombre} ha cancelado la calibración cuántica."],
    "grupo_expulsa": ["{nombre} ha sido expulsado del grupo."],
    "atc_incautando": ["{t}, nos están incautando la nave. Muévase de la plataforma."],
    "territorio_hostil_entra": ["Entramos en territorio hostil, {t}. Escudos arriba.", "Territorio hostil. Yo que usted no me pararía a hacer fotos."],
    "llamarada_solar": ["¡{t}, llamarada solar! Busque cobertura."],
    "rescate_aceptado": ["{nombre} ha aceptado su baliza de rescate. Aguante, {t}."],
    "sobredosis": ["{t}, sobredosis. Deje los medpens un rato."],
    "crimen_cometido": ["{t}, delito registrado: {x}."],
    "reubicado": ["Nos han reubicado por seguridad, {t}."],
    "muerte": ["Ha caído, {t}. Lo apunto en la bitácora.", "Ha caído, {t}. Que no se repita."],
    "regeneracion": ["Bienvenido de vuelta al mundo de los vivos, {t}."],
    "salto_error": ["El motor cuántico no estaba listo para el salto, {t}. Inténtelo otra vez."],
}
INJURY = {"minor": "leve", "moderate": "moderada", "major": "grave", "severe": "muy grave"}


def find_game_log() -> Path | None:
    """Busca el Game.log más reciente en las carpetas habituales de todas las unidades."""
    candidates = []
    drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")] if os.name == "nt" else []
    roots = ["Program Files\\Roberts Space Industries\\StarCitizen", "Roberts Space Industries\\StarCitizen",
             "Games\\Roberts Space Industries\\StarCitizen", "StarCitizen"]
    for d in drives:
        for r in roots:
            for ch in ("LIVE", "PTU", "EPTU", "HOTFIX", "TECH-PREVIEW"):
                p = Path(d) / r / ch / "Game.log"
                if p.exists():
                    candidates.append(p)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


@dataclass
class GameEvent:
    kind: str
    detail: str
    category: str
    when: float
    data: dict = field(default_factory=dict)
    replay: bool = False  # True = leído del log al arrancar (pasado), no en directo

    @property
    def important(self) -> bool:
        return bool(self.category)


def log_time(rec: str) -> float | None:
    """'<2026-11-07T21:16:37.486Z> …' -> segundos epoch (UTC)."""
    m = TIMESTAMP.match(rec)
    if not m:
        return None
    try:
        return calendar.timegm(time.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")) + float("0." + (m.group(2) or "0"))
    except ValueError:
        return None


class GameLog(threading.Thread):
    """Sigue el Game.log. Emite GameEvent para:
    - on_event: SOLO lo que pasa en directo (para los comentarios en voz);
    - sinks: TODO, también lo releído al arrancar (para el diario de sesión)."""

    def __init__(self, settings, on_event: Callable[[GameEvent], None] | None = None) -> None:
        super().__init__(daemon=True, name="gamelog")
        self.settings = settings
        self.on_event = on_event
        self.sinks: list[Callable[[GameEvent], None]] = []
        self.after_replay: list[Callable[[], None]] = []  # p. ej. el diario guarda su estado
        self.text = TEXT
        self.path: Path | None = None
        self.location = "desconocida"
        self.shard = ""
        self.player = ""
        self.version = ""
        self.contracts: dict[str, float] = {}
        self.party: set[str] = set()
        self.ship = ""  # nave en la que vas (canal de la nave)
        self.events: collections.deque[GameEvent] = collections.deque(maxlen=60)
        self.status = "inactivo"
        self._record = ""
        self._seen: dict[str, float] = {}
        self._replaying = False
        self._qt_target = ""
        self._qt_fuel = ""
        self._last_announced = ""
        self._now = 0.0  # hora (del log) del registro que se está leyendo
        self._vehicles: dict[str, str] = {}  # id de entidad -> nombre de nave
        self._ship_names: dict[str, str] = {}  # «krugerl22alphawolf» -> «Kruger L-22 Alpha Wolf» (visto en el HUD)
        self._downed = False
        self._in_pu = False
        self._text_check = 0.0
        self._slow: dict[str, float] = {}
        self._last_incap = -1e9  # tareas de carga lentas ya anotadas

    # -------------------------------------------------------------- consultas
    def summary(self) -> str:
        if self.path is None and not self.events:
            return "No encuentro el Game.log de Star Citizen (¿el juego está abierto?)."
        lines = [f"Ubicación actual (según el log): {self.location}"]
        if self.player:
            lines.append(f"Personaje: {self.player}")
        if self.ship:
            lines.append(f"Nave en la que va: {self.ship}")
        if self.shard:
            lines.append(f"Servidor: {self.shard}")
        if self.contracts:
            lines.append("Contratos activos: " + "; ".join(self.contracts))
        if self.party:
            lines.append("Grupo: " + ", ".join(sorted(self.party)))
        recent = list(self.events)[-12:]
        if recent:
            lines.append("Últimos eventos:")
            for e in recent:
                lines.append(f"- {time.strftime('%H:%M', time.localtime(e.when))} {e.kind}: {e.detail}")
        return "\n".join(lines)

    # ------------------------------------------------------------------ parseo
    def _emit(self, kind: str, category: str, data: dict | None = None, detail: str = "") -> None:
        data = {k: (v or "").strip(" :.\"") if isinstance(v, str) else v for k, v in (data or {}).items()}
        detail = detail or " · ".join(str(v) for v in data.values() if v)
        key = f"{kind}|{detail}"
        now = self._now or time.time()
        if abs(now - self._seen.get(key, -1e9)) < 3:  # el juego repite el mismo aviso varias veces
            return
        self._seen[key] = now
        if len(self._seen) > 500:
            self._seen = {k: v for k, v in self._seen.items() if now - v < 60}
        ev = GameEvent(kind, detail, category, now, data, self._replaying)
        self.events.append(ev)
        x = data.get("x", "")
        if kind == "contrato_aceptado":
            self.contracts[x] = now
        elif kind in ("contrato_completado", "contrato_fallido", "contrato_retirado"):
            self.contracts.pop(x, None)
        elif kind in ("grupo_entra", "grupo_conectado"):
            self.party.add(data.get("nombre", ""))
        elif kind in ("grupo_sale", "grupo_desconectado", "grupo_expulsa"):
            self.party.discard(data.get("nombre", ""))
        elif kind in ("grupo_dejas", "grupo_expulsado", "grupo_disuelto"):
            self.party.clear()
        elif kind == "nave_subes":
            self.ship = data.get("nave", "")
        elif kind == "nave_bajas" and data.get("nave") == self.ship:
            self.ship = ""
        for sink in list(self.sinks):
            try:
                sink(ev)
            except Exception:
                log.exception("Diario")
        if self.on_event and not self._replaying:
            self.on_event(ev)

    def _set_location(self, place: str, source: str) -> None:
        if not place or place == self.location:
            return
        self.location = place
        # Tras un salto cuántico ya se avisó de la llegada a ese mismo sitio: no repetir.
        if place == self._last_announced:
            return
        self._last_announced = place
        self._emit("ubicacion", "ubicacion", {"lugar": place})

    def _ship(self, cls: str) -> str:
        """Nombre bonito de una nave a partir de su clase interna; prefiere el que muestra el HUD."""
        name = ship_name(cls, self.text)
        return self._ship_names.get(re.sub(r"[^a-z0-9]", "", name.lower()), name)

    def _remember_vehicles(self, rec: str) -> None:
        for cls, vid in VEHICLE_ID.findall(rec):
            if vid not in self._vehicles:
                self._vehicles[vid] = self._ship(cls)

    def _pretty(self, raw: str) -> str:
        return pretty_loc(raw, self.text)

    def parse_record(self, rec: str) -> None:
        t = log_time(rec)
        if t:
            self._now = t
        if "Added notification" in rec:
            self._notification(rec)
            return
        if "RequestLocationInventory" in rec:
            m = LOCINV.search(rec) or LOCATION.search(rec)
            if m:
                self._set_location(self._pretty(m.group(1)), "inventario")
            return
        if "Log started on" in rec:
            self._in_pu = False
            self._emit("sesion_inicio", "", {}, detail="juego iniciado")
            return
        if rec.find("FileVersion:") > 0 and not self.version:
            m = re.search(r"FileVersion:\s*([\d.]+)", rec)
            if m:
                self.version = m.group(1)
            return
        if "<AccountLoginCharacterStatus_Character>" in rec:
            m = CHARACTER.search(rec)
            if m:
                self.player = m.group(1)
                self._emit("personaje", "", {"nombre": self.player})
            return
        if "<Join PU>" in rec:
            m = SHARD.search(rec)
            if m:
                self.shard = m.group(1)
                self._in_pu = True
                self._emit("servidor", "", {"x": self.shard})
            return
        if "Player Selected Quantum Target" in rec:
            self._remember_vehicles(rec)
            m = QT_DEST.search(rec)
            self._qt_target = pretty_dest(m.group(1), self.text) if m else ""
            self._qt_fuel = ""
            return
        if "<Calculate Route>" in rec and "fuel estimate" in rec:
            m = re.search(r"fuel estimate ([\d.]+)", rec)
            if m:
                self._qt_fuel = f"{float(m.group(1)):,.0f}".replace(",", ".")
            return
        if any(k in rec for k in QT_ARRIVE):
            self._remember_vehicles(rec)
            dest, self._qt_target = self._qt_target, ""
            if dest:
                self.location = self._last_announced = dest
                self._emit("llegada_cuantica", "ubicacion", {"lugar": dest, "combustible": self._qt_fuel})
            else:
                self._emit("llegada_cuantica_sin_destino", "ubicacion", {}, detail="salto completado")
            return
        if "<Trying to QT when not in Idle>" in rec:
            self._emit("salto_error", "", {}, detail="el motor cuántico no estaba listo")
            return
        if "<Vehicle Control Flow>" in rec:
            m = CONTROL_TOKEN.search(rec)
            if m:
                self._remember_vehicles(rec)
                ship = self._ship(m.group(2))
                kind = "piloto_suelta" if m.group(1).lower().startswith("releas") else "piloto_toma"
                self._emit(kind, "", {"nave": ship})
            return
        if "SetVehicleSpawningInformations" in rec:
            m = SPAWN_INFO.search(rec)
            if m:
                ship = self._vehicles.get(m.group(1), "")
                place = m.group(2).strip()
                self._emit("nave_entregada", "", {"nave": ship, "lugar": place},
                           detail=f"{ship} entregada en {place}" if ship else f"Nave entregada en {place}")
            return
        if "<Actor Death>" in rec:
            self._actor_death(rec)
            return
        if "Logged an incap" in rec:
            self._incap(rec)
            return
        if "DoesLocationContainHospital" in rec:
            m = CORPSE_HOSPITAL.search(rec)
            if m:
                who, loc = m.group("who"), self._pretty(m.group("loc").lstrip("@"))
                if self._is_me(who):
                    self._downed = True
                    self._emit("reaparicion_punto", "", {"lugar": loc}, detail=f"reaparecerás en {loc}")
                else:
                    self._emit("reaparicion_otro", "", {"nombre": who, "lugar": loc})
            return
        if "<MED BED HEAL>" in rec:
            self._med_bed(rec)
            return
        if "Loading screen for" in rec:
            m = LOADED.search(rec)
            if m:
                what = LOAD_WHAT.get(m.group("what").lower(), m.group("what"))
                secs = float(m.group("secs"))
                self._emit("carga_fin", "", {"x": what, "segundos": f"{secs:.0f}"}, detail=f"{what} cargado en {secs:.0f} s")
            return
        if "[CSessionManager::ConnectCmd] Connect started" in rec:
            self._emit("carga_conectando", "", {}, detail="conectando con el servidor")
            return
        if "[CSessionManager::OnClientConnected] Connected" in rec:
            self._emit("carga_conectado", "", {}, detail="conectado al servidor")
            return
        if "[CSessionManager::OnClientSpawned] Spawned" in rec:
            self._emit("carga_aparicion", "", {}, detail="personaje en el mundo")
            return
        if "ContextEstablisherTaskLongWait" in rec or "ContextEstablisherTaskFailed" in rec:
            m = CET_SLOW.search(rec)
            if m:
                failed = m.group("st") == "Failed"
                last = self._slow.get(m.group("task"), -1e9)
                if not failed and self._now - last < 120:
                    return  # el juego repite «sigue tardando» cada pocos segundos
                self._slow[m.group("task")] = self._now
                self._emit("carga_fallo" if failed else "carga_lenta", "", {"x": m.group("task"), "segundos": f"{float(m.group('secs')):.0f}"})
            return
        if "<Actor stall>" in rec:
            m = ACTOR_STALL.search(rec)
            if m and self._is_me(m.group("who")) and float(m.group("secs")) >= 2:
                self._emit("tiron_red", "", {"segundos": f"{float(m.group('secs')):.1f}"})
            return
        if "<Vehicle Destruction>" in rec:
            self._vehicle_destruction(rec)
            return
        if self._downed and "ResolveSpawnLocation" in rec and "Starting CET" in rec:
            self._downed = False
            self._emit("regeneracion", "salud", {}, detail="has reaparecido tras morir")
            return
        if "SystemQuit" in rec or "CCIGBroker::FastShutdown" in rec:
            self._emit("sesion_fin", "", {"lugar": self.location}, detail="juego cerrado")
            return
        if "<FatalCollision>" in rec:
            self._emit("colision_fatal", "", {}, detail="colisión")
            return

    def _notification(self, rec: str) -> None:
        m = NOTIFICATION.search(rec)
        if not m:
            return
        text = clean_notification(m.group(1))
        if not text or text.startswith("Downloading:"):
            return
        found = self.text.match(text)
        if found:
            kind, cat, data, _key = found
            self._finish_notification(kind, cat, data)
            return
        for kind, cat, rx, fields_ in RULES_RX:  # textos en inglés de versiones anteriores
            km = rx.search(text)
            if km:
                data = {f: g for f, g in zip(fields_, km.groups()) if g}
                if "nombre2" in data and "nombre" not in data:
                    data["nombre"] = data.pop("nombre2")
                data.pop("nombre2", None)
                if kind == "herida":
                    data["x"] = INJURY.get(data.get("x", "").lower(), data.get("x", ""))
                self._finish_notification(kind, cat, data)
                return
        # Cualquier otro aviso que hable de hangar, plataforma o torre: se lee tal cual.
        if re.search(r"(?i)\b(hangar|landing pad|pad \w+|atc|landing services|clearance|plataforma|aterrizaje)\b", text):
            self._emit("atc_aviso", "atc", {"x": text})

    def _finish_notification(self, kind: str, cat: str, data: dict) -> None:
        if "cantidad" in data:
            data["cantidad"] = money(data["cantidad"])
        if "lugar" in data:
            data["lugar"] = self._pretty(data["lugar"].split(":")[0])
        if kind in ("incapacitado", "sobredosis"):
            self._downed = True
            if kind == "incapacitado":
                if self._now - self._last_incap < 30:
                    cat = ""
                self._last_incap = self._now
        if kind == "regeneracion":
            self._downed = False
        if data.get("nave"):  # recordar el nombre «de HUD» de la nave (Kruger L-22 Alpha Wolf)
            self._ship_names.setdefault(re.sub(r"[^a-z0-9]", "", data["nave"].lower()), data["nave"])
        if kind == "nave_subes":  # no repetir «a bordo de la MOLE» cada vez que entras y sales
            last, when = getattr(self, "_boarded", ("", 0.0))
            if data.get("nave") == last and self._now - when < 900:
                cat = ""
            self._boarded = (data.get("nave", ""), self._now)
        if kind == "nave_bajas":
            cat = ""
        name = data.get("nombre", "")
        if name and self.player and name.lower() == self.player.lower() and kind.startswith("nave_tripulante"):
            return  # eres tú mismo entrando en tu nave (ya sale como nave_subes)
        self._emit(kind, cat, data)

    def _is_me(self, name: str) -> bool:
        return bool(self.player) and (name or "").lower() == self.player.lower()

    def _weapon(self, raw: str) -> str:
        wcls = re.sub(r"_\d{6,}$", "", raw or "")
        if not wcls or wcls.lower() == "unknown":
            return ""
        return self.text.local("item_Name" + wcls) or split_camel(wcls.replace("_", " "))

    def _actor_death(self, rec: str) -> None:
        m = ACTOR_KILL.search(rec)
        if not m:
            return
        victim, killer = m.group("victim"), m.group("killer")
        weapon = self._weapon(m.group("weapon"))
        dmg = damage_es(m.group("damage") or "")
        if self._is_me(victim):
            self._downed = True
            if self._is_me(killer) or killer.lower() == "unknown":
                who, dmg = "", dmg or "accidente"
            else:
                who = actor_name(killer)
            self._emit("muerte", "salud", {"nombre": who, "x": weapon, "dano": dmg, "lugar": self.location})
        elif self._is_me(killer):
            self._emit("baja", "", {"nombre": actor_name(victim), "x": weapon, "dano": dmg,
                                    "tipo": "npc" if is_npc(victim) else "jugador"})
        else:
            self._emit("muerte_otro", "", {"nombre": actor_name(victim), "asesino": actor_name(killer),
                                           "x": weapon, "dano": dmg, "tipo": "npc" if is_npc(victim) else "jugador"})

    def _vehicle_destruction(self, rec: str) -> None:
        m = VEHICLE_DESTROY.search(rec)
        if not m:
            return
        ship = self._ship(re.sub(r"_\d{6,}$", "", m.group("vehicle")))
        driver = m.group("driver") or ""
        attacker = m.group("attacker") or ""
        level = int(m.group("to") or 0)
        state = "destruida" if level >= 2 else "inutilizada"
        mine = self._is_me(driver) or (self.ship and ship.lower() in self.ship.lower())
        by = "" if not attacker or attacker.lower() == "unknown" else ("ti mismo" if self._is_me(attacker) else actor_name(attacker))
        if mine:
            self._emit("nave_destruida" if level >= 2 else "nave_inutilizada", "salud", {"nave": ship, "nombre": by})
        elif self._is_me(attacker):
            self._emit("nave_abatida", "", {"nave": ship, "x": state,
                                            "nombre": "" if not driver or driver.lower() == "unknown" else actor_name(driver)})
        else:
            self._emit("nave_destruida_otra", "", {"nave": ship, "x": state, "nombre": by})

    def _incap(self, rec: str) -> None:
        m = INCAP.search(rec)
        if not m:
            return
        causes = [damage_es(c) for c, _ in sorted(INCAP_CAUSE.findall(m.group("causes")), key=lambda x: -float(x[1]))]
        causes = ", ".join(dict.fromkeys(c for c in causes if c))
        if self._is_me(m.group("who")):
            self._downed = True
            cat = "" if self._now - self._last_incap < 30 else "salud"  # el HUD ya lo avisó: no repetir en voz
            self._last_incap = self._now
            self._emit("incapacitado", cat, {"causa": causes}, detail="incapacitado" + (f" ({causes})" if causes else ""))
        else:
            self._emit("incap_otro", "", {"nombre": actor_name(m.group("who")), "causa": causes})

    def _med_bed(self, rec: str) -> None:
        m = MED_BED.search(rec)
        if not m:
            return
        names = {"head": "cabeza", "torso": "torso", "larm": "brazo izquierdo", "rarm": "brazo derecho",
                 "lleg": "pierna izquierda", "rleg": "pierna derecha"}
        parts = [es for k, es in names.items() if m.group(k) == "true"]
        veh = m.group("veh")
        where = "" if not veh or veh.lower() in ("unknown", "none", "null") or veh.startswith("@") else self._ship(re.sub(r"_\d{6,}$", "", veh))
        ok = m.group("ok").lower().startswith("succ")
        who = m.group("who")
        self._downed = False
        self._emit("cama_medica" if self._is_me(who) or not self.player else "cama_medica_otro", "",
                   {"x": ", ".join(parts) or "chequeo", "nave": where, "nombre": actor_name(who), "ok": "sí" if ok else "no"})

    def feed_line(self, line: str) -> None:
        if RECORD_START.match(line):
            # Un aviso con salto de línea («Nuevo miembro unido\nX se ha unido…») sigue en las
            # líneas siguientes, cada una con su propia marca de hora: se juntan antes de leerlo.
            if self._record and "Added notification \"" in self._record and not NOTIF_END.search(self._record) \
                    and self._record.count("\n") < 8:
                self._record += "\n" + TIMESTAMP_PREFIX.sub("", line)
                return
            if self._record:
                self.parse_record(self._record)
            self._record = line
        else:
            self._record += "\n" + line

    def flush(self) -> None:
        if self._record:
            self.parse_record(self._record)
            self._record = ""

    # ---------------------------------------------------------------- bucle
    def _resolve_path(self) -> Path | None:
        custom = self.settings.get("gamelog_ruta")
        if custom and Path(custom).exists():
            return Path(custom)
        return find_game_log()

    def load_texts(self, path: Path | None = None, force: bool = False) -> None:
        """Carga (o recarga si cambió) el global.ini del juego para entender los avisos en tu idioma."""
        if not force and time.time() - self._text_check < 60:
            return
        self._text_check = time.time()
        game_log = path or self.path or self._resolve_path()
        channel = game_log.parent if game_log else None
        if channel is None or (self.settings.get("juego_carpeta") or "").strip():
            from .translation import find_live_dirs  # sin Game.log: la carpeta LIVE del juego

            lives = find_live_dirs(self.settings, game_log)
            channel = lives[0] if lives else channel
        ini, lang = find_global_ini(channel, self.settings.get("globalini_ruta") or "")
        try:
            self.text.load(ini, lang)
        except Exception:
            log.exception("global.ini")

    def run(self) -> None:
        while True:
            if not self.settings.get("gamelog_activo"):
                self.status = "desactivado"
                time.sleep(3)
                continue
            path = self._resolve_path()
            if not path:
                self.status = "Game.log no encontrado (abre el juego o indica la ruta)"
                time.sleep(10)
                continue
            self.path = path
            self.load_texts(path, force=True)
            self.status = f"leyendo {path}"
            try:
                self._follow(path)
            except Exception as e:
                log.warning("Game.log: %s", e)
                time.sleep(3)

    def replay_file(self, path: Path, max_bytes: int = 12_000_000) -> None:
        """Lee un log entero (o su final) sin hablar: para saber dónde estás y para el diario."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            size = path.stat().st_size
            if size > max_bytes:
                f.seek(size - max_bytes)
                f.readline()
            self._replaying = True
            try:
                for line in f:
                    self.feed_line(line.rstrip("\n"))
                self.flush()
            finally:
                self._replaying = False
                self._replayed()

    def _replayed(self) -> None:
        for fn in list(self.after_replay):
            try:
                fn()
            except Exception:
                log.exception("Tras releer el log")

    def _follow(self, path: Path) -> None:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            # Repaso silencioso del log para saber dónde estás ahora (y rellenar el diario).
            size = path.stat().st_size
            if size > 12_000_000:
                f.seek(size - 12_000_000)
                f.readline()
            self._replaying = True
            for line in f:
                self.feed_line(line.rstrip("\n"))
            self.flush()
            self._replaying = False
            self._replayed()
            self._seen.clear()
            pos = f.tell()
            while self.settings.get("gamelog_activo"):
                line = f.readline()
                if line:
                    self.feed_line(line.rstrip("\n"))
                    pos = f.tell()
                    continue
                self.flush()
                time.sleep(0.5)
                self.load_texts()
                try:
                    if path.stat().st_size < pos:  # el juego ha empezado un log nuevo
                        log.info("Game.log reiniciado")
                        return
                    newest = self._resolve_path()
                    if newest and newest != path:
                        return
                except OSError:
                    return


def comment_for(ev: GameEvent, treatment: str) -> str | None:
    options = COMMENTS.get(ev.kind)
    if not options:
        if ev.kind == "atc_aviso":
            return f"Aviso de control: {ev.data.get('x', '')}"
        return None
    values = collections.defaultdict(str, {"t": treatment, **ev.data})
    if "x" not in ev.data:
        values["x"] = ev.detail
    text = random.choice(options).format_map(values)
    text = re.sub(r"\s+([.,:])", r"\1", text).replace(": .", ".").strip()
    return text[:1].upper() + text[1:]

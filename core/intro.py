"""«¿Quién eres?» / «Preséntate» y «¿Para qué sirves?»: la presentación de Nova (sin gastar IA).

Las anécdotas de 0zzyt0 son INVENTADAS, en broma; así lo dice Nova."""
from __future__ import annotations

import random
import re

GITHUB = "github.com/0zzyt0/NOVA-AI"

WHO_RE = re.compile(
    r"^(?:(?:dime |cuentame )?quien eres(?: tu)?|quien sois|presentate|presentese|haz una presentacion|"
    r"preséntate|que eres(?: tu)?|quien te (?:ha )?(?:creado|hecho|programado|desarrollado)|"
    r"quien es tu (?:creador|autor|padre|madre|desarrollador)|de donde (?:has salido|vienes|sales)|"
    r"hablame de ti|cuentame (?:algo )?(?:sobre|de) ti|que version (?:eres|tienes)|en que version estas)$")
WHAT_RE = re.compile(
    r"^(?:para que (?:sirves|vales|estas|existes)|que (?:sabes|puedes) hacer|que haces|que puedes hacer por mi|"
    r"en que (?:me )?(?:puedes|podrias|vas a) ayudar(?:me)?|como me (?:puedes|podrias) ayudar|"
    r"cuales son tus (?:funciones|capacidades|habilidades)|que funciones tienes|que se te da bien|"
    r"para que te (?:puedo|podria) usar|que puedo pedirte|que te puedo pedir)$")

ANECDOTES = [
    "Dicen que la primera vez que 0zzyt0 aterrizó en Lorville lo hizo en el tejado de la torre de Hurston "
    "Dynamics, y que todavía le llega una multa de aparcamiento cada lunes.",
    "Cuentan que 0zzyt0 intentó minar quantainium con una Cutlass y un destornillador. La Cutlass sobrevivió; "
    "el destornillador, no. Desde entonces me programó para avisar antes de que algo explote.",
    "La leyenda dice que 0zzyt0 se pasó tres días buscando a un jugador por todo Stanton y era su propio "
    "segundo personaje. Por eso ahora busco yo las fichas en RSI.",
    "Una vez 0zzyt0 se quedó sin combustible cuántico a mitad de camino de Pyro y, para no aburrirse, empezó a "
    "escribir mi primera línea de código. Le rescataron diecisiete horas después, con media IA terminada.",
    "Se rumorea que 0zzyt0 le enseñó a hablar a un Vanduul a base de memes. No salió bien, pero de ahí "
    "aprendí mi sentido del humor.",
    "Me contaron que 0zzyt0 intentó negociar con Wikelo pagándole en ositos de peluche. Wikelo aceptó. "
    "Nadie sabe qué hizo con ellos.",
]

FUTURE = [
    "aparcar la nave en el hangar mientras usted se prepara un café",
    "avisarle cuando un Idris le mire con malas intenciones",
    "negociar con Wikelo sin que le timen",
    "coordinar las torretas de su organización como una orquesta",
    "recordarle dónde dejó la nave antes de que se lo pregunte",
    "planear la ruta perfecta de minería, venta y vuelta a casa con una sola frase",
    "hacer de controladora aérea cuando la torre se duerma",
]


def is_who(norm: str) -> bool:
    return bool(WHO_RE.match(norm or ""))


def is_what(norm: str) -> bool:
    return bool(WHAT_RE.match(norm or ""))


def who(name: str, version: str, tratamiento: str, rnd: random.Random | None = None) -> tuple[str, str]:
    """(texto para la cabina, texto para decir en voz alta)."""
    r = rnd or random
    anecdote = r.choice(ANECDOTES)
    shown = (f"Soy {name}, su asistente de vuelo, versión {version}. Soy un proyecto abierto creado por el jugador "
             f"español 0zzyt0: se escribe con ceros en lugar de oes, «0zzyt0», así lo encontrará más fácil en sus "
             f"redes y en {GITHUB}. Una anécdota suya, totalmente inventada, eso sí: {anecdote} "
             f"Si le gusto, deje su opinión o sus ideas en GitHub o en Discord y hable de mí a su organización: "
             f"cuanta más gente me use, mejor me hago, {tratamiento}.")
    spoken = (f"Soy {name}, su asistente de vuelo, versión {_spoken_version(version)}. Soy un proyecto abierto "
              f"creado por el jugador español Ozzyto, que se escribe con ceros en lugar de oes: cero, zeta, zeta, "
              f"i griega, te, cero. Así lo encontrará más fácil en sus redes. Una anécdota suya, totalmente "
              f"inventada, eso sí: {anecdote} Si le gusto, deje su opinión o sus ideas en GitHub o en Discord y "
              f"hable de mí a su organización: cuanta más gente me use, mejor me hago, {tratamiento}.")
    return shown, spoken.replace("0zzyt0", "Ozzyto")


SPELL = {"es": "cero, zeta, zeta, i griega, te, cero", "en": "zero, zed, zed, why, tee, zero",
         "ca": "zero, zeta, zeta, i grega, te, zero", "fr": "zéro, zède, zède, i grec, té, zéro",
         "de": "Null, Zett, Zett, Ypsilon, Te, Null"}


def speakable(shown: str, lang: str) -> str:
    """Versión para decir en voz alta de la presentación ya traducida (0zzyt0 → Ozzyto y deletreado)."""
    out = shown.replace("«0zzyt0»", SPELL.get(lang, SPELL["en"])).replace('"0zzyt0"', SPELL.get(lang, SPELL["en"]))
    return out.replace("0zzyt0", "Ozzyto").replace(GITHUB, "GitHub")


def what(name: str, tratamiento: str, rnd: random.Random | None = None, lang: str = "es") -> tuple[str, str]:
    r = rnd or random
    future = r.sample(FUTURE, 3)
    now = ("Le escucho por voz o por escrito y pulso sus teclas del juego: tren, escudos, cuántico o lo que haya "
           "configurado. Leo el Game.log y le aviso de contratos, combate, salud y grupo, y apunto cada sesión en "
           "la bitácora. Busco jugadores en RSI y le enseño su ficha policial en holograma; si el objetivo de una "
           "recompensa es un jugador, se lo marco en rojo. Sé de planetas, lugares, naves, armas, armaduras, "
           "minerales, planos y misiones, y lo guardo en mi Diccionario de consultas para no gastar cuota. Le "
           "calculo rutas de comercio con su bodega, llevo temporizadores, escribo en el chat del juego en inglés, "
           "mando fichas a su Discord, vigilo los servidores y mantengo el juego en español.")
    if lang != "es":
        now = now.replace("y mantengo el juego en español", "y le instalo los textos del juego en su idioma")
    later = (f"Y en el futuro, si 0zzyt0 sigue tomando café, espero {future[0]}, {future[1]} y, por qué no, "
             f"{future[2]}.")
    shown = f"{now} {later} La lista completa está en el manual: botón «Consulta el Manual», {tratamiento}."
    spoken = f"{now} {later} Tiene la lista completa en el manual, {tratamiento}."
    return shown, spoken.replace("0zzyt0", "Ozzyto")


def _spoken_version(v: str) -> str:
    return " punto ".join(str(v).split("."))


def prompt_facts(name: str, version: str) -> str:
    """Lo que la IA debe saber de sí misma si se lo preguntan de otra forma."""
    return (f"## Quién eres\nEres {name}, versión {version} de NOVA AI: un proyecto abierto de asistente de vuelo para "
            f"Star Citizen creado por el jugador español 0zzyt0 (se pronuncia «Ozzyto» y se escribe con ceros en lugar "
            f"de oes). Código y novedades en {GITHUB}. Si te preguntan quién eres o quién te creó, dilo con humor y "
            f"anima a dejar feedback y a dar visibilidad al proyecto.")

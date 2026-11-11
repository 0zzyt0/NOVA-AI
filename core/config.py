r"""Ajustes de Nova.

Dónde se guardan tus datos (ajustes, comandos propios, memoria, sesión, voces descargadas):
  - Instalado en «Archivos de programa»: en %LOCALAPPDATA%\NOVA AI\datos (Windows no deja
    escribir en Archivos de programa sin permisos de administrador).
  - Carpeta suelta (portátil o desarrollo): en la subcarpeta datos\ del programa.
  - La variable de entorno NOVA_DATOS manda sobre ambas.
"""
from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path

VERSION = "1.3"
APP_NAME = "NOVA AI"
APP_DIR = Path(__file__).resolve().parent.parent
FACTORY_DIR = APP_DIR / "datos"  # archivos de fábrica que vienen con el programa (solo lectura)
BASE_KEYS_FILE = APP_DIR / "recursos" / "claves_iniciales.enc"  # claves gratuitas del programa base, cifradas
BASE_KEYS_MASTER = APP_DIR / "recursos" / "llave_claves.bin"  # llave maestra: solo en el instalador oficial
BASE_VERSION = 1  # sube cuando cambian las claves o la cadena de motores de fábrica
INSTALL_MARK = APP_DIR / "instalado.json"  # lo escribe el instalador


def read_base_keys(enc_file: Path | None = None, master_file: Path | None = None) -> dict:
    """Claves de fábrica, cifradas (ver core/keyvault.py). Sin la llave maestra del instalador: ninguna."""
    from . import keyvault
    data = keyvault.load(enc_file or BASE_KEYS_FILE, master_file or BASE_KEYS_MASTER)
    return {k: str(v) for k, v in data.items() if k in PROVIDERS and v}


def write_base_keys(keys: dict, enc_file: Path | None = None, master_file: Path | None = None) -> None:
    from . import keyvault
    keyvault.save(keys, enc_file or BASE_KEYS_FILE, master_file or BASE_KEYS_MASTER)


def is_installed(app_dir: Path = APP_DIR) -> bool:
    """¿Está Nova instalada en una carpeta del sistema (Archivos de programa)?"""
    if (app_dir / "instalado.json").exists():
        return True
    here = str(app_dir.resolve()).lower()
    for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        base = os.environ.get(var)
        if base and here.startswith(str(Path(base).resolve()).lower() + os.sep):
            return True
    return False


def pick_data_dir(app_dir: Path = APP_DIR) -> Path:
    env = os.environ.get("NOVA_DATOS")
    if env:
        return Path(env)
    if is_installed(app_dir):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_NAME / "datos"
    return app_dir / "datos"


DATA_DIR = pick_data_dir()
SETTINGS_FILE = DATA_DIR / "ajustes.json"
COMMANDS_FILE = FACTORY_DIR / "comandos.json"
MEMORY_FILE = DATA_DIR / "memoria.json"
SESSION_FILE = DATA_DIR / "sesion.json"
MODELS_DIR = DATA_DIR / "modelos"
LOG_FILE = DATA_DIR / "nova.log"

FINAL_PHRASE = (
    "... la verdad señor, no tengo ni idea de lo que me está pidiendo, "
    "toda la información que le acabo de dar me la he inventado."
)

# Proveedores de IA. Todos hablan el "idioma" de OpenAI, así que un único
# cliente sirve para todos. Los modelos se pueden cambiar desde la ventana.
PROVIDERS = {
    "gemini": {
        "nombre": "Google Gemini (gratis)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "modelos": ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.1-flash-lite"],
        "clave_url": "https://aistudio.google.com/apikey",
    },
    "groq": {
        "nombre": "Groq (gratis, muy rápido)",
        "base_url": "https://api.groq.com/openai/v1",
        "modelos": ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "qwen/qwen3.6-27b", "llama-3.1-8b-instant"],
        "clave_url": "https://console.groq.com/keys",
    },
    "openrouter": {
        "nombre": "OpenRouter (modelos :free)",
        "base_url": "https://openrouter.ai/api/v1",
        "modelos": ["openrouter/free", "meta-llama/llama-3.3-70b-instruct:free"],
        "clave_url": "https://openrouter.ai/keys",
    },
    "deepseek": {
        "nombre": "DeepSeek (5M tokens de prueba, luego muy barato)",
        "base_url": "https://api.deepseek.com",
        "modelos": ["deepseek-v4-flash", "deepseek-v4-pro"],
        "clave_url": "https://platform.deepseek.com/api_keys",
    },
    "ollama": {
        "nombre": "Ollama (en tu PC, sin internet)",
        "base_url": "http://localhost:11434/v1",
        "modelos": ["qwen3:8b", "llama3.1:8b"],
        "clave_url": "https://ollama.com/download",
    },
}

DEFAULTS: dict = {
    # --- v1.3: idioma de toda la app (ventana, voz, lo que entiende, comandos, manual) ---
    "idioma": "es",  # es | en | ca | fr | de
    "idioma_elegido": False,  # True = ya lo eligió el piloto (instalador u Opciones)
    "efectos_nivel": "cine",  # cine (cinematográficos) | ligero | ninguno
    "globalini_propio": "",  # global.ini que instalaste con «Add your language global.ini [HERE]»
    "globalini_propio_idioma": "",  # carpeta de Localization donde se instaló
    "globalini_idioma_antes": "",  # g_language que había antes (para deshacerlo)
    "nombre_asistente": "Nova",  # se puede llamar como quieras: se entrena en la configuración inicial
    "nombre_piloto": "",
    "tratamiento": "señor",
    "asistente_completado": False,  # False = al abrir sale la ventana de configuración inicial
    "nombre_variantes": [],  # cómo escribe Whisper el nombre cuando TÚ lo dices (aprendido)
    "frases_entrenamiento": [],  # vacío = 3 frases al azar sobre Star Citizen (core/training.py)
    # --- IA ---------------------------------------------------------------
    "ia_cadena": [  # se prueba en orden; si uno falla o se queda sin cuota, salta al siguiente
        {"proveedor": "gemini", "modelo": "gemini-flash-lite-latest"},
        {"proveedor": "gemini", "modelo": "gemini-3.5-flash-lite"},
        {"proveedor": "groq", "modelo": "openai/gpt-oss-120b"},
        {"proveedor": "openrouter", "modelo": "openrouter/free"},
    ],
    "claves": {"gemini": "", "groq": "", "openrouter": "", "deepseek": "", "ollama": "ollama"},
    "humor": 7,  # 0 = serio, 10 = cachondo
    "inventar_si_no_sabe": True,  # si no encuentra algo, se lo inventa en broma y lo confiesa al final
    "frases_inventadas": [FINAL_PHRASE],  # una se elige al azar; {t} = tratamiento
    "ia_razonamiento": "low",  # Gemini: low (rápido) | medium | high (más listo, más lento)
    "max_turnos_contexto": 12,
    # --- Voz de Nova (TTS) ------------------------------------------------
    "tts_motor": "edge",  # edge | piper | windows
    "tts_voz_edge": "es-ES-XimenaNeural",
    "tts_velocidad": 5,  # % (-50..+50)
    "tts_tono": 0,  # Hz (-50..+50)
    "tts_voz_piper": "es_ES-davefx-medium",
    "tts_efecto_radio": True,
    "volumen": 1.0,
    "dispositivo_salida": None,
    # --- Oído de Nova (STT) -----------------------------------------------
    "stt_motor": "auto",  # auto | local | groq
    "stt_modelo_local": "small",  # tiny | base | small | medium | large-v3-turbo
    "dispositivo_entrada": None,
    # --- Activación -------------------------------------------------------
    "ptt_tecla": "insert",  # tecla para hablar (mantener)
    "ptt_joystick": None,  # {"nombre": "...", "boton": 3}
    "palabra_clave_activa": True,
    "palabras_clave": [],  # formas EXTRA de llamarla, además de su nombre y lo aprendido
    "sensibilidad_vad": 0.5,  # 0 = solo voz fuerte, 1 = oye susurros
    "silencio_fin_ms": 700,
    # --- Juego ------------------------------------------------------------
    "gamelog_activo": True,
    "gamelog_ruta": "",  # vacío = autodetectar
    "gamelog_comentarios": True,  # Nova comenta lo que pasa (contratos, combustible...)
    "gamelog_comentarios_ia": False,  # usar la IA para comentar (gasta cuota)
    "gamelog_avisos": {"ubicacion": True, "grupo": True, "dinero": True, "amistad": True, "atc": True,
                       "contratos": True, "salud": True, "ley": True, "avisos": True, "nave": True},
    "globalini_ruta": "",
    "juego_carpeta": "",  # carpeta de Star Citizen (vacío = buscarla en todas las unidades)
    "traduccion_url": "https://drive.google.com/file/d/1uOYIVrtvtkBfVan1XprWtsLnI3opZuFi/view?usp=drive_link",
    "traduccion_instalada": 0,  # cuándo la instaló Nova
    "traduccion_aviso": 0,  # cuándo volver a preguntar (cada 3 meses)
    "traduccion_recordar": False,  # «Recuérdamelo en la siguiente sesión»
    "traduccion_preguntar": True,  # False = en la configuración inicial dijiste que no la querías  # vacío = el del idioma de tu juego (LIVE\\data\\Localization\\…\\global.ini)
    "diario_activo": True,  # diario de sesión en datos\\diario
    # --- v1.1 -------------------------------------------------------------
    "discord_webhook": "",  # https://discord.com/api/webhooks/… (canal donde mandar las fichas)
    "discord_enviar_jugadores": True,  # mandar a Discord las fichas de jugadores que busques
    "discord_enviar_recompensas": True,  # y las de los objetivos de recompensa que sean jugadores
    "estado_rsi_al_iniciar": True,  # mirar el estado de los servidores de RSI al arrancar
    "objetivo_bitacora": True,  # anotar en la bitácora cuando fijas un objetivo por voz
    "perfiles_nave": {},  # {"Cutlass Black": {"dinero": False, ...}} avisos distintos según la nave
    "naves_conocidas": [],  # naves en las que te ha visto subir (para los perfiles)
    "carga_scu": 0,  # SCU de bodega por defecto para las rutas (0 = el de tu nave actual)
    # --- v1.2: hologramas de información sobre el juego --------------------
    "holo_activo": True,  # mostrar fichas en holograma sobre el juego
    "holo_opacidad": 0.85,  # 0.2 … 1
    "holo_segundos": 14,  # tiempo en pantalla
    "holo_posicion": "centro-derecha",
    "holo_escala": 1.0,  # tamaño (0.6 … 1.6)
    "holo_jugadores": True,  # al buscar un jugador
    "holo_recompensas": True,  # al aceptar una recompensa sobre un jugador
    "recompensas_buscar": True,  # buscar en RSI el objetivo de cada recompensa (jugador o piloto NPC)
    "holo_planetas": True,  # al pedir información de un planeta, luna o lugar
    "holo_llegadas": True,  # al llegar cerca de un planeta o luna
    "holo_lugares": True,  # al llegar a un lugar planetario (cueva, puesto, base…)
    "holo_traducir": True,  # traducir al español las descripciones (Google Translate o la IA)
    "holo_sonidos": True,  # sonido al encenderse y apagarse (y alerta con los objetivos de captura)
    "holo_volumen": 0.7,
    # v1.2.2: sonido de cada momento (uno de la lista, «archivo» = el tuyo, «ninguno») y su volumen
    "holo_sonido_on": "proyector", "holo_sonido_on_archivo": "", "holo_sonido_on_nombre": "", "holo_sonido_on_vol": 1.0,
    "holo_sonido_off": "proyector", "holo_sonido_off_archivo": "", "holo_sonido_off_nombre": "", "holo_sonido_off_vol": 1.0,
    "holo_sonido_alerta": "sirena", "holo_sonido_alerta_archivo": "", "holo_sonido_alerta_nombre": "", "holo_sonido_alerta_vol": 1.0,
    # v1.2.2: «envía mensaje al chat» (traducido al inglés y escrito en el chat del juego)
    "chat_activo": True,
    "chat_tecla": "f12",  # abre el chat en Star Citizen
    "chat_espera_ms": 450,  # espera tras abrirlo antes de escribir
    "chat_metodo": "escribir",  # escribir (teclas de verdad) | unicode | pegar (portapapeles + Ctrl+V)
    "chat_tecla_ms": 12,  # pausa entre teclas al escribir en el chat
    "chat_tecla_foco": "enter",  # tras abrir el chat, para poder escribir en él (F12 + Intro)
    "chat_tecla_cerrar": "f12",  # tras enviar (Intro), para cerrar el chat (Intro + F12)
    "chat_idioma": "en",  # idioma al que se traduce
    "chat_confirmar": False,  # leer la traducción y esperar «sí» antes de enviarla
    # v1.2.2: ahorro de tokens
    "ahorro_tokens": True,  # historial más corto y resultados de herramientas recortados
    "ahorro_turnos": 6,
    "respuestas_guardadas": True,  # repetir sin IA las respuestas de datos fijos (planetas, naves, armas…)
    "respuestas_locales": True,  # planetas y lugares contestados con VerseGuide, sin IA
    "traduccion_motor": "google",  # google (gratis) | ia
    "traduccion_respaldo_ia": True,  # si Google falla, traducir con la IA
    # v1.2.2: Diccionario de consultas (memoria física que no caduca)
    "diccionario_activo": True,  # consultar el diccionario antes que la IA o internet
    "diccionario_aprender": True,  # guardar en él lo que se aprende en internet
    # --- v1.3: actualizaciones de NOVA AI desde GitHub ---------------------
    "actualizar_programa": True,  # comprobar si hay versión nueva al iniciar y al cerrar
    "actualizar_al_iniciar": True,  # comprobar scmdb.net / UEX / wiki al arrancar
    "datos_canal": "live",  # live o ptu (versión de datos de scmdb)
    "teclas_retardo_ms": 60,
    "solo_si_juego_activo": False,  # solo pulsar teclas si Star Citizen está en primer plano
    "teclas_juego_sync": True,  # leer actionmaps.xml al arrancar
    "actionmaps_ruta": "",  # vacío = autodetectar
    "comandos_auto_juego": True,  # añadir como comandos las acciones con tecla en el juego
    # --- Overlay en el juego ----------------------------------------------
    "overlay_activo": True,
    "overlay_posicion": "arriba-derecha",  # arriba-izquierda | arriba-centro | arriba-derecha | abajo-izquierda | abajo-derecha | centro-derecha
    "overlay_monitor": "1",  # "1" = principal, "2", "3"… o "juego" (el monitor donde esté el juego)
    "overlay_resolucion": "auto",  # auto (detectar) o "1920x1080", "3840x2160"…
    "overlay_tamano": 110,  # píxeles a 1080p (se escala con la resolución)
    "overlay_margen": 40,
    "overlay_solo_juego": True,  # solo visible con Star Citizen en primer plano
    "overlay_reposo": "tenue",  # tenue | oculto
    "overlay_opacidad_reposo": 0.35,
    "overlay_color": "#20b8e8",  # escuchando / pensando / hablando
    "overlay_color_ok": "#39e47a",  # ha entendido
    "overlay_color_busca": "#ffc933",  # buscando en internet
    "overlay_color_error": "#ff3b4e",  # en pausa o no ha entendido
    "overlay_color_memoria": "#a35cff",  # buscando en memoria física (Diccionario de consultas)
    "overlay_color_memoriza": "#f4f7ff",  # memorizando (guardando en el diccionario lo aprendido)
    "overlay_intensidad": 1.0,
}


OLD_WAKE_DEFAULT = ["nova", "oye nova", "hey nova", "noba"]


class Settings:
    """Diccionario de ajustes con guardado atómico y acceso seguro entre hilos."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.data = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        if SETTINGS_FILE.exists():
            try:
                saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                with self._lock:
                    if saved.get("palabras_clave") == OLD_WAKE_DEFAULT:  # versiones anteriores
                        saved["palabras_clave"] = []
                        saved.setdefault("nombre_variantes", ["noba"])
                    for k, v in saved.items():
                        if k == "claves" and isinstance(v, dict):
                            self.data["claves"].update(v)
                        else:
                            self.data[k] = v
            except (OSError, ValueError):
                pass
        self._apply_base()
        # Las claves también se pueden pasar por variables de entorno.
        for prov in PROVIDERS:
            env = os.environ.get(f"{prov.upper()}_API_KEY")
            if env and not self.data["claves"].get(prov):
                self.data["claves"][prov] = env

    def save(self) -> None:
        with self._lock:
            tmp = SETTINGS_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, SETTINGS_FILE)

    def get(self, key, default=None):
        with self._lock:
            return self.data.get(key, default if default is not None else DEFAULTS.get(key))

    def set(self, key, value, save: bool = True) -> None:
        with self._lock:
            self.data[key] = value
        if save:
            self.save()

    # Lo que NO es «tuyo» y se conserva al empezar de cero: dónde está el juego y la traducción.
    KEEP_ON_RESET = ("juego_carpeta", "gamelog_ruta", "actionmaps_ruta", "globalini_ruta", "traduccion_url",
                     "traduccion_instalada", "traduccion_aviso", "dispositivo_entrada", "dispositivo_salida",
                     "discord_webhook")

    def reset(self, keep_keys: bool = True) -> None:
        """Vuelve a los ajustes de fábrica (y a la configuración inicial)."""
        with self._lock:
            keys = copy.deepcopy(self.data.get("claves") or {}) if keep_keys else {}
            kept = {k: self.data[k] for k in self.KEEP_ON_RESET if k in self.data}
            self.data = copy.deepcopy(DEFAULTS)
            self.data.update(kept)
            self.data["claves"].update(keys)
            self.data["asistente_completado"] = False
            self._apply_base(save=False)
        self.save()

    def _apply_base(self, save: bool = True) -> None:
        """Programa base: pone las claves gratuitas de fábrica en los huecos vacíos y la cadena de motores
        recomendada. Se hace una sola vez (y otra si cambian); lo que el usuario cambie después se respeta."""
        if int(self.data.get("base_aplicada") or 0) >= BASE_VERSION:
            return
        keys = read_base_keys()
        with self._lock:
            for prov, key in keys.items():
                if key and not (self.data["claves"].get(prov) or "").strip():
                    self.data["claves"][prov] = key
            self.data["ia_cadena"] = copy.deepcopy(DEFAULTS["ia_cadena"])
            self.data["base_aplicada"] = BASE_VERSION
        if save and SETTINGS_FILE.exists():
            self.save()

    def key_for(self, provider: str) -> str:
        return (self.data.get("claves") or {}).get(provider, "") or ""

"""Nova: une oído, voz, comandos, IA y Game.log."""
from __future__ import annotations

import collections
import logging
import queue
import re
import threading
import time
from typing import Callable

import numpy as np

from . import extras, gamechat, i18n, lang_data
from .commands import CommandBook, _partial, _similarity, normalize, simplify
from .config import Settings
from .gamelog import GameEvent, GameLog, comment_for, find_game_log
from .llm import Brain
from .memory import Memory
from .stt import SpeechToText
from .tools import Tools
from .tts import TextToSpeech
from .verseguide import desc_for
from .wake import strip_wake, wake_names

log = logging.getLogger("nova")

STOP_WORDS = {"silencio", "callate", "calla", "para", "basta", "stop", "cancela", "cancelar", "cierra el pico"}
PAUSE_WORDS = {"desactivate", "pausa", "modo pausa", "a dormir", "apagate", "descansa"}
HALT_WORDS = {"detente", "para todo", "detenlo todo", "deten todo", "cancela todo", "para las busquedas",
              "deten las busquedas", "cancela las busquedas"}
RESUME_WORDS = {"activate", "despierta", "vuelve", "reactivate", "enciendete", "en linea"}
INFO_TOOLS = {"buscar_wiki_star_citizen", "buscar_en_internet", "leer_pagina_web",
              "uex_precios_mercancia", "uex_rutas_comercio", "estado_servidores", "ficha_lugar"}
# «¿Dónde compro un P4-AR?», «¿dónde se vende la Morozov?», «¿dónde puedo conseguir un FR-76?» (texto normalizado)
BUY_RE = re.compile(r"^(?:donde|en que (?:sitio|tienda|lugar|terminal))(?: se)?(?: puedo| podria)?"
                    r" (?:compro|comprar|compra|venden|vende|consigo|conseguir|adquiero|adquirir)"
                    r"(?: un| una| el| la| los| las| unos| unas)? (?P<x>.+)$")
STALE_S = 90  # una orden que lleva más de esto esperando ya no tiene sentido
ASK_LIMIT_S = 75  # tiempo máximo esperando a la IA
NO_DICT_TOOLS = {"ejecutar_comando_nave", "uex_precios_mercancia", "uex_rutas_comercio", "estado_del_juego",
                 "crear_temporizador", "cancelar_temporizador", "listar_temporizadores", "estado_servidores",
                 "estadisticas_piloto", "recordar", "olvidar", "enviar_chat_juego", "buscar_misiones",
                 "abrir_pagina_consulta"}
DICT_TOOLS = {"buscar_datos_juego", "buscar_wiki_star_citizen", "buscar_en_internet", "leer_pagina_web",
              "plano_fabricacion", "donde_minar", "ficha_lugar", "datos_ubicacion"}
YES_WORDS = {"si", "sí", "envialo", "enviar", "vale", "adelante", "ok", "okey", "confirmo", "dale", "si envialo",
             "si por favor", "correcto", "mandalo"}
# «háblame de Daymar», «¿qué es Lorville?», «información de Security Post Kareah»… (texto ya normalizado)
LOCAL_ASK = re.compile(r"^(?:hablame|cuentame(?: algo)?|dime algo|informacion|info|datos|ficha|que sabes|"
                       r"que es|que hay en|como es|describeme|describe|explicame que es)"
                       r"(?: de| del| sobre| acerca de)?(?: la luna| el planeta| la| el| los| las)?\s+(?P<x>.+)$")
# ¿Parece español? (para no mandar a traducir lo que ya está en el idioma del piloto)
SPANISH_HINT = re.compile(r"[áéíóúñ¿¡]|\b(?:el|la|los|las|del|que|en|un|una|por|con|para|su|sus|no|es|está|"
                          r"señor|señora|sin|al|se|lo|le|ya|hay|muy|pero)\b", re.I)
ECHO_TAIL = 0.8  # segundos tras hablar en los que el micrófono sigue sordo (eco de la sala)


def _network_error(e: BaseException) -> bool:
    """¿El fallo fue de conexión (y no «no existe»)?"""
    import requests

    while e is not None:
        if isinstance(e, (requests.ConnectionError, requests.Timeout, ConnectionError, TimeoutError)):
            return True
        e = e.__cause__ or e.__context__
    return False


class Nova:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        i18n.set_lang(settings.get("idioma"))
        self.memory = Memory()
        self.gamelog = GameLog(settings, on_event=self._on_game_event)
        self.commands = CommandBook(settings, gamelog_path_fn=lambda: self.gamelog.path or find_game_log())
        self.tools = Tools(settings, self.commands, self.memory, self.gamelog)
        # Enciclopedia local (juego + scmdb + UEX), diario de la sesión y comprobación de las fuentes al arrancar
        from .diary import Diary
        from .knowledge import Knowledge
        from .updater import Updater

        self.knowledge = Knowledge(self.gamelog.text)
        self.diary = Diary(settings, self.gamelog)
        self.updater = Updater(settings, self.gamelog, self.knowledge)
        self.tools.knowledge = self.knowledge
        self.tools.diary = self.diary
        # v1.1: temporizadores, estadísticas, estado de los servidores de RSI
        from .config import DATA_DIR
        from .stats import Stats
        from .timers import Timers

        self.timers = Timers(on_due=self._timer_due)
        self.stats = Stats(DATA_DIR / "diario" / "estadisticas.json")
        self.status_check = extras.StatusCheck()
        self.tools.timers = self.timers
        self.tools.stats = self.stats
        self.tools.status_check = self.status_check
        self.tools.on_timer_added = self._timer_added
        self._await_handle_until = 0.0  # esperando que escribas el apodo de un jugador
        # v1.2: hologramas con fichas de jugadores, planetas y lugares (verseguide.com)
        from .holo import HoloOverlay
        from .verseguide import VerseGuide

        self.holo = HoloOverlay(settings)
        self.holo.play = self.play_sfx
        self.vg = VerseGuide()
        self._holo_seen: dict[str, float] = {}
        self.last_holo = None  # última ficha mostrada (para la ventana de NOVA)
        self.tools.on_place = self.place_info
        self.tools.on_chat = self._chat_from_ai
        # v1.2.2: ahorro de tokens (traducciones con Google, respuestas guardadas), chat del juego y Discord
        from .answers import AnswerCache
        from .translate import Savings, Translator

        self.savings = Savings(DATA_DIR / "cache" / "ahorro.json")
        self.translator = Translator(settings, None, DATA_DIR / "cache" / "traducciones.json")
        self.translator.on_saved = lambda motor: self.savings.add(
            {"google": "traducciones_google", "guardada": "traducciones_guardadas"}.get(motor, ""))
        self.answers = AnswerCache(DATA_DIR / "cache" / "respuestas.json",
                                   version_fn=lambda: self.knowledge.versions.get("scmdb")
                                   or self.knowledge.versions.get("uex") or "")
        self._gen = 0  # sube al detener a Nova: lo que estuviera en marcha se descarta
        self._await_chat_until = 0.0  # esperando el texto del mensaje para el chat del juego
        self._chat_pending: tuple[str, str] | None = None  # (original, traducido) esperando confirmación
        self._chat_confirm_until = 0.0
        self.discord_last: dict = {}  # último envío a Discord (para la ventana)
        # v1.2.2: Diccionario de consultas, la «memoria física» que no caduca (en la carpeta de datos)
        from .dictionary import FILE_NAME, Dictionary

        self.dictionary = Dictionary(DATA_DIR / FILE_NAME, DATA_DIR / "cache" / "diccionario_meta.json")
        self.tools.dictionary = self.dictionary
        from .starmap import StarMap

        self.starmap = StarMap(DATA_DIR / "cache" / "starmap")
        self.tools.starmap = self.starmap
        from .shops import Shops

        self.shops = Shops(DATA_DIR / "cache")
        self.tools.shops = self.shops
        self._dict_phase = ""  # memoria (morado) | memorizando (blanco)
        self._last_input_at = 0.0  # última orden escrita o con la tecla (para atender antes la más nueva)
        self._dict_phase_until = 0.0
        # v1.3: actualizaciones del programa desde GitHub
        from .selfupdate import Updater

        self.selfupdate = Updater(settings)
        self.selfupdate.on_change = lambda: self.on_ui({"t": "actualizacion"})
        self._update_question_until = 0.0
        self.request_quit: Callable[[], None] = lambda: None  # lo pone nova.py (cerrar NOVA)
        self.open_manual: Callable[[], object] | None = None  # lo pone la ventana (abrir el manual)
        self.on_ui: Callable[[dict], None] = lambda ev: None  # avisos para la ventana (foco, temporizadores…)
        self.brain = Brain(settings, self.tools, self.memory, self.gamelog)
        self.translator.brain = self.brain  # respaldo si Google Translate no responde
        self.stt = SpeechToText(settings)
        self.tts = TextToSpeech(settings)
        self.listener = None
        self.ptt = None

        # Ganchos para la ventana
        self.on_message: Callable[[str, str], None] = lambda who, text: None
        self.on_status: Callable[[str], None] = lambda s: None
        self.brain.on_status = lambda s: self.on_status(s)
        self.tools.on_command = self._on_ai_command
        self.tools.on_tool = self._on_tool

        self._jobs: "queue.Queue[tuple]" = queue.Queue()
        self._follow_up_until = 0.0  # tras "Nova" a secas, la siguiente frase no necesita el nombre
        self._last_comment = 0.0
        self._spoken: collections.deque = collections.deque(maxlen=12)  # (hora, texto) de lo que ha dicho Nova
        self._ptt_held = False
        self._searching = 0
        self._tint = "base"  # green | red: lo que ha pasado con tu última orden
        self._tint_until = 0.0
        self._tint_hold = False
        self.paused = False
        self.training = False  # ventana de configuración inicial abierta: no se atienden órdenes
        self.busy = False
        threading.Thread(target=self._worker, daemon=True, name="nova-worker").start()

    # ------------------------------------------------------------- arranque
    def start_audio(self) -> str | None:
        """Abre micrófono y tecla para hablar. Devuelve un error legible o None."""
        from .audio import Listener
        from .triggers import PushToTalk

        try:
            self.listener = Listener(self.settings, self._on_utterance)
            self.listener.is_suppressed = self._mic_should_be_deaf
            self.listener.start()
        except Exception as e:
            log.exception("Micrófono")
            return f"No pude abrir el micrófono: {e}"
        self.ptt = PushToTalk(self.settings, self._ptt_down, self._ptt_up)
        self.ptt.start()
        self.stt.warm_up()
        return None

    def start_gamelog(self) -> None:
        if not self.gamelog.is_alive():
            self.gamelog.start()

    # ------------------------------------------------------------- estado
    def _mic_should_be_deaf(self) -> bool:
        tts = self.tts
        return tts.speaking or tts.busy() or (time.time() - tts.ended_at < ECHO_TAIL)

    def flash(self, tint: str, seconds: float = 3.5) -> None:
        """Colorea el overlay: 'green' = entendido, 'red' = no entendido."""
        self._tint, self._tint_until, self._tint_hold = tint, time.time() + seconds, False

    def _current_tint(self) -> str:
        now = time.time()
        if self._tint_hold:
            if self.tts.speaking or self.tts.busy():
                self._tint_until = max(self._tint_until, now + 1.5)  # el color dura mientras responde
            else:
                self._tint_hold = False  # terminó de hablar: se apaga 1,5 s después
        return self._tint if now < self._tint_until else "base"

    def state(self) -> tuple[str, float, str]:
        """(modo, nivel de voz 0..1, color) para el overlay y la ventana.
        modo: off | speaking | searching | listening | thinking | idle
        color: base | green (entendido) | yellow (buscando) | red (en pausa / no entendido)"""
        if self.paused:
            return "off", 0.0, "red"
        tint = self._current_tint()
        if self._dict_phase and time.time() < self._dict_phase_until:
            return "searching", 0.0, "purple" if self._dict_phase == "memoria" else "white"
        if self.tts.speaking:
            return "speaking", self.tts.out.level, tint
        if self._searching > 0:
            return "searching", 0.0, "yellow"
        if self._ptt_held or (self.listener and self.listener.capturing) or time.time() < self._follow_up_until:
            return "listening", self.listener.level if self.listener else 0.0, "base"
        if self.busy or self.tts.busy():
            return "thinking", 0.0, tint
        if self.listener is None:  # sin micrófono: Nova no puede oírte
            return "idle", 0.0, "red"
        return "idle", 0.0, tint

    def _on_tool(self, name: str, running: bool) -> None:
        if name in INFO_TOOLS:
            self._searching = max(0, self._searching + (1 if running else -1))

    def _on_ai_command(self, name: str) -> None:
        self.flash("green")
        self.on_message("sistema", f"⚙ {name}")
        cmd = next((c for c in self.commands.commands.values() if c.nombre == name), None)
        if cmd:
            self.log_command(cmd)

    # ------------------------------------------------------------ v1.1
    def _diary_event(self, kind: str, detail: str, **data) -> None:
        try:
            self.diary.on_event(GameEvent(kind, detail, "", time.time(), {k: v for k, v in data.items() if v}))
        except Exception:
            log.exception("Bitácora")

    def log_command(self, cmd) -> None:
        """Comandos marcados con «registrar» (fijar objetivo…) quedan en la bitácora con nave y lugar."""
        if getattr(cmd, "registrar", False) and self.settings.get("objetivo_bitacora", True):
            where = self.gamelog.location if self.gamelog.location not in ("", "desconocida") else ""
            self._diary_event("objetivo", cmd.nombre, x=f"Objetivo fijado ({cmd.nombre})", nave=self.gamelog.ship,
                              lugar=where)

    def _ask_for_handle(self) -> None:
        t = self.settings.get("tratamiento")
        self._await_handle_until = time.time() + extras.WAIT_HANDLE_S
        self.flash("green")
        self.on_ui({"t": "pedir_apodo"})
        self._say(f"Entendido, {t}. Escríbame el apodo del jugador en el cuadro de texto de la cabina, "
                  f"así evitamos errores de pronunciación.")

    def _player_lookup(self, handle: str) -> None:
        t = self.settings.get("tratamiento")
        gen = self._gen
        self.on_message("sistema", f"🔎 Buscando «{handle}» en robertsspaceindustries.com…")
        self._searching += 1
        try:
            c = extras.lookup(handle)
        except Exception:
            self._searching = max(0, self._searching - 1)
            if gen != self._gen:
                return  # se detuvo a Nova mientras buscaba
            self.flash("red")
            self._say(extras.NOT_FOUND)
            return
        self._searching = max(0, self._searching - 1)
        if gen != self._gen:
            return
        self.flash("green")
        self.on_message("ficha", "FICHA DE JUGADOR\n" + c.text())
        self._log_player(c)
        self._send_discord(c, "consulta")
        self._say(extras.spoken(c, t))
        if self.settings.get("holo_jugadores", True):
            self._holo_player(c, "consulta")

    def _send_discord(self, c, motivo: str = "consulta", wait: bool = False) -> None:
        """Manda la ficha al canal de Discord (en segundo plano) y cuenta en la cabina cómo fue."""
        s = self.settings
        if not (s.get("discord_webhook") or "").strip() or not s.get("discord_enviar_jugadores", True):
            return
        if motivo == "recompensa" and not s.get("discord_enviar_recompensas", True):
            return

        def work() -> None:
            sent = extras.send_player_to_discord(s, c, motivo=motivo)
            if not sent:
                return
            self.discord_last = {"ok": sent.startswith("📨"), "texto": sent, "hora": time.time(),
                                 "jugador": c.handle}
            self.on_message("sistema", sent)
            self.on_ui({"t": "discord", **self.discord_last})
        th = threading.Thread(target=work, daemon=True, name="discord")
        th.start()
        if wait:
            th.join(20)

    def _log_player(self, c=None, nota: str = "", kind: str = "jugador_buscado", name: str = "", org: str = "") -> None:
        """Bitácora: (fecha) (hora) (jugador) (organización) en «Busquedas_de_jugadores.log» y,
        si hay una sesión de juego abierta, también en su bitácora."""
        if c is not None:
            name = c.handle + (f" ({c.apodo_juego})" if c.apodo_juego and c.apodo_juego != c.handle
                               and "REDACTED" not in c.apodo_juego.upper() else "")
            o = c.org
            org = "organización oculta" if o.oculta else (f"{o.nombre or o.sid} [{o.sid}]" if (o.sid or o.nombre)
                                                          else "sin organización")
        try:
            line = self.diary.log_player_search(name, org, nota)
            if self.diary.file:
                self._diary_event(kind, line.split(" · ", 2)[-1], x=name)
        except Exception:
            log.exception("Bitácora de jugadores")

    # ------------------------------------------------------------ hologramas (v1.2)
    SFX_KEYS = {"holo_on": "holo_sonido_on", "holo_off": "holo_sonido_off", "alerta": "holo_sonido_alerta"}

    def play_sfx(self, name: str, force: bool = False) -> None:
        """Sonidos de los hologramas (encendido, apagado y alerta de objetivo de captura): el elegido
        en Interfaz › Overlay NOVA AI (de la lista o un archivo tuyo) con su volumen."""
        if not (force or self.settings.get("holo_sonidos", True)):
            return
        from . import sfx
        key = self.SFX_KEYS.get(name)
        if not key:
            return
        s = self.settings
        data = sfx.get(name, s.get(key, ""), s.get(key + "_archivo", ""))
        if data is None:
            return
        try:
            vol = max(0.0, min(1.0, float(s.get("holo_volumen", 0.7)))) * \
                max(0.0, min(1.5, float(s.get(key + "_vol", 1.0))))
            self.tts.out.play_fx(np.clip(data * vol, -1, 1), sfx.RATE)
        except Exception:  # noqa: BLE001 — sin altavoz no pasa nada
            log.debug("Sonido %s", name, exc_info=True)

    def _seen_recently(self, key: str, seconds: float) -> bool:
        now = time.time()
        if now - self._holo_seen.get(key, -1e9) < seconds:
            return True
        self._holo_seen[key] = now
        return False

    def _show_holo(self, card, force: bool = False) -> None:
        self.last_holo = card
        self.on_ui({"t": "holo"})
        self.holo.show(card, force=force)

    def _holo_player(self, c, motivo: str) -> None:
        def work() -> None:
            from .holo import card_player, fetch_image
            try:
                photo = fetch_image(c.avatar) if c.avatar else None
                logo = fetch_image(c.org.logo) if c.org.logo and not c.org.oculta else None
                self._show_holo(card_player(c, motivo, photo, logo))
            except Exception:
                log.exception("Holograma de jugador")
        threading.Thread(target=work, daemon=True, name="holo-jugador").start()

    def _check_bounty(self, ev: GameEvent) -> None:
        """Contrato u objetivo de cazarrecompensas: se busca al objetivo en RSI. Si tiene ficha es un
        jugador (ficha policial en rojo y alarma); si no la tiene, es un piloto NPC."""
        if not self.settings.get("recompensas_buscar", True) or self.paused:
            return
        name = self.gamelog.text.bounty_target((ev.data or {}).get("x", "")) if self.gamelog.text else ""
        if not name or self._seen_recently(f"bounty:{name.lower()}", 600):
            return
        tr = self.settings.get("tratamiento")

        def npc(reason: str = "no tiene ficha en RSI") -> None:
            self.on_message("sistema", f"🎯 Objetivo nuevo: Neutralizar «{name}» · Piloto NPC ({reason})")
            self._log_player(name=name, org="piloto NPC", nota="objetivo de recompensa", kind="objetivo_recompensa")
            if not self.paused:
                self._say(f"{tr}, el objetivo {name} es un piloto NPC.")

        gen = self._gen

        def work() -> None:
            from .rsi import HANDLE_RE
            if " " in name.strip() or not HANDLE_RE.match(name.strip()):
                npc()  # los apodos de RSI no llevan espacios: es un personaje del juego
                return
            self.on_message("sistema", f"🎯 Objetivo nuevo: Neutralizar «{name}» · buscando su ficha en RSI…")
            try:
                c = extras.lookup(name)
            except Exception as e:  # noqa: BLE001
                if gen != self._gen:
                    return
                if _network_error(e):
                    self.on_message("sistema", f"⚠ No pude consultar RSI para «{name}» (sin conexión).")
                    return
                npc()
                return
            if gen != self._gen:
                return  # se detuvo a Nova mientras buscaba
            self.on_message("ficha", "OBJETIVO DE RECOMPENSA\n" + c.text())
            self._log_player(c, "objetivo de recompensa", "objetivo_recompensa")
            self._send_discord(c, "recompensa")
            if self.settings.get("holo_recompensas", True):
                self._holo_player(c, "recompensa")
            if not self.paused:
                org = c.org.nombre or c.org.sid
                self._say(f"Atención, {tr}: el objetivo de la recompensa es un jugador, {c.handle}"
                          + (f", de la organización {org}" if org and not c.org.oculta else "")
                          + ". Ficha en el overlay.")
        threading.Thread(target=work, daemon=True, name="recompensa").start()

    def _check_body(self, ev: GameEvent) -> None:
        """Llegas cerca de un planeta, luna o lugar planetario: su ficha de VerseGuide en holograma."""
        from .verseguide import resolve_body

        s = self.settings
        if self.paused or not (s.get("holo_llegadas", True) or s.get("holo_lugares", True)):
            return
        data = ev.data or {}
        raw, place_name = data.get("raw", ""), data.get("lugar") or data.get("x") or ""
        hit = resolve_body(raw) or resolve_body(place_name)
        if not hit:
            return
        body_key = f"body:{hit[0]}/{hit[1]}"
        if ev.kind == "cerca_de_cuerpo" and body_key in self._holo_seen:
            return

        def work() -> None:
            try:
                b = self.vg.body(hit[0], hit[1])
            except LookupError as e:
                log.info("VerseGuide: %s", e)
                return
            place = None
            if s.get("holo_lugares", True) and place_name and ev.kind in ("ubicacion", "llegada_cuantica"):
                place = b.find_place(place_name.split("(")[0])
            if place and not self._seen_recently(f"place:{b.codigo}:{place.nombre}", 1800):
                self._translate(b, place)
                from .holo import card_place
                self._show_holo(card_place(b, place, self._texture(b)))
                self.on_message("sistema", f"📍 {place.nombre} ({b.nombre}): ficha en el overlay")
                return
            if s.get("holo_llegadas", True) and not self._seen_recently(body_key, 1800):
                self._translate(b)
                from .holo import card_body
                self._show_holo(card_body(b, self._texture(b)))
                self.on_message("sistema", f"🪐 {b.nombre}: ficha en el overlay")
        threading.Thread(target=work, daemon=True, name="holo-cuerpo").start()

    def _texture(self, b):
        from .holo import fetch_image
        return fetch_image(b.imagen) if b.imagen else None

    def _translate(self, b, place=None) -> None:
        """Descripciones de VerseGuide (en inglés) al español con Google Translate (gratis) o, si falla,
        con la IA; se guardan en la caché y no se vuelven a traducir."""
        if not self.settings.get("holo_traducir", True):
            return
        changed = False
        lang = i18n.lang()
        for obj in ((place,) if place else ()) + (b,):
            if lang != "es":  # v1.3: inglés = la original; catalán, francés y alemán se traducen (caché)
                if lang == "en" or obj is None or not obj.descripcion or len(obj.descripcion) < 12:
                    continue
                dl = getattr(obj, "desc_l", None)
                if not (dl and dl[0] == lang):
                    tr, _motor = self.translator.translate(obj.descripcion[:1500], lang, "en")
                    if tr:
                        obj.desc_l = (lang, tr.strip().strip('"'))
                continue
            if obj is None or obj.descripcion_es or not obj.descripcion or len(obj.descripcion) < 12:
                continue
            es, _motor = self.translator.translate(obj.descripcion[:1500], "es", "en", use_cache=False)
            if es:
                obj.descripcion_es = es.strip().strip('"')
                changed = True
        if changed:
            self.vg.save(b)

    def place_info(self, nombre: str, _hit=None) -> str:
        """Herramienta de la IA: ficha de un planeta, luna o lugar planetario (y holograma)."""
        from .holo import card_body, card_place
        from .verseguide import place_text

        if _hit is not None:
            b, place = _hit
            self._translate(b, place)
            text = place_text(b, place) if place else b.texto()
            self.on_message("ficha", ("LUGAR PLANETARIO\n" if place else "CUERPO CELESTE\n") + text)
            if self.settings.get("holo_planetas", True):
                tex = self._texture(b)
                self._show_holo(card_place(b, place, tex) if place else card_body(b, tex))
            return text
        system = ""
        for key in ("PYRO", "NYX", "STANTON"):
            if key.lower() in (self.gamelog.location or "").lower() or key.lower() in (self.gamelog.shard or "").lower():
                system = key
                break
        try:
            hit = self.vg.find(nombre, system_hint=system)
        except LookupError as e:
            return f"SIN DATOS: no pude leer verseguide.com ({e})."
        if not hit:
            return f"SIN DATOS: no encuentro «{nombre}» en verseguide.com."
        b, place = hit
        self._translate(b, place)
        text = place_text(b, place) if place else b.texto()
        self.on_message("ficha", ("LUGAR PLANETARIO\n" if place else "CUERPO CELESTE\n") + text)
        if self.settings.get("holo_planetas", True):
            tex = self._texture(b)
            self._show_holo(card_place(b, place, tex) if place else card_body(b, tex))
        return text + "\n(La ficha ya está en pantalla y en el overlay.)"

    def _timer_added(self, t: dict) -> None:
        hora = time.strftime("%H:%M", time.localtime(t["fin"]))
        self._diary_event("temporizador_nuevo", t["motivo"], x=t["motivo"], hora=hora, lugar=t.get("lugar"))
        self.on_ui({"t": "timers"})

    def _timer_due(self, t: dict, late: bool) -> None:
        tr = self.settings.get("tratamiento")
        where = f" en {t['lugar']}" if t.get("lugar") else ""
        icon = {"refinado": "⚗", "contrato": "📜"}.get(t.get("tipo"), "⏰")
        self.on_message("sistema", f"{icon} Temporizador terminado: {t['motivo']}{where}"
                        + (" (terminó mientras estaba cerrada)" if late else ""))
        self._diary_event("temporizador_fin", t["motivo"], x=t["motivo"], lugar=t.get("lugar"))
        self.on_ui({"t": "timers"})
        if self.paused or self.training:
            return
        self.flash("green", 6)
        if late:
            self._say(f"{tr}, mientras estaba apagada terminó: {t['motivo']}{where}.")
        elif t.get("tipo") == "refinado":
            self._say(f"{tr}, el refinado ya está listo: {t['motivo']}{where}.")
        else:
            self._say(f"{tr}, aviso de temporizador: {t['motivo']}{where}.")

    # ------------------------------------------------------------ actualizaciones (v1.3)
    @staticmethod
    def _update_answer(norm: str) -> str:
        if "al cerrar" in norm or "cuando cierre" in norm or "luego" in norm or "despues" in norm:
            return "al_cerrar"
        if norm in ("no", "ahora no", "no gracias", "no actualices", "mejor no") or norm.startswith("no "):
            return "no"
        if norm in ("si", "vale", "venga", "adelante", "actualiza", "actualizala", "si actualiza", "actualiza ahora",
                    "si actualiza ahora", "si por favor", "dale") or norm.startswith("si "):
            return "ahora"
        return ""

    def check_update(self, announce: bool = True) -> None:
        """Al iniciar: ¿hay versión nueva en GitHub? Si la hay, pregunta (ventana + voz)."""
        from .selfupdate import is_dev_copy

        if not self.settings.get("actualizar_programa", True) or is_dev_copy():
            return
        info = self.selfupdate.check()
        if not info:
            return
        self.on_message("sistema", f"⬆ Nueva versión {info['texto']} de NOVA AI disponible en GitHub.")
        self.on_ui({"t": "actualizacion", "preguntar": True})
        if announce and not self.paused and not self.training:
            self._update_question_until = time.time() + 120
            self._say(f"Se ha detectado una nueva versión {info['texto'].lstrip('v')} de NOVA AI. "
                      f"¿Quiere actualizar ahora? Puede decirme sí, no o al cerrar la aplicación.")

    def update_choice(self, choice: str) -> str:
        """«ahora» · «no» · «al_cerrar». Devuelve un texto para la ventana."""
        up = self.selfupdate
        self._update_question_until = 0.0
        up.choice = choice
        tr = self.settings.get("tratamiento")
        if choice == "no":
            self._say(f"Entendido, {tr}. Seguimos con esta versión.")
            self.on_ui({"t": "actualizacion"})
            return "Seguimos con esta versión"
        if choice == "al_cerrar":
            self._say(f"De acuerdo, {tr}. La instalaré cuando cierre la aplicación.")
            threading.Thread(target=self._predownload, daemon=True, name="descarga-actualizacion").start()
            return "Se instalará al cerrar NOVA"
        # ahora
        self._say(f"Descargando la nueva versión, {tr}. Windows le pedirá permiso para instalarla.")

        def work() -> None:
            try:
                up.download()
            except RuntimeError as e:
                self.on_message("sistema", f"⚠ No se pudo descargar la actualización: {e}")
                self._say(f"No he podido descargar la actualización, {tr}. Lo intentaré al cerrar.")
                up.choice = "al_cerrar"
                return
            if up.launch(relaunch=True):
                self.on_message("sistema", "⬆ Instalando la nueva versión. NOVA se cierra y volverá a abrirse sola.")
                time.sleep(1.5)
                self.request_quit()
            else:
                self.on_message("sistema", "⚠ No se pudo abrir el instalador. Puedes descargarlo de GitHub.")
        threading.Thread(target=work, daemon=True, name="actualizar-ahora").start()
        return "Descargando…"

    def _predownload(self) -> None:
        try:
            self.selfupdate.download()
        except RuntimeError as e:
            log.info("Actualización: %s (se reintentará al cerrar)", e)

    def update_on_close(self) -> None:
        """Al cerrar: instala si lo pediste «al cerrar»; si no, comprueba y pregunta (ventana de Windows)."""
        from .selfupdate import ask_native, is_dev_copy

        up = self.selfupdate
        if not self.settings.get("actualizar_programa", True) or is_dev_copy():
            return
        if up.choice == "ahora":
            return  # ya se abrió el instalador
        if up.choice != "al_cerrar":
            if up.choice == "no":
                return  # ya dijiste que no en esta sesión: no insistir
            info = up.check(timeout=5) if up.state not in ("disponible", "listo") else up.latest
            if not info or up.state not in ("disponible", "listo"):
                return
            if not ask_native(info["texto"]):
                return
        try:
            up.download()
        except RuntimeError as e:
            log.warning("Actualización al cerrar: %s", e)
            return
        up.launch(relaunch=False)

    def start_extras(self) -> None:
        """Al arrancar: temporizadores pendientes, estado de los servidores de RSI y versión nueva."""
        self.timers.on_change = lambda: self.on_ui({"t": "timers"})
        self.timers.start()
        threading.Thread(target=self.check_update, daemon=True, name="buscar-version").start()
        threading.Thread(target=self._dictionary_boot, daemon=True, name="diccionario").start()
        if self.settings.get("estado_rsi_al_iniciar", True):
            threading.Thread(target=self._boot_status, daemon=True, name="estado-rsi").start()

    def _boot_status(self) -> None:
        st = self.status_check.run()
        self.on_ui({"t": "estado_rsi"})
        if st.get("error") or st.get("ok") is None:
            self.on_message("sistema", "⚠ No pude consultar el estado de los servidores de RSI.")
            return
        if st.get("ok") and not st.get("avisos"):
            self.on_message("sistema", "✓ Servidores de RSI: todo operativo.")
            return
        text = self.status_check.text()
        self.on_message("sistema", "📡 " + text.replace("\n", " · "))
        if not (self.paused or self.training):
            caidos = [k for k, v in (st.get("componentes") or {}).items() if v != "Operational"]
            tr = self.settings.get("tratamiento")
            if caidos:
                self._say(f"{tr}, la página de estado de RSI indica problemas en: {', '.join(caidos)}. "
                          f"Tiene los detalles en la cabina.")
            else:
                self._say(f"{tr}, hay avisos en la página de estado de RSI. Se los dejo en la cabina.")

    @property
    def name(self) -> str:
        return self.settings.get("nombre_asistente") or "Nova"

    def set_paused(self, paused: bool) -> None:
        """Detener (o reactivar) a Nova. Al detenerla se cancelan las búsquedas y lo que estuviera
        pensando, se calla, se quita el holograma y se vacía la cola; solo responde a «Nova, actívate»."""
        was = self.paused
        self.paused = paused
        if paused:
            self._gen += 1
            self.brain.cancel()
            self.tts.stop()
            self._drain_jobs()
            self._searching = 0
            self._await_handle_until = self._await_chat_until = self._chat_confirm_until = 0.0
            self._chat_pending = None
            self._follow_up_until = 0.0
            try:
                self.holo.dismiss()
            except Exception:  # noqa: BLE001
                log.debug("Ocultar holograma", exc_info=True)
        self.on_ui({"t": "detenida" if paused else "activa"})
        if paused == was:
            return
        self.on_message("sistema", f"⏹ {self.name} detenida: búsquedas canceladas. Vuelve con el interruptor "
                                   f"de la cabina o diciendo «{self.name}, actívate»."
                        if paused else f"▶ {self.name} activa.")

    def _drain_jobs(self) -> None:
        while True:
            try:
                self._jobs.get_nowait()
            except queue.Empty:
                return

    # -------------------------------------------------------------- eventos
    def _ptt_down(self) -> None:
        self.tts.stop()  # pulsar para hablar interrumpe a Nova
        self._ptt_held = True
        if self.listener:
            self.listener.ptt_down()
        self.on_status("🎙 Escuchando…")

    def _ptt_up(self) -> None:
        self._ptt_held = False
        if self.listener:
            self.listener.ptt_up()
        self.on_status("")

    def _on_utterance(self, audio: np.ndarray, source: str) -> None:
        if self.training:  # durante el entrenamiento el micrófono lo usa la ventana de configuración
            return
        if source == "ptt":
            self._last_input_at = time.time()
        self._jobs.put(("audio", audio, source, time.time()))

    def submit_text(self, text: str) -> None:
        """Texto escrito en la ventana: igual que si lo hubiera dicho por voz."""
        self._last_input_at = time.time()
        self._jobs.put(("text", text, "texto", time.time()))

    def _on_game_event(self, ev: GameEvent) -> None:
        label = ev.kind.replace("_", " ")
        self.on_message("juego", f"📡 {label}: {ev.detail}" if ev.detail else f"📡 {label}")
        if ev.kind == "nave_subes" and not ev.replay:
            extras.remember_ship(self.settings, (ev.data or {}).get("nave", ""))
        if not ev.replay and not self.training:
            if ev.kind in ("contrato_aceptado", "objetivo_nuevo"):
                self._check_bounty(ev)
            elif ev.kind in ("llegada_cuantica", "ubicacion", "jurisdiccion", "cerca_de_cuerpo"):
                self._check_body(ev)
        if self.paused or self.training or not ev.category or not self.settings.get("gamelog_comentarios"):
            return
        # Perfil de la nave en la que vas: cada nave puede tener sus propios avisos.
        if not extras.ship_alerts(self.settings, self.gamelog.ship).get(ev.category, True):
            return
        self._jobs.put(("event", ev, "juego", time.time()))  # en cola: no se pierde aunque Nova esté ocupada

    # --------------------------------------------------------------- trabajo
    def _worker(self) -> None:
        while True:
            job = self._jobs.get()
            kind, payload, source = job[:3]
            queued = job[3] if len(job) > 3 else time.time()
            self.busy = True
            gen = self._gen
            try:
                if kind in ("audio", "text") and time.time() - queued > STALE_S:
                    log.info("Orden descartada: llevaba %.0f s esperando", time.time() - queued)
                    self.on_message("sistema", "⌛ Descarto una orden que llevaba demasiado tiempo esperando.")
                elif kind == "audio":
                    self.on_status("Transcribiendo…")
                    text = self.stt.transcribe(payload)
                    self.on_status("")
                    if text and gen != self._gen and not self.paused:
                        pass  # se detuvo y reactivó mientras transcribía: lo dicho antes ya no vale
                    elif text:
                        self._handle(text, source)
                    elif source == "ptt" and not self.paused:
                        # Pulsaste la tecla y habló, pero no se entendió nada.
                        self.flash("red")
                        self._say(f"Perdone, {self.settings.get('tratamiento')}, no le he entendido.")
                elif kind == "text":
                    self._handle(payload, source)
                elif kind == "event":
                    if time.time() - payload.when < 45:  # un aviso viejo ya no tiene sentido
                        self._comment(payload)
            except Exception as e:
                log.exception("Error procesando")
                self.flash("red")
                self.on_message("sistema", f"Error: {e}")
            finally:
                self.busy = False
                self.on_status("")

    def _wake_names(self) -> list[str]:
        return wake_names(self.settings)

    def _strip_wake(self, text: str) -> str | None:
        """Si la frase empieza (o casi) por el nombre, devuelve el resto; si no, None.
        Tolera que Whisper oiga 'Noba' o 'Nóva' y aprende cómo te oye en el entrenamiento."""
        return strip_wake(text, self._wake_names())

    def is_own_echo(self, text: str) -> bool:
        """¿Lo que ha oído el micrófono es Nova hablando por los altavoces?"""
        heard = simplify(text)
        if len(heard) < 6:
            return False
        now = time.time()
        for when, said in list(self._spoken):
            if now - when < 45 and _partial(heard, said) >= 78:
                return True
        return False

    def _handle(self, text: str, source: str) -> None:
        if source == "vad":  # escucha continua: hace falta decir "Nova"
            if self.is_own_echo(text):
                log.info("Ignorado (es mi propia voz): %s", text)
                return
            rest = self._strip_wake(text)
            if rest is None:
                if time.time() > self._follow_up_until:
                    log.debug("Ignorado (sin palabra clave): %s", text)
                    return
                rest = text
            if not rest.strip():
                self._follow_up_until = time.time() + 8
                self.on_message("tú", text)
                self._say(f"¿Sí, {self.settings.get('tratamiento')}?")
                return
            text = rest
        self._follow_up_until = 0
        norm = normalize(text, tuple(self._wake_names()))

        if self.paused:  # en pausa solo se escucha la orden de volver
            if norm in RESUME_WORDS or norm in lang_data.words(lang_data.RESUME, i18n.lang()):
                self.on_message("tú", text)
                self.set_paused(False)
                self.flash("green")
                self._say(f"De vuelta en línea, {self.settings.get('tratamiento')}.")
            return
        self.on_message("tú", text)
        lang = i18n.lang()
        if lang != "es":  # órdenes fijas dichas en otro idioma → su forma en español
            canon = lang_data.canonical(norm, lang)
            if canon:
                text, norm = canon, canon
        if (norm in PAUSE_WORDS or norm in HALT_WORDS or norm in lang_data.words(lang_data.PAUSE, lang)
                or norm in lang_data.words(lang_data.HALT, lang)):
            self.set_paused(True)
            self._say(f"Detenida, {self.settings.get('tratamiento')}. Diga «{self.name}, actívate» para volver.")
            return
        # Mensaje para el chat del juego (esperando el texto o la confirmación)
        if self._chat_followup(text):
            return
        if norm in STOP_WORDS or norm in lang_data.words(lang_data.STOP, lang):
            self.tts.stop()
            return
        if norm in ("olvida la conversacion", "borra la conversacion", "nueva conversacion"):
            self.memory.clear_history()
            self._say(f"Conversación olvidada. Empezamos de cero, {self.settings.get('tratamiento')}.")
            return

        # Respuesta a «¿Quieres actualizar ahora?» (también se puede contestar en la ventana)
        if time.time() < self._update_question_until:
            answer = self._update_answer(norm)
            if answer:
                self.update_choice(answer)
                return

        # 0) «¿Quién eres?», «Preséntate», «¿Para qué sirves?»: la presentación de NOVA AI (sin IA)
        from . import intro
        from .config import VERSION
        if self.open_manual and re.match(r"^(?:abre(?:me)?|ensename|muestrame|consulta|quiero ver|pon(?:me)?|"
                                         r"donde esta) (?:el |tu )?manual(?: de usuario| de nova(?: ai)?)?$", norm):
            try:
                self.open_manual()
                self._say(f"Le abro el manual en el navegador, {self.settings.get('tratamiento')}.")
            except Exception as e:  # noqa: BLE001
                self._say(f"No he podido abrir el manual: {e}")
            return
        if intro.is_who(norm) or intro.is_what(norm):
            t = self.settings.get("tratamiento")
            shown, spoken = (intro.who(self.name, VERSION, t) if intro.is_who(norm)
                             else intro.what(self.name, t, lang=i18n.lang()))
            if i18n.lang() != "es":  # se traduce aquí para decirlo bien (Ozzyto deletreado en su idioma)
                shown = self._loc(shown)
                spoken = intro.speakable(shown, i18n.lang())
                self.flash("green")
                self.memory.add_turn("user", text)
                self.memory.add_turn("assistant", shown)
                self.memory.save()
                self._say(shown, spoken=spoken, translated=True)
                return
            self.flash("green")
            self.memory.add_turn("user", text)
            self.memory.add_turn("assistant", shown)
            self.memory.save()
            self._say(shown, spoken=spoken)
            return

        # 0) «Envía mensaje al chat»: traducido al inglés y escrito en el chat de Star Citizen.
        if self.settings.get("chat_activo", True):
            stripped = self._strip_wake(text)
            is_chat, msg = gamechat.parse(stripped if stripped is not None else text)
            if is_chat:
                if msg:
                    self._chat_prepare(msg)
                else:
                    self._await_chat_until = time.time() + gamechat.CHAT_WAIT_S
                    self._follow_up_until = time.time() + 30
                    self.flash("green")
                    self.on_ui({"t": "pedir_chat"})
                    self._say(f"¿Qué mensaje envío al chat, {self.settings.get('tratamiento')}?")
                return

        # 0) Buscar un jugador en la web de RSI: el apodo se escribe (por voz se entendería mal).
        if source == "texto" and time.time() < self._await_handle_until:
            self._await_handle_until = 0.0
            if extras.looks_like_handle(text):
                self._player_lookup(extras.clean_handle(text))
                return
        if extras.is_lookup(norm):
            handle = extras.handle_in(text) if source == "texto" else ""
            if handle:
                self._player_lookup(handle)
            else:
                self._ask_for_handle()
            return

        # 1) Frase de comando conocida: al instante, sin IA (teniendo en cuenta la nave en la que vas).
        cmd = self.commands.match(text, tuple(self._wake_names()), ship=self.gamelog.ship)
        if cmd:
            self.flash("green")
            self.on_message("sistema", f"⚙ {cmd.nombre}")
            self.commands.execute(cmd)
            self.log_command(cmd)
            self._say(self.commands.response_for(cmd), translated=self.commands.localized(cmd))
            return

        # 2) Ahorro de tokens: planetas y lugares con VerseGuide (con holograma), el Diccionario de consultas
        #    (memoria física; si no está, lo aprende en internet) y las respuestas ya guardadas, sin IA.
        if self._buy_answer(text, norm):
            return
        learn_subject = self._dictionary_answer(text)
        if learn_subject is True:
            return
        if self._local_answer(text):
            return
        wake = tuple(self._wake_names())
        if self.settings.get("respuestas_guardadas", True):
            saved = self.answers.get(text, wake)
            if saved:
                self.savings.add("respuestas_guardadas")
                self.flash("green")
                self.memory.add_turn("user", text)
                self.memory.add_turn("assistant", saved)
                self.memory.save()
                self._say(saved, model="respuesta guardada")
                return

        # 3) Todo lo demás: la IA (puede usar herramientas y comandos). Solo abre el navegador si se lo pides.
        self.tools.allow_open = self._asked_to_open(norm)
        gen = self._gen
        reply = self._ask_brain(text)
        if reply is None or gen != self._gen:
            return  # se detuvo a Nova, o llegó una orden nueva mientras pensaba
        self.flash("green" if self.brain.last_ok else "red")
        if self.brain.last_ok and not self.brain.last_invented and self.settings.get("respuestas_guardadas", True):
            self.answers.put(text, reply, self.brain.last_tools, wake)
        if isinstance(learn_subject, str) and self.brain.last_ok and not self.brain.last_invented \
                and not set(self.brain.last_tools) & NO_DICT_TOOLS and len(reply) > 20:
            learned = reply
            if i18n.lang() != "es":  # el Diccionario de consultas va siempre en español
                learned = self.translator.translate(reply, "es", i18n.lang())[0] or reply
            self._memorize(learn_subject, learned, "Otros (aprendido en internet)", "ia")
        self._say(reply, model=self.brain.last_model)

    def _asked_to_open(self, norm: str) -> bool:
        """¿Ha pedido abrir una página? («ábrela», «abre el buscador»… o «sí» justo después de ofrecérsela)."""
        if re.search(r"\b(abre\w*|abrir\w*|open|obre\w*|ouvre\w*|offne\w*|oeffne\w*)\b", norm):
            return True
        last = next((m.get("content", "") for m in reversed(self.memory.recent(1)) if m.get("role") == "assistant"), "")
        return bool(re.match(r"^(si|vale|ok|okey|claro|venga|adelante|yes|oui|ja|d acord)\b", norm)) and "abr" in last.lower()

    def _buy_answer(self, text: str, norm: str) -> bool:
        """«¿Dónde compro un P4-AR?»: tiendas y precios de UEX, dichos en voz alta, sin IA ni navegador."""
        from . import shops as SH
        m = BUY_RE.match(norm)
        if not m:
            return False
        what = m.group("x").strip()
        if len(what) < 2:
            return False
        self._searching += 1
        try:
            hit = self.shops.find_item(what)
            places = self.shops.where(hit[0]) if hit else None
        except LookupError as e:
            log.info("UEX tiendas: %s", e)
            return False  # sin conexión: que conteste la IA con lo que sepa
        finally:
            self._searching = max(0, self._searching - 1)
        if not hit:
            return False  # no está en UEX: la IA busca en otras fuentes
        shown, spoken = SH.summary(hit[1], places, self.settings.get("tratamiento"))
        self.on_message("ficha", shown)
        self.savings.add("respuestas_locales")
        self.flash("green")
        self.memory.add_turn("user", text)
        self.memory.add_turn("assistant", spoken)
        self.memory.save()
        self._say(spoken, model="UEX Corp")
        return True

    def _ask_brain(self, text: str) -> str | None:
        """La IA en un hilo aparte: si mientras piensa le das una orden nueva (tecla o texto), deja la
        anterior y atiende la nueva; si tarda demasiado, lo dice. None = respuesta descartada."""
        box: dict = {}
        started = time.time()

        def run() -> None:
            try:
                box["r"] = self.brain.ask(text)
            except Exception as e:  # noqa: BLE001
                box["e"] = e
        th = threading.Thread(target=run, daemon=True, name="ia")
        th.start()
        while th.is_alive():
            th.join(0.1)
            if not th.is_alive():
                break
            now = time.time()
            if self._last_input_at > started + 0.5 and now - started > 1.0:
                self.brain.cancel()
                self.on_message("sistema", "↪ Dejo la pregunta anterior para atender la nueva.")
                return None
            if self.paused:
                return None
            if now - started > ASK_LIMIT_S:
                self.brain.cancel()
                self.flash("red")
                self.on_message("sistema", "⌛ Los motores de IA tardan demasiado en responder.")
                self._say(f"Mis motores de IA no responden a tiempo, {self.settings.get('tratamiento')}. "
                          f"Pruebe de nuevo en un momento.")
                return None
        if "e" in box:
            raise box["e"]
        return box.get("r", "")

    # ------------------------------------------------------- chat del juego (v1.2.2)
    def _chat_followup(self, text: str) -> bool:
        """El mensaje que pediste, o la confirmación de enviarlo. True si lo ha gestionado."""
        now = time.time()
        tr = self.settings.get("tratamiento")
        if self._chat_pending and now < self._chat_confirm_until:
            original, translated = self._chat_pending
            self._chat_pending, self._chat_confirm_until = None, 0.0
            if re.sub(r"[^a-z ]", "", normalize(text, tuple(self._wake_names()))).strip() in (
                    YES_WORDS | lang_data.words(lang_data.YES, i18n.lang())):
                self._chat_type(original, translated, "")
            else:
                self.on_message("sistema", "💬 Mensaje al chat cancelado.")
                self._say(f"Cancelado, {tr}.")
            return True
        if now < self._await_chat_until:
            self._await_chat_until = 0.0
            if gamechat.is_cancel(text):
                self.on_message("sistema", "💬 Mensaje al chat cancelado.")
                self._say(f"Cancelado, {tr}.")
                return True
            stripped = self._strip_wake(text)
            self._chat_prepare(gamechat.clean(stripped if stripped else text))
            return True
        return False

    def _chat_from_ai(self, msg: str) -> str:
        msg = gamechat.clean(msg)
        if not msg:
            return "Mensaje vacío."
        self._chat_prepare(msg)
        return "Hecho: el mensaje se traduce y se escribe en el chat del juego. Confírmalo en pocas palabras."

    def _chat_prepare(self, msg: str) -> None:
        tr = self.settings.get("tratamiento")
        target = self.settings.get("chat_idioma", "en") or "en"
        src = i18n.lang()
        if target in ("", "es") and src == "es" or target == src:  # mismo idioma: tal cual
            translated, motor = msg, ""
        else:
            self.on_message("sistema", f"💬 Traduciendo «{msg}»…")
            translated, motor = self.translator.translate(msg, target or "es", src)
        translated = gamechat.clean(translated)
        if not translated:
            self.flash("red")
            self.on_message("sistema", "⚠ No pude traducir el mensaje (sin conexión con Google Translate ni con la IA).")
            self._say(f"No he podido traducir el mensaje, {tr}.")
            return
        if self.settings.get("chat_confirmar", False):
            self._chat_pending = (msg, translated)
            self._chat_confirm_until = time.time() + 30
            self._follow_up_until = time.time() + 30
            self.on_message("sistema", f"💬 «{translated}» · ¿Lo envío? (sí / no)")
            self._say(f"Voy a enviar: {translated}. ¿Lo envío, {tr}?")
            return
        self._chat_type(msg, translated, motor)

    def _chat_type(self, original: str, translated: str, motor: str) -> None:
        """Escribe en el chat del juego (en un hilo: si el juego no está delante, espera hasta 15 s)."""
        tr = self.settings.get("tratamiento")
        gen = self._gen
        engine = {"google": "Google Translate", "ia": "IA", "guardada": "traducción guardada"}.get(motor, "")

        def work() -> None:
            from . import keys
            if self.settings.get("solo_si_juego_activo") and not keys.game_in_foreground():
                self.on_message("sistema", "💬 Vuelve a Star Citizen: lo escribo en cuanto el juego esté delante (15 s).")
                end = time.time() + 15
                while time.time() < end and not keys.game_in_foreground() and gen == self._gen:
                    time.sleep(0.25)
                time.sleep(0.4)
            if gen != self._gen:
                return
            err = gamechat.send_to_game(translated, self.settings)
            if err:
                self.flash("red")
                self.on_message("sistema", f"⚠ No pude escribir en el chat: {err}")
                self._say(f"No he podido enviarlo, {tr}: {err}")
                return
            self.flash("green")
            self.on_message("sistema", f"💬 Enviado al chat: «{translated}»   (de «{original}»"
                                       + (f" · {engine})" if engine else ")"))
            self._diary_event("chat_enviado", f"«{translated}» (de «{original}»)", x=translated)
        threading.Thread(target=work, daemon=True, name="chat-juego").start()

    # ------------------------------------------------- Diccionario de consultas (v1.2.2)
    def _dict_set(self, phase: str, seconds: float = 30.0) -> None:
        self._dict_phase, self._dict_phase_until = phase, time.time() + seconds

    def _dictionary_boot(self) -> None:
        """Crea el diccionario si no existe (y avisa) y lo rellena con los textos oficiales del juego; si el
        global.ini cambia (parche o traducción nueva), se actualizan sus entradas sin tocar las tuyas."""
        from .dictionary import CREATED_MSG
        d = self.dictionary
        try:
            if not d.exists():
                d.save()  # se crea ya (vacío) y se rellena en cuanto estén los textos del juego
                self.on_message("sistema", "📖 " + CREATED_MSG)
                if not (self.paused or self.training):
                    self._say(CREATED_MSG)
            end = time.time() + 600
            while time.time() < end and not (self.gamelog.text and self.gamelog.text.entries):
                time.sleep(5)
            self._dictionary_refresh()
        except Exception:
            log.exception("Diccionario de consultas")

    def _patch(self) -> str:
        v = self.knowledge.versions.get("scmdb") or self.knowledge.versions.get("uex") or ""
        m = re.match(r"(\d+\.\d+(?:\.\d+)?)", v or "")
        return m.group(1) if m else ""

    def _dictionary_refresh(self, force: bool = False) -> int:
        text = self.gamelog.text
        if not (text and text.entries):
            return 0
        d = self.dictionary
        try:
            st = text.path.stat() if text.path else None
        except OSError:
            st = None
        sig = f"{text.path}|{st.st_mtime if st else 0}|{st.st_size if st else 0}|{self._patch()}|{bool(self.knowledge.ore_places)}"
        if not force and d.meta_get("global_ini") == sig and d.exists() and d.count():
            return 0
        n = d.seed_from_game(text.entries, self._patch(), self.knowledge.ores or None,
                             self.knowledge.ore_places or None)
        d.meta_set("global_ini", sig)
        if n:
            log.info("Diccionario: %s entradas del juego", n)
            self.on_ui({"t": "diccionario"})
        return n

    def _dictionary_answer(self, text: str):
        """True si ha contestado con el diccionario (o lo ha aprendido en internet). Si no, devuelve el tema
        (para memorizar lo que conteste la IA) o None si la frase no es una consulta."""
        from . import dictionary as D
        if not self.settings.get("diccionario_activo", True):
            return None
        plain = D.norm(normalize(text, tuple(self._wake_names())))
        force = False
        m = D.UPDATE_RE.match(plain)
        if m:
            force = True
        else:
            m = D.LOOKUP_RE.match(plain)
        if not m:
            return None
        subject = re.sub(r"\b(por favor|porfa|ahora|anda)\b", " ", m.group("x")).strip()
        if subject in ("ti", "mi", "ti misma", "ti mismo", "eso", "esto", "ello", "nada", "todo") or \
                D.norm(subject) in {D.norm(w) for w in self._wake_names()}:
            return None
        if not subject or len(subject) < 2 or len(subject.split()) > 6 or \
                re.search(r"\b(mejor|peor|o|vs|versus|cuanto|cuantos|cuanta|precio|donde|cuando|mi|mis)\b", subject):
            return None
        t = self.settings.get("tratamiento")
        if force:  # «actualiza la ficha de X»: si viene del juego, se relee el global.ini; si no, internet
            entry, _fam = self.dictionary.find(subject)
            if entry is not None and entry.source == "juego":
                self._dict_set("memorizando", 2)
                self._dictionary_refresh(force=True)
                force = False
        if not force:
            self._dict_set("memoria", 8)
            entry, fam = self.dictionary.find(subject)
            if entry is not None or fam:
                self.on_message("ficha", D.card_text(entry, fam))
                if entry is not None and entry.group in D.PLACE_GROUPS and not fam:
                    self._holo_for_entry(entry)
                self.savings.add("respuestas_locales")
                reply = D.spoken(entry, fam, t)
                self.flash("green")
                self.memory.add_turn("user", text)
                self.memory.add_turn("assistant", reply)
                self.memory.save()
                self._dict_set("memoria", 0.6)  # que se vea el morado un instante
                self._say(reply, model="Diccionario de consultas")
                return True
            self._dict_phase = ""
        if not self.settings.get("diccionario_aprender", True):
            return subject
        learned = self._learn_online(subject)
        if learned:
            entry = learned
            self.on_message("ficha", D.card_text(entry, []))
            reply = D.spoken(entry, [], t)
            self.flash("green")
            self.memory.add_turn("user", text)
            self.memory.add_turn("assistant", reply)
            self.memory.save()
            self._say(reply, model="aprendido en starcitizen.tools")
            return True
        return subject  # que conteste la IA y se memoriza su respuesta

    def _holo_for_entry(self, entry) -> None:
        """Holograma de un planeta, luna o lugar del diccionario: el de VerseGuide (con su imagen) si responde;
        si no, uno hecho con la definición del diccionario."""
        if not (self.settings.get("holo_planetas", True) and self.settings.get("holo_activo", True)):
            return
        from . import dictionary as D

        def work() -> None:
            card = None
            try:
                found = self.vg.find(entry.name, allow_scan=False)
                if found:
                    b, place = found
                    if place is not None or D.norm(b.nombre) == D.norm(entry.name):
                        from .holo import card_body, card_place
                        self._translate(b, place)
                        tex = self._texture(b)
                        card = card_place(b, place, tex) if place else card_body(b, tex)
            except Exception as e:  # noqa: BLE001 — VerseGuide no responde: StarMap o el diccionario
                log.info("VerseGuide (%s): %s", entry.name, e)
            if card is None:
                card = self._starmap_card(entry)
            try:
                self._show_holo(card or D.holo_card(entry))
            except Exception:
                log.exception("Holograma del diccionario")
        threading.Thread(target=work, daemon=True, name="holo-diccionario").start()

    def _starmap_card(self, entry):
        """Holograma con los datos de starmap.space (si VerseGuide no responde)."""
        from . import dictionary as D
        from . import starmap as SM
        from .holo import Card
        try:
            if entry.group in ("Planetas y lunas", "Estrellas y sistemas", "Estaciones espaciales"):
                c = self.starmap.container(entry.name)
                if c:
                    _f, prose = D._split(entry.text)
                    planet = entry.group != "Estaciones espaciales"
                    return Card(kind="planeta" if planet else "lugar", title=entry.name.upper(),
                                subtitle=f"{SM.TYPE_ES.get(c.get('Type', ''), c.get('Type', ''))} · sistema {c.get('System', '')}",
                                header="STARMAP.SPACE", fields=[(k.upper(), v) for k, v in SM.container_fields(c)[2:7]],
                                desc=prose or entry.text, footer="Fuente: starmap.space · Diccionario de consultas",
                                seed=entry.name)
            from .verseguide import resolve_body
            hit = resolve_body(self.gamelog.location or "")
            if hit:
                p = self.starmap.poi(entry.name, hit[2])
                if p:
                    _f, prose = D._split(entry.text)
                    return Card(kind="lugar", title=entry.name.upper(), subtitle=f"Lugar · {p.get('Planet', '')}",
                                header="STARMAP.SPACE", fields=[(k.upper(), v) for k, v in SM.poi_fields(p)[:5]],
                                desc=prose or entry.text, footer="Fuente: starmap.space · Diccionario de consultas",
                                seed=entry.name)
        except Exception as e:  # noqa: BLE001
            log.info("StarMap (%s): %s", entry.name, e)
        return None

    def _learn_online(self, subject: str):
        """starcitizen.tools + Google Translate (gratis). Devuelve la entrada guardada o None."""
        from . import dictionary as D
        gen = self._gen
        self._searching += 1
        self.on_message("sistema", f"🔎 «{subject}» no está en el Diccionario de consultas: lo busco en internet…")
        try:
            found = D.wiki_definition(subject)
        except Exception as e:  # noqa: BLE001
            log.info("Wiki %s: %s", subject, e)
            found = None
        finally:
            self._searching = max(0, self._searching - 1)
        if not found or gen != self._gen:
            return None
        title, text_en, group = found
        es, motor = self.translator.translate(text_en, "es", "en", use_cache=False)  # el Diccionario va en español
        definition = (es or text_en) + " (starcitizen.tools)"
        return self._memorize(title, definition, group, "internet")

    def _memorize(self, name: str, definition: str, group: str, source: str):
        """Guarda en el diccionario (overlay en blanco: «memorizando»)."""
        if not self.settings.get("diccionario_aprender", True):
            return None
        from .dictionary import one_line
        self._dict_set("memorizando", 1.5)
        try:
            e = self.dictionary.put(name[:80].strip().capitalize() if name.islower() else name[:80].strip(),
                                    one_line(definition), group, source, self._patch())
        except OSError:
            log.exception("No pude escribir en el diccionario")
            return None
        if e is not None:
            self.on_message("sistema", f"📖 Memorizado en el Diccionario de consultas: {e.name} ({e.group})")
            self.on_ui({"t": "diccionario"})
        return e

    # ------------------------------------------------- respuestas sin IA (v1.2.2)
    def _local_answer(self, text: str) -> bool:
        """«Háblame de Daymar», «¿qué es Security Post Kareah?»: ficha de VerseGuide y resumen hablado,
        sin gastar la IA. True si ha respondido."""
        if not self.settings.get("respuestas_locales", True):
            return False
        m = LOCAL_ASK.match(normalize(text, tuple(self._wake_names())))
        if not m or len(m.group("x").strip()) < 3:
            return False
        subject = m.group("x").strip()
        from .verseguide import _norm, resolve_body
        try:
            hit = resolve_body(subject)
            found = self.vg.find(subject, allow_scan=False)
        except Exception:  # noqa: BLE001 — sin conexión o sin datos: que conteste la IA
            log.debug("Respuesta local", exc_info=True)
            return False
        if not found:
            return False
        b, place = found
        if place is None:
            # Solo el nombre del planeta o luna («Daymar», «la luna Daymar»); «Hurston Dynamics» no es Hurston.
            rest = _norm(subject)
            for w in _norm(hit[2]).split() if hit else []:
                rest = rest.replace(w, " ")
            if not hit or [w for w in rest.split() if w not in ("planeta", "luna", "satelite", "el", "la", "de", "del")]:
                return False
        self.place_info("", _hit=found)
        self.savings.add("respuestas_locales")
        self.flash("green")
        reply = spoken_place(b, place, self.settings.get("tratamiento"))
        self.memory.add_turn("user", text)
        self.memory.add_turn("assistant", reply)
        self.memory.save()
        self._say(reply, model="VerseGuide")
        return True

    def _comment(self, ev: GameEvent) -> None:
        t = self.settings.get("tratamiento")
        if self.settings.get("gamelog_comentarios_ia"):
            text = self.brain.ask(
                f"[Evento del juego, no es el piloto quien habla] {ev.kind}: {ev.detail}",
                extra_system="Comenta este evento en UNA frase corta, con tu personalidad. No uses herramientas.",
                use_tools=False, remember_turn=False)
        else:
            text = comment_for(ev, t)
        if text:
            self._say(text)

    def _say(self, text: str, model: str = "", spoken: str | None = None, translated: bool = False) -> None:
        """text: lo que sale en la cabina; spoken: lo que se dice en voz alta, si es distinto.
        En otro idioma, lo que no viene de la IA (que ya contesta en el idioma del piloto) se traduce."""
        if not text:
            return
        if not model and not translated and i18n.lang() != "es":
            text = self._loc(text)
            spoken = self._loc(spoken) if spoken else None
        self._spoken.append((time.time(), simplify(spoken or text)))
        if self._tint != "base" and time.time() < self._tint_until:
            self._tint_hold = True
        self.on_message(self.settings.get("nombre_asistente"), text + (f"   ·{model}" if model else ""))
        self.tts.say(spoken or text)

    # ----------------------------------------------------------------- otros
    def preview_voice(self) -> bool:
        text = (f"Sistemas en línea, {self.settings.get('tratamiento')}. Escudos al cien por cien "
                f"y el café, por desgracia, al cero.")
        if not self.tts.busy():
            self._spoken.append((time.time(), simplify(text)))
        return self.tts.preview(text)

    def reload_commands(self) -> list[str]:
        return self.commands.load()

    # ------------------------------------------------- v1.3: textos en el idioma del piloto
    LOC_WHO = ("sistema", "juego", "ficha")

    @property
    def on_message(self) -> Callable[[str, str], None]:
        return self._emit_message

    @on_message.setter
    def on_message(self, fn: Callable[[str, str], None]) -> None:
        self._on_message_raw = fn

    def _emit_message(self, who: str, text: str) -> None:
        if who in self.LOC_WHO and i18n.lang() != "es":
            text = self._loc(text)
        self._on_message_raw(who, text)

    def _loc(self, text: str | None, net: bool = True) -> str | None:
        """Texto de Nova (escrito en español) en el idioma elegido: catálogo y, si no está, Google Translate."""
        if not text or i18n.lang() == "es":
            return text
        out = i18n.tr(text)
        if out != text or not net or not re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3}", text):
            return out
        try:
            res, _motor = self.translator.translate(text, i18n.lang(), "es", allow_ai=False)
            return res or text
        except Exception:  # noqa: BLE001 — sin conexión: mejor en español que nada
            return text

    def on_language(self) -> None:
        """El piloto cambió el idioma: comandos, voz y oído en el nuevo."""
        i18n.set_lang(self.settings.get("idioma"))
        self.reload_commands()
        try:
            self.stt.warm_up()
        except Exception:  # noqa: BLE001
            log.exception("STT tras cambiar de idioma")

    def greet(self, last_place: str = "") -> None:
        from .triggers import pretty

        t = self.settings.get("tratamiento")
        pilot = (self.settings.get("nombre_piloto") or "").strip()
        key = self.settings.get("ptt_tecla")
        how = f"Mantenga {pretty(key)} para hablarme" if key else "Use su botón para hablarme"
        if self.settings.get("palabra_clave_activa"):
            how += f", o diga «{self.name}» y su orden"
        fem = str(t).strip().lower() in ("señora", "capitana", "comandante en jefe", "señorita")
        hello = (f"{self.name} en línea. Bienvenid{'a' if fem else 'o'}, {pilot}." if pilot
                 else f"{self.name} en línea, {t}.")
        if last_place and last_place != "desconocida":
            hello += f" La última vez nos quedamos en {last_place}."
        self._say(f"{hello} {how}.")


def _first_sentence(text: str, limit: int = 260) -> str:
    text = " ".join((text or "").split())
    m = re.match(r"(.{25,}?[.!?])(\s|$)", text)
    out = m.group(1) if m else text
    out = out if len(out) <= limit else out[:limit].rsplit(" ", 1)[0] + "…"
    return out if not out or out[-1] in ".!?…" else out + "."


def spoken_place(b, place, tratamiento: str) -> str:
    """Resumen corto, para decirlo en voz alta, de un planeta, luna o lugar de VerseGuide."""
    from .verseguide import SYSTEM_ES

    def art(word: str) -> str:
        return "una" if word.lower().rstrip().endswith(("a", "ión", "ad")) else "un"

    system = SYSTEM_ES.get(b.sistema, b.sistema.title())
    if place is not None:
        kind = place.tipo_es().lower()
        out = f"{place.nombre} es {art(kind)} {kind} en {b.nombre}, sistema {system}."
        if place.temp_media is not None:
            out += f" Temperatura media de unos {round(place.temp_media)} grados."
        desc = _first_sentence(desc_for(place) if place.descripcion_es or i18n.lang() != "es" else "")
    else:
        kind = b.tipo_es().lower()
        out = f"{b.nombre} es {art(kind)} {kind} del sistema {system}."
        facts = []
        if b.gravedad_g:
            facts.append(f"gravedad de {str(round(b.gravedad_g, 2)).replace('.', ',')} g")
        if b.dia_h:
            facts.append(f"días de {str(round(b.dia_h, 1)).replace('.', ',').removesuffix(',0')} horas")
        if facts:
            out += " Tiene " + " y ".join(facts) + "."
        n = len([p for p in b.lugares if not p.oculto])
        if n:
            out += f" VerseGuide registra {n} lugares."
        desc = _first_sentence(desc_for(b) if b.descripcion_es or i18n.lang() != "es" else "")
    if desc:
        out += " " + desc
    return out + f" Tiene la ficha en pantalla, {tratamiento}."

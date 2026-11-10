"""Nova: une oído, voz, comandos, IA y Game.log."""
from __future__ import annotations

import collections
import logging
import queue
import threading
import time
from typing import Callable

import numpy as np

from . import extras
from .commands import CommandBook, _partial, _similarity, normalize, simplify
from .config import Settings
from .gamelog import GameEvent, GameLog, comment_for, find_game_log
from .llm import Brain
from .memory import Memory
from .stt import SpeechToText
from .tools import Tools
from .tts import TextToSpeech
from .wake import strip_wake, wake_names

log = logging.getLogger("nova")

STOP_WORDS = {"silencio", "callate", "calla", "para", "basta", "stop", "cancela", "cancelar", "cierra el pico"}
PAUSE_WORDS = {"desactivate", "pausa", "modo pausa", "a dormir", "apagate", "descansa"}
RESUME_WORDS = {"activate", "despierta", "vuelve", "reactivate", "enciendete", "en linea"}
INFO_TOOLS = {"buscar_wiki_star_citizen", "buscar_en_internet", "leer_pagina_web",
              "uex_precios_mercancia", "uex_rutas_comercio", "estado_servidores", "ficha_lugar"}
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
        # v1.3: actualizaciones del programa desde GitHub
        from .selfupdate import Updater

        self.selfupdate = Updater(settings)
        self.selfupdate.on_change = lambda: self.on_ui({"t": "actualizacion"})
        self._update_question_until = 0.0
        self.request_quit: Callable[[], None] = lambda: None  # lo pone nova.py (cerrar NOVA)
        self.on_ui: Callable[[dict], None] = lambda ev: None  # avisos para la ventana (foco, temporizadores…)
        self.brain = Brain(settings, self.tools, self.memory, self.gamelog)
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
        self.on_message("sistema", f"🔎 Buscando «{handle}» en robertsspaceindustries.com…")
        self._searching += 1
        try:
            c = extras.lookup(handle)
        except Exception:
            self._searching = max(0, self._searching - 1)
            self.flash("red")
            self._say(extras.NOT_FOUND)
            return
        self._searching = max(0, self._searching - 1)
        self.flash("green")
        self.on_message("ficha", "FICHA DE JUGADOR\n" + c.text())
        self._log_player(c)
        self._say(extras.spoken(c, t))
        if self.settings.get("holo_jugadores", True):
            self._holo_player(c, "consulta")
        sent = extras.send_player_to_discord(self.settings, c)
        if sent:
            self.on_message("sistema", sent)

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
    def play_sfx(self, name: str) -> None:
        """Sonidos de los hologramas (encendido, apagado y alerta de objetivo de captura)."""
        if not self.settings.get("holo_sonidos", True):
            return
        from . import sfx
        data = sfx.get(name)
        if data is None:
            return
        try:
            vol = max(0.0, min(1.0, float(self.settings.get("holo_volumen", 0.7))))
            self.tts.out.play_fx(data * vol, sfx.RATE)
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
        if not self.settings.get("recompensas_buscar", True):
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

        def work() -> None:
            from .rsi import HANDLE_RE
            if " " in name.strip() or not HANDLE_RE.match(name.strip()):
                npc()  # los apodos de RSI no llevan espacios: es un personaje del juego
                return
            self.on_message("sistema", f"🎯 Objetivo nuevo: Neutralizar «{name}» · buscando su ficha en RSI…")
            try:
                c = extras.lookup(name)
            except Exception as e:  # noqa: BLE001
                if _network_error(e):
                    self.on_message("sistema", f"⚠ No pude consultar RSI para «{name}» (sin conexión).")
                    return
                npc()
                return
            self.on_message("ficha", "OBJETIVO DE RECOMPENSA\n" + c.text())
            self._log_player(c, "objetivo de recompensa", "objetivo_recompensa")
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
        if not (s.get("holo_llegadas", True) or s.get("holo_lugares", True)):
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
        """Descripciones de VerseGuide/RSI (en inglés) al español con la IA; se guardan en la caché."""
        if not self.settings.get("holo_traducir", True):
            return
        changed = False
        for obj in ((place,) if place else ()) + (b,):
            if obj is None or obj.descripcion_es or not obj.descripcion or len(obj.descripcion) < 12:
                continue
            es = self.brain.quick("Traduce al español de España este texto de Star Citizen. Mantén los nombres "
                                  "propios. Responde solo con la traducción:\n\n" + obj.descripcion[:900])
            if es:
                obj.descripcion_es = es.strip().strip('"')
                changed = True
        if changed:
            self.vg.save(b)

    def place_info(self, nombre: str) -> str:
        """Herramienta de la IA: ficha de un planeta, luna o lugar planetario (y holograma)."""
        from .holo import card_body, card_place
        from .verseguide import place_text

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
        self.paused = paused
        if paused:
            self.tts.stop()
        self.on_message("sistema", f"⏸ {self.name} en pausa: solo responde a «{self.name}, actívate»."
                        if paused else f"▶ {self.name} activa.")

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
        self._jobs.put(("audio", audio, source))

    def submit_text(self, text: str) -> None:
        """Texto escrito en la ventana: igual que si lo hubiera dicho por voz."""
        self._jobs.put(("text", text, "texto"))

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
        self._jobs.put(("event", ev, "juego"))  # en cola: no se pierde aunque Nova esté ocupada

    # --------------------------------------------------------------- trabajo
    def _worker(self) -> None:
        while True:
            kind, payload, source = self._jobs.get()
            self.busy = True
            try:
                if kind == "audio":
                    self.on_status("Transcribiendo…")
                    text = self.stt.transcribe(payload)
                    self.on_status("")
                    if text:
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
            if norm in RESUME_WORDS:
                self.on_message("tú", text)
                self.set_paused(False)
                self.flash("green")
                self._say(f"De vuelta en línea, {self.settings.get('tratamiento')}.")
            return
        self.on_message("tú", text)
        if norm in PAUSE_WORDS:
            self._say(f"Entro en pausa, {self.settings.get('tratamiento')}. Diga «{self.name}, actívate» para volver.")
            self.set_paused(True)
            return
        if norm in STOP_WORDS:
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
            self._say(self.commands.response_for(cmd))
            return

        # 2) Todo lo demás: la IA (puede usar herramientas y comandos).
        reply = self.brain.ask(text)
        self.flash("green" if self.brain.last_ok else "red")
        self._say(reply, model=self.brain.last_model)

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

    def _say(self, text: str, model: str = "") -> None:
        if not text:
            return
        self._spoken.append((time.time(), simplify(text)))
        if self._tint != "base" and time.time() < self._tint_until:
            self._tint_hold = True
        self.on_message(self.settings.get("nombre_asistente"), text + (f"   ·{model}" if model else ""))
        self.tts.say(text)

    # ----------------------------------------------------------------- otros
    def preview_voice(self) -> bool:
        text = (f"Sistemas en línea, {self.settings.get('tratamiento')}. Escudos al cien por cien "
                f"y el café, por desgracia, al cero.")
        if not self.tts.busy():
            self._spoken.append((time.time(), simplify(text)))
        return self.tts.preview(text)

    def reload_commands(self) -> list[str]:
        return self.commands.load()

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

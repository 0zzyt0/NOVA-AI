"""Nova: une oído, voz, comandos, IA y Game.log."""
from __future__ import annotations

import collections
import logging
import queue
import threading
import time
from typing import Callable

import numpy as np

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
              "uex_precios_mercancia", "uex_rutas_comercio"}
ECHO_TAIL = 0.8  # segundos tras hablar en los que el micrófono sigue sordo (eco de la sala)


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
        if self.paused or self.training or not ev.category or not self.settings.get("gamelog_comentarios"):
            return
        if not (self.settings.get("gamelog_avisos") or {}).get(ev.category, True):
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

        # 1) Frase de comando conocida: al instante, sin IA.
        cmd = self.commands.match(text, tuple(self._wake_names()))
        if cmd:
            self.flash("green")
            self.on_message("sistema", f"⚙ {cmd.nombre}")
            self.commands.execute(cmd)
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

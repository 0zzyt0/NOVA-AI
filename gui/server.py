"""Servidor local de la interfaz (solo 127.0.0.1, con contraseña aleatoria por sesión).

La ventana de Nova es una página web servida aquí y abierta en modo aplicación
de Microsoft Edge. Habla con Nova por:
  POST /api/call    {"fn": "...", "args": {...}}  -> {"ok": true, "data": ...}
  GET  /api/events  flujo en vivo (mensajes, estado, niveles de audio)
"""
from __future__ import annotations

import json
import logging
import os
import queue
import secrets
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from core import sc_actions, triggers, wake
from core.audio import list_devices
from core.config import (APP_DIR, COMMANDS_FILE, DATA_DIR, DEFAULTS, FINAL_PHRASE, LOG_FILE, PROVIDERS, VERSION,
                         is_installed)
from core.training import calibrate, check_exercise, check_phrase, extract_name
from core.gamelog import CATEGORIES
from core.overlay import RESOLUTIONS, list_monitors
from core.tts import PIPER_VOICES, list_edge_voices

log = logging.getLogger("nova.ui")
WEB = Path(__file__).resolve().parent / "web"
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".png": "image/png", ".ico": "image/x-icon", ".svg": "image/svg+xml",
         ".ogg": "audio/ogg"}

# Ajustes que, al cambiar, necesitan hacer algo más que guardarse.
RELOAD_COMMANDS = {"teclas_juego_sync", "actionmaps_ruta", "comandos_auto_juego"}


class UIServer:
    def __init__(self, nova, overlay=None, session=None) -> None:
        self.nova = nova
        self.overlay = overlay
        self.session = session
        self._setup_samples: list[dict] = []  # ruido y volumen de voz medidos en el entrenamiento
        self._listen_lock = threading.Lock()
        self.update_skip = threading.Event()
        self._tr_busy = threading.Event()
        self.tr_reminder = False  # se calcula al arrancar: ¿toca el aviso trimestral de la traducción?
        nova.updater.on_progress = lambda ev: self.broadcast({"t": "upd", **ev})
        self.token = secrets.token_urlsafe(18)
        self._clients: list[queue.Queue] = []
        self._clients_lock = threading.Lock()
        self.last_client_seen = 0.0
        self.ever_connected = False
        # Últimos mensajes, para quien abra la ventana más tarde (y los de la sesión anterior).
        self._history: list[dict] = session.previous_chat() if session else []
        self._voices: list[str] | None = None
        self.on_shutdown = lambda: None
        self.httpd: ThreadingHTTPServer | None = None
        nova.on_message = self._on_message
        nova.on_status = lambda text: self.broadcast({"t": "status", "text": text})

    # ------------------------------------------------------------ eventos
    @property
    def clients(self) -> int:
        with self._clients_lock:
            return len(self._clients)

    def broadcast(self, ev: dict) -> None:
        with self._clients_lock:
            for q in self._clients:
                if q.qsize() < 500:
                    q.put(ev)

    def _on_message(self, who: str, text: str) -> None:
        ev = {"t": "msg", "who": who, "text": text, "ts": time.strftime("%H:%M:%S")}
        if who == self.nova.name:
            ev["ai"] = True  # mensaje de la IA (aunque luego le cambies el nombre)
        self._history = (self._history + [ev])[-80:]
        if self.session:
            self.session.update(chat=self._history)
        self.broadcast(ev)

    def _ticker(self) -> None:
        while True:
            if self.clients:
                self.last_client_seen = time.time()
                mode, level, tint = self.nova.state()
                mic = self.nova.listener.level if self.nova.listener else 0.0
                self.broadcast({"t": "lv", "mode": mode, "lvl": round(level, 3), "mic": round(mic, 3),
                                "tint": tint, "paused": self.nova.paused})
            time.sleep(0.08)

    # ------------------------------------------------------------- arranque
    def start(self) -> str:
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):  # silencio en consola
                pass

            def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):  # noqa: N802
                path, _, query = self.path.partition("?")
                if path == "/api/events":
                    if f"token={server.token}" not in query:
                        return self._send(403, b"no", "text/plain")
                    return server._serve_events(self)
                if path in ("/", "/index.html"):
                    html = (WEB / "index.html").read_text(encoding="utf-8").replace("__TOKEN__", server.token)
                    return self._send(200, html.encode("utf-8"), TYPES[".html"])
                if path in ("/logo.png", "/favicon.ico"):
                    f = APP_DIR / "recursos" / ("nova.png" if path == "/logo.png" else "nova.ico")
                else:
                    f = (WEB / path.lstrip("/")).resolve()
                    if WEB.resolve() not in f.parents:
                        return self._send(404, b"", "text/plain")
                if not f.is_file():
                    return self._send(404, b"", "text/plain")
                return self._send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"))

            def do_POST(self):  # noqa: N802
                if self.path != "/api/call" or self.headers.get("X-Nova-Token") != server.token:
                    return self._send(403, b"{}", "application/json")
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                    req = json.loads(self.rfile.read(length) or b"{}")
                    data = server.call(req.get("fn", ""), req.get("args") or {})
                    out = {"ok": True, "data": data}
                except Exception as e:  # cualquier fallo vuelve a la ventana, nunca tumba a Nova
                    log.exception("API %s", self.path)
                    out = {"ok": False, "error": str(e)}
                self._send(200, json.dumps(out, ensure_ascii=False, default=str).encode("utf-8"), "application/json")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True, name="ui-http").start()
        threading.Thread(target=self._ticker, daemon=True, name="ui-ticker").start()
        port = self.httpd.server_address[1]
        (DATA_DIR / "ui_puerto.txt").write_text(str(port), encoding="utf-8")
        log.info("Interfaz en http://127.0.0.1:%s/", port)
        return f"http://127.0.0.1:{port}/"

    def _serve_events(self, h: BaseHTTPRequestHandler) -> None:
        q: queue.Queue = queue.Queue()
        for ev in self._history:
            q.put(ev)
        with self._clients_lock:
            self._clients.append(q)
        self.ever_connected = True
        self.last_client_seen = time.time()
        try:
            h.send_response(200)
            h.send_header("Content-Type", "text/event-stream")
            h.send_header("Cache-Control", "no-store")
            h.send_header("Connection", "keep-alive")
            h.end_headers()
            while True:
                try:
                    ev = q.get(timeout=10)
                    h.wfile.write(f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode("utf-8"))
                except queue.Empty:
                    h.wfile.write(b": ping\n\n")
                h.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            with self._clients_lock:
                if q in self._clients:
                    self._clients.remove(q)
            self.last_client_seen = time.time()

    # ------------------------------------------------------------------ API
    def call(self, fn: str, args: dict):
        method = getattr(self, "api_" + fn, None)
        if not method:
            raise ValueError(f"Función desconocida: {fn}")
        return method(**args)

    def api_state(self) -> dict:
        n, s = self.nova, self.nova.settings
        return {
            "settings": {k: s.get(k) for k in DEFAULTS if k != "claves"},
            "keys_set": {p: bool(s.key_for(p)) for p in PROVIDERS},
            "providers": {k: {"nombre": v["nombre"], "modelos": v["modelos"], "url": v["clave_url"]}
                          for k, v in PROVIDERS.items()},
            "piper_voices": list(PIPER_VOICES),
            "ptt_text": triggers.pretty(s.get("ptt_tecla")),
            "stt": {"mode": n.stt.mode(), "status": n.stt.status},
            "game": {"status": n.gamelog.status, "location": n.gamelog.location,
                     "contracts": list(n.gamelog.contracts)},
            "arranque": {"comprobando": n.updater.running.is_set() and not self.update_skip.is_set(),
                         "informe": n.updater.report},
            "fuentes": self.api_sources(),
            "traduccion": self.api_translation_status(),
            "traduccion_aviso": self.tr_reminder,
            "overlay": self._overlay_info(),
            "resolutions": RESOLUTIONS,
            "monitors": [{"id": m["id"], "label": m["label"]} for m in list_monitors()],
            "event_categories": CATEGORIES,
            "final_phrase": FINAL_PHRASE,
            "history": self._history,
            "platform": sys.platform,
            "setup": self._setup_info(),
            "session": {"seccion": self.session.get("seccion") if self.session else None},
            "app": {"version": VERSION, "datos": str(DATA_DIR), "instalado": is_installed()},
            "name_warning": wake.name_warning(s.get("nombre_asistente")),
        }

    # --- cabina
    def api_send_text(self, text: str) -> bool:
        if text.strip():
            self.nova.submit_text(text.strip())
        return True

    def api_ptt(self, down: bool) -> bool:
        (self.nova._ptt_down if down else self.nova._ptt_up)()
        return True

    def api_stop_voice(self) -> bool:
        self.nova.tts.stop()
        return True

    def api_preview_voice(self) -> bool:
        return self.nova.preview_voice()

    # --- ajustes
    def api_set(self, key: str, value):
        if key not in DEFAULTS or key == "claves":
            raise ValueError(f"Ajuste desconocido: {key}")
        default = DEFAULTS[key]
        if isinstance(default, bool):
            value = bool(value)
        elif isinstance(default, int) and not isinstance(default, bool) and value is not None:
            value = int(float(value))
        elif isinstance(default, float) and value is not None:
            value = float(value)
        s, n = self.nova.settings, self.nova
        if key == "nombre_asistente":
            return wake.rename(s, str(value or ""))
        s.set(key, value)
        if key == "sensibilidad_vad" and n.listener:
            n.listener.vad.set_sensitivity(value)
        elif key == "dispositivo_entrada" and n.listener:
            n.listener.restart()
        elif key in ("stt_modelo_local", "stt_motor"):
            n.stt.warm_up()
        elif key == "ia_cadena":
            n.brain._cooldown.clear()
        elif key in RELOAD_COMMANDS:
            n.reload_commands()
        return s.get(key)

    def api_set_key(self, provider: str, value: str) -> bool:
        if provider not in PROVIDERS:
            raise ValueError("Proveedor desconocido")
        claves = dict(self.nova.settings.get("claves"))
        claves[provider] = value.strip()
        self.nova.settings.set("claves", claves)
        self.nova.brain._cooldown.clear()
        return bool(value.strip())

    def api_test_provider(self, provider: str, model: str) -> str:
        return self.nova.brain.test(provider, model)

    def api_list_models(self, provider: str) -> list[str]:
        return self.nova.brain.list_models(provider)

    def api_voices(self) -> list[str]:
        if self._voices is None:
            self._voices = list_edge_voices()
        return self._voices

    def api_devices(self) -> dict:
        ins, outs = list_devices()
        return {"inputs": ins, "outputs": outs}

    def api_assign_ptt(self) -> dict:
        ptt = self.nova.ptt
        if ptt:
            ptt.paused = True
        try:
            joys = ptt.joysticks if ptt else triggers.Joysticks()
            hit = triggers.capture_next_input(joys)
        finally:
            if ptt:
                ptt.paused = False
        if hit and hit["tipo"] == "tecla":
            self.nova.settings.set("ptt_tecla", hit["tecla"])
        elif hit:
            self.nova.settings.set("ptt_joystick", {"nombre": hit["nombre"], "boton": hit["boton"]})
        return {"hit": hit, "ptt_tecla": self.nova.settings.get("ptt_tecla"),
                "ptt_text": triggers.pretty(self.nova.settings.get("ptt_tecla")),
                "ptt_joystick": self.nova.settings.get("ptt_joystick")}

    def api_clear_joystick(self) -> bool:
        self.nova.settings.set("ptt_joystick", None)
        return True

    def api_status(self) -> dict:
        n = self.nova
        return {"stt": {"mode": n.stt.mode(), "status": n.stt.status},
                "game": {"status": n.gamelog.status, "location": n.gamelog.location,
                         "contracts": list(n.gamelog.contracts)},
                "overlay": self._overlay_info()}

    def _overlay_info(self) -> dict:
        return self.overlay.info() if self.overlay else {"status": "no disponible", "res": "", "source": ""}

    def api_pause(self, on: bool) -> bool:
        self.nova.set_paused(bool(on))
        return self.nova.paused

    # --- comandos
    def api_commands(self) -> dict:
        b = self.nova.commands
        return {"commands": b.as_list(), "sync": b.sync, "warnings": b.warnings, "hidden": b.hidden_commands()}

    def api_catalog(self) -> list[dict]:
        return [{"id": k, "nombre": v[0], "tecla": v[1], "mantener": v[2], "categoria": v[4]}
                for k, v in sorted(sc_actions.CATALOG.items(), key=lambda kv: (kv[1][4], kv[1][0]))]

    def api_save_command(self, data: dict) -> dict:
        cmd = self.nova.commands.save_command(data)
        return {"id": cmd.id, **self.api_commands()}

    def api_delete_command(self, id: str) -> dict:  # noqa: A002
        self.nova.commands.delete_command(id)
        return self.api_commands()

    def api_restore_command(self, id: str) -> dict:  # noqa: A002
        self.nova.commands.restore_command(id)
        return self.api_commands()

    def api_sync_keys(self) -> dict:
        self.nova.reload_commands()
        return self.api_commands()

    def api_test_command(self, data: dict, delay: float = 3.0) -> bool:
        """Prueba un comando (guardado o del editor) tras una cuenta atrás, para que te dé tiempo a ir al juego."""
        from core.commands import Command

        cmd = Command(id="prueba", nombre=data.get("nombre") or "Prueba", acciones=data.get("acciones") or [])

        def run():
            time.sleep(max(0.0, min(float(delay), 10.0)))
            result = self.nova.commands.execute(cmd)
            self._on_message("sistema", f"⚙ Prueba: {result}")
        threading.Thread(target=run, daemon=True).start()
        return True

    # --- memoria
    def api_memory(self) -> dict:
        return {"facts": self.nova.memory.facts}

    def api_forget(self, text: str) -> dict:
        self.nova.memory.forget(text)
        return self.api_memory()

    def api_clear_facts(self) -> dict:
        self.nova.memory.facts = []
        self.nova.memory.save()
        return self.api_memory()

    def api_clear_history(self) -> bool:
        self.nova.memory.clear_history()
        self._history = []
        if self.session:
            self.session.update(chat=[])
            self.session.save()
        return True

    # --- sesión: dónde lo dejaste
    def api_ui_state(self, seccion: str | None = None, ventana: dict | None = None) -> bool:
        if not self.session:
            return False
        if seccion:
            self.session.update(seccion=str(seccion)[:20])
        if isinstance(ventana, dict):
            self.session.update(ventana={k: int(ventana.get(k) or 0) for k in ("x", "y", "w", "h")})
        return True

    # --- nombre: lo que ha aprendido de cómo lo pronuncias
    def api_forget_variants(self) -> list:
        self.nova.settings.set("nombre_variantes", [])
        return []

    # --- configuración inicial y entrenamiento del oído
    def _phrases(self) -> list[str]:
        s = self.nova.settings
        name, pilot = s.get("nombre_asistente"), s.get("nombre_piloto") or s.get("tratamiento")
        frases = s.get("frases_entrenamiento") or DEFAULTS["frases_entrenamiento"]
        return [f.replace("{nombre}", name).replace("{piloto}", pilot) for f in frases][:6]

    def _setup_info(self) -> dict:
        s, n = self.nova.settings, self.nova
        return {"done": bool(s.get("asistente_completado")), "nombre": s.get("nombre_asistente"),
                "piloto": s.get("nombre_piloto"), "tratamiento": s.get("tratamiento"),
                "variantes": s.get("nombre_variantes"), "frases": self._phrases(),
                "mic": n.listener is not None, "stt": {"mode": n.stt.mode(), "status": n.stt.status},
                "keys": {p: bool(s.key_for(p)) for p in ("groq", "gemini")},
                "aviso": wake.name_warning(s.get("nombre_asistente"))}

    def api_setup_begin(self) -> dict:
        self.nova.training = True
        self.nova.tts.stop()
        self._setup_samples = []
        return self._setup_info()

    def api_setup_say(self, text: str) -> bool:
        n = self.nova
        n.tts.stop()
        n._spoken.append((time.time(), wake.simplify(text)))
        n.tts.say(text)
        return True

    def api_setup_check_name(self, nombre: str) -> str:
        return wake.name_warning(nombre)

    def api_setup_save(self, piloto: str, nombre: str, tratamiento: str = "") -> dict:
        s = self.nova.settings
        s.set("nombre_piloto", " ".join((piloto or "").split())[:40], save=False)
        if tratamiento.strip():
            s.set("tratamiento", tratamiento.strip()[:30], save=False)
        wake.rename(s, nombre)
        return self._setup_info()

    def api_setup_listen(self, kind: str, index: int = 0) -> dict:
        """Graba una respuesta y la califica: ✓ (ok) o ✗. kind: piloto | ia | ejercicio | frase"""
        n, s = self.nova, self.nova.settings
        if not n.listener:
            return {"ok": False, "heard": "", "note": "No tengo micrófono. Escribe la respuesta y revisa el micrófono en la sección Oído."}
        if not self._listen_lock.acquire(blocking=False):
            return {"ok": False, "heard": "", "note": "Ya te estoy escuchando."}
        try:
            t0 = time.time()
            while (n.tts.speaking or n.tts.busy()) and time.time() - t0 < 20:
                time.sleep(0.1)  # que termine de hablar antes de escucharte
            time.sleep(0.3)
            self.broadcast({"t": "setup", "phase": "listening"})
            audio, stats = n.listener.capture()
            if audio is None:
                return {"ok": False, "heard": "", "note": "No he oído nada. Comprueba que el medidor se mueve al hablar y habla un poco más alto."}
            self._setup_samples.append(stats)
            self.broadcast({"t": "setup", "phase": "processing"})
            heard = n.stt.transcribe(audio)
        finally:
            self._listen_lock.release()
        name = s.get("nombre_asistente")
        names = wake.wake_names(s)
        if kind in ("piloto", "ia"):
            value, ok = extract_name(heard, kind)
            if ok:
                note = f"Te he entendido: {value}." if kind == "piloto" else f"Me llamaré {value}."
                return {"ok": True, "heard": heard, "value": value, "note": note,
                        "aviso": wake.name_warning(value) if kind == "ia" else ""}
            return {"ok": False, "heard": heard, "value": value,
                    "note": "No te he entendido bien. Repite o escríbelo en la casilla." if heard
                    else "No te he entendido nada. Repite o escríbelo en la casilla."}
        if kind == "ejercicio":
            r = check_exercise(heard, name, names)
        else:
            phrases = self._phrases()
            r = check_phrase(heard, phrases[max(0, min(int(index), len(phrases) - 1))], name, names)
        if r.get("learn"):
            r["learned"] = wake.add_variant(s, r["learn"])
        r["heard"] = heard
        r["variantes"] = s.get("nombre_variantes")
        return r

    def api_setup_finish(self) -> dict:
        n, s = self.nova, self.nova.settings
        sens = calibrate(self._setup_samples)
        if sens is not None:
            s.set("sensibilidad_vad", sens, save=False)
            if n.listener:
                n.listener.vad.set_sensitivity(sens)
        s.set("asistente_completado", True)
        n.training = False
        pilot = s.get("nombre_piloto") or s.get("tratamiento")
        n.on_message("sistema", f"✓ Configuración completada · {n.name} reconoce su nombre en tu voz.")
        key = triggers.pretty(s.get("ptt_tecla"))
        n._say(f"Configuración completada. Un placer, {pilot}. A partir de ahora respondo al nombre de {n.name}. "
               f"Mantenga {key} para hablarme, o diga «{n.name}» y su orden.")
        return {"sensibilidad": sens, **self._setup_info()}

    def api_setup_close(self) -> bool:
        """Cerrar la ventana de configuración sin terminar (solo si ya se había hecho antes)."""
        self.nova.training = False
        return True

    # --- overlay y varios
    def api_overlay_test(self) -> str:
        if not self.overlay:
            return "no disponible"
        self.overlay.test(9)
        return self.overlay.status

    # --- traducción al español (0zzyt0) en la carpeta LIVE
    def _live(self):
        from core import translation as T
        dirs = T.find_live_dirs(self.nova.settings, self.nova.gamelog.path)
        return dirs[0] if dirs else None, dirs

    def api_translation_status(self) -> dict:
        from core import translation as T
        live, dirs = self._live()
        st = T.status(self.nova.settings, live)
        st["carpetas"] = [str(d) for d in dirs]
        st["instalando"] = self._tr_busy.is_set()
        st["preguntar"] = bool(self.nova.settings.get("traduccion_preguntar"))
        return st

    def api_translation_install(self, origen: str = "boton") -> bool:
        """Descarga la traducción de Google Drive y la descomprime en LIVE (en segundo plano)."""
        from core import translation as T
        if self._tr_busy.is_set():
            return False
        live, _ = self._live()
        if not live:
            raise ValueError("No encuentro la carpeta de Star Citizen. Elígela con «Elegir carpeta del juego».")
        self._tr_busy.set()

        def run() -> None:
            n = self.nova
            prog = lambda text, pct: self.broadcast({"t": "trad", "estado": "progreso", "texto": text, "pct": pct,
                                                     "origen": origen})
            try:
                res = T.install(n.settings, live, prog)
                n.settings.set("traduccion_preguntar", True)
                n.gamelog.load_texts(force=True)
                threading.Thread(target=n.knowledge.load, daemon=True, name="enciclopedia").start()
                msg = ("Traducción instalada" if res["nuevo"] else "Traducción actualizada" if res["cambio"]
                       else "Ya tenías la versión más reciente; reinstalada igualmente")
                self.broadcast({"t": "trad", "estado": "ok", "texto": f"{msg} ({res['idioma']}).", "pct": 100,
                                "origen": origen, "resultado": res})
                n.on_message("sistema", f"🌐 {msg} en {live}. Reinicia Star Citizen si está abierto para verla.")
            except Exception as e:
                log.exception("Traducción")
                self.broadcast({"t": "trad", "estado": "error", "texto": str(e), "origen": origen})
            finally:
                self._tr_busy.clear()

        threading.Thread(target=run, daemon=True, name="traduccion").start()
        return True

    def api_translation_answer(self, respuesta: str) -> bool:
        """Aviso trimestral: si | no | luego. En el asistente inicial, 'rechazar' = no la quiere."""
        from core import translation as T
        s = self.nova.settings
        self.tr_reminder = False
        if respuesta == "rechazar":
            s.set("traduccion_preguntar", False)
            return True
        if respuesta == "si":
            T.answer_reminder(s, "no")  # el próximo aviso, dentro de 3 meses
            return self.api_translation_install("aviso")
        T.answer_reminder(s, "luego" if respuesta == "luego" else "no")
        return True

    def api_pick_folder(self, titulo: str = "Elige la carpeta de Star Citizen") -> str:
        """Ventana de Windows para elegir carpeta. Devuelve la ruta o ''."""
        if sys.platform != "win32":
            return ""
        script = ("Add-Type -AssemblyName System.Windows.Forms;"
                  "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
                  f"$d.Description = '{titulo.replace(chr(39), '')}';"
                  "$d.ShowNewFolderButton = $false;"
                  "$f = New-Object System.Windows.Forms.Form -Property @{TopMost=$true};"
                  "if ($d.ShowDialog($f) -eq 'OK') { [Console]::Out.Write($d.SelectedPath) }")
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", script], capture_output=True,
                               text=True, timeout=300, creationflags=0x08000000)
            path = (r.stdout or "").strip()
        except (OSError, subprocess.SubprocessError):
            return ""
        if path:
            self.nova.settings.set("juego_carpeta", path)
        return path

    # --- empezar de cero
    def api_reset_all(self, conservar_claves: bool = True, conservar_comandos: bool = True) -> bool:
        """Borra todo lo aprendido del jugador y vuelve a la configuración inicial."""
        import shutil

        from core.config import SESSION_FILE
        from core.diary import DIARY_DIR
        n = self.nova
        n.tts.stop()
        n.training = True
        n.memory.wipe()
        if self.session:
            self.session.data = {}
            self.session.dirty = False
            try:
                SESSION_FILE.unlink()
            except OSError:
                pass
        self._history = []
        n.diary.reset(None)
        n.diary.file = None
        shutil.rmtree(DIARY_DIR, ignore_errors=True)
        if not conservar_comandos:
            try:
                n.commands.reset_personal()
            except Exception:
                log.exception("Borrando comandos personales")
        n.settings.reset(keep_keys=bool(conservar_claves))
        if n.listener:
            n.listener.vad.set_sensitivity(n.settings.get("sensibilidad_vad"))
        log.info("Datos del jugador borrados: empezamos de cero")
        self.broadcast({"t": "reset"})
        return True

    # --- fuentes de datos (páginas de consulta) y diario de la sesión
    def api_sources(self) -> dict:
        n = self.nova
        return {"paginas": n.updater.overview(), "enciclopedia": n.knowledge.summary(),
                "comprobando": n.updater.running.is_set(),
                "globalini": {"ruta": str(n.gamelog.text.path or ""), "idioma": n.gamelog.text.language,
                              "textos": len(n.gamelog.text.entries), "reglas": len(n.gamelog.text.rules)}}

    def api_update_now(self) -> bool:
        if self.nova.updater.running.is_set():
            return False
        threading.Thread(target=self.nova.updater.run, daemon=True, name="actualizar").start()
        return True

    def api_update_skip(self) -> bool:
        """«Continuar sin esperar»: Nova arranca y la comprobación sigue en segundo plano."""
        self.update_skip.set()
        return True

    def api_kb_search(self, q: str) -> list[dict]:
        from core.knowledge import KIND_LABEL
        src = {"juego": "textos del juego", "scmdb": "scmdb.net", "uex": "UEX Corp"}
        docs = self.nova.knowledge.search(str(q)[:200], k=8) if self.nova.knowledge.docs else []
        return [{"titulo": d.title, "texto": d.text[:400], "tipo": KIND_LABEL.get(d.kind, d.kind),
                 "fuente": src.get(d.source, d.source)} for d in docs]

    def api_diary(self) -> dict:
        d = self.nova.diary
        return {"resumen": d.summary_text(), "estado": d.state(), "archivos": d.recent_files(12)}

    def api_open_diary(self, nombre: str = "") -> bool:
        from core.diary import DIARY_DIR
        if nombre == "carpeta":
            target = DIARY_DIR
        else:
            target = DIARY_DIR / Path(nombre).name if nombre else (self.nova.diary.file or DIARY_DIR)
        if not Path(target).exists():
            DIARY_DIR.mkdir(parents=True, exist_ok=True)
            target = DIARY_DIR
        if sys.platform == "win32":
            os.startfile(str(target))  # noqa: S606
        return True

    def api_open(self, what: str) -> bool:
        from core.knowledge import KNOW_DIR
        target = {"log": LOG_FILE, "comandos": COMMANDS_FILE, "datos": DATA_DIR, "conocimiento": KNOW_DIR,
                  "actionmaps": Path(self.nova.commands.sync.get("ruta") or DATA_DIR)}.get(what)
        if what == "conocimiento":
            KNOW_DIR.mkdir(parents=True, exist_ok=True)
        if not target:
            raise ValueError("Nada que abrir")
        if sys.platform == "win32":
            if what == "actionmaps" and target.is_file():
                subprocess.Popen(["explorer", "/select,", str(target)])
            else:
                os.startfile(str(target))  # noqa: S606
        return True

    def api_shutdown(self) -> bool:
        threading.Thread(target=self.on_shutdown, daemon=True, name="apagado").start()
        return True

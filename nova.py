"""NOVA · Asistente de vuelo por voz para Star Citizen.

Ejecuta INICIAR.bat (o: python nova.py).
"""
from __future__ import annotations

import faulthandler
import logging
import os
import sys
import threading
import time
import webbrowser
from logging.handlers import RotatingFileHandler

from core.config import DATA_DIR, LOG_FILE, Settings

log = logging.getLogger("nova")


def setup_logging() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fh = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=2, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    if sys.stdout:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        root.addHandler(sh)
    for noisy in ("httpx", "httpcore", "openai", "urllib3", "faster_whisper", "primp", "ddgs"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # Si algo revienta a bajo nivel (audio, drivers), que quede escrito en vez de cerrarse sin más.
    crash = open(DATA_DIR / "fallos.log", "a", encoding="utf-8")  # noqa: SIM115
    faulthandler.enable(file=crash, all_threads=True)
    sys.excepthook = lambda t, v, tb: log.critical("Error no controlado", exc_info=(t, v, tb))
    threading.excepthook = lambda a: log.critical("Error en hilo %s", a.thread.name if a.thread else "?",
                                                  exc_info=(a.exc_type, a.exc_value, a.exc_traceback))


def windows_setup() -> bool:
    """DPI real para el overlay y una sola copia de Nova. Devuelve False si ya hay otra abierta."""
    if sys.platform != "win32":
        return True
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    ctypes.windll.kernel32.CreateMutexW(None, False, "NovaCopilotoStarCitizen")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def main() -> None:
    setup_logging()
    if not windows_setup():
        # Ya está abierta: solo enseñamos su ventana.
        from gui.window import open_window

        try:
            port = (DATA_DIR / "ui_puerto.txt").read_text().strip()
            open_window(f"http://127.0.0.1:{port}/")
        except Exception:
            pass
        return

    settings = Settings()
    from core.assistant import Nova
    from core.overlay import Overlay
    from core.session import Session
    from gui.server import UIServer
    from gui.window import open_window

    nova = Nova(settings)
    session = Session()
    overlay = Overlay(settings, nova.state)
    server = UIServer(nova, overlay, session)
    url = server.start()
    stopping = threading.Event()
    window: dict = {"proc": None}

    def close_window() -> None:
        """Cierra la ventana de Nova (es un proceso de Edge aparte)."""
        server.broadcast({"t": "bye"})  # la propia página se cierra
        time.sleep(0.8)
        proc = window["proc"]
        if proc is not None and proc.poll() is None:
            try:
                if sys.platform == "win32":
                    import subprocess

                    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True,
                                   creationflags=0x08000000, timeout=5)
                else:
                    proc.terminate()
            except Exception:
                log.exception("No pude cerrar la ventana")

    def save_all() -> None:
        """Guarda dónde lo dejaste: sesión (chat, ventana, ubicación) y memoria."""
        loc = nova.gamelog.location
        if loc and loc != "desconocida":
            session.update(ubicacion=loc)
        session.save_if_dirty()
        if nova.memory.dirty:
            nova.memory.save()

    def shutdown() -> None:
        if stopping.is_set():
            return
        stopping.set()
        log.info("Cerrando Nova")
        try:
            nova.paused = True  # el overlay se pone rojo un momento antes de apagarse
            nova.tts.stop()
            close_window()
            time.sleep(0.6)
            settings.save()
            nova.memory.save()
            nova.diary.flush()
            session.dirty = True
            save_all()
            overlay.stop()
            nova.tts.stop()
            nova.tts.out.close()
            if nova.listener:
                nova.listener.close()
        finally:
            os._exit(0)

    server.on_shutdown = shutdown

    def check_sources() -> None:
        """Antes de activar nada: ¿hay datos nuevos en scmdb.net, UEX, la wiki o tu global.ini?"""
        if not settings.get("actualizar_al_iniciar", True):
            nova.updater.check_global_ini()
            threading.Thread(target=nova.knowledge.load, daemon=True, name="enciclopedia").start()
            return
        worker = threading.Thread(target=nova.updater.run, daemon=True, name="actualizar")
        worker.start()
        while worker.is_alive() and not server.update_skip.is_set():
            worker.join(0.3)
        rep = nova.updater.report
        if server.update_skip.is_set() and worker.is_alive():
            nova.on_message("sistema", "⟳ La comprobación de datos sigue en segundo plano.")
            return
        news = [f"{k}: {v.get('texto', '')}" for k, v in rep.items() if v.get("estado") == "actualizado"]
        offline = [k for k, v in rep.items() if v.get("estado") in ("sin conexión", "error")]
        if news:
            nova.on_message("sistema", "⬇ Datos actualizados · " + " · ".join(news))
        elif offline:
            nova.on_message("sistema", "⚠ Sin conexión con " + ", ".join(offline) + ": uso los datos guardados.")
        else:
            nova.on_message("sistema", "✓ Fuentes de datos al día.")

    def translation_reminder() -> None:
        """Cada 3 meses: «¿Comprobar y reinstalar la traducción?» (Sí / No / Recuérdamelo)."""
        from core import translation as T

        if not settings.get("asistente_completado"):
            return  # en la configuración inicial ya se pregunta por la traducción
        st = server.api_translation_status()
        if T.reminder_due(settings, st):
            server.tr_reminder = True
            server.broadcast({"t": "trad_aviso", **st})

    def boot() -> None:
        try:
            check_sources()
        except Exception:
            log.exception("Comprobando las fuentes")
        try:
            translation_reminder()
        except Exception:
            log.exception("Aviso de la traducción")
        err = nova.start_audio()
        if err:
            nova.on_message("sistema", f"⚠ {err}. Puedes escribirme mientras tanto.")
        nova.start_gamelog()
        overlay.start()
        sync = nova.commands.sync
        if sync.get("estado") == "ok":
            n = len(sync.get("aplicadas", [])) + len(sync.get("nuevas", []))
            nova.on_message("sistema", f"⟳ Teclas sincronizadas con Star Citizen ({n} cambios).")
        if not settings.get("asistente_completado"):
            # La ventana abre la configuración inicial; hasta terminarla no se atienden órdenes.
            nova.training = True
            log.info("Configuración inicial pendiente")
            return
        if not any(settings.key_for(p) for p in ("gemini", "groq", "openrouter", "deepseek")):
            nova.on_message("sistema",
                            "👋 Falta una clave de IA: ve a la sección Inteligencia y pega una clave GRATIS de "
                            "Gemini y/o Groq. Sin clave funcionan los comandos de la nave por frase directa, "
                            "pero no la conversación ni las búsquedas.")
        from core.diary import last_location

        nova.greet(last_place=last_location() or session.get("ubicacion") or "")
        log.info("Nova en marcha")

    threading.Thread(target=boot, daemon=True).start()

    started = time.time()
    proc = window["proc"] = open_window(url, session.window_bounds())
    last_save = time.time()
    # Si la ventana es un proceso propio, Nova se cierra cuando la cierras.
    # Si no (navegador normal o Edge ya abierto), se cierra cuando ninguna ventana la está mirando.
    while True:
        time.sleep(1)
        if time.time() - last_save > 30:  # por si se va la luz o se cuelga Windows
            last_save = time.time()
            try:
                save_all()
            except Exception:
                log.exception("Guardando la sesión")
        if proc is not None and proc.poll() is not None:
            if time.time() - started > 4:
                shutdown()
            proc = window["proc"] = None  # se fue al instante: el navegador reutilizó otra instancia
        # Ventana cerrada (aunque Edge siga en segundo plano): nadie conectado durante 25 s.
        if server.ever_connected and server.clients == 0 and time.time() - server.last_client_seen > 25:
            shutdown()
        if not server.ever_connected and time.time() - started > 45:
            webbrowser.open(url)
            started = time.time()


if __name__ == "__main__":
    main()

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


def first_language(settings) -> None:
    """v1.3: idioma de NOVA AI. El instalador deja datos\\idioma.txt con el que eligió el piloto; si no hay
    nada elegido todavía, se usa el de Windows. Después se cambia en Ajustes."""
    from core import i18n
    f = DATA_DIR / "idioma.txt"
    chosen = ""
    try:
        chosen = f.read_text(encoding="utf-8-sig").strip()
        f.unlink()
    except OSError:
        pass
    if not chosen and settings.get("asistente_completado") and not settings.get("idioma_elegido"):
        settings.set("idioma_elegido", True)  # ya usabas NOVA AI (en español): no se cambia nada
        return
    if chosen or not settings.get("idioma_elegido"):
        lang = i18n.norm(chosen or i18n.detect_windows())
        changes = i18n.apply_language(settings, lang, i18n.norm(settings.get("idioma")))
        settings.set("idioma_elegido", bool(chosen) or bool(settings.get("idioma_elegido")), save=False)
        settings.save()
        logging.getLogger("nova").info("Idioma inicial: %s %s", lang, changes)

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
    first_language(settings)
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
    window: dict = {"proc": None, "started": time.time(), "hidden": False, "avisado": False}
    tray = None

    def close_window(to_tray: bool = False) -> None:
        """Cierra la ventana de Nova (es un proceso de Edge aparte)."""
        server.broadcast({"t": "bye", "bandeja": to_tray})  # la propia página se cierra
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
            try:
                nova.update_on_close()  # ¿versión nueva? (o la que dejaste «para al cerrar»)
            except Exception:
                log.exception("Actualización al cerrar")
            if tray is not None:
                tray.stop()  # sin icono fantasma en la bandeja
            overlay.stop()
            nova.holo.stop()
            nova.tts.stop()
            nova.tts.out.close()
            if nova.listener:
                nova.listener.close()
        finally:
            os._exit(0)

    server.on_shutdown = shutdown

    # ------------------------------------------------ 1.4: bandeja de Windows
    def in_tray() -> bool:
        return tray is not None and tray.ok and bool(settings.get("bandeja_al_cerrar", True))

    def show_window() -> None:
        """Abre la ventana (o la trae al frente si ya está abierta)."""
        from core.tray import focus_window

        if server.clients > 0 and focus_window("NOVA AI · "):
            return
        window["proc"] = open_window(url, session.window_bounds())
        window["started"] = time.time()

    def window_gone() -> None:
        """Se cerró la ventana: a la bandeja (Nova sigue escuchando y el overlay sigue) o se apaga."""
        if not in_tray():
            shutdown()
            return
        if window["hidden"]:
            return
        window["hidden"] = True
        log.info("Ventana cerrada: Nova sigue en la bandeja")
        try:
            save_all()
        except Exception:
            log.exception("Guardando la sesión")
        if not window["avisado"]:
            window["avisado"] = True
            from core import i18n

            tray.notify(i18n.tr("NOVA AI sigue en marcha"),
                        i18n.tr("Está aquí, en la bandeja, con el overlay activo. Clic en el icono para abrirla; "
                                "clic derecho › Salir para cerrarla del todo."))

    def hide_to_tray() -> bool:
        if not in_tray():
            return False
        window_gone()
        threading.Thread(target=close_window, args=(True,), daemon=True, name="a-la-bandeja").start()
        return True

    def tray_tip() -> str:
        from core import i18n

        if nova.paused:
            st = "detenida"
        elif nova.asleep:
            st = "en reposo"
        elif settings.get("microfono_silenciado"):
            st = "micrófono silenciado (MUTE)"
        else:
            st = "en espera"
        return f"NOVA AI · {i18n.tr(st)}"

    def toggle_mute() -> None:
        server.api_set("microfono_silenciado", not settings.get("microfono_silenciado"))

    def toggle_sleep() -> None:
        server.api_sleep(not nova.asleep)

    def start_tray() -> None:
        nonlocal tray
        from core import i18n
        from core.config import APP_DIR
        from core.tray import SEPARATOR, MenuItem, Tray

        t = Tray(APP_DIR / "recursos" / "nova.ico", tray_tip, [
            MenuItem(lambda: i18n.tr("Abrir NOVA AI"), show_window, default=True),
            SEPARATOR,
            MenuItem(lambda: i18n.tr("Silenciar el micrófono (MUTE)"), toggle_mute,
                     checked=lambda: bool(settings.get("microfono_silenciado"))),
            MenuItem(lambda: i18n.tr("Modo reposo"), toggle_sleep, checked=lambda: nova.asleep),
            SEPARATOR,
            MenuItem(lambda: i18n.tr("Salir de NOVA AI"),
                     lambda: threading.Thread(target=shutdown, daemon=True, name="apagado").start()),
        ])
        t.start()
        if t.wait_ready(3.0):
            tray = t
            log.info("Icono en la bandeja listo")
        else:
            log.warning("Sin icono en la bandeja (%s): cerrar la ventana cerrará Nova", t.error or "no responde")

    try:
        start_tray()
    except Exception:
        log.exception("Bandeja")
    server.on_hide = hide_to_tray
    server.tray_ok = lambda: tray is not None and tray.ok
    nova.request_quit = lambda: threading.Thread(target=shutdown, daemon=True, name="apagado").start()

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

    def boot() -> None:
        try:
            check_sources()
        except Exception:
            log.exception("Comprobando las fuentes")
        # 2.1.4: ya no hay aviso trimestral: la traducción la mantiene al día el Gestor de traducción de 0zzyt0
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
        if settings.get("claves_fabrica_quitadas"):
            # 2.1.5: las claves de fábrica eran de todos y se agotaban entre todos; ahora cada piloto pone las suyas
            nova.on_message("sistema",
                            "🔑 NOVA ya no trae claves de IA de serie (se agotaban entre todos los usuarios). "
                            "Ve a Nova › Inteligencia, pulsa CONSEGUIR CLAVE GRATIS en Gemini y Groq y pega cada clave: "
                            "NOVA reconoce de cuál es y la prueba. Son 2 minutos y no cuesta nada.")
        elif not any(settings.key_for(p) for p in ("gemini", "groq", "openrouter", "mistral", "deepseek")):
            nova.on_message("sistema",
                            "👋 Falta una clave de IA: ve a Nova › Inteligencia y pega una clave GRATIS de "
                            "Gemini y/o Groq (NOVA reconoce de cuál es). Sin clave funcionan los comandos de la nave "
                            "por frase directa, pero no la conversación ni las búsquedas.")
        from core.diary import last_location

        nova.greet(last_place=last_location() or session.get("ubicacion") or "")
        try:
            nova.start_extras()  # temporizadores y estado de los servidores
        except Exception:
            log.exception("Temporizadores / estado de RSI")
        log.info("Nova en marcha")

    threading.Thread(target=boot, daemon=True).start()

    window["started"] = time.time()
    window["proc"] = open_window(url, session.window_bounds())
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
        proc = window["proc"]
        if proc is not None and proc.poll() is not None:
            window["proc"] = None  # si se fue al instante, el navegador reutilizó otra instancia
            if time.time() - window["started"] > 4:
                window_gone()
        if server.clients > 0:
            window["hidden"] = False
        # Ventana cerrada (aunque Edge siga en segundo plano): nadie conectado durante 25 s.
        elif (server.ever_connected and not window["hidden"]
              and time.time() - server.last_client_seen > 25):
            window_gone()
        if not server.ever_connected and time.time() - window["started"] > 45:
            webbrowser.open(url)
            window["started"] = time.time()


if __name__ == "__main__":
    main()

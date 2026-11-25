"""2.1 · Activar (y desactivar) la telemetría del juego desde NOVA con un botón.

Lo que hace «ACTIVAR», en cada carpeta del juego que encuentra (LIVE, PTU, EPTU, HOTFIX…):

1. user.cfg (lo lee el juego al arrancar; se guarda copia la primera vez en user.cfg.nova_telemetria):
       server.game.telemetry.enabled = 1     ← 5.0 y posteriores (abre el servidor local)
       grpc.client.server.enabled = 1        ← el servidor de servicios locales
2. Variable de entorno de tu usuario de Windows GRPC_CLIENT_SERVER_ENABLED=true: es lo que lee la 4.10
   (LIVE). El juego la hereda del RSI Launcher, así que el launcher se tiene que cerrar del todo
   (también de la bandeja) y volver a abrir.

El servidor solo escucha en tu PC (127.0.0.1), sin acceso desde la red local (no se toca
grpc.client.server.external). «DESACTIVAR» quita esas dos líneas y la variable.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import string
import subprocess
import sys
from pathlib import Path

from . import i18n

log = logging.getLogger("nova.telemetry")

CHANNELS = ("LIVE", "PTU", "EPTU", "HOTFIX", "TECH-PREVIEW")
ROOTS = ("Program Files\\Roberts Space Industries\\StarCitizen", "Roberts Space Industries\\StarCitizen",
         "Games\\Roberts Space Industries\\StarCitizen", "StarCitizen")
CFG_LINES = {"server.game.telemetry.enabled": "1", "grpc.client.server.enabled": "1"}
ENV_VAR = "GRPC_CLIENT_SERVER_ENABLED"
BACKUP = "user.cfg.nova_telemetria"
_NO_WINDOW = 0x08000000


def _key_rx(key: str) -> re.Pattern:
    """La misma opción se puede escribir con puntos o guiones («grpc.client.server.enabled» / «grpc-client-…»)."""
    k = re.escape(key).replace(r"\.", r"[.\-_]")
    return re.compile(rf"^\s*{k}\s*=\s*(\S*)", re.I)


def is_channel(p: Path) -> bool:
    try:
        return (p / "Bin64" / "StarCitizen.exe").is_file()
    except OSError:
        return False


def channel_dirs(settings=None, gamelog=None) -> list[Path]:
    """Carpetas de canal del juego (LIVE, PTU…) que hay en este PC, sin repetir."""
    roots: list[Path] = []

    def add_root(p: Path | None) -> None:
        if p and p not in roots:
            roots.append(p)

    gp = getattr(gamelog, "path", None) if gamelog is not None else None
    if gp:
        add_root(Path(gp).parent.parent)
    if settings is not None:
        for key in ("juego_carpeta", "gamelog_ruta"):
            v = (settings.get(key) or "").strip()
            if v:
                p = Path(v)
                if p.suffix.lower() == ".log":
                    p = p.parent
                add_root(p.parent if p.name.upper() in CHANNELS else p)
    if os.name == "nt":
        for d in string.ascii_uppercase:
            drive = f"{d}:\\"
            if os.path.exists(drive):
                for r in ROOTS:
                    p = Path(drive) / r
                    if p.is_dir():
                        add_root(p)
    out: list[Path] = []
    for root in roots:
        for ch in CHANNELS:
            p = root / ch
            if is_channel(p) and p not in out:
                out.append(p)
        if is_channel(root) and root not in out:
            out.append(root)
    return out


def version_of(ch: Path) -> str:
    import json

    try:
        d = json.loads((ch / "build_manifest.id").read_text(encoding="utf-8", errors="replace"))["Data"]
        return str(d.get("Version") or d.get("Branch") or "")
    except Exception:  # noqa: BLE001
        return ""


def _major_minor(v: str) -> tuple[int, int]:
    m = re.match(r"(\d+)\.(\d+)", v or "")
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def read_cfg(ch: Path) -> dict[str, str]:
    """Valores de las opciones de telemetría (y el puerto) que hay en user.cfg."""
    out: dict[str, str] = {}
    try:
        text = (ch / "user.cfg").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for key in (*CFG_LINES, "grpc.client.server.port"):
        rx = _key_rx(key)
        for line in text.splitlines():
            m = rx.match(line)
            if m:
                out[key] = m.group(1)
    return out


def read_port(ch: Path | None) -> int:
    from .telemetry import DEFAULT_PORT

    if ch is not None:
        v = read_cfg(ch).get("grpc.client.server.port", "")
        if v.isdigit() and 1024 <= int(v) <= 65535:
            return int(v)
    v = os.environ.get("GRPC_CLIENT_SERVER_PORT", "")
    return int(v) if v.isdigit() and 1024 <= int(v) <= 65535 else DEFAULT_PORT


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in ("1", "true", "yes", "on")


def write_cfg(ch: Path, enable: bool) -> bool:
    """Pone o quita las líneas de telemetría en user.cfg sin tocar el resto. True si ha cambiado algo."""
    cfg = ch / "user.cfg"
    lines = cfg.read_text(encoding="utf-8", errors="replace").splitlines() if cfg.exists() else []
    out: list[str] = []
    seen: set[str] = set()
    changed = False
    for line in lines:
        hit = next((k for k in CFG_LINES if _key_rx(k).match(line)), None)
        if hit is None:
            out.append(line)
            continue
        if not enable or hit in seen:
            changed = True
            continue
        seen.add(hit)
        new = f"{hit} = {CFG_LINES[hit]}"
        changed |= line.strip() != new
        out.append(new)
    if enable:
        for k, v in CFG_LINES.items():
            if k not in seen:
                out.append(f"{k} = {v}")
                changed = True
    if not changed:
        return False
    if cfg.exists() and not (ch / BACKUP).exists():
        shutil.copy2(cfg, ch / BACKUP)
    while out and not out[-1].strip():
        out.pop()
    cfg.write_text("\r\n".join(out) + ("\r\n" if out else ""), encoding="utf-8")
    return True


# ------------------------------------------------------------ variable de entorno (4.10)
def env_enabled() -> bool:
    if sys.platform != "win32":
        return _truthy(os.environ.get(ENV_VAR))
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return _truthy(str(winreg.QueryValueEx(k, ENV_VAR)[0]))
    except OSError:
        return False


def set_env(enable: bool) -> bool:
    """Variable de entorno de TU usuario (no hace falta ser administrador). True si ha cambiado."""
    if sys.platform != "win32":
        return False
    import winreg

    before = env_enabled()
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
        if enable:
            winreg.SetValueEx(k, ENV_VAR, 0, winreg.REG_SZ, "true")
        else:
            try:
                winreg.DeleteValue(k, ENV_VAR)
            except FileNotFoundError:
                pass
    _broadcast_env()
    return before != enable


def _broadcast_env() -> None:
    """Avisa a Windows de que han cambiado las variables (los programas que se abran a partir de ahora las ven)."""
    try:
        import ctypes

        HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG = 0xFFFF, 0x001A, 0x0002
        result = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment",
                                                 SMTO_ABORTIFHUNG, 3000, ctypes.byref(result))
    except Exception:  # noqa: BLE001
        log.debug("WM_SETTINGCHANGE", exc_info=True)


# ------------------------------------------------------------------ programas abiertos
def running(names: tuple[str, ...]) -> set[str]:
    """Cuáles de esos .exe están abiertos ahora."""
    if sys.platform != "win32":
        return set()
    try:
        r = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=10,
                           creationflags=_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return set()
    out = set()
    low = {n.lower(): n for n in names}
    for line in (r.stdout or "").splitlines():
        exe = line.split('","', 1)[0].strip('"').lower()
        if exe in low:
            out.add(low[exe])
    return out


# ---------------------------------------------------------------------- lo que ve la ventana
def status(settings=None, gamelog=None) -> dict:
    chans = []
    for ch in channel_dirs(settings, gamelog):
        cfg = read_cfg(ch)
        ver = version_of(ch)
        on = all(_truthy(cfg.get(k)) for k in CFG_LINES)
        chans.append({"canal": ch.name, "ruta": str(ch), "version": ver, "cfg": on,
                      "lee_cfg": _major_minor(ver) >= (5, 0), "puerto": read_port(ch)})
    env = env_enabled()
    procs = running(("StarCitizen.exe", "RSI Launcher.exe"))
    try:
        import grpc  # noqa: F401
        comp = True
    except ImportError:
        comp = False
    return {"canales": chans, "variable": env, "activada": bool(chans) and env and all(c["cfg"] for c in chans),
            "juego_abierto": "StarCitizen.exe" in procs, "launcher_abierto": "RSI Launcher.exe" in procs,
            "componente": comp}


def enable(settings=None, gamelog=None, on: bool = True) -> dict:
    """Botón ACTIVAR / DESACTIVAR. Devuelve el estado y un mensaje para la ventana."""
    done, errors = [], []
    for ch in channel_dirs(settings, gamelog):
        try:
            if write_cfg(ch, on):
                done.append(ch.name)
        except PermissionError:
            errors.append(i18n.tr("{c}: sin permiso para escribir user.cfg (abre NOVA como administrador)", c=ch.name))
        except OSError as e:
            errors.append(f"{ch.name}: {e}")
    env_changed = False
    try:
        env_changed = set_env(on)
    except OSError as e:
        errors.append(f"variable de entorno: {e}")
    st = status(settings, gamelog)
    if not st["canales"]:
        msg = i18n.tr("No encuentro la carpeta de Star Citizen: elígela en Juego › Idioma del juego o indica la ruta del Game.log.")
    elif on:
        parts = [i18n.tr("Telemetría activada en {c}.", c=", ".join(c["canal"] for c in st["canales"]))]
        if st["launcher_abierto"] and env_changed:
            parts.append(i18n.tr("Cierra el RSI Launcher del todo (también desde la bandeja, junto al reloj) y vuelve a abrirlo."))
        if st["juego_abierto"]:
            parts.append(i18n.tr("Reinicia Star Citizen para que se aplique."))
        if len(parts) == 1:
            parts.append(i18n.tr("Se aplica la próxima vez que abras el juego (abre el RSI Launcher después de esto)."))
        msg = " ".join(parts)
    else:
        msg = i18n.tr("Telemetría desactivada. Se aplica al reiniciar el juego y el RSI Launcher.") if env_changed else \
            i18n.tr("Telemetría desactivada. Se aplica al reiniciar el juego.")
    if errors:
        msg += " " + i18n.tr("Problemas: {p}", p="; ".join(errors))
    st.update({"mensaje": msg, "cambiados": done, "errores": errors})
    return st


def install_component() -> dict:
    """Instala grpcio y protobuf en el entorno de NOVA. Si está en «Archivos de programa», con permiso de
    administrador (Windows lo pregunta). Devuelve {ok, mensaje}; si se pide permiso, termina en segundo plano."""
    py = Path(sys.executable)
    if py.name.lower() == "pythonw.exe":
        py = py.with_name("python.exe")
    pkgs = ["grpcio>=1.60", "protobuf>=5.26"]
    args = ["-m", "pip", "install", "--no-input", "--prefer-binary", "--only-binary=grpcio", *pkgs]
    if sys.platform == "win32" and not _writable(py.parent):
        quoted = ",".join("'" + a.replace("'", "''") + "'" for a in args)
        ps = (f"Start-Process -FilePath '{str(py).replace(chr(39), chr(39) * 2)}' -ArgumentList {quoted} "
              f"-Verb RunAs -Wait -WindowStyle Hidden")
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                               timeout=900, creationflags=_NO_WINDOW)
        except (OSError, subprocess.SubprocessError) as e:
            return {"ok": False, "mensaje": i18n.tr("No se pudo instalar: {e}", e=e)}
        if r.returncode != 0:
            return {"ok": False, "mensaje": i18n.tr("Instalación cancelada o sin permiso de administrador.")}
    else:
        try:
            r = subprocess.run([str(py), *args], capture_output=True, text=True, timeout=900,
                               creationflags=_NO_WINDOW if sys.platform == "win32" else 0)
        except (OSError, subprocess.SubprocessError) as e:
            return {"ok": False, "mensaje": i18n.tr("No se pudo instalar: {e}", e=e)}
        if r.returncode != 0:
            tail = " ".join((r.stdout or r.stderr or "").strip().splitlines()[-2:])
            return {"ok": False, "mensaje": i18n.tr("pip terminó con error: {e}", e=tail)}
    import importlib

    importlib.invalidate_caches()
    try:
        import grpc  # noqa: F401
        return {"ok": True, "mensaje": i18n.tr("Componente de telemetría instalado.")}
    except ImportError:
        return {"ok": True, "mensaje": i18n.tr("Instalado. Si no se conecta, reinicia NOVA.")}


def _writable(folder: Path) -> bool:
    try:
        probe = folder / ".nova_prueba_escritura"
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False

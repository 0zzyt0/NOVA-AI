"""Actualizaciones de NOVA AI desde GitHub (github.com/0zzyt0/NOVA-AI › Releases).

Al iniciar y al cerrar, NOVA pregunta a GitHub cuál es la última versión publicada. Si es más nueva,
avisa: «Se ha detectado una nueva versión vX.X de NOVA AI. ¿Quieres actualizar ahora?»
[SÍ] [NO] [AL CERRAR LA APLICACIÓN].

Para actualizar descarga el instalador de esa versión («NOVA AI Setup … .exe», adjunto a la Release),
comprueba que la descarga está completa (tamaño y, si GitHub lo publica, su huella SHA-256) y lo abre
en modo actualización: Windows pide permiso (va a «Archivos de programa»), conserva tus datos y,
si actualizas ahora, vuelve a abrir NOVA al terminar.
"""
from __future__ import annotations

import hashlib
import logging
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from .config import APP_DIR, VERSION

log = logging.getLogger("nova.selfupdate")

REPO = "0zzyt0/NOVA-AI"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
DOWNLOAD_PREFIX = f"https://github.com/{REPO}/releases/download/"
UA = f"NOVA-AI/{VERSION} (+https://github.com/{REPO})"
ASSET_RE = re.compile(r"(?i)setup.*\.exe$")


def parse_version(text: str) -> tuple[int, ...]:
    """'v1.3', 'v1.3.0', 'NOVA AI 1.3.1' -> (1, 3, 1). () si no hay número de versión."""
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    if not m:
        return ()
    return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)


def pretty(v: tuple[int, ...]) -> str:
    """(1, 3, 0) -> 'v1.3' · (1, 3, 1) -> 'v1.3.1'."""
    if not v:
        return "v?"
    return f"v{v[0]}.{v[1]}" + (f".{v[2]}" if len(v) > 2 and v[2] else "")


def newer(remote: tuple[int, ...], local: tuple[int, ...]) -> bool:
    return bool(remote) and remote > local


def is_dev_copy(app_dir: Path = APP_DIR) -> bool:
    """Copia de desarrollo (clon de git): no se actualiza sola."""
    return (app_dir / ".git").exists()


class Updater:
    def __init__(self, settings, http=None, download_dir: Path | None = None) -> None:
        self.settings = settings
        self.http = http
        if download_dir is None:
            import tempfile
            download_dir = Path(tempfile.gettempdir()) / "NOVA_AI_actualizacion"
        self.dir = Path(download_dir)
        self.latest: dict = {}  # {"version": (1,3,0), "tag", "nombre", "notas", "url", "tam", "sha256", "pagina"}
        self.checked = 0.0
        self.error = ""
        self.choice = ""  # "" | "ahora" | "no" | "al_cerrar"
        self.file: Path | None = None
        self.progress = 0.0  # 0..1 durante la descarga
        self.state = "inactivo"  # inactivo | comprobando | al_dia | disponible | descargando | listo | error
        self._lock = threading.Lock()
        self.on_change = lambda: None

    # ------------------------------------------------------------ consulta
    def _get(self, url: str, **kw):
        http = self.http
        if http is None:
            import requests as http
        return http.get(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"}, **kw)

    def check(self, timeout: float = 8.0) -> dict | None:
        """Pregunta a GitHub. Devuelve la versión nueva (dict) o None si estás al día o no se pudo saber."""
        with self._lock:
            self.state, self.error = "comprobando", ""
        try:
            r = self._get(API, timeout=timeout)
            if r.status_code == 404:
                raise RuntimeError("todavía no hay versiones publicadas")
            if r.status_code == 403:
                raise RuntimeError("GitHub limita las consultas; se reintentará más tarde")
            if r.status_code != 200:
                raise RuntimeError(f"GitHub respondió {r.status_code}")
            data = r.json()
            info = self._parse(data)
        except Exception as e:  # noqa: BLE001
            with self._lock:
                self.state, self.error, self.checked = "error", str(e), time.time()
            log.info("Actualizaciones: %s", e)
            self.on_change()
            return None
        with self._lock:
            self.checked = time.time()
            self.latest = info or {}
            if info and newer(info["version"], parse_version(VERSION)):
                if self.state != "listo":
                    self.state = "disponible"
            else:
                self.state = "al_dia"
        self.on_change()
        return self.latest if self.state in ("disponible", "listo") else None

    @staticmethod
    def _parse(data: dict) -> dict | None:
        if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
            return None
        version = parse_version(data.get("tag_name") or "") or parse_version(data.get("name") or "")
        if not version:
            return None
        asset = None
        for a in data.get("assets") or []:
            if ASSET_RE.search(a.get("name") or "") and str(a.get("browser_download_url", "")).startswith(DOWNLOAD_PREFIX):
                asset = a
                break
        digest = ""
        if asset and str(asset.get("digest") or "").startswith("sha256:"):
            digest = asset["digest"].split(":", 1)[1].lower()
        notes = re.sub(r"\r", "", data.get("body") or "").strip()
        return {"version": version, "texto": pretty(version), "tag": data.get("tag_name") or "",
                "nombre": data.get("name") or "", "notas": notes[:1500],
                "url": asset.get("browser_download_url") if asset else "", "archivo": asset.get("name") if asset else "",
                "tam": int(asset.get("size") or 0) if asset else 0, "sha256": digest,
                "pagina": data.get("html_url") or f"https://github.com/{REPO}/releases/latest"}

    # ------------------------------------------------------------ descarga
    def download(self) -> Path:
        """Descarga el instalador de la versión nueva. Lanza RuntimeError si algo no cuadra."""
        info = self.latest
        if not info or not info.get("url"):
            raise RuntimeError("esa versión no trae instalador para descargar; ábrela en GitHub")
        if self.file and self.file.is_file() and self.state == "listo":
            return self.file
        with self._lock:
            self.state, self.progress, self.error = "descargando", 0.0, ""
        self.on_change()
        self.dir.mkdir(parents=True, exist_ok=True)
        dest = self.dir / f"NOVA_AI_Setup_{info['texto']}.exe"
        part = dest.with_suffix(".part")
        h = hashlib.sha256()
        got = 0
        last = 0.0
        try:
            r = self._get(info["url"], timeout=30, stream=True)
            if r.status_code != 200:
                raise RuntimeError(f"la descarga respondió {r.status_code}")
            total = info.get("tam") or int(r.headers.get("content-length") or 0)
            with open(part, "wb") as f:
                for chunk in r.iter_content(256 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    h.update(chunk)
                    got += len(chunk)
                    if got > 400 * 1024 * 1024:
                        raise RuntimeError("el archivo es demasiado grande")
                    if total:
                        self.progress = min(1.0, got / total)
                        if time.time() - last > 0.3:
                            last = time.time()
                            self.on_change()
            if info.get("tam") and got != info["tam"]:
                raise RuntimeError("la descarga está incompleta")
            if info.get("sha256") and h.hexdigest() != info["sha256"]:
                raise RuntimeError("la huella SHA-256 no coincide con la publicada en GitHub")
            with open(part, "rb") as f:
                if f.read(2) != b"MZ":
                    raise RuntimeError("lo descargado no es un instalador de Windows")
            part.replace(dest)
        except Exception as e:
            try:
                part.unlink()
            except OSError:
                pass
            with self._lock:
                self.state, self.error = "error", str(e)
            self.on_change()
            raise RuntimeError(str(e)) from e
        with self._lock:
            self.file, self.state, self.progress = dest, "listo", 1.0
        self.on_change()
        return dest

    def launch(self, relaunch: bool) -> bool:
        """Abre el instalador en modo actualización. relaunch: volver a abrir NOVA al terminar."""
        if not self.file or not self.file.is_file():
            return False
        args = [str(self.file), "/actualizar", f"/destino={APP_DIR}"] + ([] if relaunch else ["/sin-iniciar"])
        if sys.platform != "win32":
            log.info("Actualización (simulada fuera de Windows): %s", args)
            return True
        try:
            import ctypes
            params = " ".join(f'"{a}"' if " " in a else a for a in args[1:])
            # ShellExecute: el instalador pide permiso de administrador (UAC) con su manifiesto.
            rc = ctypes.windll.shell32.ShellExecuteW(None, "open", args[0], params, str(self.file.parent), 1)
            return rc > 32
        except Exception:  # noqa: BLE001
            try:
                subprocess.Popen(args, close_fds=True)
                return True
            except OSError:
                log.exception("No se pudo abrir el instalador")
                return False

    def info(self) -> dict:
        i = self.latest or {}
        return {"estado": self.state, "actual": pretty(parse_version(VERSION)), "nueva": i.get("texto", ""),
                "notas": i.get("notas", ""), "pagina": i.get("pagina", f"https://github.com/{REPO}/releases"),
                "comprobado": self.checked, "error": self.error, "eleccion": self.choice,
                "progreso": round(self.progress, 3), "descargable": bool(i.get("url"))}


def ask_native(version_text: str) -> bool:
    """Pregunta en una ventana de Windows (al cerrar NOVA, cuando su ventana ya no está)."""
    msg = (f"Se ha detectado una nueva versión {version_text} de NOVA AI.\n\n¿Quieres actualizar ahora?\n\n"
           "Se descargará el instalador oficial de GitHub y tus datos se conservan.")
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        MB_YESNO, MB_ICONQUESTION, MB_TOPMOST, IDYES = 0x4, 0x20, 0x40000, 6
        return ctypes.windll.user32.MessageBoxW(None, msg, "NOVA AI · Actualización", MB_YESNO | MB_ICONQUESTION | MB_TOPMOST) == IDYES
    except Exception:  # noqa: BLE001
        return False

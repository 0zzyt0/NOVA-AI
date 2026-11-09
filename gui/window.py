"""Abre la interfaz como una ventana de aplicación (Edge o Chrome en modo --app)."""
from __future__ import annotations

import logging
import os
import subprocess
import webbrowser
from pathlib import Path

from core.config import DATA_DIR

log = logging.getLogger("nova.window")


def find_browser() -> str | None:
    env = os.environ
    bases = [env.get("ProgramFiles(x86)"), env.get("ProgramFiles"), env.get("LOCALAPPDATA")]
    rels = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe",
            r"BraveSoftware\Brave-Browser\Application\brave.exe"]
    for rel in rels:
        for base in bases:
            if base and (Path(base) / rel).exists():
                return str(Path(base) / rel)
    return None


def open_window(url: str, bounds: dict | None = None) -> subprocess.Popen | None:
    """Devuelve el proceso de la ventana (para saber cuándo la cierras) o None si se usó el navegador normal."""
    exe = find_browser()
    if not exe:
        log.warning("No encuentro Edge ni Chrome: abro el navegador predeterminado")
        webbrowser.open(url)
        return None
    profile = DATA_DIR / "interfaz"
    profile.mkdir(parents=True, exist_ok=True)
    size = f"--window-size={bounds['w']},{bounds['h']}" if bounds else "--window-size=1340,880"
    args = [exe, f"--app={url}", f"--user-data-dir={profile}", size,
            "--no-first-run", "--no-default-browser-check", "--disable-features=Translate,msEdgeSidebarV2",
            "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
            "--autoplay-policy=no-user-gesture-required"]
    if bounds:  # donde estaba la última vez
        args.insert(3, f"--window-position={bounds['x']},{bounds['y']}")
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    log.info("Abriendo la ventana con %s", Path(exe).name)
    return subprocess.Popen(args, creationflags=flags)

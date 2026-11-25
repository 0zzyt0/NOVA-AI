"""v2.0: copia de seguridad de NOVA: exportar e importar ajustes, comandos y memoria.

La copia es un .zip normal (extensión .novacopia) con un manifest.json. Nunca lleva las claves de API: así se
puede pasar a un amigo o subir a la nube sin miedo. Al importar, lo que había se guarda antes en
datos/copias/antes_de_importar_<fecha>/ por si quieres volver atrás.
"""
from __future__ import annotations

import json
import shutil
import time
import zipfile
from pathlib import Path

from .config import DATA_DIR, VERSION

EXT = ".novacopia"
# parte: (nombre para la ventana, ficheros o carpetas dentro de la carpeta de datos)
PARTS: dict[str, tuple[str, list[str]]] = {
    "ajustes": ("Ajustes", ["ajustes.json", "logo_overlay.png", "sonidos"]),
    "comandos": ("Comandos de voz", ["comandos_personales.json"]),
    "memoria": ("Memoria y diccionario", ["memoria.json", "lo_que_sabe_de_ti.txt", "Diccionario_de_consultas.txt", "temporizadores.json"]),
    "bitacora": ("Bitácora", ["diario"]),
}
# Ajustes que dependen de este PC: al importar se conservan los de aquí
LOCAL_KEYS = ("juego_carpeta", "gamelog_ruta", "actionmaps_ruta", "globalini_ruta", "traduccion_instalada",
              "dispositivo_entrada", "dispositivo_salida", "overlay_monitor", "overlay_logo_ruta",
              "base_aplicada", "migrado_2_0", "migrado_2_1_5", "claves_fabrica_quitadas",
              "controles_estado", "controles_al_cerrar", "controles_diferido", "copias_ruta", "copia_nova_ultima")
SECRET_KEYS = ("claves", "discord_webhook", "motherlode_clave")
MAX_FILE = 200 * 1024 * 1024


def _clean_settings(data: dict) -> dict:
    return {k: v for k, v in data.items() if k not in SECRET_KEYS}


def export(dest: Path, parts: list[str] | None = None, data_dir: Path = DATA_DIR) -> dict:
    """Crea la copia. Devuelve {ruta, partes, ficheros}."""
    parts = [p for p in (parts or list(PARTS)) if p in PARTS]
    dest = Path(dest)
    if dest.suffix.lower() not in (EXT, ".zip"):
        dest = dest.with_suffix(EXT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    files = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for part in parts:
            for name in PARTS[part][1]:
                src = data_dir / name
                if name == "ajustes.json" and src.is_file():
                    try:
                        data = json.loads(src.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        continue
                    z.writestr(f"{part}/{name}", json.dumps(_clean_settings(data), indent=2, ensure_ascii=False))
                    files += 1
                elif src.is_file():
                    z.write(src, f"{part}/{name}")
                    files += 1
                elif src.is_dir():
                    for f in sorted(src.rglob("*")):
                        if f.is_file() and f.stat().st_size < MAX_FILE:
                            z.write(f, f"{part}/{f.relative_to(data_dir).as_posix()}")
                            files += 1
        z.writestr("manifest.json", json.dumps({"app": "NOVA AI", "version": VERSION, "fecha": time.strftime("%Y-%m-%d %H:%M"),
                                                 "partes": parts, "sin_claves": True}, indent=2, ensure_ascii=False))
    return {"ruta": str(dest), "partes": parts, "ficheros": files}


def inspect(src: Path) -> dict:
    """Lo que trae una copia (sin tocar nada)."""
    with zipfile.ZipFile(src) as z:
        try:
            man = json.loads(z.read("manifest.json").decode("utf-8"))
        except (KeyError, ValueError) as e:
            raise ValueError("Este archivo no es una copia de NOVA AI.") from e
        if man.get("app") != "NOVA AI":
            raise ValueError("Este archivo no es una copia de NOVA AI.")
        present = sorted({n.split("/", 1)[0] for n in z.namelist() if "/" in n} & set(PARTS))
    return {"version": man.get("version", "?"), "fecha": man.get("fecha", ""), "partes": present}


def _safe_target(data_dir: Path, rel: str) -> Path | None:
    target = (data_dir / rel).resolve()
    base = data_dir.resolve()
    return target if base in target.parents else None


def restore(src: Path, parts: list[str] | None = None, data_dir: Path = DATA_DIR) -> dict:
    """Importa la copia. Lo que había se guarda antes en copias/antes_de_importar_<fecha>."""
    info = inspect(src)
    parts = [p for p in (parts or info["partes"]) if p in info["partes"]]
    stamp = time.strftime("%Y%m%d_%H%M%S")
    saved = data_dir / "copias" / f"antes_de_importar_{stamp}"
    restored = 0
    with zipfile.ZipFile(src) as z:
        for part in parts:
            # 1) guardar lo actual de esta parte
            for name in PARTS[part][1]:
                cur = data_dir / name
                if cur.exists():
                    dst = saved / name
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    (shutil.copytree if cur.is_dir() else shutil.copy2)(cur, dst)
            # 2) traer lo de la copia
            for member in z.infolist():
                if member.is_dir() or not member.filename.startswith(part + "/"):
                    continue
                rel = member.filename.split("/", 1)[1]
                if not any(rel == n or rel.startswith(n + "/") for n in PARTS[part][1]) or member.file_size > MAX_FILE:
                    continue
                target = _safe_target(data_dir, rel)
                if target is None:
                    continue
                if rel == "ajustes.json":
                    incoming = json.loads(z.read(member).decode("utf-8"))
                    try:
                        current = json.loads((data_dir / "ajustes.json").read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        current = {}
                    merged = dict(current)
                    merged.update({k: v for k, v in incoming.items() if k not in LOCAL_KEYS and k not in SECRET_KEYS})
                    target.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(member) as fsrc, open(target, "wb") as fdst:
                        shutil.copyfileobj(fsrc, fdst)
                restored += 1
    return {"partes": parts, "ficheros": restored, "anterior": str(saved) if saved.exists() else ""}

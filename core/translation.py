"""Traducción al español de Star Citizen (la de 0zzyt0, en Google Drive).

- find_live_dirs():  dónde está instalado el juego (carpetas LIVE de todas las unidades).
- status():          ¿hay global.ini en LIVE? ¿de qué idioma? ¿cuándo se instaló?
- install():         descarga el .zip de Google Drive y lo descomprime en LIVE (sobrescribe),
                     y deja user.cfg con el idioma (guardando copia del tuyo).
- reminder_due():    cada 3 meses pregunta si comprobar y reinstalar
                     (Sí = reinstala · No = nada hasta dentro de 3 meses · Recuérdamelo = en la próxima sesión).

El juego no trae el español en un archivo aparte: la traducción vive en
LIVE\\data\\Localization\\spanish_(spain)\\global.ini y se activa con g_language en LIVE\\user.cfg.
"""
from __future__ import annotations

import hashlib
import html
import io
import logging
import os
import re
import shutil
import string
import time
import zipfile
from pathlib import Path
from typing import Callable

import requests

from .config import VERSION

log = logging.getLogger("nova.translation")

DEFAULT_URL = "https://drive.google.com/file/d/1uOYIVrtvtkBfVan1XprWtsLnI3opZuFi/view?usp=drive_link"
AUTHOR = "0zzyt0"
EVERY = 90 * 24 * 3600  # 3 meses
ROOTS = ("Program Files\\Roberts Space Industries\\StarCitizen", "Roberts Space Industries\\StarCitizen",
         "Games\\Roberts Space Industries\\StarCitizen", "Program Files (x86)\\Roberts Space Industries\\StarCitizen",
         "StarCitizen", "Games\\StarCitizen")
UA = {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) NOVA-AI/{VERSION}"}

Progress = Callable[[str, float], None]


# ------------------------------------------------------------- dónde está el juego
def is_live_dir(p: Path) -> bool:
    try:
        return p.is_dir() and ((p / "Data.p4k").exists() or (p / "Bin64").is_dir() or (p / "Game.log").exists())
    except OSError:
        return False


def find_live_dirs(settings=None, game_log: Path | None = None) -> list[Path]:
    """Carpetas LIVE encontradas (la indicada a mano y la del Game.log, primero)."""
    found: list[Path] = []

    def add(p: Path | None) -> None:
        if p and is_live_dir(p) and p not in found:
            found.append(p)

    if settings is not None:
        custom = (settings.get("juego_carpeta") or "").strip()
        if custom:
            c = Path(custom)
            add(c if c.name.upper() == "LIVE" else c / "LIVE")
            add(c)
        gl = (settings.get("gamelog_ruta") or "").strip()
        if gl:
            add(Path(gl).parent)
    if game_log:
        add(game_log.parent)
    if os.name == "nt":
        for d in string.ascii_uppercase:
            drive = f"{d}:\\"
            if not os.path.exists(drive):
                continue
            for r in ROOTS:
                add(Path(drive) / r / "LIVE")
    return found


def read_cfg_language(live: Path) -> str:
    try:
        for line in (live / "user.cfg").read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*g_language\s*=\s*([^\s;#]+)", line, re.I)
            if m:
                return m.group(1).strip()
    except OSError:
        pass
    return ""


def global_inis(live: Path) -> list[Path]:
    try:
        return sorted((live / "data" / "Localization").glob("*/global.ini"))
    except OSError:
        return []


def status(settings, live: Path | None) -> dict:
    """Estado de la traducción en esa carpeta LIVE."""
    out = {"live": str(live) if live else "", "encontrado": False, "idioma": "", "ruta": "", "espanol": False,
           "fecha": 0.0, "instalada_por_nova": float(settings.get("traduccion_instalada") or 0),
           "aviso": float(settings.get("traduccion_aviso") or 0), "url": settings.get("traduccion_url") or DEFAULT_URL}
    if not live:
        return out
    inis = global_inis(live)
    lang = read_cfg_language(live)
    chosen = next((p for p in inis if p.parent.name.lower() == lang.lower()), inis[0] if inis else None)
    if chosen:
        out.update(encontrado=True, idioma=chosen.parent.name, ruta=str(chosen),
                   espanol="spanish" in chosen.parent.name.lower() or "espa" in chosen.parent.name.lower(),
                   fecha=chosen.stat().st_mtime, activo=(lang.lower() == chosen.parent.name.lower()))
    return out


# ---------------------------------------------------------------- Google Drive
def drive_id(url: str) -> str:
    m = re.search(r"/d/([\w-]{20,})", url) or re.search(r"[?&]id=([\w-]{20,})", url)
    if m:
        return m.group(1)
    if re.fullmatch(r"[\w-]{20,}", url.strip()):
        return url.strip()
    raise ValueError("El enlace de Google Drive no es válido.")


def _confirm_form(page: str) -> tuple[str, dict] | None:
    """Página «no se puede analizar en busca de virus»: el formulario con el que se confirma la descarga."""
    m = re.search(r'<form[^>]+id="download-form"[^>]+action="([^"]+)"(.*?)</form>', page, re.S)
    if not m:
        return None
    fields = dict(re.findall(r'<input[^>]+name="([^"]+)"[^>]+value="([^"]*)"', m.group(2)))
    return html.unescape(m.group(1)), {k: html.unescape(v) for k, v in fields.items()}


def download_zip(url: str, progress: Progress | None = None, http: requests.Session | None = None) -> bytes:
    """Descarga el .zip de Google Drive (también los grandes, que piden confirmación)."""
    fid = drive_id(url)
    http = http or requests.Session()
    http.headers.update(UA)
    tries = [("https://drive.usercontent.google.com/download", {"id": fid, "export": "download", "confirm": "t"}),
             ("https://drive.google.com/uc", {"id": fid, "export": "download"})]
    last = "sin respuesta"
    for base, params in tries:
        for _ in range(2):  # 2.º intento: con el formulario de confirmación
            try:
                r = http.get(base, params=params, stream=True, timeout=(10, 60))
                r.raise_for_status()
            except requests.RequestException as e:
                last = str(e)
                break
            ctype = r.headers.get("Content-Type", "")
            if "text/html" in ctype:
                page = r.text
                form = _confirm_form(page)
                if form:
                    base, params = form
                    continue
                if re.search(r"(?i)quota|cuota", page):
                    last = "Google Drive dice que se ha superado la cuota de descargas de hoy"
                elif re.search(r"(?i)sign in|iniciar sesi|accounts\.google|request access|solicitar acceso", page):
                    last = "el archivo no es público (compártelo como «Cualquier persona con el enlace»)"
                else:
                    last = "Google Drive devolvió una página en vez del archivo"
                break
            total = int(r.headers.get("Content-Length") or 0)
            buf, got, tick = io.BytesIO(), 0, 0.0
            for chunk in r.iter_content(256 * 1024):
                buf.write(chunk)
                got += len(chunk)
                if progress and time.time() - tick > 0.25:
                    tick = time.time()
                    progress(f"Descargando… {got / 1e6:.1f} MB", (got / total * 100) if total else -1)
            data = buf.getvalue()
            if not zipfile.is_zipfile(io.BytesIO(data)):
                last = "lo descargado no es un .zip"
                break
            return data
    raise RuntimeError(f"No se pudo descargar la traducción: {last}.")


# ------------------------------------------------------------------ instalación
def _plan(zf: zipfile.ZipFile) -> tuple[str, str]:
    """(prefijo dentro del zip que corresponde a la carpeta LIVE, idioma)."""
    names = [n for n in zf.namelist() if not n.endswith("/")]
    ini = next((n for n in names if n.lower().endswith("/global.ini") or n.lower() == "global.ini"), None)
    if not ini:
        raise RuntimeError("El .zip no contiene ningún global.ini.")
    parts = ini.split("/")
    low = [p.lower() for p in parts]
    if "localization" in low:
        li = low.index("localization")
        lang = parts[li + 1] if li + 1 < len(parts) - 1 else "spanish_(spain)"
        if li >= 1 and low[li - 1] == "data":
            return "/".join(parts[:li - 1]), lang
    lang = parts[-2] if len(parts) >= 2 else "spanish_(spain)"
    return "", lang  # zip sin estructura: se coloca en data\Localization\<idioma>\


def _merge_user_cfg(live: Path, lang: str, from_zip: str = "") -> None:
    """user.cfg con g_language = <idioma> y voces en inglés, sin perder el resto de tus líneas."""
    cfg = live / "user.cfg"
    wanted = {"g_language": lang, "g_languageaudio": "english"}
    for line in from_zip.splitlines():
        m = re.match(r"\s*(g_language|g_languageAudio)\s*=\s*([^\s;#]+)", line, re.I)
        if m:
            wanted[m.group(1).lower()] = m.group(2)
    lines = []
    if cfg.exists():
        backup = live / "user.cfg.nova_copia"
        if not backup.exists():
            shutil.copy2(cfg, backup)
        lines = cfg.read_text(encoding="utf-8", errors="replace").splitlines()
    seen = set()
    out = []
    for line in lines:
        m = re.match(r"\s*(g_language|g_languageAudio)\s*=", line, re.I)
        if m:
            key = m.group(1).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(f"{'g_language' if key == 'g_language' else 'g_languageAudio'} = {wanted[key]}")
        else:
            out.append(line)
    for key, name in (("g_language", "g_language"), ("g_languageaudio", "g_languageAudio")):
        if key not in seen:
            out.append(f"{name} = {wanted[key]}")
    cfg.write_text("\r\n".join(out) + "\r\n", encoding="utf-8")


def install_zip(data: bytes, live: Path, progress: Progress | None = None) -> dict:
    """Descomprime la traducción en la carpeta LIVE (sobrescribe). Devuelve qué se instaló."""
    if not is_live_dir(live):
        raise RuntimeError(f"{live} no parece la carpeta LIVE de Star Citizen.")
    zf = zipfile.ZipFile(io.BytesIO(data))
    prefix, lang = _plan(zf)
    old_ini = next((p for p in global_inis(live) if p.parent.name.lower() == lang.lower()), None)
    old_hash = hashlib.sha256(old_ini.read_bytes()).hexdigest() if old_ini and old_ini.exists() else ""
    user_cfg = ""
    written = 0
    root = live.resolve()
    entries = [i for i in zf.infolist() if not i.is_dir()]
    for n, info in enumerate(entries, 1):
        name = info.filename
        if prefix:
            if not name.startswith(prefix + "/"):
                continue
            rel = name[len(prefix) + 1:]
        else:
            rel = name
        if not rel:
            continue
        if rel.lower() == "user.cfg":
            user_cfg = zf.read(info).decode("utf-8", "replace")
            continue
        if not prefix and rel.lower().endswith("global.ini") and "/data/" not in "/" + rel.lower():
            rel = f"data/Localization/{lang}/global.ini"
        dest = (live / rel).resolve()
        if root not in dest.parents:  # nada fuera de LIVE
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, open(dest, "wb") as dst:
            shutil.copyfileobj(src, dst)
        written += 1
        if progress:
            progress(f"Instalando {rel}", 100 * n / len(entries))
    _merge_user_cfg(live, lang, user_cfg)
    new_ini = live / "data" / "Localization" / lang / "global.ini"
    new_hash = hashlib.sha256(new_ini.read_bytes()).hexdigest() if new_ini.exists() else ""
    return {"idioma": lang, "archivos": written, "ruta": str(new_ini), "cambio": new_hash != old_hash,
            "nuevo": not old_hash}


def install(settings, live: Path, progress: Progress | None = None, http=None) -> dict:
    url = settings.get("traduccion_url") or DEFAULT_URL
    if progress:
        progress("Conectando con Google Drive…", -1)
    data = download_zip(url, progress, http)
    res = install_zip(data, live, progress)
    now = time.time()
    settings.set("traduccion_instalada", now, save=False)
    settings.set("traduccion_aviso", now + EVERY, save=False)
    settings.set("traduccion_recordar", False)
    log.info("Traducción instalada en %s: %s", live, res)
    return res


# ------------------------------------------------------------- aviso trimestral
def reminder_due(settings, st: dict, now: float | None = None) -> bool:
    """¿Toca preguntar «¿Comprobar y reinstalar la traducción?» en este arranque?"""
    if not st.get("encontrado"):
        return False
    now = now or time.time()
    if settings.get("traduccion_recordar"):
        return True
    nxt = float(settings.get("traduccion_aviso") or 0)
    if not nxt:  # primera vez que Nova ve esta traducción: empieza a contar desde la fecha del archivo
        base = float(settings.get("traduccion_instalada") or 0) or float(st.get("fecha") or now)
        settings.set("traduccion_aviso", base + EVERY)
        nxt = base + EVERY
    return now >= nxt


def answer_reminder(settings, answer: str) -> None:
    """Respuesta al aviso: 'si' (lo reinstala el que llama), 'no' o 'luego'."""
    if answer == "luego":
        settings.set("traduccion_recordar", True)
    else:
        settings.set("traduccion_recordar", False, save=False)
        settings.set("traduccion_aviso", time.time() + EVERY)


# ------------------------------------------------- v1.3: «Add your language global.ini [HERE]»
# Idiomas que Star Citizen acepta en g_language (solo carga uno de estos)
GAME_LANG_CODES = ("english", "spanish_(spain)", "spanish_(latin_america)", "french_(france)", "german_(germany)",
                   "italian_(italy)", "portuguese_(brazil)", "polish_(poland)", "japanese_(japan)",
                   "korean_(south_korea)", "chinese_(simplified)", "chinese_(traditional)")
INI_LINE = re.compile(r"^[\w.\-@]+(?:,P)?\s*=", re.M)
BACKUP_SUFFIX = ".antes_de_nova"


def check_ini(data: bytes) -> int:
    """Nº de textos del global.ini; ValueError si no lo parece."""
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("El archivo es demasiado grande para ser un global.ini (máximo 64 MB).")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = data.decode("utf-16")
        except UnicodeError:
            raise ValueError("El archivo no es un global.ini de Star Citizen (no es texto UTF-8).") from None
    n = len(INI_LINE.findall(text))
    if n < 500:
        raise ValueError("El archivo no parece un global.ini de Star Citizen (tiene muy pocos textos).")
    return n


def install_custom_ini(data: bytes, live: Path, lang: str, settings=None) -> dict:
    """Copia tu global.ini a LIVE\\data\\Localization\\<lang>\\ (guardando el que hubiera) y ajusta user.cfg."""
    if lang not in GAME_LANG_CODES:
        raise ValueError(f"Star Citizen no admite el idioma «{lang}».")
    if not is_live_dir(live):
        raise ValueError(f"{live} no parece la carpeta LIVE de Star Citizen.")
    n = check_ini(data)
    dest = live / "data" / "Localization" / lang / "global.ini"
    dest.parent.mkdir(parents=True, exist_ok=True)
    backup = dest.with_name("global.ini" + BACKUP_SUFFIX)
    had = dest.exists()
    if had and not backup.exists():
        shutil.copy2(dest, backup)
    before = read_cfg_language(live)
    dest.write_bytes(data)
    _merge_user_cfg(live, lang)
    if settings is not None:
        settings.set("globalini_ruta", str(dest), save=False)
        settings.set("globalini_propio", str(dest), save=False)
        settings.set("globalini_propio_idioma", lang, save=False)
        settings.set("globalini_idioma_antes", before or "", save=False)
        settings.save()
    log.info("global.ini propio instalado en %s (%d textos, copia: %s)", dest, n, backup if had else "no había")
    return {"ruta": str(dest), "idioma": lang, "textos": n, "copia": str(backup) if backup.exists() else "",
            "antes": before}


def uninstall_custom_ini(settings) -> dict:
    """Deshace lo anterior: devuelve el global.ini que había (o lo quita) y el idioma de user.cfg."""
    path = (settings.get("globalini_propio") or "").strip()
    if not path:
        raise ValueError("No hay ningún global.ini instalado desde NOVA AI.")
    dest = Path(path)
    backup = dest.with_name("global.ini" + BACKUP_SUFFIX)
    restored = False
    if backup.exists():
        shutil.copy2(backup, dest)
        backup.unlink(missing_ok=True)
        restored = True
    else:
        dest.unlink(missing_ok=True)
    live = dest.parents[3] if len(dest.parents) > 3 else None
    before = settings.get("globalini_idioma_antes") or ""
    if live and is_live_dir(live):
        if before:
            _merge_user_cfg(live, before)
        else:  # no había idioma: quita la línea que pusimos
            cfg = live / "user.cfg"
            if cfg.exists():
                lines = [ln for ln in cfg.read_text(encoding="utf-8", errors="replace").splitlines()
                         if not re.match(r"\s*g_language\s*=", ln, re.I)]
                cfg.write_text("\r\n".join(lines) + ("\r\n" if lines else ""), encoding="utf-8")
    if (settings.get("globalini_ruta") or "") == path:
        settings.set("globalini_ruta", "", save=False)
    settings.set("globalini_propio", "", save=False)
    settings.set("globalini_propio_idioma", "", save=False)
    settings.save()
    return {"restaurado": restored, "idioma": before}

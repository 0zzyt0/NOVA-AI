"""2.1.6: copias de seguridad de tus controles de Star Citizen (y de lo que NOVA ha aprendido).

Qué se guarda de cada versión del juego (LIVE, PTU, EPTU, HOTFIX, TECH-PREVIEW):
  user/client/<n>/Profiles/default/actionmaps.xml   teclas de teclado, ratón, mando y HOTAS/HOSAS
  user/client/<n>/Profiles/default/attributes.xml   opciones (sensibilidades, curvas, invertir ejes…)
  user/client/<n>/Profiles/default/profile.xml
  user/client/<n>/controls/mappings/*.xml           perfiles de controles que exportaste desde el juego
  user/client/<n>/Profiles/defaultActions.xml       (solo para comparar versiones: nunca se repone)
  user.cfg                                          (se repone solo si falta)

Las copias van a Documentos\\NOVA AI\\Copias de seguridad (fuera del juego y de NOVA: sobreviven a las
actualizaciones de los dos y a una reinstalación). Cada copia es una carpeta con los archivos tal cual y un
manifest.json (versión del juego, fecha, huellas y resumen de teclas).

Cuándo actúa (sin tocar nada mientras juegas):
  · al arrancar NOVA, al abrir el juego y al cerrarlo compara tus controles con la última copia;
  · si los has cambiado → «Veo que has realizado cambios en los controles. ¿Quieres hacer una copia…?»
    [SÍ] [NO] [MÁS TARDE] [AL CERRAR NOVA];
  · si el juego se ha actualizado y tus controles ya no son los de la copia (los ha borrado o cambiado) →
    «¿Quiere reponer sus controles personalizados?», con las opciones nuevas que trae la versión para que las
    revises a mano. Reponer MEZCLA: tus teclas de la copia + lo nuevo del juego (no se pierde nada);
  · reponer solo con el juego cerrado (el juego reescribe sus archivos al salir). Antes de reponer se guarda
    lo que había, así que siempre se puede volver atrás.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from . import i18n

log = logging.getLogger("nova.controles")

KEEP_PER_CHANNEL = 20
KEEP_NOVA = 10
POLL_S = 20
LATER_S = 2 * 3600

# Lo que define «tus controles» (si cambia, se pregunta) y lo que solo acompaña a la copia
WATCH_PATTERNS = ("user/client/*/Profiles/default/actionmaps.xml", "user/client/*/controls/mappings/*.xml")
EXTRA_PATTERNS = ("user/client/*/Profiles/default/attributes.xml", "user/client/*/Profiles/default/profile.xml",
                  "user/client/*/Profiles/defaultActions.xml")
NEVER_RESTORE = ("defaultActions.xml",)
DEVICE = {"kb": "teclado", "mo": "ratón", "js": "joystick", "gp": "mando"}


# ------------------------------------------------------------------------- dónde
def documents_dir() -> Path:
    """La carpeta Documentos de verdad (también si OneDrive la ha movido)."""
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
                v, _ = winreg.QueryValueEx(k, "Personal")
                p = Path(os.path.expandvars(v))
                if p.is_dir():
                    return p
        except OSError:
            pass
    return Path.home() / "Documents"


def safe_root(settings=None) -> Path:
    custom = (settings.get("copias_ruta") if settings is not None else "") or ""
    return Path(custom) if custom.strip() else documents_dir() / "NOVA AI" / "Copias de seguridad"


# ------------------------------------------------------------------------- leer los controles
def _files(ch: Path, patterns) -> list[Path]:
    out: list[Path] = []
    for pat in patterns:
        out.extend(p for p in ch.glob(pat) if p.is_file())
    return sorted(set(out))


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fingerprint(ch: Path) -> str:
    """Huella de tus controles (teclas y perfiles exportados) en esa versión del juego."""
    h = hashlib.sha256()
    for p in _files(ch, WATCH_PATTERNS):
        rel = p.relative_to(ch).as_posix().lower()
        try:
            h.update(rel.encode() + b"\0" + _normalized(p) + b"\0")
        except OSError:
            continue
    return h.hexdigest()


def _normalized(p: Path) -> bytes:
    """El contenido sin espacios ni saltos de línea de más (el juego a veces solo cambia el formato)."""
    return re.sub(rb"\s+", b" ", p.read_bytes()).strip()


def summary(ch: Path) -> dict:
    """Cuántas teclas tuyas hay, por dispositivo, y qué joysticks/HOTAS tiene el perfil."""
    count = {k: 0 for k in DEVICE}
    devices: list[str] = []
    actions = 0
    for p in ch.glob("user/client/*/Profiles/default/actionmaps.xml"):
        try:
            root = ET.parse(p).getroot()
        except (ET.ParseError, OSError):
            continue
        gp_products = []
        for opt in root.iter("options"):
            prod = (opt.get("Product") or "").strip()
            if prod and opt.get("type") == "gamepad":
                gp_products.append(re.sub(r"\s*\{.*\}\s*$", "", prod).strip())
            if prod and opt.get("type") == "joystick":
                name = re.sub(r"\s*\{.*\}\s*$", "", prod).strip()
                if name and name not in devices:
                    devices.append(name)
        for act in root.iter("action"):
            hit = False
            for rb in act.iter("rebind"):
                dev = (rb.get("input") or "")[:2]
                if dev in count:
                    count[dev] += 1
                    hit = True
            actions += hit
        if count["gp"]:  # el mando solo cuenta si tiene teclas tuyas (el juego siempre lo apunta)
            devices += [g for g in gp_products if g and g not in devices]
    mappings = len(list(ch.glob("user/client/*/controls/mappings/*.xml")))
    return {"teclas": sum(count.values()), "acciones": actions, "dispositivos": count, "mandos": devices,
            "perfiles": mappings, "hay_archivo": any(ch.glob("user/client/*/Profiles/default/actionmaps.xml"))}


def summary_text(s: dict) -> str:
    if not s.get("teclas"):
        return i18n.tr("sin teclas personalizadas")
    parts = [f"{i18n.tr(DEVICE[k])} {n}" for k, n in s["dispositivos"].items() if n]
    out = i18n.tr("{n} teclas personalizadas ({d})", n=s["teclas"], d=", ".join(parts))
    if s.get("mandos"):
        out += " · " + ", ".join(s["mandos"][:3])
    return out


def _attr_names(p: Path) -> set[str]:
    try:
        return {a.get("name") for a in ET.parse(p).getroot().iter("Attr") if a.get("name")}
    except (ET.ParseError, OSError):
        return set()


def _entries(p: Path) -> set[str]:
    try:
        return {e.get("Description") for e in ET.parse(p).getroot().iter("Entry") if e.get("Description")}
    except (ET.ParseError, OSError):
        return set()


# ------------------------------------------------------------------------- copias
class ControlBackups:
    """Copias de los controles de cada versión del juego, en la carpeta segura."""

    def __init__(self, settings) -> None:
        self.settings = settings
        self._lock = threading.RLock()

    @property
    def root(self) -> Path:
        return safe_root(self.settings) / "Controles"

    def list(self, channel: str | None = None) -> list[dict]:
        """Copias (la más nueva primero), de un canal o de todos."""
        out = []
        base = self.root
        chans = [channel] if channel else ([d.name for d in base.iterdir() if d.is_dir()] if base.is_dir() else [])
        for ch in chans:
            d = base / ch
            if not d.is_dir():
                continue
            for c in d.iterdir():
                man = c / "manifest.json"
                if c.is_dir() and man.is_file():
                    try:
                        m = json.loads(man.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        continue
                    m["id"] = f"{ch}/{c.name}"
                    m["ruta"] = str(c)
                    out.append(m)
        return sorted(out, key=lambda m: m.get("ts", 0), reverse=True)

    def latest(self, channel: str, real_only: bool = True) -> dict | None:
        for m in self.list(channel):
            if not real_only or m.get("motivo") != "antes_de_reponer":
                return m
        return None

    def backup(self, ch: Path, motivo: str = "manual", version: str = "") -> dict:
        """Copia los controles de esa versión del juego. Si son iguales a la última copia, no repite."""
        with self._lock:
            files = _files(ch, WATCH_PATTERNS + EXTRA_PATTERNS)
            if (ch / "user.cfg").is_file():
                files.append(ch / "user.cfg")
            if not files:
                raise RuntimeError(i18n.tr("No hay controles guardados en {c} todavía (abre el juego una vez).", c=ch.name))
            fp = fingerprint(ch)
            last = self.latest(ch.name, real_only=False)
            if last and last.get("huella") == fp and motivo not in ("antes_de_reponer", "manual"):
                return last
            stamp = time.strftime("%Y%m%d_%H%M%S")
            dest = self.root / ch.name / stamp
            n = 1
            while dest.exists():
                n += 1
                dest = self.root / ch.name / f"{stamp}_{n}"
            hashes = {}
            for f in files:
                rel = f.relative_to(ch).as_posix()
                target = dest / "archivos" / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, target)
                hashes[rel] = _sha(target)
            s = summary(ch)
            man = {"app": "NOVA AI", "tipo": "controles", "canal": ch.name, "version": version, "ts": time.time(),
                   "fecha": time.strftime("%Y-%m-%d %H:%M"), "motivo": motivo, "huella": fp, "archivos": hashes,
                   "resumen": s}
            (dest / "manifest.json").write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")
            self._prune(ch.name)
            log.info("Copia de controles %s (%s): %s", ch.name, motivo, summary_text(s))
            man["id"] = f"{ch.name}/{dest.name}"
            man["ruta"] = str(dest)
            return man

    def _prune(self, channel: str) -> None:
        copies = self.list(channel)
        real = [m for m in copies if m.get("motivo") != "antes_de_reponer"]
        before = [m for m in copies if m.get("motivo") == "antes_de_reponer"]
        for m in real[KEEP_PER_CHANNEL:] + before[5:]:
            shutil.rmtree(m["ruta"], ignore_errors=True)

    def find(self, copy_id: str) -> dict | None:
        ch = copy_id.split("/", 1)[0]
        return next((m for m in self.list(ch) if m["id"] == copy_id), None)

    # --------------------------------------------------------------- reponer (mezclando)
    def restore(self, ch: Path, copy: dict, version: str = "") -> dict:
        """Repone los controles de una copia en esa versión del juego (puede ser de otra versión: LIVE → PTU).
        Mezcla: tus teclas de la copia + lo que el juego tenga ahora y la copia no. Antes guarda lo actual."""
        with self._lock:
            src = Path(copy["ruta"]) / "archivos"
            if not src.is_dir():
                raise RuntimeError(i18n.tr("La copia está incompleta."))
            # comprobar que la copia está sana antes de tocar nada
            for rel, h in (copy.get("archivos") or {}).items():
                f = src / rel
                if not f.is_file() or _sha(f) != h:
                    raise RuntimeError(i18n.tr("La copia está dañada ({f}): no la repongo.", f=rel))
            safety = None
            if _files(ch, WATCH_PATTERNS + EXTRA_PATTERNS):
                safety = self.backup(ch, "antes_de_reponer", version)
            done = []
            for f in sorted(src.rglob("*")):
                if not f.is_file() or f.name in NEVER_RESTORE:
                    continue
                rel = f.relative_to(src).as_posix()
                target = ch / rel
                if rel == "user.cfg":
                    if target.exists():
                        continue  # el user.cfg actual manda (traducción, telemetría…); solo se repone si falta
                    data = f.read_bytes()
                elif f.name == "actionmaps.xml" and target.is_file():
                    data = merge_actionmaps(f, target)
                elif f.name == "attributes.xml" and target.is_file():
                    data = merge_attributes(f, target)
                else:
                    data = f.read_bytes()
                if f.suffix.lower() == ".xml":
                    ET.fromstring(data)  # nunca escribir un XML roto
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = target.with_name(target.name + ".nova_tmp")
                tmp.write_bytes(data)
                os.replace(tmp, target)
                done.append(rel)
            log.info("Controles repuestos en %s desde %s (%d archivos)", ch.name, copy.get("id"), len(done))
            return {"archivos": done, "anterior": safety.get("id") if safety else "", "resumen": summary(ch)}


def _key(el: ET.Element) -> str:
    return el.get("name") or ""


def merge_actionmaps(backup_file: Path, current_file: Path) -> bytes:
    """Tus teclas de la copia + las acciones que el archivo actual tiene y la copia no."""
    base = ET.parse(backup_file)
    cur = ET.parse(current_file)
    bprof = base.getroot().find("ActionProfiles")
    cprof = cur.getroot().find("ActionProfiles")
    if bprof is None or cprof is None:
        return backup_file.read_bytes()
    maps = {_key(m): m for m in bprof.findall("actionmap")}
    for cmap in cprof.findall("actionmap"):
        bmap = maps.get(_key(cmap))
        if bmap is None:
            bprof.append(cmap)
            continue
        have = {_key(a) for a in bmap.findall("action")}
        for act in cmap.findall("action"):
            if _key(act) not in have:
                bmap.append(act)
    ET.indent(base, space=" ")
    return ET.tostring(base.getroot(), encoding="unicode").encode("utf-8") + b"\n"  # sin <?xml?>, como el juego


def merge_attributes(backup_file: Path, current_file: Path) -> bytes:
    """Las opciones actuales con tus valores de la copia (las opciones nuevas del juego se quedan)."""
    cur = ET.parse(current_file)
    mine = {a.get("name"): a.get("value") for a in ET.parse(backup_file).getroot().iter("Attr")}
    root = cur.getroot()
    seen = set()
    for a in root.iter("Attr"):
        n = a.get("name")
        seen.add(n)
        if n in mine and mine[n] is not None:
            a.set("value", mine[n])
    for n, v in mine.items():
        if n not in seen and v is not None:
            ET.SubElement(root, "Attr", {"name": n, "value": v})
    ET.indent(cur, space=" ")
    return ET.tostring(root, encoding="unicode").encode("utf-8") + b"\n"


def new_options(ch: Path, copy: dict | None) -> list[str]:
    """Lo que trae la versión actual del juego que la copia no tenía (para revisarlo a mano)."""
    if not copy:
        return []
    src = Path(copy["ruta"]) / "archivos"
    out: list[str] = []
    for p in ch.glob("user/client/*/Profiles/default/attributes.xml"):
        old = src / p.relative_to(ch)
        if old.is_file():
            out += [f"{i18n.tr('Opción')}: {n}" for n in sorted(_attr_names(p) - _attr_names(old))]
    for p in ch.glob("user/client/*/Profiles/defaultActions.xml"):
        old = src / p.relative_to(ch)
        if old.is_file():
            out += [f"{i18n.tr('Acción')}: {n}" for n in sorted(_entries(p) - _entries(old))]
    return list(dict.fromkeys(out))[:40]


# ------------------------------------------------------------------------- copias de NOVA
def nova_backup(settings, motivo: str) -> str:
    """Copia de lo que NOVA ha aprendido (ajustes sin claves, comandos, memoria, diccionario, bitácora)."""
    from . import backup

    settings.save()
    d = safe_root(settings) / "NOVA"
    d.mkdir(parents=True, exist_ok=True)
    name = f"NOVA_{time.strftime('%Y-%m-%d_%H%M%S')}_{re.sub(r'[^a-z0-9]+', '_', motivo.lower())[:30]}{backup.EXT}"
    r = backup.export(d / name)
    copies = sorted(d.glob("NOVA_*" + backup.EXT), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in copies[KEEP_NOVA:]:
        try:
            old.unlink()
        except OSError:
            pass
    settings.set("copia_nova_ultima", time.time())
    log.info("Copia de NOVA (%s): %s", motivo, r["ruta"])
    return r["ruta"]


def latest_nova_backup(root: Path | None = None) -> Path | None:
    from . import backup

    d = (root or safe_root()) / "NOVA"
    if not d.is_dir():
        return None
    copies = sorted(d.glob("NOVA_*" + backup.EXT), key=lambda p: p.stat().st_mtime, reverse=True)
    return copies[0] if copies else None


def restore_nova_if_lost(data_dir: Path) -> str:
    """Al arrancar, antes de leer los ajustes: si la carpeta de datos está vacía (Windows reinstalado, carpeta
    borrada…) y hay una copia de NOVA en Documentos, la repone. Devuelve la ruta de la copia o ''."""
    from . import backup

    if (data_dir / "ajustes.json").exists() or (data_dir / "memoria.json").exists():
        return ""
    src = latest_nova_backup()
    if not src:
        return ""
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        backup.restore(src, None, data_dir)
        log.info("Datos de NOVA repuestos desde %s", src)
        return str(src)
    except Exception:  # noqa: BLE001
        log.exception("No pude reponer la copia de NOVA")
        return ""


# ------------------------------------------------------------------------- el vigilante
class ControlGuard:
    """Vigila tus controles: pregunta si los cambias y ofrece reponerlos cuando el juego se actualiza."""

    def __init__(self, settings, gamelog=None) -> None:
        self.settings = settings
        self.gamelog = gamelog
        self.store = ControlBackups(settings)
        self.pending: dict[str, dict] = {}  # id → pregunta en la ventana
        self.on_prompt = lambda p: None  # la ventana (y la bandeja) muestran la pregunta
        self.on_message = lambda text: None
        self.on_restored = lambda ch: None  # para que NOVA vuelva a leer tus teclas
        self.on_attention = lambda title, text, show: None  # bandeja + abrir la ventana
        self.game_running = False
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------ estado guardado
    def _state(self) -> dict:
        return dict(self.settings.get("controles_estado") or {})

    def _set_state(self, ch: str, **kw) -> None:
        st = self._state()
        st[ch] = {**st.get(ch, {}), **kw}
        self.settings.set("controles_estado", st)

    def channels(self) -> list[Path]:
        from .telemetry_setup import channel_dirs

        try:
            return [c for c in channel_dirs(self.settings, self.gamelog) if (c / "user").is_dir() or
                    self.store.latest(c.name)]
        except Exception:  # noqa: BLE001
            log.exception("Buscando las versiones del juego")
            return []

    @staticmethod
    def version(ch: Path) -> str:
        from .telemetry_setup import version_of

        return version_of(ch)

    def _running(self) -> bool:
        from .telemetry_setup import running

        return "StarCitizen.exe" in running(("StarCitizen.exe",))

    # ------------------------------------------------------------ bucle
    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, daemon=True, name="controles")
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        time.sleep(8)  # que arranque todo lo demás primero
        try:
            self.game_running = self._running()
            self.check("inicio")
        except Exception:  # noqa: BLE001
            log.exception("Controles al arrancar")
        while not self._stop.wait(POLL_S):
            try:
                now = self._running()
                if now != self.game_running:
                    self.game_running = now
                    self.check("juego_abierto" if now else "juego_cerrado")
                elif not now and any(t <= time.time() for t in self._later_times()):
                    self.check("mas_tarde")
            except Exception:  # noqa: BLE001
                log.exception("Vigilando los controles")

    def _later_times(self) -> list[float]:
        return [float(v.get("mas_tarde_hasta") or 0) for v in self._state().values() if v.get("mas_tarde_hasta")]

    # ------------------------------------------------------------ la comprobación
    def check(self, trigger: str = "manual") -> list[dict]:
        """Compara cada versión del juego con su última copia y pregunta o repone si hace falta."""
        if not self.settings.get("controles_vigilar", True):
            return []
        asked = []
        with self._lock:
            for ch in self.channels():
                try:
                    p = self._check_channel(ch, trigger)
                except Exception:  # noqa: BLE001
                    log.exception("Controles de %s", ch.name)
                    continue
                if p:
                    asked.append(p)
        if trigger == "juego_cerrado":
            self._do_deferred()
        return asked

    def _check_channel(self, ch: Path, trigger: str) -> dict | None:
        name = ch.name
        st = self._state().get(name, {})
        ver = self.version(ch)
        s = summary(ch)
        last = self.store.latest(name)
        fp = fingerprint(ch)
        if last is None:
            if s["teclas"] and not self.game_running:
                m = self.store.backup(ch, "primera", ver)
                self._set_state(name, version=ver)
                self.on_message(i18n.tr("🎮 Primera copia de seguridad de tus controles de {c}: {s}.", c=name,
                                        s=summary_text(s)))
                return None
            return None
        if fp == last.get("huella"):
            if ver and ver != last.get("version") and not self.game_running:
                # el juego se actualizó y respetó tus controles: copia nueva con la versión y aviso de lo nuevo
                news = new_options(ch, last)
                self.store.backup(ch, "nueva_version", ver)
                if news:
                    self.on_message(i18n.tr("🎮 Star Citizen {v} ({c}) ha conservado tus controles. Trae opciones "
                                            "nuevas que conviene revisar a mano: {n}.", v=ver, c=name,
                                            n=", ".join(x.split(": ", 1)[-1] for x in news[:8])))
            return None
        # ¿ya contestaste a esto?
        if st.get("descartado") == fp:
            return None
        if trigger != "mas_tarde" and float(st.get("mas_tarde_hasta") or 0) > time.time():
            return None
        version_changed = bool(ver and last.get("version") and ver != last.get("version"))
        wiped = last["resumen"].get("teclas", 0) > 0 and (not s["hay_archivo"] or s["teclas"] < last["resumen"]["teclas"])
        if version_changed or (wiped and not s["hay_archivo"]):
            return self._ask_restore(ch, last, ver, s, fp, version_changed)
        if self.settings.get("controles_copia_sin_preguntar"):
            if not self.game_running:
                self.store.backup(ch, "cambios", ver)
                self.on_message(i18n.tr("🎮 Copia de seguridad de tus controles de {c} hecha: {s}.", c=name,
                                        s=summary_text(s)))
            return None
        if trigger == "juego_abierto":
            # mientras juegas no se pregunta: se hará al cerrar el juego
            return None
        return self._ask(ch, "copia", fp, ver, s, last,
                         i18n.tr("Veo que has realizado cambios en los controles de {c}. ¿Quieres realizar una copia "
                                 "de seguridad por si en un futuro Star Citizen se actualiza?", c=name))

    def _ask_restore(self, ch, last, ver, s, fp, version_changed) -> dict | None:
        name = ch.name
        news = new_options(ch, last)
        if self.settings.get("controles_reponer_auto") and not self.game_running:
            r = self.store.restore(ch, last, ver)
            self._after_restore(ch, ver)
            self.on_message(i18n.tr("🎮 Star Citizen {v} había cambiado tus controles de {c}: los he repuesto "
                                    "desde la copia del {f} ({s}).", v=ver or "?", c=name, f=last.get("fecha", ""),
                                    s=summary_text(r["resumen"])))
            self._news_message(ver, name, news)
            return None
        why = (i18n.tr("Star Citizen se ha actualizado a la versión {v} en {c} y tus controles ya no son los de tu "
                       "copia ({s}).", v=ver, c=name, s=summary_text(last["resumen"])) if version_changed else
               i18n.tr("Tus controles de {c} han desaparecido (el juego ha empezado de cero).", c=name))
        text = why + " " + i18n.tr("¿Quiere reponer sus controles personalizados?")
        if self.game_running:
            text += " " + i18n.tr("Se repondrán al cerrar el juego.")
        return self._ask(ch, "reponer", fp, ver, s, last, text, news=news)

    def _ask(self, ch, kind, fp, ver, s, last, text, news=None) -> dict:
        pid = f"{kind}:{ch.name}"
        again = pid in self.pending and self.pending[pid].get("huella") == fp
        p = {"id": pid, "tipo": kind, "canal": ch.name, "version": ver, "texto": text, "huella": fp,
             "actual": summary_text(s), "copia": last.get("id") if last else "",
             "copia_fecha": last.get("fecha", "") if last else "",
             "copia_resumen": summary_text(last["resumen"]) if last else "", "nuevas": news or [],
             "ts": time.time()}
        self.pending[pid] = p
        self.on_prompt(p)
        if not again or not self.game_running:
            self.on_attention(i18n.tr("Controles de Star Citizen"), text, not self.game_running)
        return p

    def _news_message(self, ver, name, news) -> None:
        if news:
            self.on_message(i18n.tr("🎮 Star Citizen {v} ({c}) trae opciones nuevas: revísalas a mano en el juego: "
                                    "{n}.", v=ver or "?", c=name, n=", ".join(x.split(": ", 1)[-1] for x in news[:8])))

    # ------------------------------------------------------------ respuestas
    def answer(self, pid: str, choice: str) -> dict:
        """SÍ / NO / MÁS TARDE / AL CERRAR NOVA (y REPONER / NO para la pregunta de reponer)."""
        p = self.pending.pop(pid, None)
        if not p:
            return {"ok": False, "texto": i18n.tr("Esa pregunta ya no está pendiente.")}
        ch = self._channel(p["canal"])
        name = p["canal"]
        if choice == "no":
            self._set_state(name, descartado=p["huella"], mas_tarde_hasta=0)
            if p["tipo"] == "reponer" and ch is not None and not self.game_running:
                # te quedas con los controles nuevos: que la próxima copia parta de ellos
                self.store.backup(ch, "nueva_version", p["version"])
            return {"ok": True, "texto": i18n.tr("De acuerdo: no te lo vuelvo a preguntar por estos cambios.")}
        if choice == "mas_tarde":
            self._set_state(name, mas_tarde_hasta=time.time() + LATER_S)
            return {"ok": True, "texto": i18n.tr("Te lo vuelvo a preguntar más tarde.")}
        if choice == "al_cerrar":
            todo = set(self.settings.get("controles_al_cerrar") or [])
            todo.add(name)
            self.settings.set("controles_al_cerrar", sorted(todo))
            self._set_state(name, mas_tarde_hasta=time.time() + 365 * 86400)
            return {"ok": True, "texto": i18n.tr("Haré la copia de {c} cuando cierres NOVA.", c=name)}
        if ch is None:
            return {"ok": False, "texto": i18n.tr("No encuentro {c} en este PC.", c=name)}
        if p["tipo"] == "copia":
            if self.game_running:
                self._defer(name, "copia", "")
                return {"ok": True, "texto": i18n.tr("Haré la copia en cuanto cierres el juego.")}
            m = self.store.backup(ch, "cambios", p["version"])
            self._set_state(name, mas_tarde_hasta=0, descartado="")
            return {"ok": True, "texto": i18n.tr("Copia hecha: {s}.", s=summary_text(m["resumen"]))}
        # reponer
        if self.game_running:
            self._defer(name, "reponer", p["copia"])
            return {"ok": True, "texto": i18n.tr("Los repondré en cuanto cierres el juego.")}
        return self.restore(name, p["copia"])

    def _defer(self, name: str, what: str, copy_id: str) -> None:
        d = dict(self.settings.get("controles_diferido") or {})
        d[name] = {"que": what, "copia": copy_id}
        self.settings.set("controles_diferido", d)

    def _do_deferred(self) -> None:
        d = dict(self.settings.get("controles_diferido") or {})
        if not d or self.game_running:
            return
        self.settings.set("controles_diferido", {})
        for name, job in d.items():
            ch = self._channel(name)
            if ch is None:
                continue
            try:
                if job.get("que") == "reponer":
                    r = self.restore(name, job.get("copia") or "")
                    self.on_attention(i18n.tr("Controles de Star Citizen"), r["texto"], False)
                else:
                    m = self.store.backup(ch, "cambios", self.version(ch))
                    self.on_message(i18n.tr("🎮 Copia de seguridad de tus controles de {c} hecha: {s}.", c=name,
                                            s=summary_text(m["resumen"])))
            except Exception as e:  # noqa: BLE001
                log.exception("Tarea pendiente de controles")
                self.on_message(f"⚠ {e}")

    def _channel(self, name: str) -> Path | None:
        return next((c for c in self.channels() if c.name == name), None)

    def restore(self, name: str, copy_id: str = "") -> dict:
        """Repone en `name` la copia indicada (o la última de esa versión; si no hay, la última de cualquiera)."""
        if self._running():
            raise RuntimeError(i18n.tr("Cierra Star Citizen antes de reponer los controles (el juego reescribe sus "
                                       "archivos al salir)."))
        ch = self._channel(name)
        if ch is None:
            raise RuntimeError(i18n.tr("No encuentro {c} en este PC.", c=name))
        copy = self.store.find(copy_id) if copy_id else (self.store.latest(name) or
                                                           next(iter(self.store.list()), None))
        if not copy:
            raise RuntimeError(i18n.tr("Todavía no hay ninguna copia de tus controles."))
        ver = self.version(ch)
        news = new_options(ch, copy)
        r = self.store.restore(ch, copy, ver)
        self._after_restore(ch, ver)
        for pid in [k for k, v in self.pending.items() if v["canal"] == name]:
            self.pending.pop(pid, None)
        text = i18n.tr("Controles repuestos en {c} desde la copia de {o} del {f}: {s}.", c=name, o=copy.get("canal"),
                       f=copy.get("fecha", ""), s=summary_text(r["resumen"]))
        if news:
            text += " " + i18n.tr("Esta versión trae opciones nuevas: revísalas a mano en el juego ({n}).",
                                  n=", ".join(x.split(": ", 1)[-1] for x in news[:6]))
        self.on_message("🎮 " + text)
        return {"ok": True, "texto": text, "nuevas": news, "anterior": r.get("anterior", "")}

    def _after_restore(self, ch: Path, ver: str) -> None:
        m = self.store.backup(ch, "repuesta", ver)  # lo repuesto pasa a ser la copia de referencia
        self._set_state(ch.name, version=ver, descartado="", mas_tarde_hasta=0)
        try:
            self.on_restored(ch)
        except Exception:  # noqa: BLE001
            log.exception("Releyendo las teclas")
        return m

    def backup_now(self, name: str) -> dict:
        ch = self._channel(name)
        if ch is None:
            raise RuntimeError(i18n.tr("No encuentro {c} en este PC.", c=name))
        m = self.store.backup(ch, "manual", self.version(ch))
        self._set_state(name, descartado="", mas_tarde_hasta=0)
        for pid in [k for k, v in self.pending.items() if v["canal"] == name and v["tipo"] == "copia"]:
            self.pending.pop(pid, None)
        return m

    def on_nova_exit(self) -> None:
        """«AL CERRAR NOVA»: las copias que dejaste para el final."""
        todo = list(self.settings.get("controles_al_cerrar") or [])
        if not todo:
            return
        for name in todo:
            ch = self._channel(name)
            if ch is not None:
                try:
                    self.store.backup(ch, "al_cerrar_nova", self.version(ch))
                    self._set_state(name, mas_tarde_hasta=0, descartado="")
                except Exception:  # noqa: BLE001
                    log.exception("Copia al cerrar NOVA")
        self.settings.set("controles_al_cerrar", [])

    # ------------------------------------------------------------ para la ventana
    def status(self) -> dict:
        chans = []
        for ch in self.channels():
            s = summary(ch)
            last = self.store.latest(ch.name)
            fp = fingerprint(ch)
            ver = self.version(ch)
            chans.append({"canal": ch.name, "version": ver, "resumen": summary_text(s), "teclas": s["teclas"],
                          "ultima": last.get("fecha", "") if last else "",
                          "ultima_version": last.get("version", "") if last else "",
                          "al_dia": bool(last and last.get("huella") == fp),
                          "pendiente_al_cerrar": ch.name in (self.settings.get("controles_al_cerrar") or [])})
        copies = [{"id": m["id"], "canal": m.get("canal"), "fecha": m.get("fecha"), "version": m.get("version", ""),
                   "motivo": m.get("motivo", ""), "resumen": summary_text(m.get("resumen") or {})}
                  for m in self.store.list()]
        return {"canales": chans, "copias": copies[:60], "carpeta": str(safe_root(self.settings)),
                "preguntas": list(self.pending.values()), "juego_abierto": self.game_running}

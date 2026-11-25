"""2.1 · Telemetría en directo de Star Citizen (servidor gRPC local del propio juego).

Desde la 4.10.2 (LIVE, solo lectura) y la 5.0 (PTU) el juego puede servir en 127.0.0.1:2942 un flujo
`sc.game.telemetry.v1.GameTelemetryService/TelemetryStream` con el estado REAL de tu personaje y de tu
nave unas 17-20 veces por segundo: salud, oxígeno, hambre, sed, temperatura, combustible de hidrógeno y
cuántico, escudos, casco, velocidad, viaje cuántico, contrato seguido…

- No toca el juego: solo se conecta a ese servidor local (como un cliente más) y lee.
- El esquema (.proto) no lo publica CIG: se saca del StarCitizen.exe que tienes instalado
  (telemetry_schema), así los nombres de campo siempre son los de tu versión.
- Hay que activarlo en el juego (telemetry_setup: botón «ACTIVAR» en Juego › Avisos).

Con esto NOVA avisa en voz (sed, hambre, oxígeno, salud, hidrógeno, cuántico, escudos, casco, averías,
misiles), contesta al momento «¿cuánto hidrógeno me queda?» sin gastar IA y la IA ve los valores reales.
"""
from __future__ import annotations

import logging
import re
import socket
import threading
import time
import unicodedata
from pathlib import Path
from typing import Callable

from . import i18n
from .gamelog import GameEvent

log = logging.getLogger("nova.telemetry")

DEFAULT_PORT = 2942
STREAM = "/sc.game.telemetry.v1.GameTelemetryService/TelemetryStream"
PKG = "sc.game.telemetry.v1"
FRESH_S = 5.0  # un estado con más de 5 s ya no es «en directo»
PROCESS_EVERY = 0.2  # se procesan como mucho 5 fotogramas por segundo (llegan 17-20)
GRACE_S = 10.0  # tras conectar o cambiar de nave: primero se mira, luego se avisa
HOLD_S = 2.0  # un valor tiene que mantenerse por debajo del umbral 2 s para avisar

# Hambre y sed: la telemetría da un indicador (actual/máximo) como el del HUD, que BAJA con el tiempo
# (100 % = saciado). Si en una versión del juego resultase al revés, basta con poner esto a False.
SATIETY_HIGH_IS_GOOD = True

# (tipo de aviso, categoría, umbral, se rearma por encima de)
THRESHOLDS = {
    "sed_baja": ("cuerpo", 0.25, 0.40), "sed_critica": ("cuerpo", 0.10, 0.20),
    "hambre_baja": ("cuerpo", 0.25, 0.40), "hambre_critica": ("cuerpo", 0.10, 0.20),
    "oxigeno_bajo": ("cuerpo", 0.25, 0.40), "oxigeno_critico": ("cuerpo", 0.10, 0.20),
    "salud_baja": ("cuerpo", 0.35, 0.55),
    "hidrogeno_bajo": ("sistemas", 0.20, 0.30), "hidrogeno_critico": ("sistemas", 0.07, 0.15),
    "cuantico_bajo": ("sistemas", 0.15, 0.25),
    "casco_danado": ("sistemas", 0.50, 0.65), "casco_critico": ("sistemas", 0.25, 0.40),
}
# Si se avisa del crítico, el bajo ya no hace falta (y al revés no se repite)
_PAIRS = {"sed_critica": "sed_baja", "hambre_critica": "hambre_baja", "oxigeno_critico": "oxigeno_bajo",
          "hidrogeno_critico": "hidrogeno_bajo", "casco_critico": "casco_danado"}

_CRITICAL_OF = {low: crit for crit, low in _PAIRS.items()}

ANNUNCIATORS = {"pwr": "energía", "wpn": "armas", "thr": "propulsores", "shld": "escudos", "cool": "refrigeración",
                "qdrv": "motor cuántico", "radr": "radar", "prox": "proximidad", "hit": "impactos", "misl": "misiles"}
# Testigos que avisan en voz cuando pasan a «avería grave» (proximidad e impactos saltarían a cada momento)
ANNUNCIATOR_ALERT = ("pwr", "thr", "cool", "qdrv", "wpn", "radr")
ANNUNCIATOR_REPEAT = 120.0
GEAR_WARN_M = 100  # 2.1.2: por debajo de esto, bajando y con el tren recogido: aviso
GEAR_REARM_M = 250  # se vuelve a avisar tras subir por encima de esto (o bajar el tren)
GEAR_REPEAT_S = 90.0
CONTRACT_WARN_S = 300  # aviso cuando a un contrato le quedan 5 minutos
MISSILE_REPEAT = 20.0

LOCOMOTION = {"ON_FOOT": "a pie", "EVA": "en EVA (fuera de la nave)", "SEATED": "sentado"}
CREW_ROLE = {"PILOT": "piloto", "GUNNER": "artillero", "CREW": "tripulante"}
OPERATOR = {"INACTIVE": "", "FLIGHT": "vuelo", "COMBAT": "combate", "TURRET": "torreta", "MISSILE": "misiles",
            "SCANNING": "escaneo", "MINING": "minería", "QUANTUM_NAVIGATION": "navegación cuántica",
            "REFUEL": "repostaje", "SALVAGE": "recuperación"}
VEHICLE_TYPE = {"SPACESHIP": "nave espacial", "GROUND": "vehículo de tierra", "GRAVLEV": "gravlev", "BOAT": "barco"}
MASTER_MODE = {"NAVIGATION": "navegación (NAV)", "SCM": "combate (SCM)", "STEALTH": "sigilo"}
DEPLOY = {"RETRACTED": "recogido", "DEPLOYING": "bajando", "DEPLOYED": "desplegado", "RETRACTING": "subiendo"}
QT_STATE = {"OFF": "apagado", "IDLE": "listo", "ALIGNING": "alineando", "TRAVELING": "en viaje cuántico",
            "COOLDOWN": "enfriándose"}
POWER = {"engines": "motores", "weapons": "armas", "shield_generators": "escudos", "coolers": "refrigeración",
         "life_support": "soporte vital", "sensors": "sensores", "gravity_generators": "gravedad",
         "powerplants": "planta de energía", "shield_emitters": "emisores de escudo"}


# ------------------------------------------------------------------ lectura segura de mensajes
def _has(msg, name: str) -> bool:
    try:
        return msg.HasField(name)
    except Exception:  # noqa: BLE001 — campo escalar sin presencia o que no existe en esta versión
        return hasattr(msg, name)


def _get(msg, path: str, default=None):
    """msg.a.b.c, con None si falta algún tramo (campo ausente o que no existe en esta versión del juego)."""
    cur = msg
    for name in path.split("."):
        if cur is None:
            return default
        try:
            if not _has(cur, name):
                return default
            cur = getattr(cur, name)
        except Exception:  # noqa: BLE001
            return default
    return cur


def _enum(msg, path: str) -> str:
    """Nombre corto de un valor enumerado: VEHICLE_MASTER_MODE_SCM -> SCM."""
    parent, _, name = path.rpartition(".")
    m = _get(msg, parent) if parent else msg
    if m is None:
        return ""
    try:
        if not _has(m, name):
            return ""
        val = getattr(m, name)
        fd = m.DESCRIPTOR.fields_by_name[name]
        ev = fd.enum_type.values_by_number.get(int(val)) if fd.enum_type else None
        if not ev:
            return ""
        prefix = re.sub(r"(?<!^)(?=[A-Z])", "_", fd.enum_type.name).upper() + "_"
        short = ev.name[len(prefix):] if ev.name.startswith(prefix) else ev.name
        return "" if short.endswith("UNSPECIFIED") else short
    except Exception:  # noqa: BLE001
        return ""


def _gauge(msg, path: str) -> float | None:
    g = _get(msg, path)
    if g is None:
        return None
    cur, mx = float(getattr(g, "current", 0.0) or 0.0), float(getattr(g, "max", 0.0) or 0.0)
    if mx > 0:
        return max(0.0, min(1.0, cur / mx))
    return None


def pct(x: float | None) -> str:
    return "?" if x is None else f"{round(x * 100)} %"


def _num(x: float, dec: int = 0) -> str:
    s = f"{x:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _clock(seconds: float) -> str:
    """Tiempo dicho en voz: «45 segundos», «1 minuto y 35 segundos», «2 horas y 5 minutos»."""
    s = int(round(seconds))
    if s < 60:
        return f"{s} segundo" + ("" if s == 1 else "s")
    m, s = divmod(s, 60)
    if m < 60:
        mm = f"{m} minuto" + ("" if m == 1 else "s")
        return f"{mm} y {s} segundo" + ("" if s == 1 else "s") if s else mm
    h, m = divmod(m, 60)
    hh = f"{h} hora" + ("" if h == 1 else "s")
    return f"{hh} y {m} minuto" + ("" if m == 1 else "s") if m else hh


# --------------------------------------------------------------------------- el lector
class Telemetry(threading.Thread):
    """Sigue el flujo de telemetría del juego y guarda el último estado (self.snap)."""

    grace = GRACE_S

    def __init__(self, settings, gamelog=None, on_event: Callable[[GameEvent], None] | None = None,
                 cache_dir: Path | None = None) -> None:
        super().__init__(daemon=True, name="telemetria")
        self.settings = settings
        self.gamelog = gamelog
        self.on_event = on_event
        self.cache_dir = cache_dir
        self.status = i18n.tr("inactiva")
        self.connected = False
        self.build = ""
        self.channel = ""
        self.port = DEFAULT_PORT
        self.snap: dict = {}
        self.snap_t = 0.0
        self.frames = 0
        self.last_frame_raw = None  # último fotograma completo (para «guardar muestra»)
        self._classes = None
        self._call = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._scale_max: dict[str, float] = {}
        self._reset_alerts(time.time())

    # ------------------------------------------------------------ consultas
    def live(self) -> bool:
        return self.connected and bool(self.snap) and time.time() - self.snap_t < FRESH_S

    def info(self) -> dict:
        """Para la ventana: estado de la conexión y los valores principales."""
        s = self.snap if self.live() else {}
        a, v = s.get("actor") or {}, s.get("vehicle") or {}
        return {"status": self.status, "conectada": self.live(), "activa": bool(self.settings.get("telemetria_activa", True)), "build": self.build, "canal": self.channel,
                "puerto": self.port, "fotogramas": self.frames,
                "valores": {k: x for k, x in {
                    "salud": a.get("health"), "sed": a.get("thirst"), "hambre": a.get("hunger"),
                    "oxigeno": a.get("oxygen"), "hidrogeno": v.get("hydrogen"), "cuantico": v.get("quantum"),
                    "escudos": v.get("shields"), "casco": v.get("health")}.items() if x is not None},
                "nave": v.get("label", ""), "lugar": a.get("location", "")}

    def stop(self) -> None:
        self._stop.set()
        self._cancel()

    def restart(self) -> None:
        """Volver a conectar (p. ej. después de activarla en el juego)."""
        self._classes = None
        self._cancel()

    def _cancel(self) -> None:
        call = self._call
        if call is not None:
            try:
                call.cancel()
            except Exception:  # noqa: BLE001
                pass

    # ---------------------------------------------------------- dónde está el juego
    def channel_dir(self) -> Path | None:
        """Carpeta del canal que estás jugando (LIVE, PTU…): la del Game.log que se está leyendo."""
        from .telemetry_setup import channel_dirs

        p = getattr(self.gamelog, "path", None) if self.gamelog else None
        if p:
            d = Path(p).parent
            if (d / "Bin64" / "StarCitizen.exe").is_file():
                return d
        dirs = channel_dirs(self.settings, self.gamelog)
        if not dirs:
            return None
        # El canal más reciente (el último que se ha jugado)
        def mtime(d: Path) -> float:
            try:
                return (d / "Game.log").stat().st_mtime
            except OSError:
                return 0.0
        return max(dirs, key=mtime)

    # ------------------------------------------------------------------ bucle
    def run(self) -> None:
        backoff = 3.0
        while not self._stop.is_set():
            if not self.settings.get("telemetria_activa", True):
                self._set_disconnected(i18n.tr("desactivada"))
                self._stop.wait(3)
                continue
            try:
                import grpc  # noqa: F401
                from google.protobuf import descriptor_pb2  # noqa: F401
            except ImportError:
                self._set_disconnected(i18n.tr("falta el componente gRPC (botón INSTALAR COMPONENTE)"))
                self._stop.wait(30)
                continue
            ch = self.channel_dir()
            if ch is None:
                self._set_disconnected(i18n.tr("no encuentro la carpeta de Star Citizen"))
                self._stop.wait(15)
                continue
            from .telemetry_setup import read_port

            self.port = read_port(ch)
            hint = self._log_hint(ch)
            if hint.get("port"):
                self.port = hint["port"]
            if not _port_open(self.port):
                if hint.get("no_service"):  # 2.1.3: el juego arrancó su servidor local, pero sin la telemetría
                    self._set_disconnected(i18n.tr(
                        "Star Citizen no está sirviendo la telemetría: el Game.log dice «No services configured» aunque "
                        "está activada. Esta versión del juego no la abre; prueba en otra (LIVE o la próxima PTU)."))
                elif hint.get("running"):
                    self._set_disconnected(i18n.tr("el juego dice que la telemetría está en {p}, pero no responde",
                                                   p=f"127.0.0.1:{self.port}"))
                else:
                    self._set_disconnected(i18n.tr("esperando al juego (telemetría sin abrir: actívala y reinicia el juego)"))
                self._stop.wait(5)
                continue
            try:
                self._ensure_schema(ch)
                self.status = i18n.tr("conectando…")
                self._stream()
                backoff = 3.0
                self._stop.wait(2)  # el juego cerró el flujo (salir al menú, cerrar el juego): se reintenta luego
            except Exception as e:  # noqa: BLE001
                msg = getattr(e, "details", lambda: "")() if hasattr(e, "details") else ""
                log.info("Telemetría: %s %s", type(e).__name__, msg or e)
                self._set_disconnected(i18n.tr("sin conexión ({e}); reintentando", e=msg or type(e).__name__))
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 15.0)
        self._set_disconnected(i18n.tr("detenida"))

    def _set_disconnected(self, status: str) -> None:
        self.connected = False
        if status != self.status:
            log.info("Telemetría: %s", status)  # 2.1.3: queda en nova.log para poder diagnosticar
        self.status = status

    # 2.1.3: lo que dice el Game.log del servidor local del juego
    _RX_REG = re.compile(r"Register Service>.*GameTelemetryService|<GameTelemetry> Local services server is running on")
    _RX_PORT = re.compile(r"Local services server (?:is running on|listens on) [\d.:\[\]a-fA-F]*?:(\d{4,5})")
    _RX_NONE = re.compile(r"<GRPC Server> No services configured")
    _RX_START = re.compile(r"BackupNameAttachment=|\[Cmdline  \]")

    def _log_hint(self, ch: Path) -> dict:
        """Lee solo lo nuevo del Game.log del canal: ¿registró el juego el servicio de telemetría, en qué puerto,
        o arrancó el servidor sin servicios? Se reinicia cuando el juego vuelve a arrancar (Game.log nuevo)."""
        path = ch / "Game.log"
        try:
            st = path.stat()
        except OSError:
            return {}
        cache = getattr(self, "_hint", None)
        if cache is None or cache["path"] != path or st.st_size < cache["pos"]:
            cache = self._hint = {"path": path, "pos": 0, "running": False, "no_service": False, "port": 0}
        if st.st_size > cache["pos"]:
            try:
                with open(path, "rb") as f:
                    f.seek(cache["pos"])
                    chunk = f.read(min(st.st_size - cache["pos"], 8_000_000)).decode("utf-8", "replace")
                    cache["pos"] = f.tell()
            except OSError:
                return cache
            if self._RX_REG.search(chunk):
                cache["running"], cache["no_service"] = True, False
            m = self._RX_PORT.search(chunk)
            if m:
                cache["running"], cache["no_service"], cache["port"] = True, False, int(m.group(1))
            if self._RX_NONE.search(chunk) and not cache["running"]:
                cache["no_service"] = True
        return cache

    def _ensure_schema(self, ch: Path) -> None:
        from . import telemetry_schema

        name = ch.name
        if self._classes is not None and self.channel == name:
            return
        cache = self.cache_dir or Path.home()
        self.status = i18n.tr("leyendo el esquema de tu versión del juego…")
        blob, bid = telemetry_schema.load_or_extract(ch, cache)
        self._classes = _message_classes(blob)
        self.build, self.channel = bid, name
        log.info("Telemetría: esquema de %s (%s)", name, bid)

    def _stream(self) -> None:
        import grpc

        req_cls, resp_cls = self._classes
        opts = [("grpc.keepalive_time_ms", 20000), ("grpc.keepalive_timeout_ms", 10000),
                ("grpc.max_receive_message_length", 16 * 1024 * 1024), ("grpc.enable_http_proxy", 0)]
        with grpc.insecure_channel(f"127.0.0.1:{self.port}", options=opts) as chan:
            method = chan.unary_stream(STREAM, request_serializer=lambda m: m.SerializeToString(),
                                       response_deserializer=resp_cls.FromString)
            self._call = call = method(req_cls())
            self.connected = True
            self.status = i18n.tr("conectada ({c} {v}); esperando a tu personaje", c=self.channel, v=self.build.split("-")[0])
            self._reset_alerts(time.time())
            last = 0.0
            try:
                for frame in call:
                    if self._stop.is_set() or not self.settings.get("telemetria_activa", True):
                        call.cancel()
                        break
                    self.frames += 1
                    now = time.time()
                    if _has(frame, "events"):
                        self._events(frame, now)
                    if now - last < PROCESS_EVERY:
                        continue
                    last = now
                    self.last_frame_raw = frame
                    self.feed(frame, now)
            finally:
                self._call = None
                self.connected = False

    # -------------------------------------------------------------- fotogramas
    def feed(self, frame, now: float | None = None) -> dict:
        """Convierte un fotograma en un estado sencillo y comprueba los avisos. Devuelve el estado."""
        now = now or time.time()
        snap = self.snapshot(frame)
        with self._lock:
            self.snap, self.snap_t = snap, now
        if snap.get("actor"):
            self.status = i18n.tr("en directo ({c} {v})", c=self.channel, v=self.build.split("-")[0])
        try:
            self._check_alerts(snap, now)
            self._check_info(snap, now)
        except Exception:  # noqa: BLE001 — un aviso mal calculado no debe cortar la lectura
            log.exception("Avisos de telemetría")
        return snap

    def _frac(self, key: str, value) -> float | None:
        """Valores sin máximo (combustible, escudos, casco): pueden venir como 0-1 o 0-100."""
        if value is None:
            return None
        v = float(value)
        mx = max(self._scale_max.get(key, 0.0), v)
        self._scale_max[key] = mx
        if mx > 1.5:
            v /= 100.0
        return max(0.0, min(1.0, v))

    def snapshot(self, f) -> dict:
        snap: dict = {}
        gs = _enum(f, "game.state")
        if gs:
            snap["game_state"] = gs
            snap["menu_open"] = bool(_get(f, "game.menu_open", False))
        dbg = _get(f, "game.debug")
        if dbg is not None:
            snap["fps"] = round(float(dbg.fps or 0), 1)
            ping = _get(dbg, "network.ping_ms")
            if ping is not None:
                snap["ping"] = round(float(ping))
            if _get(dbg, "shard_name"):
                snap["shard"] = dbg.shard_name
        if _has(f, "actor"):
            snap["actor"] = self._actor(f.actor)
        if _has(f, "vehicle") and _has(f.vehicle, "state"):
            snap["vehicle"] = self._vehicle(f.vehicle.state)
        if _has(f, "weapons"):
            w = f.weapons
            ws = list(getattr(w, "weapons", []) or [])
            cm = {}
            for c in getattr(w, "countermeasures", []) or []:
                t = _enum(c, "type")
                cm[{"DECOY": "señuelos", "NOISE": "ruido"}.get(t, t.lower() or "contramedidas")] = int(c.amount)
            snap["weapons"] = {"preset": getattr(w, "preset_name", "") or "", "total": len(ws),
                               "listas": sum(1 for x in ws if x.ready_to_fire),
                               "con_energia": sum(1 for x in ws if x.is_powered), "contramedidas": cm,
                               "gimbal_fijo": bool(_get(w, "settings.gimbals_locked", False))}
        return snap

    def _actor(self, a) -> dict:
        out: dict = {}
        hunger, thirst = _gauge(a, "vitals.hunger"), _gauge(a, "vitals.thirst")
        if not SATIETY_HIGH_IS_GOOD:
            hunger = None if hunger is None else 1 - hunger
            thirst = None if thirst is None else 1 - thirst
        for k, v in (("health", _gauge(a, "vitals.health")), ("oxygen", _gauge(a, "vitals.oxygen")),
                     ("hunger", hunger), ("thirst", thirst)):
            if v is not None:
                out[k] = v
        bt = _get(a, "vitals.body_temperature")
        if bt is not None:
            out["body_temp"] = round(float(bt.current), 1)
        for k, path in (("heart_rate", "vitals.heart_rate"), ("gravity", "vitals.gravity"),
                        ("pressure", "vitals.pressure"), ("intox", "vitals.intoxication_level"),
                        ("ext_temp", "environment.external_temperature"),
                        ("radiation", "environment.ambient_radiation_rate")):
            v = _get(a, path)
            if v is not None:
                out[k] = round(float(v), 2)
        if _has(a, "environment"):
            out["breathable"] = bool(getattr(a.environment, "breathable_atmosphere", True))
        st = _get(a, "state")
        if st is not None:
            out["locomotion"] = _enum(st, "locomotion")
            out["role"] = _enum(st, "crew_role")
            out["seat"] = getattr(st, "seat_name", "") or ""
            out["uec"] = int(getattr(st, "uec_balance", 0) or 0)
            out["mode"] = _enum(st, "operator_mode")
            out["crime"] = int(getattr(st, "crime_stat", 0) or 0)
            out["player"] = getattr(st, "player_name", "") or ""
            loc = _get(st, "location")
            if loc is not None:
                names = [h.display_name or h.id for h in loc.hierarchy if (h.display_name or h.id)]
                out["location"] = " › ".join(names)
                j = _get(loc, "jurisdiction")
                if j is not None:
                    out["jurisdiction"] = j.display_name or j.id
                out["armistice"] = bool(loc.armistice_zone)
            c = _get(st, "tracked_contract.details")
            if c is not None:
                out["contract"] = {"titulo": c.title, "de": c.giver_name,
                                   "objetivo": _get(c, "current_objective.text", "") or "",
                                   "hechos": int(c.objectives_completed), "total": int(c.objectives_total),
                                   "fin": int(c.ends_at_unix_ms) / 1000 if _has(c, "ends_at_unix_ms") else None}
        return out

    def _vehicle(self, s) -> dict:
        out: dict = {"name": getattr(s, "name", "") or "", "class": getattr(s, "class_name", "") or "",
                     "maker": getattr(s, "manufacturer", "") or "", "type": _enum(s, "type"),
                     "lights": bool(getattr(s, "lights_enabled", False))}
        out["label"] = _vehicle_label(out)
        inst = _get(s, "flight.instruments")
        if inst is not None:
            out["speed"] = round(float(inst.speed or 0), 1)
            out["hydrogen"] = self._frac("hydrogen", inst.hydrogen_fuel)
            if _has(inst, "quantum_fuel"):
                out["quantum"] = self._frac("quantum", inst.quantum_fuel)
            if _has(inst, "altitude"):
                out["altitude"] = round(float(inst.altitude))
            out["radar_alt"] = round(float(inst.radar_altitude or 0))
            out["vsi"] = round(float(inst.vertical_speed_indicator or 0), 1)
            b = _get(inst, "boost")
            if b is not None:
                out["boost"] = self._frac("boost", b.reserves)
        fs = _get(s, "flight.state")
        if fs is not None:
            out["landed"] = bool(fs.is_landed)
            for k in ("gear", "vtol", "transformation"):
                e = _enum(fs, k)
                if e:
                    out[k] = e
        if _has(s, "shields"):
            out["shields"] = self._frac("shields", s.shields.level)
            out["faces"] = [self._frac("shields", x) for x in s.shields.faces]
        if _has(s, "health"):
            out["health"] = self._frac("vhealth", s.health)
        mm = _enum(s, "master_mode.mode")
        if mm:
            out["master_mode"] = mm
        if _has(s, "power"):
            out["power"] = {k: bool(getattr(s.power, k, False)) for k in POWER if hasattr(s.power, k)}
        if _has(s, "annunciators"):
            out["annunciators"] = {k: _enum(s.annunciators, k) for k in ANNUNCIATORS if hasattr(s.annunciators, k)}
        qt = _get(s, "quantum_travel")
        if qt is not None:
            q = {"state": _enum(qt, "state"), "spool": float(getattr(qt, "spool_ratio", 0) or 0),
                 "calib": float(getattr(qt, "calibration_ratio", 0) or 0)}
            d = _get(qt, "destination")
            if d is not None:
                q["dest"] = d.display_name or d.id
            if _has(qt, "eta_seconds"):
                q["eta"] = float(qt.eta_seconds)
            if _has(qt, "remaining_distance_m"):
                q["dist"] = float(qt.remaining_distance_m)
            out["qt"] = q
        if _has(s, "doors"):
            out["doors"] = {"abiertas": _enum(s.doors, "open_state") == "OPENED",
                            "bloqueadas": _enum(s.doors, "lock_state") == "LOCKED"}
        return out

    # ---------------------------------------------------------------- avisos
    def _reset_alerts(self, now: float) -> None:
        self._fired: dict[str, bool] = {}
        self._below_since: dict[str, float] = {}
        self._grace_until = now + self.grace
        self._ann_said: dict[str, float] = {}
        self._ann_prev: dict[str, str] = {}
        self._shield_prev: float | None = None
        self._vehicle_key = ""
        # 2.1.2: viaje cuántico, aproximación con el tren recogido y contrato seguido
        self._qt_prev = ""
        self._gear_armed = True
        self._gear_low_since: float | None = None
        self._gear_said = -1e9
        self._contract_key = None
        self._contract_warned: set[str] = set()

    def _emit(self, kind: str, category: str, now: float, **data) -> None:
        detail = " · ".join(f"{v}" for v in data.values() if v not in (None, ""))
        ev = GameEvent(kind, detail, category, now, data, False)
        if self.gamelog is not None:
            try:
                self.gamelog.events.append(ev)
            except Exception:  # noqa: BLE001
                pass
        if self.on_event:
            try:
                self.on_event(ev)
            except Exception:  # noqa: BLE001
                log.exception("Aviso de telemetría")

    def _level(self, kind: str, value: float | None, now: float, **data) -> None:
        """Avisa una vez cuando el valor baja del umbral (y se queda ahí HOLD_S); se rearma al recuperarse."""
        if value is None:
            return
        cat, low, rearm = THRESHOLDS[kind]
        if self._fired.get(kind):
            if value >= rearm:
                self._fired[kind] = False
            return
        if value > low:
            self._below_since.pop(kind, None)
            return
        crit = _CRITICAL_OF.get(kind)
        if crit and value <= THRESHOLDS[crit][1]:
            return  # ya está en zona crítica: de eso se encarga el aviso crítico (no dos avisos seguidos)
        since = self._below_since.setdefault(kind, now)
        if now - since < HOLD_S or now < self._grace_until:
            return
        self._fired[kind] = True
        pair = _PAIRS.get(kind)
        if pair:
            self._fired[pair] = True  # el crítico cubre al bajo
        elif any(self._fired.get(k) for k, v in _PAIRS.items() if v == kind):
            return  # ya se avisó del crítico
        self._emit(kind, cat, now, x=round(value * 100), **data)

    def _check_alerts(self, snap: dict, now: float) -> None:
        if snap.get("game_state") and snap["game_state"] != "IN_GAME":
            return
        a = snap.get("actor") or {}
        if a:
            # Los críticos primero: si ya estás al 8 %, se dice el crítico y no el «bajo»
            self._level("sed_critica", a.get("thirst"), now)
            self._level("sed_baja", a.get("thirst"), now)
            self._level("hambre_critica", a.get("hunger"), now)
            self._level("hambre_baja", a.get("hunger"), now)
            if a.get("breathable") is False:  # con aire respirable el oxígeno del traje no importa
                self._level("oxigeno_critico", a.get("oxygen"), now)
                self._level("oxigeno_bajo", a.get("oxygen"), now)
            h = a.get("health")
            if h is not None and h > 0:  # 0 = caído o muerto: de eso ya avisa el Game.log
                self._level("salud_baja", h, now)
        v = snap.get("vehicle")
        if not v:
            self._vehicle_key = ""
            self._shield_prev = None
            return
        key = v.get("class") or v.get("name")
        if key != self._vehicle_key:  # nave nueva: se mira un momento antes de avisar
            self._vehicle_key = key
            for k in list(self._fired):
                if THRESHOLDS.get(k, ("",))[0] == "sistemas":
                    self._fired.pop(k)
            self._below_since.clear()
            self._ann_prev.clear()
            self._shield_prev = None
            self._grace_until = max(self._grace_until, now + 5)
        ship = v.get("label", "")
        if v.get("type") in ("", "SPACESHIP") and a.get("role") in ("", "PILOT"):
            self._level("hidrogeno_critico", v.get("hydrogen"), now, nave=ship)
            self._level("hidrogeno_bajo", v.get("hydrogen"), now, nave=ship)
            self._level("cuantico_bajo", v.get("quantum"), now, nave=ship)
        self._level("casco_critico", v.get("health"), now, nave=ship)
        self._level("casco_danado", v.get("health"), now, nave=ship)
        sh = v.get("shields")
        if sh is not None:
            gens_on = (v.get("power") or {}).get("shield_generators", True)
            if self._shield_prev is not None and self._shield_prev >= 0.25 and sh <= 0.03 and gens_on \
                    and now >= self._grace_until:
                self._emit("escudos_caidos", "sistemas", now, nave=ship)
            if self._shield_prev is None or sh >= 0.25 or sh <= 0.03:
                self._shield_prev = sh
        for k, state in (v.get("annunciators") or {}).items():
            prev = self._ann_prev.get(k, "")
            self._ann_prev[k] = state
            if now < self._grace_until or state == prev:
                continue
            if k == "misl" and state not in ("", "NOMINAL", "OFF"):
                if now - self._ann_said.get(k, -1e9) >= MISSILE_REPEAT:
                    self._ann_said[k] = now
                    self._emit("alerta_misil", "sistemas", now, nave=ship)
            elif k in ANNUNCIATOR_ALERT and state.startswith("MAJOR") and not prev.startswith("MAJOR"):
                if now - self._ann_said.get(k, -1e9) >= ANNUNCIATOR_REPEAT:
                    self._ann_said[k] = now
                    self._emit("averia_grave", "sistemas", now, x=ANNUNCIATORS[k], nave=ship)

    def _check_info(self, snap: dict, now: float) -> None:
        """2.1.2: sucesos para los hologramas en directo: salto cuántico, aterrizaje sin tren y contrato."""
        if snap.get("game_state") and snap["game_state"] != "IN_GAME":
            return
        a, v = snap.get("actor") or {}, snap.get("vehicle") or {}
        # Viaje cuántico: al empezar el salto
        q = v.get("qt") or {}
        st = q.get("state", "")
        if st == "TRAVELING" and self._qt_prev != "TRAVELING":
            self._emit("viaje_cuantico", "", now, x=q.get("dest", ""), eta=q.get("eta"), dist=q.get("dist"),
                       nave=v.get("label", ""))
        self._qt_prev = st
        # Aproximación al suelo con el tren recogido (solo piloto de nave con tren)
        alt, vsi = v.get("radar_alt") or 0, v.get("vsi") or 0
        if not v or v.get("landed") or v.get("gear") != "RETRACTED" or alt > GEAR_REARM_M:
            self._gear_armed = True
            self._gear_low_since = None
        elif (self._gear_armed and v.get("type") in ("", "SPACESHIP") and a.get("role") in ("", "PILOT")
              and 1 < alt <= GEAR_WARN_M and vsi < -0.5 and now >= self._grace_until):
            since = self._gear_low_since = self._gear_low_since or now
            if now - since >= 1.0 and now - self._gear_said >= GEAR_REPEAT_S:
                self._gear_armed = False
                self._gear_said = now
                self._emit("tren_recogido", "sistemas", now, x=round(alt), nave=v.get("label", ""))
        else:
            self._gear_low_since = None
        # Contrato seguido: objetivo nuevo (solo holograma) y aviso a 5 minutos de caducar (voz y holograma)
        c = a.get("contract")
        key = (c["titulo"], c.get("objetivo", ""), c.get("hechos", 0)) if c else None
        if key != self._contract_key:
            first = self._contract_key is None and now < self._grace_until + 20
            self._contract_key = key
            if c and not first and (c.get("objetivo") or c.get("total")):
                self._emit("contrato_objetivo", "", now, x=c["titulo"], c=c["titulo"])
        if c and c.get("fin"):
            left = c["fin"] - time.time()
            if 0 < left <= CONTRACT_WARN_S and c["titulo"] not in self._contract_warned:
                self._contract_warned.add(c["titulo"])
                self._emit("contrato_caduca", "contratos", now, x=max(1, round(left / 60)), c=c["titulo"])

    def _events(self, frame, now: float) -> None:
        for e in getattr(frame.events, "events", []) or []:
            t = _enum(e, "type")
            if t in ("ACTOR_SPAWN", "ACTOR_RESPAWN"):
                self._reset_alerts(now)

    # ---------------------------------------------------------------- textos
    def summary(self) -> str:
        """Estado para la IA (va dentro del estado del juego). Vacío si no hay telemetría en directo."""
        if not self.live():
            return ""
        s = self.snap
        lines = ["Telemetría EN DIRECTO (valores reales que da el propio juego ahora mismo):"]
        a = s.get("actor") or {}
        if a:
            bits = []
            if a.get("health") is not None:
                bits.append(f"salud {pct(a['health'])}")
            if a.get("thirst") is not None:
                bits.append(f"hidratación {pct(a['thirst'])} (100 % = sin sed)")
            if a.get("hunger") is not None:
                bits.append(f"nutrición {pct(a['hunger'])} (100 % = sin hambre)")
            if a.get("oxygen") is not None:
                bits.append(f"oxígeno del traje {pct(a.get('oxygen'))}")
            if "breathable" in a:
                bits.append("aire respirable" if a["breathable"] else "aire NO respirable")
            if a.get("body_temp"):
                bits.append(f"temperatura corporal {_num(a['body_temp'], 1)} °C")
            if a.get("ext_temp") is not None:
                bits.append(f"temperatura exterior {_num(a['ext_temp'])} °C")
            if a.get("heart_rate"):
                bits.append(f"pulso {round(a['heart_rate'])} lpm")
            if a.get("intox"):
                bits.append(f"intoxicación nivel {int(a['intox'])}")
            if a.get("radiation"):
                bits.append(f"radiación ambiente {a['radiation']}")
            if bits:
                lines.append("- Personaje: " + ", ".join(bits))
            where = [LOCOMOTION.get(a.get("locomotion", ""), "")]
            if a.get("role"):
                where.append(CREW_ROLE.get(a["role"], a["role"].lower()))
            if OPERATOR.get(a.get("mode", ""), ""):
                where.append("modo " + OPERATOR[a["mode"]])
            where = [w for w in where if w]
            if where:
                lines.append("- Situación: " + ", ".join(where))
            if a.get("location"):
                loc = a["location"]
                if a.get("jurisdiction"):
                    loc += f" (jurisdicción de {a['jurisdiction']})"
                if a.get("armistice"):
                    loc += ", en zona de armisticio"
                lines.append("- Ubicación: " + loc)
            lines.append(f"- Saldo: {_num(a.get('uec', 0))} aUEC; CrimeStat: {a.get('crime', 0)}")
            c = a.get("contract")
            if c:
                t = f"- Contrato seguido: {c['titulo']}"
                if c.get("de"):
                    t += f" (de {c['de']})"
                if c.get("objetivo"):
                    t += f"; objetivo actual: {c['objetivo']}"
                if c.get("total"):
                    t += f"; {c['hechos']}/{c['total']} objetivos"
                if c.get("fin"):
                    left = c["fin"] - time.time()
                    if left > 0:
                        t += f"; termina en {_clock(left)}"
                lines.append(t)
        v = s.get("vehicle")
        if v:
            bits = []
            for k, name in (("health", "casco"), ("shields", "escudos"), ("hydrogen", "hidrógeno"),
                            ("quantum", "combustible cuántico"), ("boost", "reserva de impulso")):
                if v.get(k) is not None:
                    bits.append(f"{name} {pct(v[k])}")
            if v.get("speed") is not None:
                bits.append(f"velocidad {_num(v['speed'])} m/s")
            if v.get("altitude") is not None:
                bits.append(f"altitud {_num(v['altitude'])} m")
            elif v.get("radar_alt"):
                bits.append(f"altitud radar {_num(v['radar_alt'])} m")
            if v.get("landed"):
                bits.append("posada")
            if v.get("gear"):
                bits.append(f"tren {DEPLOY.get(v['gear'], v['gear'].lower())}")
            if v.get("master_mode"):
                bits.append(f"modo {MASTER_MODE.get(v['master_mode'], v['master_mode'])}")
            lines.append(f"- Vehículo: {v.get('label') or 'desconocido'}: " + ", ".join(bits))
            pw = v.get("power") or {}
            off = [POWER[k] for k, on in pw.items() if not on and k in POWER]
            if pw:
                lines.append("- Energía: " + ("todo encendido" if not off else "apagado: " + ", ".join(off)))
            bad = [f"{ANNUNCIATORS[k]} ({'grave' if st.startswith('MAJOR') else 'leve'})"
                   for k, st in (v.get("annunciators") or {}).items() if st.startswith(("MAJOR", "MINOR"))]
            if bad:
                lines.append("- Testigos de avería encendidos: " + ", ".join(bad))
            q = v.get("qt") or {}
            if q.get("state") and q["state"] != "OFF":
                t = f"- Viaje cuántico: {QT_STATE.get(q['state'], q['state'].lower())}"
                if q.get("dest"):
                    t += f" hacia {q['dest']}"
                if q.get("eta"):
                    t += f", llega en {_clock(q['eta'])}"
                if q.get("dist"):
                    t += f" ({_num(q['dist'] / 1000)} km)"
                lines.append(t)
        w = s.get("weapons")
        if w and w.get("total"):
            t = f"- Armas: {w['listas']}/{w['total']} listas"
            if w.get("preset"):
                t += f" (grupo «{w['preset']}»)"
            if w.get("contramedidas"):
                t += "; contramedidas: " + ", ".join(f"{k} {n}" for k, n in w["contramedidas"].items())
            lines.append(t)
        lines.append("(La munición no la da el juego por telemetría.)")
        return "\n".join(lines)

    # ------------------------------------------------- respuestas al momento, sin IA
    def quick_answer(self, text: str, treatment: str = "") -> str | None:
        """«¿Cuánto hidrógeno me queda?», «¿cómo voy de sed?», «¿cuánto falta para llegar?»… Si la telemetría
        está en directo y la pregunta es de esas, la respuesta hablada; si no, None (la contesta la IA)."""
        if not self.live():
            return None
        q = _plain(text)
        if not QUESTION.search(q) or NOT_STATE.search(q) or IMPERATIVE.match(q):
            return None
        s = self.snap
        a, v = s.get("actor") or {}, s.get("vehicle") or {}
        t = f", {treatment}" if treatment else ""
        parts: list[str] = []
        for rx, fn in (
            (R_THIRST, lambda: a.get("thirst") is not None and f"Hidratación al {pct(a['thirst'])}"),
            (R_HUNGER, lambda: a.get("hunger") is not None and f"Nutrición al {pct(a['hunger'])}"),
            (R_OXYGEN, lambda: a.get("oxygen") is not None and f"Oxígeno del traje al {pct(a['oxygen'])}"
                + ("" if a.get("breathable", True) else "; el aire de fuera no es respirable")),
            (R_HEALTH, lambda: a.get("health") is not None and f"Salud al {pct(a['health'])}"),
            (R_QFUEL, lambda: v.get("quantum") is not None and f"Combustible cuántico al {pct(v['quantum'])}"),
            (R_FUEL, lambda: v.get("hydrogen") is not None and f"Hidrógeno al {pct(v['hydrogen'])}"),
            (R_SHIELDS, lambda: v.get("shields") is not None and f"Escudos al {pct(v['shields'])}"),
            (R_HULL, lambda: v.get("health") is not None and f"Casco al {pct(v['health'])}"),
            (R_SPEED, lambda: v.get("speed") is not None and f"Vamos a {_num(v['speed'])} metros por segundo"),
            (R_ETA, lambda: _eta_text(v)),
            (R_CREDITS, lambda: a.get("uec") is not None and f"Tiene {_num(a['uec'])} aUEC"),
            (R_TEMP, lambda: a.get("body_temp") and f"Temperatura corporal de {_num(a['body_temp'], 1)} grados"
                + (f" y {_num(a['ext_temp'])} fuera" if a.get("ext_temp") is not None else "")),
        ):
            if rx.search(q):
                if rx is R_FUEL and R_QFUEL.search(q):
                    continue
                r = fn()
                if r:
                    parts.append(r)
        if not parts and R_ME.search(q) and a:
            bits = [f"{n} al {pct(a[k])}" for k, n in (("health", "salud"), ("thirst", "hidratación"),
                                                        ("hunger", "nutrición")) if a.get(k) is not None]
            if bits:
                parts.append(", ".join(bits[:-1]) + (" y " if len(bits) > 1 else "") + bits[-1])
        if not parts and R_SHIP.search(q) and v:
            bits = [f"{n} al {pct(v[k])}" for k, n in (("health", "casco"), ("shields", "escudos"),
                                                         ("hydrogen", "hidrógeno"), ("quantum", "cuántico"))
                    if v.get(k) is not None]
            if bits:
                parts.append((v.get("label") or "La nave") + ": " + ", ".join(bits))
        if not parts:
            return None
        text = "; ".join(parts) + t + "."
        return text[:1].upper() + text[1:]


def _eta_text(v: dict) -> str | None:
    q = v.get("qt") or {}
    st = q.get("state", "")
    if not st or st in ("OFF", "IDLE"):
        return "No estamos en viaje cuántico" if v else None
    if st == "TRAVELING" and q.get("eta"):
        dest = f" a {q['dest']}" if q.get("dest") else ""
        return f"Llegamos{dest} en {_clock(q['eta'])}"
    return f"Motor cuántico {QT_STATE.get(st, st.lower())}" + (f", rumbo a {q['dest']}" if q.get("dest") else "")


def _vehicle_label(v: dict) -> str:
    name = v.get("name") or ""
    if not name and v.get("class"):
        try:
            from .localization import ship_name

            name = ship_name(v["class"]) or ""
        except Exception:  # noqa: BLE001
            name = ""
        if not name:
            name = re.sub(r"_\d+$", "", v["class"]).replace("_", " ")
    maker = v.get("maker") or ""
    if maker and not name.lower().startswith(maker.lower().split()[0]):
        return f"{maker} {name}".strip()
    return name


def _plain(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


# Tiene que preguntar por un ESTADO («¿cuánto…?», «¿cómo voy de…?», «¿me queda…?»), no por datos del juego
QUESTION = re.compile(r"\b(cuant[oa]s?|como (?:voy|vamos|estoy|estamos|esta|estan|va|van|ando|andamos)|que tal|nivel|"
                      r"niveles|estado|queda|quedan|tengo|tenemos|llevo|llevamos|porcentaje|falta|faltan|a que|"
                      r"dime|dame|cual es mi|cual es el nivel)\b")
NOT_STATE = re.compile(r"\b(donde|comprar|compro|compra|vender|vendo|precio|cuesta|cuestan|mejor|mejores|recomienda\w*|"
                       r"que es|para que sirve|diferencia|tiene (?:un|una)|cuantos? (?:tipos|clases))\b")
IMPERATIVE = re.compile(r"^\s*(?:nova[ ,]*)?(sube|baja|activa|desactiva|enciende|apaga|abre|cierra|pon|quita|"
                        r"carga|reposta|llena|rellena|recarga|cambia|selecciona|lanza|dispara)\b")
R_THIRST = re.compile(r"\b(sed|hidratacion|hidratado|deshidrata\w*)\b")
R_HUNGER = re.compile(r"\b(hambre|nutricion|comida|comer)\b")
R_OXYGEN = re.compile(r"\b(oxigeno|o2)\b")
R_HEALTH = re.compile(r"\b(salud|vida|herid\w*)\b")
R_QFUEL = re.compile(r"\b(cuantic[oa]s?|quantum)\b")
R_FUEL = re.compile(r"\b(combustible|hidrogeno|gasolina|fuel|deposito)\b")
R_SHIELDS = re.compile(r"\b(escudos?)\b")
R_HULL = re.compile(r"\b(casco|danos?|integridad)\b")
R_SPEED = re.compile(r"\b(velocidad|que rapido|a cuanto vamos)\b")
R_ETA = re.compile(r"\b(cuanto falta|falta para llegar|cuando llegamos|tiempo de llegada|llegada|eta)\b")
R_CREDITS = re.compile(r"\b(auec|creditos|saldo|dinero tengo|cuanto dinero)\b")
R_TEMP = re.compile(r"\b(temperatura|frio|calor)\b")
R_ME = re.compile(r"\b(como estoy|mi estado|estado del personaje|constantes|mis valores)\b")
R_SHIP = re.compile(r"\b(estado de la nave|como esta la nave|como va la nave|estado de mi nave|la nave como)\b")


# ------------------------------------------------------------------ utilidades
def _port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _message_classes(blob: bytes):
    """(TelemetryStreamRequest, TelemetryStreamResponse) construidas al vuelo desde el esquema."""
    from google.protobuf import descriptor_pb2, descriptor_pool

    fds = descriptor_pb2.FileDescriptorSet()
    fds.ParseFromString(blob)
    pool = descriptor_pool.DescriptorPool()
    for f in fds.file:
        for dep in f.dependency:  # tipos bien conocidos de Google (timestamp, etc.) si alguno los usa
            if dep.startswith("google/protobuf/"):
                try:
                    pool.FindFileByName(dep)
                except KeyError:
                    _add_well_known(pool, dep)
        pool.Add(f)

    def cls(name: str):
        d = pool.FindMessageTypeByName(f"{PKG}.{name}")
        try:
            from google.protobuf.message_factory import GetMessageClass

            return GetMessageClass(d)
        except ImportError:  # protobuf antiguo
            from google.protobuf import message_factory

            return message_factory.MessageFactory(pool).GetPrototype(d)

    return cls("TelemetryStreamRequest"), cls("TelemetryStreamResponse")


def _add_well_known(pool, name: str) -> None:
    import importlib

    mod = "google.protobuf." + Path(name).stem + "_pb2"
    try:
        m = importlib.import_module(mod)
        from google.protobuf import descriptor_pb2

        fdp = descriptor_pb2.FileDescriptorProto()
        m.DESCRIPTOR.CopyToProto(fdp)
        pool.Add(fdp)
    except Exception:  # noqa: BLE001
        log.debug("Tipo conocido %s no disponible", name)


# ------------------------------------------------------- 2.1.1: hologramas de las alertas
# tipo de aviso -> (icono, título, consejo, de dónde sale el nivel, grave)
ALERT_HOLO = {
    "sed_baja": ("sed", "HIDRATACIÓN BAJA", "Bebe algo pronto: agua o cualquier bebida del inventario.", ("actor", "thirst"), False),
    "sed_critica": ("sed", "DESHIDRATACIÓN", "Bebe ya: la deshidratación te va quitando salud.", ("actor", "thirst"), True),
    "hambre_baja": ("hambre", "NUTRICIÓN BAJA", "Come algo cuando puedas.", ("actor", "hunger"), False),
    "hambre_critica": ("hambre", "HAMBRE CRÍTICA", "Come algo ya: sin nutrición pierdes salud y aguante.", ("actor", "hunger"), True),
    "oxigeno_bajo": ("oxigeno", "OXÍGENO BAJO", "El aire de aquí no es respirable: vuelve a la nave o cambia la bombona.", ("actor", "oxygen"), False),
    "oxigeno_critico": ("oxigeno", "OXÍGENO CRÍTICO", "Busca aire respirable o cambia la bombona del traje ya.", ("actor", "oxygen"), True),
    "salud_baja": ("salud", "SALUD BAJA", "Usa un MedPen o busca una cama médica.", ("actor", "health"), False),
    "hidrogeno_bajo": ("hidrogeno", "HIDRÓGENO BAJO", "Reposta en la próxima estación o puesto con servicio.", ("vehicle", "hydrogen"), False),
    "hidrogeno_critico": ("hidrogeno", "HIDRÓGENO CRÍTICO", "Aterriza o reposta ya, o te quedarás a la deriva.", ("vehicle", "hydrogen"), True),
    "cuantico_bajo": ("cuantico", "CUÁNTICO BAJO", "Reposta combustible cuántico antes de un salto largo.", ("vehicle", "quantum"), False),
    "casco_danado": ("casco", "CASCO DAÑADO", "Repara la nave en cuanto puedas.", ("vehicle", "health"), False),
    "casco_critico": ("casco", "CASCO CRÍTICO", "Sal del combate y repara: la nave no aguantará mucho más.", ("vehicle", "health"), True),
    "escudos_caidos": ("escudos", "ESCUDOS CAÍDOS", "Sin escudos: aléjate del fuego hasta que se recarguen.", ("vehicle", "shields"), True),
    "averia_grave": ("averia", "AVERÍA GRAVE", "Revisa la energía y los componentes en los MFD.", None, True),
    "alerta_misil": ("misil", "ALERTA DE MISIL", "Lanza contramedidas y maniobra.", None, True),
}


def alert_card(ev: GameEvent, snap: dict | None = None):
    """Ficha de holograma de una alerta de telemetría (None si el aviso no tiene holograma)."""
    from .holo import AMBER_HOLO, CRIT_HOLO, Card

    info = ALERT_HOLO.get(ev.kind)
    if not info:
        return None
    icon, title, advice, src, grave = info
    snap = snap or {}
    a, v = snap.get("actor") or {}, snap.get("vehicle") or {}
    data = ev.data or {}
    level = None
    if src:
        part = a if src[0] == "actor" else v
        level = part.get(src[1])
        if level is None and isinstance(data.get("x"), (int, float)):
            level = data["x"] / 100
    thr = THRESHOLDS.get(ev.kind, (None, None))[1] if ev.kind in THRESHOLDS else None
    if ev.kind == "escudos_caidos":
        thr = None
    personal = icon in ("sed", "hambre", "oxigeno", "salud")
    if personal:
        gauges = [(name, a.get(k), k == (src[1] if src else "")) for k, name in
                  (("health", "SALUD"), ("thirst", "HIDRATACIÓN"), ("hunger", "NUTRICIÓN"), ("oxygen", "OXÍGENO"))]
        header = "TELEMETRÍA · SOPORTE VITAL"
        subtitle = a.get("player") or "Tu personaje"
    else:
        gauges = [(name, v.get(k), k == (src[1] if src else "")) for k, name in
                  (("health", "CASCO"), ("shields", "ESCUDOS"), ("hydrogen", "HIDRÓGENO"), ("quantum", "CUÁNTICO"))]
        header = "TELEMETRÍA · TU NAVE"
        subtitle = data.get("nave") or v.get("label") or "Tu nave"
    gauges = [g for g in gauges if g[1] is not None or g[2]]
    fields: list[tuple[str, str]] = []
    big = ""
    if ev.kind == "averia_grave":
        big = str(data.get("x") or "").upper()
        ann = (v.get("annunciators") or {}).items()
        bad = [ANNUNCIATORS[k].upper() for k, st in ann if st.startswith("MAJOR")] + \
              [ANNUNCIATORS[k] for k, st in ann if st.startswith("MINOR")]  # graves en mayúsculas, leves en minúsculas
        if bad:
            fields.append(("TESTIGOS ENCENDIDOS", " · ".join(bad)))
    elif ev.kind == "alerta_misil":
        big = "¡MISIL!"
        w = snap.get("weapons") or {}
        cm = w.get("contramedidas") or {}
        if cm:
            fields.append(("CONTRAMEDIDAS", " · ".join(f"{k} {n}" for k, n in cm.items())))
        if v.get("shields") is not None:
            fields.append(("ESCUDOS", pct(v["shields"])))
    acc = CRIT_HOLO if grave else AMBER_HOLO
    return Card(kind="alerta", title=title, header=header, subtitle=subtitle, icon=icon, level=level, threshold=thr,
                gauges=gauges if src else [], big=big, fields=fields, desc=advice, accent=acc, alert=grave,
                stamp="CRÍTICO" if grave else "AVISO", broken=ev.kind in ("escudos_caidos", "casco_critico", "casco_danado"),
                footer="Fuente: Star Citizen", seed=ev.kind, seconds=8.0)


# ------------------------------------------- 2.1.2: estado, viaje cuántico, aterrizaje y contrato
QUANTUM_HOLO = (110, 150, 255)  # azul cuántico
CONTRACT_HOLO = (232, 194, 90)  # dorado de los contratos
HOLO_KINDS = set(ALERT_HOLO) | {"viaje_cuantico", "tren_recogido", "contrato_objetivo", "contrato_caduca"}


def _mmss(seconds: float | None) -> str:
    if seconds is None:
        return "--:--"
    s = max(0, int(round(seconds)))
    h, rem = divmod(s, 3600)
    return f"{h}:{rem // 60:02d}:{rem % 60:02d}" if h else f"{rem // 60:02d}:{rem % 60:02d}"


def _short_clock(seconds: float) -> str:
    m = int(seconds // 60)
    if m >= 60:
        return f"{m // 60} h {m % 60:02d} min"
    return f"{m} min {int(seconds % 60):02d} s"


def _km(meters: float | None) -> str:
    if meters is None:
        return "—"
    return f"{_num(meters / 1000)} km" if meters >= 10_000 else f"{_num(meters)} m"


def status_card(snap: dict | None):
    """Ficha de estado a petición: personaje arriba y nave abajo, con su icono cada uno."""
    from .holo import Card

    snap = snap or {}
    a, v = snap.get("actor") or {}, snap.get("vehicle") or {}
    tiles = []
    for icon, key, label, thr in (("salud", "health", "SALUD", 0.35), ("sed", "thirst", "HIDRATACIÓN", 0.25),
                                  ("hambre", "hunger", "NUTRICIÓN", 0.25), ("oxigeno", "oxygen", "OXÍGENO", 0.25)):
        if a.get(key) is not None:
            tiles.append((icon, label, a[key], thr))
    if v:
        for icon, key, label, thr in (("casco", "health", "CASCO", 0.5), ("escudos", "shields", "ESCUDOS", 0.25),
                                      ("hidrogeno", "hydrogen", "HIDRÓGENO", 0.2), ("cuantico", "quantum", "CUÁNTICO", 0.15)):
            if v.get(key) is not None:
                tiles.append((icon, label, v[key], thr))
    extra = []
    q = v.get("qt") or {}
    if q.get("state") == "TRAVELING":
        extra.append(f"Viaje cuántico hacia {q.get('dest') or '?'}: llega en {_clock(q['eta'])}" if q.get("eta")
                     else f"En viaje cuántico hacia {q.get('dest') or '?'}")
    c = a.get("contract")
    if c:
        t = f"Contrato: {c['titulo']}"
        if c.get("total"):
            t += f" ({c['hechos']}/{c['total']})"
        extra.append(t)
    if v.get("speed") is not None and not v.get("landed"):
        extra.append(f"{_num(v['speed'])} m/s" + (f" · {_km(v['radar_alt'])} sobre el suelo" if v.get("radar_alt") else ""))
    title = v.get("label") or a.get("player") or "TU PERSONAJE"
    return Card(kind="estado", title=title.upper(), header="TELEMETRÍA · ESTADO",
                subtitle=a.get("location", "") or "", icon="casco" if v else "salud", tiles=tiles,
                desc=" · ".join(extra[:2]), footer="Fuente: Star Citizen", seed="estado", seconds=12.0)


def quantum_card(snap: dict | None, eta0: float | None = None):
    from .holo import Card

    v = (snap or {}).get("vehicle") or {}
    q = v.get("qt") or {}
    if q.get("state") != "TRAVELING":
        return None
    eta = q.get("eta")
    prog = None
    if eta is not None and eta0:
        prog = max(0.0, min(1.0, 1 - eta / eta0))
    fields = [("DISTANCIA", _km(q.get("dist")))]
    if v.get("quantum") is not None:
        fields.append(("COMBUSTIBLE CUÁNTICO", pct(v["quantum"])))
    return Card(kind="alerta", title=(q.get("dest") or "DESTINO").upper(), header="TELEMETRÍA · VIAJE CUÁNTICO",
                subtitle=v.get("label", ""), icon="cuantico", level=prog, value_text=_mmss(eta),
                value_label="LLEGADA EN", fields=fields, accent=QUANTUM_HOLO, stamp="EN VIAJE",
                footer="Fuente: Star Citizen", seed="cuantico")


def gear_card(snap: dict | None):
    from .holo import Card

    v = (snap or {}).get("vehicle") or {}
    alt = v.get("radar_alt")
    if not v or v.get("landed") or v.get("gear") != "RETRACTED" or alt is None or alt > GEAR_REARM_M:
        return None
    return Card(kind="alerta", title="TREN RECOGIDO", header="TELEMETRÍA · ATERRIZAJE", subtitle=v.get("label", ""),
                icon="tren", level=max(0.0, min(1.0, alt / GEAR_WARN_M)), value_text=f"{_num(alt)} m",
                value_label="ALTITUD SOBRE EL SUELO",
                fields=[("VELOCIDAD VERTICAL", f"{_num(v.get('vsi') or 0, 1)} m/s"),
                        ("VELOCIDAD", f"{_num(v.get('speed') or 0)} m/s")],
                accent=CRIT_HOLO_RGB, alert=True, stamp="TREN", footer="Fuente: Star Citizen", seed="tren")


def contract_card(snap: dict | None, expiring: bool = False):
    from .holo import AMBER_HOLO, Card

    c = ((snap or {}).get("actor") or {}).get("contract")
    if not c:
        return None
    left = (c["fin"] - time.time()) if c.get("fin") else None
    fields = []
    total = c.get("total") or 0
    if c.get("de"):
        fields.append(("ENCARGADO POR", c["de"]))
    if expiring and total:
        fields.append(("OBJETIVOS", f"{c['hechos']}/{total}"))
    elif left is not None and left > 0:
        fields.append(("TIEMPO RESTANTE", _short_clock(left)))
    return Card(kind="alerta", title=c["titulo"].upper(), header="CONTRATO SEGUIDO", icon="contrato",
                level=(c["hechos"] / total) if total else None,
                value_text=_mmss(left) if expiring and left is not None else (f"{c['hechos']}/{total}" if total else "—"),
                value_label="CADUCA EN" if expiring else "OBJETIVOS",
                fields=fields, desc=i18n.tr("Objetivo: {o}", o=c["objetivo"]) if c.get("objetivo") else "",
                accent=AMBER_HOLO if expiring else CONTRACT_HOLO, alert=expiring,
                stamp="CADUCA" if expiring else "OBJETIVO", footer="Fuente: Star Citizen", seed="contrato",
                seconds=12.0)


CRIT_HOLO_RGB = (255, 62, 62)


def holo_card(ev: GameEvent, snap: dict | None = None, tel: "Telemetry | None" = None):
    """Ficha de holograma para cualquier suceso de la telemetría (None si no tiene)."""
    if ev.kind in ALERT_HOLO:
        return alert_card(ev, snap)
    if ev.kind == "viaje_cuantico":
        eta0 = (ev.data or {}).get("eta")
        card = quantum_card(snap, eta0)
        if card is not None and tel is not None:
            card.updater = lambda: quantum_card(tel.snap, eta0) if tel.live() else None
            card.seconds = min(900.0, (eta0 or 60) + 6)
        return card
    if ev.kind == "tren_recogido":
        card = gear_card(snap)
        if card is not None and tel is not None:
            card.updater = lambda: gear_card(tel.snap) if tel.live() else None
            card.update_every = 0.5
            card.seconds = 40.0
        return card
    if ev.kind in ("contrato_objetivo", "contrato_caduca"):
        expiring = ev.kind == "contrato_caduca"
        card = contract_card(snap, expiring)
        if card is not None and expiring and tel is not None:  # cuenta atrás en directo
            title = card.title
            card.updater = lambda: (lambda c: c if c is not None and c.title == title else None)(
                contract_card(tel.snap, True)) if tel.live() else None
            card.seconds = 12.0
        return card
    return None

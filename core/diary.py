"""Diario de vuelo: lo importante de cada sesión de juego, en un .log que puedes abrir.

Un archivo por sesión en datos\\diario\\AAAA-MM-DD_HHMM_<personaje>.log, con:
  - cada cosa relevante con su hora (llegadas, naves, quién sube y baja, grupo, muertes…);
  - un RESUMEN al final: dónde dejaste el personaje, última nave pilotada, estado de la nave,
    cuántas veces ha entrado y salido gente de tu nave, muertes, saltos…

Todo sale del Game.log, así que si abres Nova con la partida ya empezada (o después de
jugar) el diario de esa sesión se rehace entero. ultima_sesion.json guarda el resumen
para que Nova sepa al día siguiente dónde lo dejaste.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path

from .config import DATA_DIR

log = logging.getLogger("nova.diary")

DIARY_DIR = DATA_DIR / "diario"
LAST_FILE = DIARY_DIR / "ultima_sesion.json"
MAX_FILES = 60  # se guardan las últimas 60 sesiones

# tipo de evento -> (etiqueta, plantilla). Sin plantilla = no se apunta en el diario.
LINES = {
    "sesion_inicio": ("JUEGO", "Star Citizen arrancado"),
    "personaje": ("JUEGO", "Personaje: {nombre}"),
    "servidor": ("JUEGO", "Entras al universo · servidor {x}"),
    "sesion_fin": ("JUEGO", "Juego cerrado · personaje en {lugar}"),
    "ubicacion": ("LUGAR", "Estás en {lugar}"),
    "llegada_cuantica": ("SALTO", "Llegada cuántica a {lugar}{fuel}"),
    "llegada_cuantica_sin_destino": ("SALTO", "Salto cuántico completado"),
    "salto_error": ("SALTO", "Fallo del motor cuántico: no estaba listo"),
    "jurisdiccion": ("ZONA", "Jurisdicción de {x}"),
    "zona_armisticio_entra": ("ZONA", "Entras en zona de armisticio"),
    "zona_armisticio_sale": ("ZONA", "Sales de la zona de armisticio"),
    "espacio_vigilado_entra": ("ZONA", "Entras en espacio vigilado"),
    "espacio_vigilado_sale": ("ZONA", "Sales del espacio vigilado"),
    "territorio_hostil_entra": ("ZONA", "Entras en territorio hostil"),
    "zona_restringida": ("LEY", "Zona restringida"),
    "propiedad_privada": ("ZONA", "Propiedad privada"),
    "reubicado": ("LEY", "Te han reubicado por seguridad"),
    "nave_entregada": ("NAVE", "{detail}"),
    "nave_subes": ("NAVE", "Subes a la {nave}{de}"),
    "nave_bajas": ("NAVE", "Bajas de la {nave}{de}"),
    "piloto_toma": ("NAVE", "Tomas los mandos de la {nave}"),
    "piloto_suelta": ("NAVE", "Dejas los mandos de la {nave}"),
    "nave_tripulante_entra": ("TRIPULACIÓN", "{nombre} sube a la {nave}{de}"),
    "nave_tripulante_sale": ("TRIPULACIÓN", "{nombre} baja de la {nave}{de}"),
    "nave_inutilizada": ("DAÑOS", "La {nave} ha quedado inutilizada{por}"),
    "nave_destruida": ("DAÑOS", "La {nave} ha sido destruida{por}"),
    "atc_hangar_listo": ("TORRE", "Autorización de la torre concedida"),
    "atc_cola_hangar": ("TORRE", "En cola para el hangar · puesto {puesto}"),
    "atc_incautada": ("TORRE", "Nave incautada: {x}"),
    "atc_incautando": ("TORRE", "Te están incautando la nave"),
    "atc_aviso": ("TORRE", "{x}"),
    "grupo_creado": ("GRUPO", "Has creado un grupo"),
    "grupo_lanzamiento": ("GRUPO", "Lanzamiento de grupo"),
    "grupo_invitacion": ("GRUPO", "Invitación de grupo de {nombre}"),
    "grupo_entra": ("GRUPO", "{nombre} entra en el grupo"),
    "grupo_sale": ("GRUPO", "{nombre} sale del grupo"),
    "grupo_expulsa": ("GRUPO", "{nombre} expulsado del grupo"),
    "grupo_lider": ("GRUPO", "Nuevo líder del grupo: {nombre}"),
    "grupo_te_unes": ("GRUPO", "Te unes al grupo"),
    "grupo_dejas": ("GRUPO", "Dejas el grupo"),
    "grupo_expulsado": ("GRUPO", "Te expulsan del grupo"),
    "grupo_disuelto": ("GRUPO", "Grupo disuelto"),
    "grupo_salto_hacia_ti": ("GRUPO", "{nombre} salta hacia tu posición"),
    "grupo_calibracion_inicio": ("GRUPO", "{nombre} calibra el salto cuántico del grupo"),
    "grupo_calibracion": ("GRUPO", "{nombre} completa la calibración cuántica"),
    "amistad_peticion": ("AMIGOS", "Petición de amistad de {nombre}"),
    "amistad_aceptada": ("AMIGOS", "{nombre} añadido a tus amigos"),
    "llamada": ("AMIGOS", "Llamada entrante{nombre_sp}"),
    "hangar_acceso": ("AMIGOS", "{nombre} te da acceso a su hangar"),
    "dinero_recibido": ("DINERO", "{nombre} te envía {cantidad} aUEC"),
    "dinero_ofrecido": ("DINERO", "{nombre} quiere enviarte {cantidad} {moneda}"),
    "dinero_enviado": ("DINERO", "Envías {cantidad} aUEC a {nombre}"),
    "multa": ("LEY", "Multa de {cantidad} UEC"),
    "crimestat": ("LEY", "Te suben el CrimeStat"),
    "crimen_contra_ti": ("LEY", "{nombre} comete {x} contra ti"),
    "crimen_cometido": ("LEY", "Delito: {x}"),
    "contrato_aceptado": ("CONTRATO", "Aceptado: {x}"),
    "contrato_completado": ("CONTRATO", "Completado: {x}"),
    "contrato_fallido": ("CONTRATO", "Fallido: {x}"),
    "contrato_retirado": ("CONTRATO", "Retirado: {x}"),
    "recompensa": ("CONTRATO", "Recompensa: {x}"),
    "plano_recibido": ("PLANO", "Plano recibido: {x}"),
    "refineria_lista": ("REFINERÍA", "Orden de refinería lista en {lugar}"),
    "herida": ("SALUD", "Herida {x}"),
    "incapacitado": ("SALUD", "Incapacitado{causa_p}"),
    "incap_otro": ("SALUD", "{nombre} incapacitado{causa_p}"),
    "cama_medica": ("SALUD", "Camilla médica{en_nave}: curado {x}"),
    "cama_medica_otro": ("SALUD", "{nombre} usa una camilla médica{en_nave}: {x}"),
    "sobredosis": ("SALUD", "Sobredosis"),
    "emergencias": ("SALUD", "Servicios de emergencia en camino"),
    "rescate_aceptado": ("SALUD", "{nombre} acepta tu baliza de rescate"),
    "muerte": ("MUERTE", "Has muerto{por}{con}{causa}"),
    "regeneracion": ("MUERTE", "Reapareces (regeneración)"),
    "reaparicion_punto": ("MUERTE", "Punto de reaparición: {lugar}"),
    "reaparicion_otro": ("MUERTES", "{nombre} reaparecerá en {lugar}"),
    "baja": ("COMBATE", "Abates a {nombre}{con}{causa}"),
    "muerte_otro": ("MUERTES", "{nombre} muere{a_manos}{con}{causa}"),
    "nave_abatida": ("COMBATE", "{nave} {x} por ti{piloto}"),
    "nave_destruida_otra": ("NAVES", "{nave} {x}{por}"),
    "carga_conectando": ("CARGA", "Conectando con el servidor…"),
    "carga_conectado": ("CARGA", "Conectado al servidor"),
    "carga_aparicion": ("CARGA", "Personaje en el mundo"),
    "carga_fin": ("CARGA", "Carga completa: {x} en {segundos} s"),
    "carga_lenta": ("CARGA", "La carga va lenta: «{x}» lleva {segundos} s"),
    "carga_fallo": ("CARGA", "Fallo de carga en «{x}» ({segundos} s)"),
    "tiron_red": ("RED", "Tirón de red de {segundos} s"),
    "objetivo": ("OBJETIVO", "{x}{en_nave}{lugar_p}"),
    "jugador_buscado": ("JUGADOR", "{detail}"),
    "jugador_org": ("JUGADOR", "{detail}"),
    "temporizador_nuevo": ("TEMPORIZADOR", "{x}: termina a las {hora}{lugar_p}"),
    "temporizador_fin": ("TEMPORIZADOR", "Terminado: {x}{lugar_p}"),
    "llamarada_solar": ("PELIGRO", "Llamarada solar"),
    "combustible_bajo": ("NAVE", "Combustible bajo"),
}


def _fmt_duration(sec: float) -> str:
    sec = int(max(0, sec))
    h, m = divmod(sec // 60, 60)
    return f"{h} h {m} min" if h else f"{m} min"


class Diary:
    """Escucha los eventos del Game.log (también los releídos al arrancar) y escribe el diario."""

    def __init__(self, settings, gamelog=None, directory: Path = DIARY_DIR) -> None:
        self.settings = settings
        self.gamelog = gamelog
        self.dir = directory
        self._lock = threading.RLock()
        self.file: Path | None = None
        self._last_write = 0.0
        self.reset(None)
        if gamelog is not None:
            gamelog.sinks.append(self.on_event)
            gamelog.after_replay.append(self.flush)

    # ------------------------------------------------------------- estado
    def reset(self, start: float | None) -> None:
        self.start = start
        self.end: float | None = None
        self.last_time = start or 0.0
        self.player = ""
        self.version = ""
        self.server = ""
        self.location = ""
        self.places: list[str] = []
        self.ship_now = ""  # nave en la que estás
        self.ship_boarded = ""  # última nave a la que subiste
        self.ship_piloted = ""
        self.ship_piloted_at = 0.0
        self.ship_delivered = ""
        self.ship_state = "sin daños registrados"
        self.ships = Counter()
        self.crew = defaultdict(lambda: {"entradas": 0, "salidas": 0, "personas": Counter()})
        self.party_in = 0
        self.party_out = 0
        self.party_leader = ""
        self.deaths: list[dict] = []
        self.downed = 0
        self.kills = 0
        self.kills_npc = 0
        self.kills_player = 0
        self.ships_downed = 0  # naves que has destruido o inutilizado tú
        self.seen_deaths = 0  # muertes de otros que anotó el juego
        self.seen_ships = 0
        self.med_bed = 0
        self.respawn_point = ""
        self.load_secs = ""
        self.load_slow = 0
        self.stalls = 0
        self._last_downed = 0.0
        self.jumps = 0
        self.last_jump = ""
        self.last_fuel = ""
        self.atc = 0
        self.contracts = Counter()
        self.money_in: list[str] = []
        self.money_out: list[str] = []
        self.friends: list[str] = []
        self.calls = 0
        self.blueprints: list[str] = []
        self.lines: list[str] = []

    # ------------------------------------------------------------- eventos
    def on_event(self, ev) -> None:
        if not self.settings.get("diario_activo", True):
            return
        with self._lock:
            if ev.kind == "sesion_inicio" or self.start is None:
                if ev.kind == "sesion_inicio" or not self.file:
                    self._new_session(ev.when)
            self._apply(ev)
            line = self._describe(ev)
            if line:
                self.lines.append(line)
                self._append(line)
            if ev.kind == "sesion_fin":
                self.end = ev.when
                self._write_full()
            elif not ev.replay and time.time() - self._last_write > 5:
                self._save_state()

    def _new_session(self, when: float) -> None:
        self.reset(when)
        self.dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d_%H%M", time.localtime(when))
        self.file = self.dir / f"{stamp}_sesion.log"
        try:
            self.file.write_text(self._header(), encoding="utf-8")
        except OSError as e:
            log.warning("Diario: %s", e)
        self._prune()

    def _apply(self, ev) -> None:
        d = ev.data
        self.last_time = ev.when
        k = ev.kind
        if k == "personaje":
            self.player = d.get("nombre", "")
            if self.file and self.player and "_sesion.log" in self.file.name:
                new = self.file.with_name(self.file.name.replace("_sesion.log", f"_{self.player}.log"))
                try:
                    os.replace(self.file, new)
                    self.file = new
                except OSError:
                    pass
        elif k == "servidor":
            self.server = d.get("x", "")
            if self.gamelog is not None:
                self.version = self.gamelog.version
        elif k in ("ubicacion", "llegada_cuantica"):
            place = d.get("lugar", "")
            if place:
                self.location = place
                if not self.places or self.places[-1] != place:
                    self.places.append(place)
            if k == "llegada_cuantica":
                self.jumps += 1
                self.last_jump = place
                self.last_fuel = d.get("combustible", "")
        elif k == "llegada_cuantica_sin_destino":
            self.jumps += 1
        elif k == "sesion_fin":
            if d.get("lugar") and d.get("lugar") != "desconocida":
                self.location = d["lugar"]
        elif k == "nave_subes":
            ship = self._ship_label(d)
            self.ship_now = self.ship_boarded = ship
            self.ships[ship] += 1
        elif k == "nave_bajas":
            self.ship_now = ""
        elif k in ("piloto_toma", "piloto_suelta"):
            self.ship_piloted = d.get("nave", "") or self.ship_piloted
            self.ship_piloted_at = ev.when
        elif k == "nave_entregada":
            self.ship_delivered = f"{d.get('nave') or 'nave'} en {d.get('lugar', '?')}"
        elif k in ("nave_tripulante_entra", "nave_tripulante_sale"):
            c = self.crew[self._ship_label(d)]
            c["entradas" if k.endswith("entra") else "salidas"] += 1
            c["personas"][d.get("nombre", "alguien")] += 1
        elif k == "nave_inutilizada":
            self.ship_state = "inutilizada" + (f" ({time.strftime('%H:%M', time.localtime(ev.when))})")
        elif k == "nave_destruida":
            self.ship_state = "DESTRUIDA" + (f" ({time.strftime('%H:%M', time.localtime(ev.when))})")
        elif k == "atc_incautada":
            self.ship_state = "incautada"
        elif k == "grupo_entra":
            self.party_in += 1
        elif k in ("grupo_sale", "grupo_expulsa"):
            self.party_out += 1
        elif k == "grupo_lider":
            self.party_leader = d.get("nombre", "")
        elif k == "muerte":
            self.deaths.append({"hora": ev.when, "por": d.get("nombre", ""), "arma": d.get("x", ""),
                                "lugar": d.get("lugar") or self.location})
        elif k in ("incapacitado", "sobredosis"):
            # El aviso del HUD y la línea técnica del log llegan juntos: se cuenta una vez.
            if ev.when - self._last_downed > 30:
                self.downed += 1
            self._last_downed = ev.when
        elif k == "regeneracion" and (not self.deaths or ev.when - self.deaths[-1]["hora"] > 120):
            self.deaths.append({"hora": ev.when, "por": "", "arma": "", "lugar": self.location})
        elif k == "baja":
            self.kills += 1
            if d.get("tipo") == "jugador":
                self.kills_player += 1
            else:
                self.kills_npc += 1
        elif k == "nave_abatida":
            self.ships_downed += 1
        elif k == "muerte_otro":
            self.seen_deaths += 1
        elif k == "nave_destruida_otra":
            self.seen_ships += 1
        elif k == "cama_medica":
            self.med_bed += 1
        elif k == "reaparicion_punto":
            self.respawn_point = d.get("lugar", "")
        elif k == "carga_fin" and "universo" in d.get("x", ""):
            self.load_secs = d.get("segundos", "")
        elif k in ("carga_lenta", "carga_fallo"):
            self.load_slow += 1
        elif k == "tiron_red":
            self.stalls += 1
        elif k == "atc_hangar_listo":
            self.atc += 1
        elif k.startswith("contrato_") and k in ("contrato_aceptado", "contrato_completado", "contrato_fallido"):
            self.contracts[k.split("_")[1]] += 1
        elif k == "dinero_recibido":
            self.money_in.append(f"{d.get('cantidad', '?')} de {d.get('nombre', '?')}")
        elif k == "dinero_enviado":
            self.money_out.append(f"{d.get('cantidad', '?')} a {d.get('nombre', '?')}")
        elif k in ("amistad_peticion", "amistad_aceptada"):
            if d.get("nombre") and d["nombre"] not in self.friends:
                self.friends.append(d["nombre"])
        elif k == "llamada":
            self.calls += 1
        elif k == "plano_recibido":
            self.blueprints.append(d.get("x", ""))

    def _ship_label(self, d: dict) -> str:
        ship, owner = d.get("nave", "") or "nave", d.get("dueno", "")
        if owner and self.player and owner.lower() != self.player.lower():
            return f"{ship} de {owner}"
        return ship

    def _describe(self, ev) -> str:
        spec = LINES.get(ev.kind)
        if not spec:
            return ""
        tag, tpl = spec
        d = defaultdict(str, ev.data)
        d["detail"] = ev.detail
        owner = d.get("dueno", "")
        d["de"] = f" (de {owner})" if owner and self.player and owner.lower() != self.player.lower() else ""
        d["por"] = f" por {d['nombre']}" if d.get("nombre") and ev.kind in (
            "muerte", "nave_destruida", "nave_inutilizada", "nave_destruida_otra") else ""
        d["con"] = f" con {d['x']}" if d.get("x") and ev.kind in ("muerte", "baja", "muerte_otro") else ""
        d["causa_p"] = f" ({d['causa']})" if d.get("causa") else ""
        d["causa"] = f" ({d['dano']})" if d.get("dano") and ev.kind in ("muerte", "baja", "muerte_otro") else ""
        d["a_manos"] = f" a manos de {d['asesino']}" if d.get("asesino") and d.get("asesino") != d.get("nombre") else ""
        d["piloto"] = f" (piloto: {d['nombre']})" if d.get("nombre") and ev.kind == "nave_abatida" else ""
        d["en_nave"] = f" en la {d['nave']}" if d.get("nave") else ""
        d["lugar_p"] = f" ({d['lugar']})" if d.get("lugar") and ev.kind in ("objetivo", "temporizador_nuevo", "temporizador_fin") else ""
        d["fuel"] = f" (combustible estimado {d['combustible']})" if d.get("combustible") else ""
        d["nombre_sp"] = f" de {d['nombre']}" if d.get("nombre") else ""
        try:
            text = tpl.format_map(d).strip()
        except (KeyError, ValueError):
            text = ev.detail
        if not text:
            return ""
        return f"{time.strftime('%H:%M:%S', time.localtime(ev.when))}  {tag:<12} {text}"

    # ------------------------------------------------------------- archivos
    def _header(self) -> str:
        when = time.strftime("%d/%m/%Y %H:%M", time.localtime(self.start)) if self.start else "?"
        return ("=" * 72 + "\n"
                f"  CUADERNO DE BITÁCORA · NOVA AI · sesión del {when}\n"
                + "=" * 72 + "\n")

    def _append(self, line: str) -> None:
        if not self.file:
            return
        try:
            with open(self.file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as e:
            log.warning("Diario: %s", e)

    def _write_full(self) -> None:
        """Al cerrar el juego: el diario completo con el resumen al final."""
        if not self.file:
            return
        try:
            self.file.write_text(self._header() + "\n".join(self.lines) + "\n\n" + self.summary_text(full=True) + "\n",
                                 encoding="utf-8")
        except OSError as e:
            log.warning("Diario: %s", e)
        self._save_state()

    def _save_state(self) -> None:
        self._last_write = time.time()
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = LAST_FILE.with_suffix(".tmp") if self.dir == DIARY_DIR else self.dir / "ultima_sesion.tmp"
            target = LAST_FILE if self.dir == DIARY_DIR else self.dir / "ultima_sesion.json"
            st = self.state()
            tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, target)
            # Estadísticas entre sesiones (horas, bajas, saltos, contratos…)
            from .stats import Stats, record_from_state
            Stats(self.dir / "estadisticas.json").save_session(record_from_state({**st, "ultimo": self.last_time}))
        except OSError as e:
            log.warning("Diario: %s", e)

    def flush(self) -> None:
        """Guardar ahora (al cerrar Nova)."""
        with self._lock:
            if self.file:
                self._save_state()

    def _prune(self) -> None:
        try:
            files = sorted(self.dir.glob("*.log"), key=lambda p: p.stat().st_mtime)
            for p in files[:-MAX_FILES]:
                p.unlink()
        except OSError:
            pass

    # ------------------------------------------------------------- consultas
    def state(self) -> dict:
        crew = {ship: {"entradas": c["entradas"], "salidas": c["salidas"], "personas": dict(c["personas"])}
                for ship, c in self.crew.items()}
        return {
            "archivo": str(self.file) if self.file else "",
            "inicio": self.start, "fin": self.end, "personaje": self.player, "version": self.version,
            "servidor": self.server, "ubicacion": self.location, "lugares": self.places[-30:],
            "nave_actual": self.ship_now, "ultima_nave_subida": self.ship_boarded,
            "ultima_nave_pilotada": self.ship_piloted, "pilotada_a_las": self.ship_piloted_at,
            "nave_entregada": self.ship_delivered, "estado_nave": self.ship_state,
            "naves": dict(self.ships), "tripulacion": crew,
            "grupo": {"entradas": self.party_in, "salidas": self.party_out, "lider": self.party_leader},
            "muertes": self.deaths, "incapacitado": self.downed, "bajas": self.kills,
            "bajas_npc": self.kills_npc, "bajas_jugadores": self.kills_player, "naves_abatidas": self.ships_downed,
            "muertes_vistas": self.seen_deaths, "naves_destruidas_vistas": self.seen_ships,
            "camilla_medica": self.med_bed, "punto_reaparicion": self.respawn_point,
            "carga_segundos": self.load_secs, "cargas_lentas": self.load_slow, "tirones_red": self.stalls,
            "saltos": self.jumps, "ultimo_salto": self.last_jump, "combustible_ultimo_salto": self.last_fuel,
            "autorizaciones_atc": self.atc, "contratos": dict(self.contracts),
            "dinero_recibido": self.money_in, "dinero_enviado": self.money_out,
            "amigos": self.friends, "llamadas": self.calls, "planos": self.blueprints,
        }

    def summary_text(self, full: bool = False) -> str:
        with self._lock:
            if self.start is None and not self.lines:
                return previous_summary() or "Todavía no hay datos de esta sesión de juego."
            t = lambda x: time.strftime("%H:%M", time.localtime(x)) if x else "?"
            out = []
            if full:
                out.append("=" * 30 + " RESUMEN DE LA SESIÓN " + "=" * 20)
            head = f"Personaje: {self.player or '?'}"
            if self.version:
                head += f" · versión {self.version}"
            if self.server:
                head += f" · servidor {self.server}"
            out.append(head)
            end = self.end or self.last_time
            out.append(f"Sesión: {t(self.start)} – {t(end) if self.end else 'en curso'}"
                       + (f" ({_fmt_duration(end - self.start)})" if self.start and end else ""))
            verb = "Dónde dejaste el personaje" if self.end else "Dónde está el personaje"
            out.append(f"{verb}: {self.location or 'desconocido'}")
            if self.ship_now:
                out.append(f"Nave en la que estás: {self.ship_now}")
            if self.ship_piloted:
                out.append(f"Última nave pilotada: {self.ship_piloted} ({t(self.ship_piloted_at)})")
            state = [self.ship_state]
            if self.ship_delivered:
                state.append(f"última entrega: {self.ship_delivered}")
            if self.last_jump:
                state.append(f"último salto: {self.last_jump}" + (f" (combustible estimado {self.last_fuel})" if self.last_fuel else ""))
            out.append("Estado de la nave: " + " · ".join(state))
            if self.ships:
                out.append("Naves a las que has subido: " + ", ".join(f"{s} (×{n})" for s, n in self.ships.most_common()))
            for ship, c in self.crew.items():
                people = ", ".join(f"{p} ({n})" for p, n in c["personas"].most_common())
                out.append(f"Gente en la {ship}: {c['entradas']} entradas y {c['salidas']} salidas · {people}")
            if self.party_in or self.party_out or self.party_leader:
                out.append(f"Grupo: {self.party_in} entradas, {self.party_out} salidas"
                           + (f" · líder: {self.party_leader}" if self.party_leader else ""))
            deaths = len(self.deaths)
            line = f"Muertes: {deaths} · incapacitado: {self.downed} · bajas: {self.kills}"
            if self.kills:
                line += f" ({self.kills_npc} NPC, {self.kills_player} jugadores)"
            if self.deaths:
                last = self.deaths[-1]
                line += f" · última: {t(last['hora'])} en {last['lugar'] or '?'}" + (f" por {last['por']}" if last["por"] else "")
            out.append(line)
            extra = []
            if self.ships_downed:
                extra.append(f"naves que has derribado: {self.ships_downed}")
            if self.seen_deaths or self.seen_ships:
                extra.append(f"otras muertes anotadas: {self.seen_deaths} · otras naves destruidas: {self.seen_ships}")
            if self.med_bed:
                extra.append(f"curas en camilla médica: {self.med_bed}")
            if self.respawn_point:
                extra.append(f"punto de reaparición: {self.respawn_point}")
            if extra:
                out.append("Combate y salud: " + " · ".join(extra))
            if self.load_secs or self.load_slow or self.stalls:
                out.append("Carga y red: " + " · ".join(x for x in (
                    f"entrada al universo en {self.load_secs} s" if self.load_secs else "",
                    f"cargas lentas: {self.load_slow}" if self.load_slow else "",
                    f"tirones de red: {self.stalls}" if self.stalls else "") if x))
            out.append(f"Saltos cuánticos: {self.jumps} · autorizaciones de la torre: {self.atc}")
            if self.contracts:
                out.append("Contratos: " + ", ".join(f"{k} {v}" for k, v in self.contracts.items()))
            if self.money_in or self.money_out:
                out.append("Dinero: recibido " + ("; ".join(self.money_in) or "nada")
                           + " · enviado " + ("; ".join(self.money_out) or "nada"))
            if self.friends or self.calls:
                out.append(f"Amistad: {', '.join(f for f in self.friends if f) or '—'} · llamadas: {self.calls}")
            if self.blueprints:
                out.append("Planos recibidos: " + ", ".join(self.blueprints))
            if self.places and full:
                out.append("Recorrido: " + " → ".join(self.places[-20:]))
            if full:
                out.append("Nota: desde la versión 4.0.2 el juego solo anota las muertes, incapacitaciones y naves "
                           "destruidas en las que participas tú; el resto no llega al Game.log.")
            return "\n".join(out)

    def recent_files(self, n: int = 10) -> list[dict]:
        try:
            files = sorted(self.dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:n]
        except OSError:
            return []
        return [{"nombre": p.name, "ruta": str(p), "tam": p.stat().st_size} for p in files]


def last_location() -> str:
    """Dónde quedó el personaje en la última sesión registrada."""
    try:
        d = json.loads(LAST_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return d.get("ubicacion") or ""


def previous_summary() -> str:
    """Resumen de la última sesión guardada (para cuando el juego aún no está abierto)."""
    try:
        d = json.loads(LAST_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    when = time.strftime("%d/%m %H:%M", time.localtime(d.get("fin") or d.get("inicio") or 0))
    parts = [f"Última sesión ({when}): personaje {d.get('personaje') or '?'} en {d.get('ubicacion') or 'lugar desconocido'}"]
    if d.get("ultima_nave_pilotada"):
        parts.append(f"última nave pilotada: {d['ultima_nave_pilotada']}")
    if d.get("estado_nave"):
        parts.append(f"estado de la nave: {d['estado_nave']}")
    parts.append(f"muertes: {len(d.get('muertes') or [])}")
    return " · ".join(parts)

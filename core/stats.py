"""Estadísticas entre sesiones: horas de vuelo, bajas, muertes, saltos, contratos y aUEC, por semana.

Cada sesión de juego deja su resumen en `diario/estadisticas.json` (lo escribe la bitácora al guardar).
Para el pasado se pueden recalcular desde los Game.log antiguos que guarda el juego (`logbackups`)."""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
from collections import Counter
from pathlib import Path

log = logging.getLogger("nova.stats")
FIELDS = ("segundos", "muertes", "incapacitado", "bajas", "bajas_npc", "bajas_jugadores", "naves_abatidas",
          "saltos", "contratos_completados", "contratos_fallidos", "auec_recibidos", "auec_enviados", "camilla")


def _amount(text: str) -> int:
    m = re.match(r"\s*([\d.,\s]+)", text or "")
    if not m:
        return 0
    digits = re.sub(r"[^\d]", "", m.group(1))
    return int(digits) if digits else 0


def record_from_state(st: dict) -> dict | None:
    """Resumen de una sesión a partir del estado de la bitácora."""
    start = st.get("inicio")
    if not start:
        return None
    end = st.get("fin") or st.get("ultimo") or start
    con = st.get("contratos") or {}
    return {
        "inicio": start, "fin": end, "segundos": max(0, int(end - start)), "personaje": st.get("personaje", ""),
        "muertes": len(st.get("muertes") or []), "incapacitado": st.get("incapacitado", 0),
        "bajas": st.get("bajas", 0), "bajas_npc": st.get("bajas_npc", 0), "bajas_jugadores": st.get("bajas_jugadores", 0),
        "naves_abatidas": st.get("naves_abatidas", 0), "saltos": st.get("saltos", 0),
        "contratos_completados": con.get("completado", 0), "contratos_fallidos": con.get("fallido", 0),
        "auec_recibidos": sum(_amount(x) for x in st.get("dinero_recibido") or []),
        "auec_enviados": sum(_amount(x) for x in st.get("dinero_enviado") or []),
        "camilla": st.get("camilla_medica", 0), "naves": dict(st.get("naves") or {}),
        "lugares": len(st.get("lugares") or []),
    }


class Stats:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save_session(self, rec: dict | None) -> None:
        if not rec or rec["segundos"] < 60:  # menos de un minuto: no cuenta
            return
        # Sin juego (solo búsquedas o temporizadores con Star Citizen cerrado): no es una sesión de vuelo.
        if not rec.get("personaje") and not rec.get("lugares") and not rec.get("naves") \
                and not any(rec.get(f) for f in FIELDS if f != "segundos"):
            return
        data = self.load()
        data[str(int(rec["inicio"]))] = rec
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as e:
            log.warning("Estadísticas: %s", e)

    # ------------------------------------------------------------ resúmenes
    def weeks(self, n: int = 8) -> list[dict]:
        """Totales por semana (lunes a domingo), de la más reciente a la más antigua."""
        data = self.load().values()
        out: dict[str, dict] = {}
        for r in data:
            lt = time.localtime(r["inicio"])
            monday = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday - lt.tm_wday, 0, 0, 0, 0, 0, -1))
            key = time.strftime("%Y-%m-%d", time.localtime(monday))
            w = out.setdefault(key, {"semana": key, "sesiones": 0, **{f: 0 for f in FIELDS}, "naves": Counter()})
            w["sesiones"] += 1
            for f in FIELDS:
                w[f] += r.get(f, 0) or 0
            w["naves"].update(r.get("naves") or {})
        rows = sorted(out.values(), key=lambda w: w["semana"], reverse=True)[:n]
        for w in rows:
            w["horas"] = round(w["segundos"] / 3600, 1)
            w["nave_favorita"] = w["naves"].most_common(1)[0][0] if w["naves"] else ""
            w["naves"] = dict(w["naves"])
        return rows

    def totals(self, days: int | None = None) -> dict:
        since = time.time() - days * 86400 if days else 0
        rs = [r for r in self.load().values() if r["inicio"] >= since]
        t = {"sesiones": len(rs), **{f: sum(r.get(f, 0) or 0 for r in rs) for f in FIELDS}}
        t["horas"] = round(t["segundos"] / 3600, 1)
        naves = Counter()
        for r in rs:
            naves.update(r.get("naves") or {})
        t["naves_top"] = [n for n, _ in naves.most_common(3)]
        t["desde"] = min((r["inicio"] for r in rs), default=None)
        return t

    def describe(self, periodo: str = "semana") -> str:
        days = {"hoy": 1, "semana": 7, "mes": 30, "año": 365, "ano": 365}.get((periodo or "").lower())
        t = self.totals(days)
        if not t["sesiones"]:
            return "SIN DATOS: todavía no hay sesiones registradas en ese periodo."
        label = {"hoy": "hoy", "semana": "los últimos 7 días", "mes": "los últimos 30 días",
                 "año": "el último año", "ano": "el último año"}.get((periodo or "").lower(), "todas las sesiones")
        lines = [f"Estadísticas de {label}: {t['sesiones']} sesiones, {t['horas']} h de juego.",
                 f"Bajas: {t['bajas']} ({t['bajas_npc']} NPC, {t['bajas_jugadores']} jugadores) · naves derribadas: "
                 f"{t['naves_abatidas']} · muertes: {t['muertes']} · incapacitado: {t['incapacitado']}.",
                 f"Saltos cuánticos: {t['saltos']} · contratos completados: {t['contratos_completados']} "
                 f"(fallidos {t['contratos_fallidos']}) · curas en camilla: {t['camilla']}.",
                 f"aUEC por transferencias: +{t['auec_recibidos']:,} / -{t['auec_enviados']:,}".replace(",", ".")]
        if t["naves_top"]:
            lines.append("Naves más usadas: " + ", ".join(t["naves_top"]) + ".")
        lines.append("Nota: el juego no escribe en el Game.log lo que ganas con contratos o ventas; los aUEC "
                     "son solo las transferencias entre jugadores.")
        return "\n".join(lines)

    # ------------------------------------------------------------ pasado
    def rebuild(self, log_files: list[Path], settings, progress=lambda i, n: None) -> int:
        """Lee Game.log antiguos (logbackups) y guarda sus sesiones. Devuelve cuántas añadió."""
        from .diary import Diary
        from .gamelog import GameLog
        added = 0
        have = set(self.load())
        for i, p in enumerate(log_files):
            progress(i, len(log_files))
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    g = GameLog(settings)
                    g.text = getattr(self, "texts", None) or g.text
                    d = Diary(settings, g, Path(tmp))
                    g.replay_file(p)
                    st = d.state()
                    st["ultimo"] = d.last_time
                    rec = record_from_state(st)
                    if rec and str(int(rec["inicio"])) not in have and rec["segundos"] >= 60:
                        self.save_session(rec)
                        have.add(str(int(rec["inicio"])))
                        added += 1
            except Exception as e:
                log.warning("Estadísticas de %s: %s", p.name, e)
        progress(len(log_files), len(log_files))
        return added

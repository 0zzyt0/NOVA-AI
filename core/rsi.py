"""Consultas a la web de Roberts Space Industries (solo lectura, como un navegador):
- ficha pública de un ciudadano: https://robertsspaceindustries.com/en/citizens/<apodo>
- ficha pública de una organización: https://robertsspaceindustries.com/en/orgs/<SID>
- estado de los servidores: https://status.robertsspaceindustries.com (página + RSS)

NOVA AI no inicia sesión, no modifica nada y solo lee lo que cualquiera ve en esas páginas.
"""
from __future__ import annotations

import html
import logging
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from email.utils import parsedate_to_datetime

import requests

log = logging.getLogger("nova.rsi")
BASE = "https://robertsspaceindustries.com"
STATUS = "https://status.robertsspaceindustries.com"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NovaAI/1.1 (asistente de voz para Star Citizen)",
      "Accept-Language": "en-US,en;q=0.8"}
HANDLE_RE = re.compile(r"^[A-Za-z0-9_\-]{2,60}$")
NOT_FOUND = "Usuario no encontrado, ¿Está bien escrito el apodo?"

LANGS = {"spanish": "español", "english": "inglés", "french": "francés", "german": "alemán", "italian": "italiano",
         "portuguese": "portugués", "russian": "ruso", "chinese": "chino", "japanese": "japonés", "polish": "polaco",
         "dutch": "neerlandés", "korean": "coreano", "turkish": "turco", "swedish": "sueco", "czech": "checo",
         "catalan": "catalán", "arabic": "árabe", "ukrainian": "ucraniano", "finnish": "finés", "danish": "danés",
         "norwegian": "noruego", "greek": "griego", "hungarian": "húngaro", "romanian": "rumano"}
MONTHS = {"Jan": "ene", "Feb": "feb", "Mar": "mar", "Apr": "abr", "May": "may", "Jun": "jun", "Jul": "jul",
          "Aug": "ago", "Sep": "sep", "Oct": "oct", "Nov": "nov", "Dec": "dic"}


class NotFound(Exception):
    pass


def _text(fragment: str) -> str:
    fragment = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", fragment or "")
    fragment = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"[ \t\r\f\v]+", " ", html.unescape(fragment)).strip()


def _lines(page: str) -> list[str]:
    """La página como líneas de texto visibles (respaldo si cambia el HTML)."""
    page = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", page)
    page = re.sub(r"(?i)</?(p|div|li|h\d|span|strong|a|dt|dd|br|tr|td|section|ul)\b[^>]*>", "\n", page)
    page = re.sub(r"<[^>]+>", " ", page)
    out = []
    for ln in html.unescape(page).splitlines():
        ln = re.sub(r"\s+", " ", ln).strip()
        if ln:
            out.append(ln)
    return out


def _labelled(page: str, label: str) -> str:
    """Valor de «<span class=label>Etiqueta</span><strong class=value>valor</strong>» (o lo que venga detrás)."""
    m = re.search(r'class="[^"]*\blabel\b[^"]*"[^>]*>\s*' + re.escape(label) + r'\s*</[^>]+>\s*(?:<[^>]+>\s*)*?'
                  r'<(strong|span|a|div|p)[^>]*class="[^"]*\bvalue\b[^"]*"[^>]*>(.*?)</\1>', page, re.S | re.I)
    if m:
        return _text(m.group(2))
    lines = _lines(page)
    for i, ln in enumerate(lines):
        if ln.lower() == label.lower() and i + 1 < len(lines):
            return lines[i + 1]
    return ""


HIDDEN_TEXT = "Oculto (aparece como [REDACTED] en RSI)"


def redacted(value: str) -> bool:
    """RSI enseña «[REDACTED]» en lo que el jugador o la organización ocultan."""
    return "REDACTED" in (value or "").upper()


def shown(value: str, empty: str = "—") -> str:
    if redacted(value):
        return HIDDEN_TEXT
    return value or empty


def es_date(enlisted: str) -> str:
    """'Apr 20, 2016' -> '20 abr 2016'."""
    m = re.match(r"([A-Za-z]{3})[a-z]*\.? (\d{1,2}), (\d{4})", enlisted or "")
    return f"{int(m.group(2))} {MONTHS.get(m.group(1), m.group(1))} {m.group(3)}" if m else enlisted


def es_langs(fluency: str) -> str:
    parts = [p.strip() for p in (fluency or "").split(",") if p.strip()]
    return ", ".join(f"{p} ({LANGS[p.lower()]})" if p.lower() in LANGS else p for p in parts)


@dataclass
class Org:
    sid: str = ""
    nombre: str = ""
    rango: str = ""
    miembros: str = ""
    etiquetas: list[str] = field(default_factory=list)  # p. ej. PMC, Regular, Role play
    actividad_principal: str = ""
    actividad_secundaria: str = ""
    descripcion: str = ""
    url: str = ""
    oculta: bool = False


@dataclass
class Citizen:
    apodo_juego: str = ""  # «moniker»: el nombre que se ve en el juego
    handle: str = ""
    expediente: str = ""  # UEE Citizen Record
    alta: str = ""  # Enlisted (tal cual)
    idiomas: str = ""  # Fluency (tal cual)
    ubicacion: str = ""
    org: Org = field(default_factory=Org)
    url: str = ""
    consultado: float = 0.0

    def as_dict(self) -> dict:
        return asdict(self)

    def lines(self) -> list[tuple[str, str]]:
        """Los campos que pide la ficha, en orden."""
        o = self.org
        if o.oculta:
            main = "Oculta (aparece como [REDACTED] en RSI)"
        elif o.sid or o.nombre:
            main = f"{o.nombre or o.sid} [{o.sid}]" + (f" · rango: {o.rango}" if o.rango else "")
        else:
            main = "Sin organización principal"
        alta = shown(self.alta) if redacted(self.alta) or not self.alta else f"{self.alta} ({es_date(self.alta)})"
        idiomas = shown(self.idiomas) if redacted(self.idiomas) else (es_langs(self.idiomas) or "—")
        return [("Apodo en juego", shown(self.apodo_juego or self.handle)), ("HandleName", shown(self.handle)),
                ("UEE Citizen Record", shown(self.expediente)),
                ("Fecha de alta (Enlisted)", alta),
                ("Fluency (Idioma)", idiomas), ("Main Organization", main)]

    def hidden_fields(self) -> list[str]:
        """Lo que aparece como [REDACTED] (oculto) en la ficha del jugador o de su organización."""
        out = [k for k, v in self.lines() if v.startswith("Oculta") or v == HIDDEN_TEXT]
        out += [f"organización · {k.lower()}" for k, v in self.org_lines() if v == HIDDEN_TEXT]
        return out

    def org_lines(self) -> list[tuple[str, str]]:
        o = self.org
        if not (o.sid and not o.oculta and (o.miembros or o.etiquetas or o.actividad_principal)):
            return []
        out = [("Organización", f"{shown(o.nombre)} [{o.sid}]" if not redacted(o.nombre) else HIDDEN_TEXT)]
        if o.miembros:
            out.append(("Miembros", shown(o.miembros)))
        if o.etiquetas:
            tags = [t for t in o.etiquetas if not redacted(t)]
            out.append(("Tipo", " · ".join(tags) if tags else HIDDEN_TEXT))
        acts = [x for x in (o.actividad_principal, o.actividad_secundaria) if x]
        if acts:
            out.append(("Actividad", HIDDEN_TEXT if all(redacted(x) for x in acts)
                        else " / ".join(x for x in acts if not redacted(x))))
        if o.descripcion:
            out.append(("Descripción", shown(o.descripcion)))
        out.append(("Página de la org", o.url))
        return out

    def text(self) -> str:
        rows = [f"• {k}: {v}" for k, v in self.lines()]
        org = self.org_lines()
        if org:
            rows.append("")
            rows += [f"  {k}: {v}" for k, v in org]
        rows.append(f"Ficha: {self.url}")
        return "\n".join(rows)


# ------------------------------------------------------------------ análisis de páginas
def parse_citizen(page: str, handle: str) -> Citizen:
    c = Citizen(url=f"{BASE}/en/citizens/{urllib.parse.quote(handle)}", consultado=time.time())
    c.handle = _labelled(page, "Handle name")
    c.expediente = _labelled(page, "UEE Citizen Record")
    if not c.handle or not c.expediente:
        raise NotFound(handle)
    # Apodo en juego: el primer valor del bloque de perfil (antes de «Handle name»)
    prof = re.search(r'class="[^"]*\bprofile\b[^"]*".*?class="[^"]*\binfo\b[^"]*"[^>]*>(.*?)Handle name', page, re.S | re.I)
    if prof:
        m = re.search(r'class="[^"]*\bvalue\b[^"]*"[^>]*>(.*?)</', prof.group(1), re.S)
        if m:
            c.apodo_juego = _text(m.group(1))
    if not c.apodo_juego:
        lines = _lines(page)
        i = next((i for i, ln in enumerate(lines) if ln == "Handle name"), -1)
        if i > 0:
            c.apodo_juego = lines[i - 1]
    c.alta = _labelled(page, "Enlisted")
    c.idiomas = _labelled(page, "Fluency")
    c.ubicacion = _labelled(page, "Location")
    # Organización principal
    o = c.org
    i = page.find("main-org")
    scope = ""
    if i >= 0:
        end = len(page)
        for marker in ("citizen-record", ">Enlisted<", "Enlisted"):
            j = page.find(marker, i + 8)
            if j > 0:
                end = min(end, j)
        scope = page[i:min(end, i + 8000)]
        if re.search(r'main-org[^"]*visibility-[RH]\b', page[i:i + 200]):
            o.oculta = True
    o.sid = _labelled(scope, "Spectrum Identification (SID)")
    o.rango = _labelled(scope, "Organization rank")
    m = re.search(r'<a[^>]*href="/(?:en/)?orgs/([A-Za-z0-9_\-]+)"[^>]*>([^<]{1,80})</a>', scope)
    if m:
        o.sid = o.sid or m.group(1)
        o.nombre = _text(m.group(2))
    if not o.nombre:
        lines = _lines(scope)
        i = next((i for i, ln in enumerate(lines) if ln.lower() == "main organization"), -1)
        if i >= 0 and i + 1 < len(lines) and lines[i + 1] != "Spectrum Identification (SID)":
            o.nombre = lines[i + 1]
    if redacted(o.sid) or redacted(o.nombre):  # organización principal tapada con [REDACTED]
        o.oculta, o.sid, o.nombre, o.rango = True, "", "", ""
    if o.sid and not o.nombre:
        o.nombre = o.sid
    if re.search(r"(?i)\bno main org|has no main org|NO ORG", _text(scope)) and not o.sid:
        o.sid = o.nombre = ""
    if o.sid:
        o.url = f"{BASE}/en/orgs/{urllib.parse.quote(o.sid)}"
    return c


def parse_org(page: str, sid: str) -> Org:
    o = Org(sid=sid, url=f"{BASE}/en/orgs/{urllib.parse.quote(sid)}")
    m = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
    if m:
        name = _text(re.sub(r'<span[^>]*class="[^"]*symbol[^"]*"[^>]*>.*?</span>', "", m.group(1)))
        o.nombre = name.strip(" /") or sid
    txt = _text(page)
    m = re.search(r"(\d[\d,.]*)\s+members?\b", txt, re.I)
    if m:
        o.miembros = m.group(1)
    elif re.search(r"(?i)\[?REDACTED\]?\s+members?\b", txt):
        o.miembros = "[REDACTED]"
    m = re.search(r'<ul[^>]*class="[^"]*\btags\b[^"]*"[^>]*>(.*?)</ul>', page, re.S)
    if m:
        o.etiquetas = [t for t in (_text(x) for x in re.findall(r"<li[^>]*>(.*?)</li>", m.group(1), re.S)) if t]
    for which in ("primary", "secondary"):
        m = re.search(r'class="[^"]*\b' + which + r'\b[^"]*\btooltip-wrap\b[^"]*"[^>]*>\s*<img[^>]*alt="([^"]+)"', page)
        if not m:
            m = re.search(r'class="[^"]*\b' + which + r'\b[^"]*"[^>]*>\s*<img[^>]*alt="([^"]+)"', page)
        if m:
            setattr(o, "actividad_principal" if which == "primary" else "actividad_secundaria", html.unescape(m.group(1)))
    m = re.search(r'class="[^"]*\bbody\b[^"]*\bmarkitup-text\b[^"]*"[^>]*>(.*?)</div>', page, re.S)
    if m:
        d = _text(m.group(1))
        o.descripcion = (d[:217] + "…") if len(d) > 220 else d
    return o


# ------------------------------------------------------------------ consultas en línea
class RSI:
    def __init__(self, http=None) -> None:
        self.http = http or requests.Session()

    def _page(self, url: str) -> str:
        r = self.http.get(url, headers=UA, timeout=15)
        if r.status_code == 404:
            raise NotFound(url)
        r.raise_for_status()
        return r.text

    def citizen(self, handle: str) -> Citizen:
        """Ficha del jugador y de su organización principal. NotFound si no existe o no se puede leer."""
        handle = (handle or "").strip().strip("@").strip()
        if not HANDLE_RE.match(handle):
            raise NotFound(handle)
        try:
            c = parse_citizen(self._page(f"{BASE}/en/citizens/{urllib.parse.quote(handle)}"), handle)
        except NotFound:
            raise
        except Exception as e:  # cualquier error: no se ha podido obtener la ficha
            log.warning("Ficha de %s: %s", handle, e)
            raise NotFound(handle) from e
        if c.org.sid and not c.org.oculta:
            try:
                full = parse_org(self._page(c.org.url), c.org.sid)
                full.rango = c.org.rango
                full.nombre = full.nombre or c.org.nombre
                c.org = full
            except Exception as e:  # la ficha del jugador vale aunque falle la de la organización
                log.warning("Organización %s: %s", c.org.sid, e)
        return c

    def status(self) -> dict:
        """Estado de los servidores: componentes + avisos recientes o programados."""
        out = {"componentes": {}, "avisos": [], "ok": True, "url": STATUS}
        page = self._page(STATUS + "/")
        lines = _lines(page)
        names = ("Platform", "Persistent Universe", "Electronic Access", "Arena Commander")
        words = ("Operational", "Degraded Performance", "Degraded", "Partial Outage", "Major Outage",
                 "Under Maintenance", "Maintenance", "Down", "Disrupted")
        for i, ln in enumerate(lines):
            if ln in names:
                for nxt in lines[i + 1:i + 4]:
                    w = next((w for w in words if nxt.lower().startswith(w.lower())), None)
                    if w:
                        out["componentes"][ln] = w
                        break
        out["ok"] = all(v == "Operational" for v in out["componentes"].values()) if out["componentes"] else True
        try:
            rss = self._page(STATUS + "/index.xml")
            now = time.time()
            for item in ET.fromstring(rss.encode("utf-8")).iter("item"):
                title = (item.findtext("title") or "").strip()
                try:
                    when = parsedate_to_datetime(item.findtext("pubDate") or "").timestamp()
                except (TypeError, ValueError):
                    continue
                desc = _text(item.findtext("description") or "")
                resolved = bool(re.search(r"(?i)\b(resolved|completed|deployed)\b", desc))
                if when > now or (now - when < 36 * 3600 and not resolved):
                    out["avisos"].append({"titulo": title, "fecha": when, "link": item.findtext("link") or "",
                                          "futuro": when > now})
        except Exception as e:
            log.info("RSS de estado: %s", e)
        return out


def status_text(st: dict) -> str:
    comp = st.get("componentes") or {}
    es = {"Operational": "operativo", "Degraded Performance": "rendimiento degradado", "Degraded": "degradado",
          "Partial Outage": "caída parcial", "Major Outage": "caída grave", "Under Maintenance": "en mantenimiento",
          "Maintenance": "en mantenimiento", "Down": "caído", "Disrupted": "con incidencias"}
    names = {"Platform": "Plataforma (web y lanzador)", "Persistent Universe": "Universo persistente",
             "Arena Commander": "Arena Commander", "Electronic Access": "Electronic Access"}
    parts = [f"{names.get(k, k)}: {es.get(v, v)}" for k, v in comp.items()]
    for a in st.get("avisos") or []:
        when = time.strftime("%d/%m %H:%M", time.localtime(a["fecha"]))
        parts.append(("Programado" if a.get("futuro") else "Aviso") + f" ({when}): {a['titulo']}")
    if not parts:
        return "No he podido leer el estado de los servidores."
    head = "Todo operativo." if st.get("ok") and not st.get("avisos") else "Atención a los servidores:"
    return head + "\n" + "\n".join("- " + p for p in parts)

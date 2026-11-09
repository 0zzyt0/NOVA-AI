"""Herramientas que la IA puede usar: nave, enciclopedia local (juego + scmdb + UEX), wiki, internet,
UEX en directo, Game.log, diario de sesión y memoria."""
from __future__ import annotations

import html
import json
import logging
import re
import time
import unicodedata
from typing import Any, Callable

import requests

log = logging.getLogger("nova.tools")
UA = {"User-Agent": "NovaCopiloto/1.0 (asistente de voz para Star Citizen; uso personal)"}
WIKI_API = "https://starcitizen.tools/api.php"
UEX = "https://api.uexcorp.uk/2.0"


def _strip_html(s: str) -> str:
    s = re.sub(r"(?is)<(script|style|table|sup)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if c.isalnum() or c == " ").strip()


def _fmt(n: Any) -> str:
    try:
        return f"{float(n):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


class Tools:
    def __init__(self, settings, commands, memory, gamelog) -> None:
        self.settings, self.commands, self.memory, self.gamelog = settings, commands, memory, gamelog
        self.knowledge = None  # enciclopedia local (la pone el asistente)
        self.diary = None  # diario de la sesión de juego
        self._cache: dict[str, tuple[float, Any]] = {}
        self.on_command: Callable[[str], None] | None = None  # avisa a la ventana
        self.on_tool: Callable[[str, bool], None] = lambda name, running: None  # inicio/fin de cada herramienta

    # ---------------------------------------------------------------- utilidades
    def _get(self, url: str, params: dict | None = None, ttl: int = 0, timeout: int = 12) -> Any:
        key = url + json.dumps(params or {}, sort_keys=True)
        if ttl and key in self._cache and time.time() - self._cache[key][0] < ttl:
            return self._cache[key][1]
        r = requests.get(url, params=params, headers=UA, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        if ttl:
            self._cache[key] = (time.time(), data)
        return data

    # ------------------------------------------------------------------ esquema
    def schemas(self) -> list[dict]:
        ids = self.commands.ai_ids()
        return [
            {"type": "function", "function": {
                "name": "ejecutar_comando_nave",
                "description": "Pulsa las teclas de Star Citizen para uno o varios comandos de la nave, en orden. "
                               "Úsalo SIEMPRE que el piloto pida actuar sobre la nave. Comandos disponibles:\n"
                               + self.commands.tool_catalog(),
                "parameters": {"type": "object", "properties": {
                    "comandos": {"type": "array", "items": {"type": "string", "enum": ids},
                                 "description": "IDs de los comandos a ejecutar, en orden"}},
                    "required": ["comandos"]}}},
            {"type": "function", "function": {
                "name": "buscar_datos_juego",
                "description": "PRIMERA OPCIÓN para cualquier dato del juego. Busca en la enciclopedia local, al día con "
                               "el parche que tienes instalado: textos oficiales del juego (naves, objetos con fabricante/"
                               "tipo/tamaño, planetas y lunas con sus minerales, recursos y criaturas, estaciones, "
                               "fabricantes, delitos, lore, consejos), scmdb.net (misiones, planos, minería, refinerías, "
                               "equipo de minería) y UEX (mercancías con precio medio, naves con SCU y tripulación). "
                               "Funciona en español o inglés.",
                "parameters": {"type": "object", "properties": {
                    "consulta": {"type": "string", "description": "Lo que buscas, p. ej. 'Anvil Paladin', 'Hurston minerales'"},
                    "tipo": {"type": "string", "enum": ["todo", "nave", "objeto", "lugar", "fabricante", "mision", "plano",
                                                       "mineral", "mercancia", "lore", "consejo", "ley", "equipo", "refineria"],
                             "description": "Para filtrar (opcional)"}},
                    "required": ["consulta"]}}},
            {"type": "function", "function": {
                "name": "buscar_misiones",
                "description": "Misiones/contratos del parche LIVE (scmdb.net): título, contratista, tipo, pago en aUEC, "
                               "sistemas, reputación necesaria y ganada, PLANOS (blueprints) que pueden dar, objetos de "
                               "recompensa, si es ilegal o compartible.",
                "parameters": {"type": "object", "properties": {
                    "consulta": {"type": "string", "description": "Texto libre (contratista, objetivo, plano…), opcional"},
                    "sistema": {"type": "string", "description": "Stanton, Pyro o Nyx (opcional)"},
                    "tipo": {"type": "string", "description": "Tipo o contratista: Mercenary, Delivery, Bounty Hunter, "
                                                              "Salvage, Ship Mining, Hauling, Headhunters… (opcional)"},
                    "con_planos": {"type": "boolean", "description": "Solo las que dan planos"},
                    "legal": {"type": "boolean", "description": "true = solo legales, false = solo ilegales"}}}}},
            {"type": "function", "function": {
                "name": "plano_fabricacion",
                "description": "Receta de fabricación de un objeto (blueprint/plano/BP) del parche LIVE: materiales, "
                               "cantidades en SCU, calidad mínima, tiempo, y QUÉ MISIONES dan ese plano.",
                "parameters": {"type": "object", "properties": {
                    "objeto": {"type": "string", "description": "Nombre del objeto, p. ej. 'P4-AR', 'Antium Core'"}},
                    "required": ["objeto"]}}},
            {"type": "function", "function": {
                "name": "donde_minar",
                "description": "Dónde encontrar un mineral o recurso (nave, ROC, a mano o recolección) según los datos del "
                               "parche LIVE: ubicaciones con su porcentaje, rareza, firma de escáner, mejores refinerías "
                               "para ese mineral y precio medio de venta (UEX).",
                "parameters": {"type": "object", "properties": {
                    "mineral": {"type": "string", "description": "p. ej. 'Quantainium', 'Hadanite', 'Laranite'"}},
                    "required": ["mineral"]}}},
            {"type": "function", "function": {
                "name": "buscar_wiki_star_citizen",
                "description": "Busca en la Star Citizen Wiki (starcitizen.tools): lore, naves, armas, componentes, "
                               "ubicaciones, facciones, misiones, mecánicas. Búsqueda en INGLÉS da mejores resultados.",
                "parameters": {"type": "object", "properties": {
                    "consulta": {"type": "string", "description": "Términos de búsqueda, preferiblemente en inglés"}},
                    "required": ["consulta"]}}},
            {"type": "function", "function": {
                "name": "buscar_en_internet",
                "description": "Busca en internet información actual (parches, noticias, eventos, guías, Reddit, Spectrum).",
                "parameters": {"type": "object", "properties": {"consulta": {"type": "string"}},
                               "required": ["consulta"]}}},
            {"type": "function", "function": {
                "name": "leer_pagina_web",
                "description": "Lee el texto de una página web concreta (por ejemplo, un resultado de búsqueda).",
                "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
            {"type": "function", "function": {
                "name": "uex_precios_mercancia",
                "description": "Precios actuales de compra y venta de una mercancía (comercio) en las terminales, según UEX Corp.",
                "parameters": {"type": "object", "properties": {
                    "mercancia": {"type": "string", "description": "Nombre en inglés, p. ej. 'Laranite', 'Quantanium', 'Agricium'"}},
                    "required": ["mercancia"]}}},
            {"type": "function", "function": {
                "name": "uex_rutas_comercio",
                "description": "Mejores rutas comerciales (dónde comprar y dónde vender) según UEX Corp. Indica mercancía o terminal de origen.",
                "parameters": {"type": "object", "properties": {
                    "mercancia": {"type": "string", "description": "Nombre en inglés (opcional)"},
                    "origen": {"type": "string", "description": "Terminal/estación de origen (opcional), p. ej. 'Lorville', 'Area 18'"},
                    "inversion": {"type": "integer", "description": "aUEC disponibles para invertir (opcional)"}}}}},
            {"type": "function", "function": {
                "name": "estado_del_juego",
                "description": "Lo que dice el Game.log y el diario de la sesión: dónde está o dónde dejó el personaje, "
                               "nave actual, última nave pilotada, estado de la nave, quién ha entrado y salido de la nave, "
                               "grupo, muertes, saltos, contratos y últimos eventos.",
                "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {
                "name": "recordar",
                "description": "Guarda en la memoria permanente un dato útil sobre el piloto (su nave, gustos, organización, planes).",
                "parameters": {"type": "object", "properties": {"dato": {"type": "string"}}, "required": ["dato"]}}},
            {"type": "function", "function": {
                "name": "olvidar",
                "description": "Borra de la memoria los datos que contengan un texto.",
                "parameters": {"type": "object", "properties": {"texto": {"type": "string"}}, "required": ["texto"]}}},
        ]

    # ---------------------------------------------------------------- despacho
    def call(self, name: str, args: dict) -> str:
        fn = getattr(self, "t_" + name, None)
        if not fn:
            return f"Herramienta desconocida: {name}"
        self.on_tool(name, True)
        try:
            out = fn(**(args or {}))
        except TypeError as e:
            out = f"Argumentos no válidos: {e}"
        except requests.RequestException as e:
            out = f"No pude conectar ({type(e).__name__}). Sin datos."
        except RuntimeError as e:  # p. ej. la enciclopedia aún se está preparando
            out = f"SIN DATOS: {e}"
        except Exception as e:  # una herramienta rota no debe tumbar a Nova
            log.exception("Herramienta %s", name)
            out = f"Error en {name}: {e}"
        finally:
            self.on_tool(name, False)
        return str(out)[:6000]

    # --------------------------------------------------------------- la nave
    def t_ejecutar_comando_nave(self, comandos: list[str] | str) -> str:
        if isinstance(comandos, str):
            comandos = [comandos]
        results = []
        for cid in comandos:
            cmd = self.commands.commands.get(cid)
            if not cmd or cmd.solo_frase_exacta:
                results.append(f"{cid}: no existe")
                continue
            if self.on_command:
                self.on_command(cmd.nombre)
            results.append(self.commands.execute(cmd))
        return "; ".join(results)

    # -------------------------------------------------------------- wiki
    def t_buscar_wiki_star_citizen(self, consulta: str) -> str:
        data = self._get(WIKI_API, {"action": "query", "list": "search", "srsearch": consulta,
                                    "srlimit": 4, "format": "json"}, ttl=3600)
        hits = data.get("query", {}).get("search", [])
        if not hits:
            return "SIN RESULTADOS en la wiki."
        out = ["Resultados de la wiki:"]
        for h in hits:
            out.append(f"- {h['title']}: {_strip_html(h.get('snippet', ''))}")
        top = hits[0]["title"]
        text = ""
        try:  # extracto del mejor resultado
            d = self._get(WIKI_API, {"action": "query", "prop": "extracts", "explaintext": 1,
                                     "exchars": 3500, "titles": top, "format": "json", "redirects": 1}, ttl=3600)
            pages = d.get("query", {}).get("pages", {})
            text = next(iter(pages.values()), {}).get("extract", "") if pages else ""
        except Exception:
            text = ""
        if not text:
            try:
                d = self._get(WIKI_API, {"action": "parse", "page": top, "prop": "text",
                                         "format": "json", "redirects": 1}, ttl=3600)
                text = _strip_html(d.get("parse", {}).get("text", {}).get("*", ""))[:3500]
            except Exception:
                text = ""
        if text:
            out.append(f"\nContenido de '{top}' (https://starcitizen.tools/{top.replace(' ', '_')}):\n{text}")
        return "\n".join(out)

    # ---------------------------------------------------------- internet
    def t_buscar_en_internet(self, consulta: str) -> str:
        try:
            from ddgs import DDGS
        except ImportError:
            return "La búsqueda web no está instalada (paquete ddgs)."
        results = list(DDGS().text(consulta, max_results=6))
        if not results:
            return "SIN RESULTADOS en internet."
        return "\n".join(f"- {r.get('title')}: {r.get('body', '')[:300]} ({r.get('href')})" for r in results)

    def t_leer_pagina_web(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            return "URL no válida."
        r = requests.get(url, headers=UA, timeout=15)
        r.raise_for_status()
        return _strip_html(r.text)[:5000]

    # ---------------------------------------------------------------- UEX
    def _uex(self, resource: str, params: dict | None = None, ttl: int = 600) -> list[dict]:
        d = self._get(f"{UEX}/{resource}", params, ttl=ttl)
        if d.get("status") != "ok":
            raise RuntimeError(d.get("message", "UEX no respondió"))
        return d.get("data") or []

    def _find(self, items: list[dict], name: str, keys=("name", "code", "nickname")) -> dict | None:
        q = _norm(name)
        best, score = None, 0
        for it in items:
            for k in keys:
                v = _norm(str(it.get(k) or ""))
                if not v:
                    continue
                s = 3 if v == q else 2 if v.startswith(q) else 1 if q in v else 0
                if s > score:
                    best, score = it, s
        return best

    def t_uex_precios_mercancia(self, mercancia: str) -> str:
        com = self._find(self._uex("commodities", ttl=86400), mercancia)
        if not com:
            return f"SIN DATOS: UEX no conoce la mercancía '{mercancia}'."
        rows = self._uex("commodities_prices", {"id_commodity": com["id"]})
        buy = sorted([r for r in rows if (r.get("price_buy") or 0) > 0], key=lambda r: r["price_buy"])[:5]
        sell = sorted([r for r in rows if (r.get("price_sell") or 0) > 0], key=lambda r: -r["price_sell"])[:5]
        out = [f"{com['name']} (UEX, aUEC por SCU):"]
        if buy:
            out.append("Comprar más barato en: " + "; ".join(
                f"{r.get('terminal_name')} ({r.get('star_system_name') or ''}) {_fmt(r['price_buy'])}" for r in buy))
        if sell:
            out.append("Vender más caro en: " + "; ".join(
                f"{r.get('terminal_name')} ({r.get('star_system_name') or ''}) {_fmt(r['price_sell'])}" for r in sell))
        return "\n".join(out) if len(out) > 1 else f"SIN DATOS de precios para {com['name']}."

    def t_uex_rutas_comercio(self, mercancia: str | None = None, origen: str | None = None,
                             inversion: int | None = None) -> str:
        params: dict = {}
        if mercancia:
            com = self._find(self._uex("commodities", ttl=86400), mercancia)
            if not com:
                return f"SIN DATOS: UEX no conoce '{mercancia}'."
            params["id_commodity"] = com["id"]
        if origen:
            term = self._find(self._uex("terminals", ttl=86400), origen,
                              keys=("name", "nickname", "space_station_name", "city_name", "outpost_name"))
            if not term:
                return f"SIN DATOS: no encuentro la terminal '{origen}'."
            params["id_terminal_origin"] = term["id"]
        if not params:
            return "Necesito una mercancía o un origen."
        if inversion:
            params["investment"] = int(inversion)
        rows = self._uex("commodities_routes", params)
        rows = sorted(rows, key=lambda r: -(r.get("profit") or 0))[:5]
        if not rows:
            return "SIN DATOS: no hay rutas con esos criterios."
        return "Mejores rutas (UEX):\n" + "\n".join(
            f"- {r.get('commodity_name')}: comprar en {r.get('origin_terminal_name')} a {_fmt(r.get('price_origin'))}, "
            f"vender en {r.get('destination_terminal_name')} a {_fmt(r.get('price_destination'))}; "
            f"beneficio {_fmt(r.get('profit'))} aUEC con inversión {_fmt(r.get('investment'))}"
            for r in rows)

    # ------------------------------------------------- enciclopedia local
    def _kn(self):
        if self.knowledge is None or not self.knowledge.docs:
            raise RuntimeError("La enciclopedia local todavía no está lista (se prepara al arrancar).")
        return self.knowledge

    def t_buscar_datos_juego(self, consulta: str, tipo: str | None = None) -> str:
        from .knowledge import describe_doc
        kn = self._kn()
        kinds = None if not tipo or tipo == "todo" else (tipo,)
        docs = kn.search(consulta, kinds, k=6)
        if not docs:
            return "SIN RESULTADOS en la enciclopedia local."
        v = kn.versions
        head = f"Enciclopedia local (juego {v.get('global.ini', 'inglés')}, scmdb {v.get('scmdb', '—')}, UEX {v.get('uex', '—')}):"
        return head + "\n" + "\n".join("- " + describe_doc(d) for d in docs)

    def t_buscar_misiones(self, consulta: str = "", sistema: str = "", tipo: str = "", con_planos: bool = False,
                          legal: bool | None = None) -> str:
        kn = self._kn()
        found = kn.find_contracts(consulta, sistema, tipo, bool(con_planos), legal, k=8)
        if not found:
            return "SIN RESULTADOS: ninguna misión encaja (scmdb.net)."
        out = [f"Misiones (scmdb.net, {kn.versions.get('scmdb', '')}; https://scmdb.net):"]
        for c in found:
            bits = [f"«{c['titulo']}»", c["contratista"], c["tipo"], f"{_fmt(c['pago'])} aUEC" if c["pago"] else "",
                    "/".join(c["sistemas"])]
            if c["rep_min"]:
                bits.append(f"rep. mínima {c['rep_min']}")
            if c["rep_gana"]:
                bits.append(f"+{_fmt(c['rep_gana'])} rep")
            if c["planos"]:
                pr = f" ({int(c['prob_plano'] * 100)} %)" if isinstance(c.get("prob_plano"), (int, float)) else ""
                bits.append("PLANOS" + pr + ": " + ", ".join(c["planos"][:8]))
            if c["objetos"]:
                bits.append("objetos: " + ", ".join(c["objetos"][:4]))
            if c["ilegal"]:
                bits.append("ILEGAL")
            if c["compartible"]:
                bits.append("compartible")
            if c["lugares"]:
                bits.append("lugares: " + ", ".join(c["lugares"][:4]))
            out.append("- " + " · ".join(b for b in bits if b))
        return "\n".join(out)

    def t_plano_fabricacion(self, objeto: str) -> str:
        kn = self._kn()
        found = kn.find_blueprints(objeto, 3)
        if not found:
            return f"SIN DATOS: no encuentro ningún plano de «{objeto}» (scmdb.net)."
        out = []
        for b in found[:2]:
            out.append(f"Plano: {b['producto']}" + (f" ({b['tipo']})" if b["tipo"] else ""))
            for n, t in enumerate(b["niveles"][:3], 1):
                mins = f"{int(t['tiempo'] // 60)} min {int(t['tiempo'] % 60)} s" if t.get("tiempo") else "?"
                out.append(f"  Nivel {n} · tiempo {mins}:")
                for s in t["huecos"]:
                    out.append(f"    - {s['nombre']}: " + " o ".join(s["opciones"])
                               + (" (afecta a la calidad)" if s["modificadores"] else ""))
            if b["misiones"]:
                ms = b["misiones"][:6]
                out.append("  Se consigue en misiones: " + "; ".join(
                    f"«{m['titulo']}» de {m['contratista']} ({'/'.join(m['sistemas'])})"
                    + (f", {int(m['probabilidad'] * 100)} %" if isinstance(m.get("probabilidad"), (int, float)) else "")
                    for m in ms))
            else:
                out.append("  No aparece como recompensa de misiones (puede ser de serie, de compra o de botín).")
        if len(found) > 2:
            out.append("Otros planos parecidos: " + ", ".join(b["producto"] for b in found[2:]))
        out.append("Fuente: scmdb.net · https://scmdb.net")
        return "\n".join(out)

    def t_donde_minar(self, mineral: str) -> str:
        kn = self._kn()
        ore, places = kn.find_ore(mineral)
        if not ore and not places:
            return f"SIN DATOS de «{mineral}» en los datos de minería (scmdb.net)."
        name = ore.get("nombre", mineral) if ore else mineral
        out = [f"{name}" + (f" · rareza {ore.get('rareza')}" if ore and ore.get("rareza") else "")]
        if ore:
            sig = [f"{lbl} {ore[k]}" for k, lbl in (("firma_nave", "nave"), ("firma_roc", "ROC"), ("firma_mano", "a mano"))
                   if ore.get(k)]
            if sig:
                out.append("Firma de escáner: " + ", ".join(sig))
        by_how: dict[str, list] = {}
        for p in places:
            by_how.setdefault(p[2], []).append(p)
        for how, lst in by_how.items():
            out.append(f"Dónde ({how}): " + "; ".join(f"{p[0]} ({p[1]}) {p[3]:g} %" for p in lst[:8]))
        refs = kn.best_refineries(name)
        if refs:
            out.append("Mejores refinerías para él: " + "; ".join(f"{r[0]} ({r[1]}) {r[2]:+d} %" for r in refs))
        com = kn.commodity(name)
        if com and (com.get("price_sell") or com.get("price_buy")):
            out.append(f"Precio medio (UEX): venta {_fmt(com.get('price_sell'))} aUEC/SCU")
        out.append("El % es la proporción de los depósitos de ese tipo en ese lugar. Fuente: scmdb.net (parche LIVE).")
        return "\n".join(out)

    # ------------------------------------------------------- juego y memoria
    def t_estado_del_juego(self) -> str:
        parts = [self.gamelog.summary() if self.gamelog else "El lector del Game.log está desactivado."]
        if self.diary is not None:
            parts.append("Diario de la sesión:\n" + self.diary.summary_text())
        return "\n\n".join(parts)

    def t_recordar(self, dato: str) -> str:
        return self.memory.remember(dato)

    def t_olvidar(self, texto: str) -> str:
        return self.memory.forget(texto)

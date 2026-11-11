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
        self.timers = None  # temporizadores (los pone el asistente)
        self.stats = None  # estadísticas entre sesiones
        self.status_check = None  # estado de los servidores de RSI
        self.on_timer_added: Callable[[dict], None] = lambda t: None
        self.on_place: Callable[[str], str] | None = None  # ficha de planeta/lugar (la pone el asistente)
        self.on_chat: Callable[[str], str] | None = None  # mensaje al chat del juego (lo pone el asistente)
        self.dictionary = None  # Diccionario de consultas (lo pone el asistente)
        self.starmap = None  # starmap.space (lo pone el asistente)
        self.shops = None  # tiendas de UEX (lo pone el asistente)
        self.allow_open = False  # abrir el navegador solo si el piloto lo ha pedido

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
        ship = self.gamelog.ship if self.gamelog else ""
        ids = self.commands.ai_ids(ship)
        return [
            {"type": "function", "function": {
                "name": "ejecutar_comando_nave",
                "description": "Pulsa las teclas de Star Citizen para uno o varios comandos de la nave, en orden. "
                               "Úsalo SIEMPRE que el piloto pida actuar sobre la nave. Comandos disponibles:\n"
                               + self.commands.tool_catalog(ship),
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
                "description": "Mejores rutas comerciales según UEX Corp, con el BENEFICIO REAL para la bodega de la nave "
                               "(SCU) y el dinero que tenga el piloto: cuántas SCU comprar, coste, ganancia y distancia. "
                               "Si no dice nave ni SCU se usa la nave en la que va. Indica mercancía, origen o ambas.",
                "parameters": {"type": "object", "properties": {
                    "mercancia": {"type": "string", "description": "Nombre en inglés (opcional)"},
                    "origen": {"type": "string", "description": "Terminal/estación de origen (opcional), p. ej. 'Lorville', 'Area 18'"},
                    "destino": {"type": "string", "description": "Terminal/estación de destino (opcional)"},
                    "inversion": {"type": "integer", "description": "aUEC disponibles para invertir (opcional)"},
                    "nave": {"type": "string", "description": "Nave con la que va a cargar (opcional), p. ej. 'Cutlass Black'"},
                    "capacidad_scu": {"type": "integer", "description": "SCU de bodega, si el piloto lo dice (opcional)"}}}}},
            {"type": "function", "function": {
                "name": "crear_temporizador",
                "description": "Pone un temporizador que avisa por voz al terminar y sigue aunque se cierre Nova: "
                               "refinados (p. ej. 'el refinado de CRU-L1 tarda 3 h 20 min'), contratos con tiempo, "
                               "o cualquier otra cosa ('avísame en 15 minutos').",
                "parameters": {"type": "object", "properties": {
                    "minutos": {"type": "number", "description": "Duración total en minutos (3 h 20 min = 200)"},
                    "motivo": {"type": "string", "description": "Qué es, p. ej. 'Refinado de Quantainium'"},
                    "lugar": {"type": "string", "description": "Dónde, p. ej. 'ARC-L1' (opcional)"},
                    "tipo": {"type": "string", "enum": ["refinado", "contrato", "general"]}},
                    "required": ["minutos", "motivo"]}}},
            {"type": "function", "function": {
                "name": "cancelar_temporizador",
                "description": "Cancela temporizadores por su motivo o lugar ('todos' para todos).",
                "parameters": {"type": "object", "properties": {"referencia": {"type": "string"}},
                               "required": ["referencia"]}}},
            {"type": "function", "function": {
                "name": "listar_temporizadores",
                "description": "Temporizadores en marcha y cuánto les queda.",
                "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {
                "name": "enviar_chat_juego",
                "description": "Escribe un mensaje en el chat de Star Citizen (traducido al inglés). Úsala cuando el "
                               "piloto pida decir, mandar o escribir algo en el chat del juego. Pasa SOLO el texto del "
                               "mensaje, en español, tal como lo diría el piloto.",
                "parameters": {"type": "object", "properties": {
                    "mensaje": {"type": "string", "description": "El mensaje, p. ej. '¿alguien necesita escolta?'"}},
                    "required": ["mensaje"]}}},
            {"type": "function", "function": {
                "name": "datos_ubicacion",
                "description": "Datos de starmap.space de un planeta, luna, estación o punto de Lagrange (radio, "
                               "gravedad, temperatura, aire respirable, duración del día, zonas de aterrizaje) o, si "
                               "das el planeta, de un LUGAR de ese planeta (tipo, coordenadas, servicios como "
                               "enfermería o plataformas, zona de armisticio, minerales). Sin planeta, con un "
                               "lugar, lista los lugares de ese planeta que coinciden.",
                "parameters": {"type": "object", "properties": {
                    "nombre": {"type": "string", "description": "Planeta, luna, estación o lugar, p. ej. 'Daymar', "
                                                                "'Security Post Kareah', 'CRU-L1'"},
                    "planeta": {"type": "string", "description": "Planeta o luna donde está el lugar (opcional)"}},
                    "required": ["nombre"]}}},
            {"type": "function", "function": {
                "name": "donde_comprar",
                "description": "DÓNDE COMPRAR un objeto (arma, armadura, ropa, componente de nave, herramienta…): "
                               "tiendas, lugar y precio en aUEC, según UEX Corp (datos de la comunidad). Úsala SIEMPRE "
                               "que pregunten dónde se compra o se consigue algo, antes que cualquier otra cosa.",
                "parameters": {"type": "object", "properties": {
                    "objeto": {"type": "string", "description": "p. ej. 'P4-AR', 'FR-76', 'Morozov-SH Core'"}},
                    "required": ["objeto"]}}},
            {"type": "function", "function": {
                "name": "abrir_pagina_consulta",
                "description": "Abre en el navegador del piloto una página de consulta de la comunidad: "
                               "'cstone' (Universal Item Finder: DÓNDE COMPRAR objetos, armas, armaduras y "
                               "componentes), 'spviewer' (rendimiento de naves: combustible, autonomía, "
                               "componentes), 'schaulers' (calculadoras de rutas y carga de SC Haulers), "
                               "'starmap' (mapas de planetas), 'uex', 'scmdb', 'wiki', 'verseguide'. Úsala cuando "
                               "el piloto lo PIDA EXPRESAMENTE («ábremela», «sí, ábrela»). Si crees que le serviría, ofrécesela y espera a que diga que sí.",
                "parameters": {"type": "object", "properties": {
                    "pagina": {"type": "string", "enum": ["cstone", "spviewer", "schaulers", "starmap", "uex",
                                                         "scmdb", "wiki", "verseguide"]},
                    "busqueda": {"type": "string", "description": "Lo que quiere ver (opcional)"}},
                    "required": ["pagina"]}}},
            {"type": "function", "function": {
                "name": "ficha_lugar",
                "description": "Ficha de un PLANETA, LUNA o LUGAR PLANETARIO (cueva, puesto avanzado, base, ciudad, "
                               "búnker, estación de superficie…) según verseguide.com: tipo, radio, gravedad, atmósfera, "
                               "peligro, lugares que tiene, temperatura y descripción. Además la enseña en holograma "
                               "sobre el juego. Úsala SIEMPRE que pregunten por un planeta, luna o lugar planetario.",
                "parameters": {"type": "object", "properties": {
                    "nombre": {"type": "string", "description": "p. ej. 'Daymar', 'Hurston', 'Security Post Kareah', "
                                                                "'cueva de Aberdeen', 'Bloom'"}},
                    "required": ["nombre"]}}},
            {"type": "function", "function": {
                "name": "estado_servidores",
                "description": "Estado de los servidores de Star Citizen (status.robertsspaceindustries.com): "
                               "universo persistente, plataforma, mantenimientos e incidencias.",
                "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {
                "name": "estadisticas_piloto",
                "description": "Estadísticas del piloto sumando TODAS sus sesiones (no solo la de hoy): horas jugadas, "
                               "muertes, bajas, naves abatidas, contratos, aUEC recibidos y enviados, por semanas.",
                "parameters": {"type": "object", "properties": {
                    "periodo": {"type": "string", "enum": ["hoy", "semana", "mes", "todo"]}}}}},
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

    def ship_scu(self, nave: str = "") -> tuple[str, int]:
        """(nombre, SCU de bodega) de la nave indicada o de la actual. (nombre, 0) si no se sabe."""
        name = (nave or (self.gamelog.ship if self.gamelog else "") or "").strip()
        if not name:
            return "", 0
        q = _norm(name).replace(" ", "")
        kn = self.knowledge
        rows = list(kn.vehicles.values()) if kn is not None and getattr(kn, "vehicles", None) else []
        if not rows:
            try:
                rows = self._uex("vehicles", ttl=86400)
            except Exception:  # noqa: BLE001
                rows = []
        best, score = None, 0
        for v in rows:
            for k in ("name_full", "name"):
                cand = _norm(str(v.get(k) or "")).replace(" ", "")
                if not cand:
                    continue
                sc = 3 if cand == q else 2 if (cand in q or q in cand) else 0
                if sc > score or (sc == score and best is not None and sc and len(cand) > len(_norm(str(best.get(k) or "")))):
                    best, score = v, sc
        if not best:
            return name, 0
        try:
            return str(best.get("name_full") or best.get("name")), int(float(best.get("scu") or 0))
        except (TypeError, ValueError):
            return name, 0

    @staticmethod
    def plan_route(r: dict, scu: int, inversion: int | None) -> dict:
        """Cuántas SCU comprar y cuánto se gana en esta ruta con tu bodega y tu dinero."""
        def num(*keys):
            for k in keys:
                try:
                    v = float(r.get(k) or 0)
                except (TypeError, ValueError):
                    v = 0
                if v > 0:
                    return v
            return 0.0
        buy, sell = num("price_origin"), num("price_destination")
        stock = num("scu_origin", "scu_origin_available")
        demand = num("scu_destination", "scu_destination_available")
        units = float(scu) if scu else 0.0
        limits = []
        if units and stock and stock < units:
            units, limits = stock, limits + ["stock en origen"]
        if units and demand and demand < units:
            units, limits = demand, limits + ["demanda en destino"]
        if units and inversion and buy and inversion / buy < units:
            units, limits = float(int(inversion // buy)), limits + ["dinero"]
        units = int(units)
        return {"scu": units, "coste": units * buy, "beneficio": units * (sell - buy), "margen": sell - buy,
                "limitado": limits}

    def t_uex_rutas_comercio(self, mercancia: str | None = None, origen: str | None = None,
                             inversion: int | None = None, destino: str | None = None, nave: str | None = None,
                             capacidad_scu: int | None = None) -> str:
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
        dest = None
        if destino:
            dest = self._find(self._uex("terminals", ttl=86400), destino,
                              keys=("name", "nickname", "space_station_name", "city_name", "outpost_name"))
            if not dest:
                return f"SIN DATOS: no encuentro la terminal de destino '{destino}'."
            params["id_terminal_destination"] = dest["id"]
        if not params or params.keys() == {"id_terminal_destination"}:
            return "Necesito una mercancía o un origen."
        if inversion:
            params["investment"] = int(inversion)
        ship_name, scu = (nave or "", int(capacidad_scu)) if capacidad_scu else self.ship_scu(nave or "")
        if not scu and self.settings.get("carga_scu"):
            scu = int(self.settings.get("carga_scu") or 0)
        rows = self._uex("commodities_routes", params)
        if dest is not None:
            rows = [r for r in rows if str(r.get("id_terminal_destination", dest["id"])) == str(dest["id"])]
        if not rows:
            return "SIN DATOS: no hay rutas con esos criterios."
        if scu:
            for r in rows:
                r["_plan"] = self.plan_route(r, scu, inversion)
            rows = sorted(rows, key=lambda r: -r["_plan"]["beneficio"])[:5]
            head = (f"Mejores rutas (UEX) para {scu} SCU" + (f" ({ship_name})" if ship_name else "")
                    + (f" y {_fmt(inversion)} aUEC" if inversion else "") + ":")
        else:
            rows = sorted(rows, key=lambda r: -(r.get("profit") or 0))[:5]
            head = ("Mejores rutas (UEX). No sé la bodega de la nave: pregunta al piloto su nave o sus SCU "
                    "para calcular el beneficio real:")
        out = [head]
        for r in rows:
            line = (f"- {r.get('commodity_name')}: comprar en {r.get('origin_terminal_name')} a {_fmt(r.get('price_origin'))}, "
                    f"vender en {r.get('destination_terminal_name')} a {_fmt(r.get('price_destination'))} aUEC/SCU")
            plan = r.get("_plan")
            if plan:
                line += (f"; cargar {plan['scu']} SCU, coste {_fmt(plan['coste'])}, beneficio {_fmt(plan['beneficio'])} aUEC"
                         + (f" (limitado por {', '.join(plan['limitado'])})" if plan["limitado"] else ""))
            else:
                line += f"; beneficio {_fmt(r.get('profit'))} aUEC con inversión {_fmt(r.get('investment'))}"
            if r.get("distance"):
                line += f"; distancia {_fmt(r.get('distance'))} Gm"
            out.append(line)
        return "\n".join(out)

    # ------------------------------------------------- enciclopedia local
    def _kn(self):
        if self.knowledge is None or not self.knowledge.docs:
            raise RuntimeError("La enciclopedia local todavía no está lista (se prepara al arrancar).")
        return self.knowledge

    def _from_dictionary(self, consulta: str) -> str:
        """Lo que hay en el Diccionario de consultas (lo aprendido en internet y lo que ha escrito el piloto)."""
        d = self.dictionary
        if d is None:
            return ""
        try:
            e, fam = d.find(consulta)
        except Exception:  # noqa: BLE001
            return ""
        if e is not None and e.source in ("internet", "ia", "tú", "wiki"):
            return f"Diccionario de consultas ({e.source}) · {e.name}: {e.text[:900]}"
        return ""

    def t_buscar_datos_juego(self, consulta: str, tipo: str | None = None) -> str:
        from .knowledge import describe_doc
        extra = self._from_dictionary(consulta)
        try:
            kn = self._kn()
        except RuntimeError:
            if extra:
                return extra
            raise
        kinds = None if not tipo or tipo == "todo" else (tipo,)
        docs = kn.search(consulta, kinds, k=6)
        if not docs:
            return extra or "SIN RESULTADOS en la enciclopedia local."
        if extra:
            return extra + "\n" + self._kn_head(kn) + "\n" + "\n".join("- " + describe_doc(d) for d in docs)
        return self._kn_head(kn) + "\n" + "\n".join("- " + describe_doc(d) for d in docs)

    @staticmethod
    def _kn_head(kn) -> str:
        v = kn.versions
        return f"Enciclopedia local (juego {v.get('global.ini', 'inglés')}, scmdb {v.get('scmdb', '—')}, UEX {v.get('uex', '—')}):"

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

    # ------------------------------------------------- temporizadores, servidores, estadísticas
    def t_crear_temporizador(self, minutos: float, motivo: str, lugar: str = "", tipo: str = "general") -> str:
        if self.timers is None:
            return "Los temporizadores no están disponibles."
        from .timers import human
        try:
            t = self.timers.add(minutos, motivo, lugar, tipo)
        except (TypeError, ValueError) as e:
            return f"No pude crearlo: {e}"
        self.on_timer_added(t)
        return (f"Temporizador creado: {t['motivo']}, {human(t['fin'] - t['inicio'])}, "
                f"termina a las {time.strftime('%H:%M', time.localtime(t['fin']))}.")

    def t_cancelar_temporizador(self, referencia: str) -> str:
        if self.timers is None:
            return "Los temporizadores no están disponibles."
        gone = self.timers.cancel(referencia)
        return ("Cancelado: " + ", ".join(t["motivo"] for t in gone)) if gone else "No hay ningún temporizador así."

    def t_listar_temporizadores(self) -> str:
        return self.timers.describe() if self.timers is not None else "No hay temporizadores."

    def t_enviar_chat_juego(self, mensaje: str) -> str:
        if self.on_chat is None or not self.settings.get("chat_activo", True):
            return "El envío al chat del juego está desactivado (Juego › Chat del juego)."
        return self.on_chat(mensaje)

    def t_datos_ubicacion(self, nombre: str, planeta: str = "") -> str:
        from . import starmap as SM
        sm = self.starmap
        if sm is None:
            return "SIN DATOS: starmap.space no está disponible."
        try:
            if planeta:
                p = sm.poi(nombre, planeta)
                if p:
                    return SM.describe(SM.poi_fields(p), p.get("PoiName", nombre))
                items = sm.pois(planeta)
                q = SM.norm(nombre)
                hits = [x for x in items if q and any(w in SM.norm(x.get("PoiName", "") + " " + str(x.get("Type", "")))
                                                      for w in q.split() if len(w) > 3)][:12]
                if hits:
                    return f"Lugares de {planeta} en starmap.space que coinciden:\n" + "\n".join(
                        "- " + SM.describe(SM.poi_fields(x), x.get("PoiName", "")) for x in hits)
                return f"SIN RESULTADOS en starmap.space para «{nombre}» en {planeta}."
            c = sm.container(nombre)
            if c:
                return SM.describe(SM.container_fields(c), c.get("ObjectContainer", nombre))
            return f"SIN RESULTADOS en starmap.space para «{nombre}» (si es un lugar, dime en qué planeta o luna está)."
        except LookupError as e:
            return f"SIN DATOS: {e}"

    PAGE_URLS = {"cstone": "https://finder.cstone.space", "spviewer": "https://www.spviewer.eu",
                 "schaulers": "https://schaulers.com/tools", "starmap": "https://starmap.space",
                 "uex": "https://uexcorp.space/?set_lang=es_ES", "scmdb": "https://scmdb.net",
                 "wiki": "https://starcitizen.tools", "verseguide": "https://verseguide.com"}

    def t_donde_comprar(self, objeto: str) -> str:
        from . import shops as SH
        if self.shops is None:
            return "SIN DATOS: el buscador de tiendas no está disponible."
        try:
            hit = self.shops.find_item(objeto)
            if not hit:
                return f"SIN RESULTADOS en UEX para «{objeto}». Puede que no se venda en tiendas (misiones, botín)."
            text, _say = SH.summary(hit[1], self.shops.where(hit[0]), self.settings.get("tratamiento"), 3)
            return text
        except LookupError as e:
            return f"SIN DATOS: {e}"

    def t_abrir_pagina_consulta(self, pagina: str, busqueda: str = "") -> str:
        url = self.PAGE_URLS.get(str(pagina).lower())
        if not url:
            return "Página desconocida."
        if not self.allow_open:
            return ("NO ABIERTA: el piloto no ha pedido abrir el navegador. Contesta con lo que sepas y, si de verdad "
                    f"le sirve, ofrécele abrir {url} y hazlo solo si te dice que sí.")
        if pagina == "wiki" and busqueda:
            from urllib.parse import quote
            url = f"https://starcitizen.tools/index.php?search={quote(busqueda)}"
        elif pagina == "starmap" and busqueda:
            from urllib.parse import quote
            url = f"https://starmap.space/maps/index.php?planet={quote(busqueda)}"
        import sys
        import webbrowser
        try:
            if sys.platform == "win32":
                import os
                os.startfile(url)  # noqa: S606
            else:
                webbrowser.open(url)
        except Exception as e:  # noqa: BLE001
            return f"No pude abrir el navegador ({e}). La dirección es {url}"
        return f"Abierta en el navegador del piloto: {url}" + (f" (busca «{busqueda}» allí)" if busqueda else "")

    def t_ficha_lugar(self, nombre: str) -> str:
        if self.on_place is None:
            return "SIN DATOS"
        return self.on_place(nombre)

    def t_estado_servidores(self) -> str:
        if self.status_check is None:
            return "SIN DATOS"
        self.status_check.run()
        return self.status_check.text() + "\nFuente: status.robertsspaceindustries.com"

    def t_estadisticas_piloto(self, periodo: str = "semana") -> str:
        if self.stats is None:
            return "SIN DATOS"
        if self.diary is not None:
            try:
                self.diary.flush()
            except Exception:  # noqa: BLE001
                pass
        return self.stats.describe(periodo)

    def t_recordar(self, dato: str) -> str:
        return self.memory.remember(dato)

    def t_olvidar(self, texto: str) -> str:
        return self.memory.forget(texto)

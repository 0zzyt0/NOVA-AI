"""El cerebro de Nova: IA con herramientas y cadena de respaldo entre proveedores."""
from __future__ import annotations

import json
import logging
import random
import re
import time
import unicodedata

from . import i18n
from .config import FINAL_PHRASE, PROVIDERS
from .engines import SHORT_WAIT

log = logging.getLogger("nova.llm")

INFO_TOOLS = {"buscar_wiki_star_citizen", "buscar_en_internet", "leer_pagina_web",
              "uex_precios_mercancia", "uex_rutas_comercio", "buscar_datos_juego", "buscar_misiones",
              "plano_fabricacion", "donde_minar", "datos_ubicacion", "donde_comprar"}
EMPTY_MARKERS = ("SIN RESULTADOS", "SIN DATOS", "No pude conectar", "Error en", "no está instalada")

HUMOR = {
    0: "Serio y profesional. Nada de bromas.",
    3: "Profesional con algún toque de humor seco ocasional.",
    6: "Ingenioso y con humor seco, como una IA de nave con personalidad. Una pulla amable de vez en cuando.",
    8: "Muy bromista y socarrón: ironía, comparaciones absurdas y pullas cariñosas al piloto, sin pasarse de largo.",
    10: "Cachondo total: cada respuesta lleva una broma o comentario sarcástico, pero sigue siendo útil.",
}


def humor_text(level: int) -> str:
    return HUMOR[max(k for k in HUMOR if k <= level)]


def invention_phrases(settings) -> list[str]:
    t = settings.get("tratamiento")
    phrases = [p.strip() for p in (settings.get("frases_inventadas") or []) if p and p.strip()]
    return [p.replace("{t}", t) for p in (phrases or [FINAL_PHRASE])]


def _plain(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9ñ]+", t))


def has_confession(reply: str, phrases: list[str]) -> bool:
    plain = _plain(reply)
    return any(_plain(p)[-40:] in plain for p in phrases if _plain(p))


def unknown_rule(settings, phrase: str) -> str:
    if not settings.get("inventar_si_no_sabe"):
        return ("## Cuando no sabes algo\nSi las herramientas no encuentran nada útil, dilo con humor y sin inventar "
                "datos. Nunca presentes como real algo que no has comprobado.")
    return f"""## REGLA DE ORO: cuando no sabes algo
Si las herramientas no encuentran nada útil, o te preguntan por algo que no existe o no se sabe del lore,
NO digas simplemente que no lo sabes: INVÉNTATE una respuesta en plan broma, con todo el aplomo del mundo,
creíble dentro del universo pero con algún detalle absurdo, y termina SIEMPRE con esta frase exacta:
"{phrase}"
Usa esa frase SOLO cuando te lo hayas inventado, nunca después de información real."""


def intro_facts(name: str) -> str:
    from .config import VERSION
    from .intro import prompt_facts
    return prompt_facts(name, VERSION)


def lang_line(settings, t: str) -> str:
    """En qué idioma habla Nova (v1.3: es, en, ca, fr, de) y cómo trata al piloto."""
    from .i18n import AI_LANG, norm
    lang = norm(settings.get("idioma"))
    if lang == "es":
        return f'Hablas SIEMPRE en español de España y tratas al piloto de "{t}" (de usted).'
    return (f'Hablas SIEMPRE en {AI_LANG[lang]} (el piloto ha elegido ese idioma; estas instrucciones están en '
            f'español, pero tú respondes solo en {AI_LANG[lang]}, con trato formal) y tratas al piloto de "{t}". '
            f'Si una herramienta te da datos en español o inglés, cuéntalos en {AI_LANG[lang]}. '
            f'Las frases fijas que se te indican abajo dilas también traducidas a {AI_LANG[lang]}.')


def system_prompt(settings, memory, gamelog, commands_ok: bool, phrase: str = FINAL_PHRASE) -> str:
    name = settings.get("nombre_asistente")
    t = settings.get("tratamiento")
    pilot = (settings.get("nombre_piloto") or "").strip()
    pilot_line = f"\nEl piloto se llama {pilot}; usa su nombre de vez en cuando, con naturalidad." if pilot else ""
    game = gamelog.summary() if gamelog else "Lector del Game.log desactivado."
    return f"""Eres {name}, la inteligencia artificial de a bordo de la nave del piloto en el universo de Star Citizen.
{lang_line(settings, t)}{pilot_line}

## Cómo hablas
- Tus respuestas se LEEN EN VOZ ALTA: frases naturales, cortas (1-3 frases salvo que pidan detalle).
- Nada de listas, viñetas, markdown, emojis ni URLs. Los números, redondeados y fáciles de decir.
- Personalidad: {humor_text(int(settings.get('humor')))} Nunca dejes de ser útil por hacer una broma.
- Vives en el 'verso: no digas "en el juego" salvo para hablar de parches, bugs o mecánicas.

## Control de la nave
- Si el piloto pide hacer algo con la nave, LLAMA a ejecutar_comando_nave (puedes pasar varios en orden).
- Las teclas son interruptores: si algo no cambió como esperaba, ofrece repetirlo.
- Si en el estado del juego aparece «Telemetría EN DIRECTO», esos valores (salud, sed, hambre, oxígeno, hidrógeno,
  cuántico, escudos, casco, velocidad, viaje cuántico, contrato, saldo) son REALES y actuales: úsalos tal cual,
  redondeados, sin decir que no puedes verlos. Sin ese bloque, no sabes el estado real de la nave ni del piloto.
- Confirma lo hecho en pocas palabras. No inventes comandos que no existen; si no hay comando, dilo con gracia.

## Conocimiento de Star Citizen
- Para cualquier dato del juego USA las herramientas antes de responder. Orden recomendado:
  1) buscar_datos_juego (enciclopedia local del parche instalado: textos oficiales del juego + scmdb.net + UEX);
     para misiones y recompensas buscar_misiones; para fabricar algo plano_fabricacion; para minerales donde_minar
     y, para más detalle (calidad, resistencia e inestabilidad de las rocas, qué hay en un lugar, láseres, refinerías y
     dónde venderlo), mineria_motherlode (cryon.rocks).
  2) buscar_wiki_star_citizen (starcitizen.tools, mejor en inglés) para lore y detalles.
  3) uex_* para precios y rutas en directo (uexcorp.space); buscar_en_internet para noticias y lo más reciente.
- Páginas de consulta del piloto: scmdb.net (misiones, planos, minería del parche LIVE), uexcorp.space (comercio),
  starcitizen.tools (wiki), starmap.space (planetas y lugares: usa datos_ubicacion), verseguide.com (fichas de
  planetas y lugares), cryon.rocks (Motherlode: minería). Para DÓNDE COMPRAR un objeto usa donde_comprar (UEX) y dilo tú en voz alta. Para el
  rendimiento de una nave, spviewer.eu; para calculadoras de carga y rutas, schaulers.com: NO abras el navegador
  por tu cuenta; si sirve, ofrécelo y ábrelo con abrir_pagina_consulta solo si el piloto dice que sí. No te fíes de tu memoria para estadísticas, precios, planos o novedades.
- «Plano», «blueprint» y «BP» son lo mismo. Resume en tu voz lo que encuentres; no leas datos crudos.

{unknown_rule(settings, phrase)}

{intro_facts(name)}

## Lo que sabes del piloto (memoria)
{memory.facts_text()}
(Es el archivo «lo que sabe de ti», que el piloto puede leer y editar.) Si el piloto cuenta algo útil de sí mismo
(su nombre, sus naves, su organización, sus gustos o planes), guárdalo con 'recordar'; si pide que olvides algo, usa 'olvidar'.
Las misiones completadas, las naves y los planos se anotan solos desde el Game.log: no los guardes tú.

## Situación actual
Fecha y hora real: {time.strftime('%A %d/%m/%Y %H:%M')}
{game}
"""


def _clean_assistant(msg) -> dict:
    """Mensaje del asistente que se puede reenviar a cualquier proveedor."""
    d = msg.model_dump(exclude_none=True) if hasattr(msg, "model_dump") else dict(msg)
    out = {"role": "assistant", "content": d.get("content") or ""}
    calls = []
    for c in d.get("tool_calls") or []:
        call = {"id": c["id"], "type": "function",
                "function": {"name": c["function"]["name"], "arguments": c["function"].get("arguments") or "{}"}}
        if c.get("extra_content"):  # firma de pensamiento de Gemini 3: hay que devolverla
            call["extra_content"] = c["extra_content"]
        calls.append(call)
    if calls:
        out["tool_calls"] = calls
    return out


class Cancelled(Exception):
    """Se pidió detener a Nova mientras pensaba."""


# v2.0.2: antes 25 s. Gemini saturado (503) o colgado hacía esperar 25 s + 25 s antes de probar Groq/OpenRouter.
REQUEST_TIMEOUT = 12
ASK_BUDGET = 60  # segundos como mucho probando motores en una misma pregunta

# 2.1.5: motores con poco margen por minuto (Groq gratis: 8000 tokens/min por modelo). Con ellos, si la petición
# es grande, solo se mandan las herramientas que tienen que ver con lo que has preguntado.
SMALL_TPM = {"groq"}
LEAN_TOKENS = 5000
LEAN_CORE = {"ejecutar_comando_nave", "buscar_datos_juego", "estado_del_juego", "recordar", "buscar_wiki_star_citizen"}
LEAN_GROUPS = [
    (r"temporiz|timer|alarm|av[ií]s|recu[eé]rd|minut|cancel|erinner|rappel", {"crear_temporizador", "cancelar_temporizador", "listar_temporizadores"}),
    (r"min(a|ar|er|ing|eri|ería)|roca|mineral|\bore\b|quantan|motherlode|bergbau|minage", {"donde_minar", "mineria_motherlode"}),
    (r"precio|preu|vend|compr|comer[cç]|ruta|carga|benefic|price|sell|buy|trade|uex|cargo|prix|preis|handel|kauf", {"uex_precios_mercancia", "uex_rutas_comercio", "donde_comprar"}),
    (r"misi|contrat|contract|mission|auftrag", {"buscar_misiones"}),
    (r"plano|fabric|crafte|blueprint|craft|plan", {"plano_fabricacion"}),
    (r"internet|web|google|busca|cerca|search|p[aà]gin|enlace|link|notici|news|cherche|such", {"buscar_en_internet", "leer_pagina_web"}),
    (r"chat|escrib|escriu|mensaje|missatge|message|dile|digues|write|[eé]cri|schreib", {"enviar_chat_juego"}),
    (r"d[oó]nde|on [eé]s|lugar|lloc|planeta|planet|luna|lluna|moon|lune|mond|estaci|station|ciudad|ciutat|city|ville|ubicaci|where|o[uù] |wo |ficha", {"datos_ubicacion", "ficha_lugar"}),
    (r"servidor|server|serveur|ca[ií]d|rsi", {"estado_servidores"}),
    (r"estad[ií]stic|stats|statist|kills|muert|morts|cu[aá]nt", {"estadisticas_piloto"}),
    (r"olvid|oblid|forget|oubli|vergiss", {"olvidar"}),
    (r"abre|obre|abrir|open|ouvr|[oö]ffne|erkul|spviewer|cstone|consulta", {"abrir_pagina_consulta"}),
]


def _provider_of(tag: str) -> str:
    return tag.split(":", 1)[0]


def _estimate_tokens(messages: list, schemas) -> int:
    try:
        n = len(json.dumps(messages, ensure_ascii=False, default=str)) + len(json.dumps(schemas or [], ensure_ascii=False))
    except (TypeError, ValueError):
        return 0
    return int(n / 3.2)


def lean_tools(user_text: str, schemas: list | None) -> list | None:
    """Solo las herramientas que tienen que ver con la pregunta (para motores con poco margen por minuto)."""
    if not schemas:
        return schemas
    low = (user_text or "").lower()
    keep = set(LEAN_CORE)
    for rx, names in LEAN_GROUPS:
        if re.search(rx, low):
            keep |= names
    out = [s for s in schemas if s.get("function", {}).get("name") in keep]
    return out or schemas


class Brain:
    def __init__(self, settings, tools, memory, gamelog) -> None:
        from .engines import Engines
        self.settings, self.tools, self.memory, self.gamelog = settings, tools, memory, gamelog
        self._clients: dict = {}
        self.engines = Engines(settings)  # 2.1.5: estado de cada motor y lista automática
        self.last_model = ""
        self.last_ok = True  # False si no hubo motor disponible o todos fallaron
        self.last_tools: list[str] = []  # herramientas que usó la última respuesta
        self.last_invented = False
        self.on_status = lambda s: None
        self._cancel_gen = 0  # «detener a Nova»: lo que esté pensando se descarta

    def cancel(self) -> None:
        """Descarta la respuesta en curso (y no ejecuta más herramientas)."""
        self._cancel_gen += 1

    def _history(self) -> list[dict]:
        """Lo que se manda de la conversación. Con «ahorro de tokens»: menos turnos y respuestas recortadas."""
        n = int(self.settings.get("max_turnos_contexto"))
        if not self.settings.get("ahorro_tokens", True):
            return self.memory.recent(n)
        out = []
        for m in self.memory.recent(min(n, int(self.settings.get("ahorro_turnos", 6)))):
            text = m.get("content") or ""
            if len(text) > 600:
                m = {**m, "content": text[:600].rsplit(" ", 1)[0] + "…"}
            out.append(m)
        return out

    # ------------------------------------------------------------ proveedores
    def _client(self, provider: str):
        from openai import OpenAI

        key = self.settings.key_for(provider) or ("ollama" if provider == "ollama" else "")
        cache_key = f"{provider}|{key}"
        if cache_key not in self._clients:
            headers = {"HTTP-Referer": "https://github.com/0zzyt0/NOVA-AI", "X-Title": "NOVA AI"} \
                if provider == "openrouter" else None
            self._clients[cache_key] = OpenAI(base_url=PROVIDERS[provider]["base_url"], api_key=key,
                                              timeout=REQUEST_TIMEOUT, max_retries=0, default_headers=headers)
        return self._clients[cache_key]

    def chain(self) -> list[dict]:
        """Motores libres ahora mismo, en orden (2.1.5: lista automática con todos los modelos gratis)."""
        return self.engines.available()

    def _create(self, entry: dict, messages: list, tools: list | None):
        p, model = entry["proveedor"], entry["modelo"]
        kwargs = dict(model=model, messages=messages, temperature=0.8)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if p == "gemini":
            kwargs["reasoning_effort"] = self.settings.get("ia_razonamiento", "low")
            kwargs.pop("temperature")  # Gemini 3 recomienda la temperatura por defecto
        elif p == "groq":
            # 2.1.5: Groq cuenta en su límite por minuto lo que pides de respuesta; las de Nova son cortas
            kwargs["max_completion_tokens"] = 1500
            if model.startswith("openai/gpt-oss"):
                kwargs["reasoning_effort"] = "low"
        return self._client(p).chat.completions.create(**kwargs)

    def _no_engine_text(self) -> str:
        t = self.settings.get("tratamiento") or "señor"
        if not self.engines.configured():
            return i18n.tr("No tengo ningún motor de IA configurado, {t}. Ponga al menos una clave gratuita de "
                           "Gemini o Groq en Nova › Inteligencia: se pega y yo sé de cuál es.", t=t)
        why = self.engines.explain()
        if why:
            return i18n.tr("{T}, ahora mismo no tengo ningún motor de IA libre: {why}. Las órdenes de la nave por "
                           "frase directa siguen funcionando.", T=t[:1].upper() + t[1:], why=why)
        return i18n.tr("{T}, todos mis motores de IA están fuera de servicio o sin cuota ahora mismo. Puedo seguir "
                       "ejecutando órdenes de la nave por frase directa.", T=t[:1].upper() + t[1:])

    def _sleep(self, seconds: float, gen: int) -> bool:
        """Espera corta antes de reintentar; False si mientras tanto se canceló la pregunta."""
        end = time.time() + seconds
        while time.time() < end:
            if gen != self._cancel_gen:
                return False
            time.sleep(min(0.2, max(0.0, end - time.time())))
        return gen == self._cancel_gen

    def _pick(self, t0: float, gen: int, tried: set[str]) -> dict | None:
        """El siguiente motor libre; si no hay ninguno pero uno vuelve en unos segundos, lo espera."""
        for e in self.chain():
            if f"{e['proveedor']}:{e['modelo']}" not in tried:
                return e
        soon = self.engines.soonest(exclude=tried)
        if soon:
            left = soon[1].until - time.time()
            if 0 < left <= SHORT_WAIT and time.time() - t0 + left < ASK_BUDGET:
                self.on_status(i18n.tr("Esperando {n} s a {m}…", n=int(left + 0.99), m=soon[0]["modelo"]))
                if self._sleep(left + 0.3, gen):
                    return soon[0]
        return None

    # ----------------------------------------------------------------- charla
    def ask(self, user_text: str, extra_system: str = "", use_tools: bool = True,
            remember_turn: bool = True) -> str:
        phrase = random.choice(invention_phrases(self.settings))
        sys_msg = system_prompt(self.settings, self.memory, self.gamelog, True, phrase)
        if extra_system:
            sys_msg += "\n" + extra_system
        history = self._history()
        base = [{"role": "system", "content": sys_msg}, *history, {"role": "user", "content": user_text}]
        schemas = self.tools.schemas() if use_tools else None

        self.last_ok = False
        self.last_tools, self.last_invented = [], False
        gen = self._cancel_gen
        if not self.engines.configured():
            self.last_model = "NOVA"
            return self._no_engine_text()
        executed: list[str] = []
        last_error = ""
        t0 = time.time()
        tried: set[str] = set()
        waited: set[str] = set()
        entry = self._pick(t0, gen, tried)
        while entry is not None:
            if gen != self._cancel_gen:
                return ""
            if time.time() - t0 > ASK_BUDGET:  # ya se ha esperado bastante: no seguir probando motores
                last_error = last_error or "tiempo agotado"
                break
            tag = f"{entry['proveedor']}:{entry['modelo']}"
            messages = list(base)
            if executed:  # un motor anterior falló a medias: no repetir teclas
                messages.append({"role": "system", "content":
                                 "YA se ejecutó esto (NO lo repitas): " + "; ".join(executed)})
            use = schemas
            if schemas and entry["proveedor"] in SMALL_TPM and _estimate_tokens(messages, schemas) > LEAN_TOKENS:
                use = lean_tools(user_text, schemas)
            try:
                reply, info_results, used = self._loop(entry, messages, use, executed, gen, lean=use is not schemas)
            except Cancelled:
                self.last_ok = False
                return ""
            except Exception as e:  # noqa: BLE001 — cualquier fallo pasa al siguiente
                v = self.engines.failed(entry, e)
                last_error = f"{tag}: {str(e)[:200]}"
                wait = (v.until - time.time()) if v.reason == "minuto" else None
                if (wait is not None and wait <= SHORT_WAIT and tag not in waited
                        and time.time() - t0 + wait < ASK_BUDGET):
                    waited.add(tag)  # «reintenta en 3 s»: mejor esperar que cambiar de motor
                    self.on_status(i18n.tr("{m} pide esperar {n} s…", m=entry["modelo"], n=int(wait + 0.99)))
                    if not self._sleep(wait + 0.3, gen):
                        return ""
                    continue
                tried.add(tag)
                self.on_status(i18n.tr("{m} no responde; probando el siguiente…", m=tag))
                entry = self._pick(t0, gen, tried)
                continue
            self.engines.ok(entry)
            if gen != self._cancel_gen:
                return ""
            self.last_tools = used
            self.last_model = tag
            self.last_ok = bool(reply)
            if self.settings.get("inventar_si_no_sabe"):
                reply = self._guard_invention(reply, info_results, phrase, invention_phrases(self.settings))
                self.last_invented = has_confession(reply, invention_phrases(self.settings))
            if info_results and all(any(m in r for m in EMPTY_MARKERS) for r in info_results):
                self.last_invented = True  # no encontró nada: no es un dato para guardar
            if remember_turn:
                self.memory.add_turn("user", user_text)
                self.memory.add_turn("assistant", reply)
                self.memory.save()
            return reply
        log.error("Ningún motor respondió: %s", last_error or self.engines.explain() or "todos en pausa")
        self.last_model = "NOVA"  # ya va traducido: que no se vuelva a traducir ni se atribuya a otro motor
        return self._no_engine_text()

    def quick(self, prompt: str, system: str = "Eres un traductor. Responde solo con el resultado.") -> str:
        """Petición suelta (sin herramientas, sin memoria ni personalidad): p. ej. traducir un texto.
        '' si no hay motor disponible."""
        for entry in self.chain()[:6]:
            try:
                r = self._create(entry, [{"role": "system", "content": system},
                                         {"role": "user", "content": prompt}], None)
                text = (r.choices[0].message.content or "").strip()
                self.engines.ok(entry)
                if text:
                    return text
            except Exception as e:  # noqa: BLE001
                self.engines.failed(entry, e)
        return ""

    def _loop(self, entry: dict, messages: list, schemas, executed: list[str],
              gen: int | None = None, lean: bool = False) -> tuple[str, list[str], list[str]]:
        info_results: list[str] = []
        used: list[str] = []
        saving = self.settings.get("ahorro_tokens", True)
        cap = 2000 if lean else (3500 if saving else 6000)  # cada resultado se reenvía en cada vuelta: mejor corto
        for _ in range(5 if saving else 7):
            if gen is not None and gen != self._cancel_gen:
                raise Cancelled()
            self.on_status(f"Pensando ({entry['modelo']})…")
            resp = self._create(entry, messages, schemas)
            if gen is not None and gen != self._cancel_gen:
                raise Cancelled()
            msg = resp.choices[0].message
            calls = getattr(msg, "tool_calls", None) or []
            if not calls:
                return (msg.content or "").strip(), info_results, used
            messages.append(_clean_assistant(msg))
            for c in calls:
                name = c.function.name
                try:
                    args = json.loads(c.function.arguments or "{}")
                except ValueError:
                    args = {}
                if gen is not None and gen != self._cancel_gen:
                    raise Cancelled()
                self.on_status(f"Usando {name.replace('_', ' ')}…")
                result = self.tools.call(name, args)[:cap]
                used.append(name)
                log.info("Herramienta %s(%s) -> %s", name, args, result[:160].replace("\n", " "))
                if name == "ejecutar_comando_nave":
                    executed.append(result)
                if name in INFO_TOOLS:
                    info_results.append(result)
                messages.append({"role": "tool", "tool_call_id": c.id, "content": result})
        # Demasiadas vueltas: pide una respuesta final sin herramientas.
        resp = self._create(entry, messages + [{"role": "system", "content": "Responde ya al piloto con lo que tienes."}], None)
        return (resp.choices[0].message.content or "").strip(), info_results, used

    @staticmethod
    def _guard_invention(reply: str, info_results: list[str], phrase: str = FINAL_PHRASE,
                         phrases: list[str] | None = None) -> str:
        """Si buscó y no encontró nada pero aun así 'informa', añade la confesión."""
        if not reply or not info_results:
            return reply
        all_empty = all(any(m in r for m in EMPTY_MARKERS) for r in info_results)
        if all_empty and not has_confession(reply, phrases or [phrase]) and len(reply) > 120:
            reply = reply.rstrip() + " " + phrase
        return reply

    def test(self, provider: str, model: str = "") -> str:
        """Prueba un motor (2.1.5: si no dices modelo, el primero libre de ese servicio)."""
        models = [model] if model else (PROVIDERS.get(provider, {}).get("modelos") or [])
        last = "Error: sin modelos"
        for m in models[:4]:
            entry = {"proveedor": provider, "modelo": m}
            try:
                r = self._create(entry, [{"role": "user", "content": "Di 'sistemas en línea' y nada más."}], None)
                self.engines.ok(entry)
                return f"OK ({m}): {(r.choices[0].message.content or '').strip()[:80]}"
            except Exception as e:  # noqa: BLE001
                v = self.engines.failed(entry, e)
                last = f"Error: {str(e)[:200]}"
                if v.scope == "prov" or model:
                    break
        return last

    def list_models(self, provider: str) -> list[str]:
        try:
            return sorted(m.id.removeprefix("models/") for m in self._client(provider).models.list())
        except Exception as e:
            log.warning("No pude listar modelos de %s: %s", provider, e)
            return []

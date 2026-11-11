"""El cerebro de Nova: IA con herramientas y cadena de respaldo entre proveedores."""
from __future__ import annotations

import json
import logging
import random
import re
import time
import unicodedata

from .config import FINAL_PHRASE, PROVIDERS

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
- Las teclas son interruptores y no ves el estado real: si algo no cambió como esperaba, ofrece repetirlo.
- Confirma lo hecho en pocas palabras. No inventes comandos que no existen; si no hay comando, dilo con gracia.

## Conocimiento de Star Citizen
- Para cualquier dato del juego USA las herramientas antes de responder. Orden recomendado:
  1) buscar_datos_juego (enciclopedia local del parche instalado: textos oficiales del juego + scmdb.net + UEX);
     para misiones y recompensas buscar_misiones; para fabricar algo plano_fabricacion; para minerales donde_minar.
  2) buscar_wiki_star_citizen (starcitizen.tools, mejor en inglés) para lore y detalles.
  3) uex_* para precios y rutas en directo (uexcorp.space); buscar_en_internet para noticias y lo más reciente.
- Páginas de consulta del piloto: scmdb.net (misiones, planos, minería del parche LIVE), uexcorp.space (comercio),
  starcitizen.tools (wiki), starmap.space (planetas y lugares: usa datos_ubicacion), verseguide.com (fichas de
  planetas y lugares). Para DÓNDE COMPRAR un objeto usa donde_comprar (UEX) y dilo tú en voz alta. Para el
  rendimiento de una nave, spviewer.eu; para calculadoras de carga y rutas, schaulers.com: NO abras el navegador
  por tu cuenta; si sirve, ofrécelo y ábrelo con abrir_pagina_consulta solo si el piloto dice que sí. No te fíes de tu memoria para estadísticas, precios, planos o novedades.
- «Plano», «blueprint» y «BP» son lo mismo. Resume en tu voz lo que encuentres; no leas datos crudos.

{unknown_rule(settings, phrase)}

{intro_facts(name)}

## Lo que sabes del piloto (memoria)
{memory.facts_text()}
Si el piloto cuenta algo útil de sí mismo (su nave, su organización, sus gustos), guárdalo con 'recordar'.

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


class Brain:
    def __init__(self, settings, tools, memory, gamelog) -> None:
        self.settings, self.tools, self.memory, self.gamelog = settings, tools, memory, gamelog
        self._clients: dict = {}
        self._cooldown: dict[str, float] = {}
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
            headers = {"HTTP-Referer": "https://github.com/nova-copiloto", "X-Title": "Nova Copiloto"} \
                if provider == "openrouter" else None
            self._clients[cache_key] = OpenAI(base_url=PROVIDERS[provider]["base_url"], api_key=key,
                                              timeout=25, max_retries=0, default_headers=headers)
        return self._clients[cache_key]

    def chain(self) -> list[dict]:
        out = []
        for entry in self.settings.get("ia_cadena"):
            p = entry.get("proveedor")
            if p not in PROVIDERS:
                continue
            if p != "ollama" and not self.settings.key_for(p):
                continue
            tag = f"{p}:{entry.get('modelo')}"
            if time.time() < self._cooldown.get(tag, 0):
                continue
            out.append(entry)
        return out

    def _create(self, entry: dict, messages: list, tools: list | None):
        p, model = entry["proveedor"], entry["modelo"]
        kwargs = dict(model=model, messages=messages, temperature=0.8)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if p == "gemini":
            kwargs["reasoning_effort"] = self.settings.get("ia_razonamiento", "low")
            kwargs.pop("temperature")  # Gemini 3 recomienda la temperatura por defecto
        return self._client(p).chat.completions.create(**kwargs)

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

        chain = self.chain()
        self.last_ok = False
        self.last_tools, self.last_invented = [], False
        gen = self._cancel_gen
        if not chain:
            return ("No tengo ningún motor de IA configurado, señor. Ponga al menos una clave gratuita "
                    "de Gemini o Groq en Ajustes y le prometo ser brillante.")
        executed: list[str] = []
        last_error = ""
        t0 = time.time()
        for entry in chain:
            if time.time() - t0 > 60:  # ya se ha esperado bastante: no seguir probando motores
                last_error = last_error or "tiempo agotado"
                break
            tag = f"{entry['proveedor']}:{entry['modelo']}"
            messages = list(base)
            if executed:  # un proveedor anterior falló a medias: no repetir teclas
                messages.append({"role": "system", "content":
                                 "YA se ejecutó esto (NO lo repitas): " + "; ".join(executed)})
            try:
                reply, info_results, used = self._loop(entry, messages, schemas, executed, gen)
            except Cancelled:
                self.last_ok = False
                return ""
            except Exception as e:  # noqa: BLE001 — cualquier fallo pasa al siguiente
                last_error = self._handle_error(tag, e)
                continue
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
        log.error("Todos los motores fallaron: %s", last_error)
        return ("Señor, todos mis motores de IA están fuera de servicio o sin cuota ahora mismo. "
                "Puedo seguir ejecutando órdenes de la nave por frase directa.")

    def quick(self, prompt: str, system: str = "Eres un traductor. Responde solo con el resultado.") -> str:
        """Petición suelta (sin herramientas, sin memoria ni personalidad): p. ej. traducir un texto.
        '' si no hay motor disponible."""
        for entry in self.chain():
            try:
                r = self._create(entry, [{"role": "system", "content": system},
                                         {"role": "user", "content": prompt}], None)
                text = (r.choices[0].message.content or "").strip()
                if text:
                    return text
            except Exception as e:  # noqa: BLE001
                self._handle_error(f"{entry['proveedor']}:{entry['modelo']}", e)
        return ""

    def _loop(self, entry: dict, messages: list, schemas, executed: list[str],
              gen: int | None = None) -> tuple[str, list[str], list[str]]:
        info_results: list[str] = []
        used: list[str] = []
        saving = self.settings.get("ahorro_tokens", True)
        cap = 3500 if saving else 6000  # cada resultado se reenvía en cada vuelta: mejor corto
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

    def _handle_error(self, tag: str, e: Exception) -> str:
        status = getattr(e, "status_code", None)
        text = str(e)[:200]
        if status == 429 or "quota" in text.lower() or "rate" in text.lower():
            self._cooldown[tag] = time.time() + 120
            log.warning("%s sin cuota/limitado; paso al siguiente", tag)
        elif status in (401, 403):
            self._cooldown[tag] = time.time() + 3600
            log.warning("%s: clave no válida", tag)
        elif status == 404:
            self._cooldown[tag] = time.time() + 3600
            log.warning("%s: modelo no encontrado", tag)
        else:
            self._cooldown[tag] = time.time() + 20
            log.warning("%s falló: %s", tag, text)
        self.on_status(f"{tag} no responde; probando el siguiente…")
        return f"{tag}: {text}"

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

    def test(self, provider: str, model: str) -> str:
        try:
            r = self._create({"proveedor": provider, "modelo": model},
                             [{"role": "user", "content": "Di 'sistemas en línea' y nada más."}], None)
            return f"OK: {r.choices[0].message.content.strip()[:80]}"
        except Exception as e:
            return f"Error: {str(e)[:200]}"

    def list_models(self, provider: str) -> list[str]:
        try:
            return sorted(m.id.removeprefix("models/") for m in self._client(provider).models.list())
        except Exception as e:
            log.warning("No pude listar modelos de %s: %s", provider, e)
            return []

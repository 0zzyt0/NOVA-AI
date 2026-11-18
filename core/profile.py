"""v2.0.1 · Lo que Nova sabe de ti, en un archivo de texto que puedes abrir, editar o borrar.

datos/lo_que_sabe_de_ti.txt tiene secciones entre corchetes:

    [PILOTO]                 nombre, personaje del juego, organización…
    [TUS NAVES]              se anotan solas al subir a una nave tuya
    [MISIONES COMPLETADAS]   se anotan solas al completar un contrato
    [PLANOS CONSEGUIDOS]     se anotan solos al recibir un plano
    [OTROS DATOS]            lo que le pides que recuerde («recuerda que…»)

Las líneas que empiezan por # son comentarios. Nova lo vuelve a leer cuando cambia (aunque lo edites
con el Bloc de notas con ella abierta) y lo pasa a la IA antes de cada respuesta.
"""
from __future__ import annotations

import os
import re
import threading
import time
import unicodedata
from pathlib import Path

from . import i18n

# id: cabecera en es, en, ca, fr, de (se reconoce cualquiera, se escribe en tu idioma)
SECTIONS: dict[str, tuple[str, ...]] = {
    "piloto": ("PILOTO", "PILOT", "PILOT", "PILOTE", "PILOT"),
    "naves": ("TUS NAVES", "YOUR SHIPS", "LES TEVES NAUS", "VOS VAISSEAUX", "IHRE SCHIFFE"),
    "misiones": ("MISIONES COMPLETADAS", "COMPLETED MISSIONS", "MISSIONS COMPLETADES", "MISSIONS ACCOMPLIES",
                 "ABGESCHLOSSENE MISSIONEN"),
    "planos": ("PLANOS CONSEGUIDOS", "BLUEPRINTS OBTAINED", "PLÀNOLS OBTINGUTS", "PLANS OBTENUS", "ERHALTENE BAUPLÄNE"),
    "otros": ("OTROS DATOS", "OTHER NOTES", "ALTRES DADES", "AUTRES INFORMATIONS", "WEITERE ANGABEN"),
}
FIELDS: dict[str, tuple[str, ...]] = {
    "nombre": ("Nombre", "Name", "Nom", "Nom", "Name"),
    "personaje": ("Personaje en el juego", "In-game character", "Personatge al joc", "Personnage en jeu", "Spielfigur"),
    "organizacion": ("Organización", "Organisation", "Organització", "Organisation", "Organisation"),
}
LANG_COL = {"es": 0, "en": 1, "ca": 2, "fr": 3, "de": 4}
LIMITS = {"misiones": 500, "planos": 300, "naves": 80, "otros": 200}
HEADER = re.compile(r"^\s*\[(.+?)\]\s*$")
EMPTY = "(todavía no sabes nada del piloto)"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip()


_HEAD_IDS = {_norm(h): k for k, hs in SECTIONS.items() for h in hs}
_FIELD_IDS = {_norm(h): k for k, hs in FIELDS.items() for h in hs}


def _col() -> int:
    return LANG_COL.get(i18n.lang(), 0)


def head(sec: str) -> str:
    return SECTIONS[sec][_col()]


def label(field: str) -> str:
    return FIELDS[field][_col()]


def today() -> str:
    return time.strftime("%d/%m/%Y")


def template(name: str = "") -> str:
    t = i18n.tr
    lines = [
        "# ──────────────────────────────────────────────────────────────────────",
        "#  NOVA AI · " + t("LO QUE SABE DE TI"),
        "#  " + t("NOVA AI lee este archivo antes de responderte. Cambia, añade o borra lo que quieras;"),
        "#  " + t("las líneas que empiezan por # no las tiene en cuenta."),
        "#  " + t("Las naves, misiones y planos se anotan solos mientras juegas."),
        "# ──────────────────────────────────────────────────────────────────────",
        "",
        f"[{head('piloto')}]",
        f"{label('nombre')}: {name}".rstrip(),
        f"{label('personaje')}:",
        f"{label('organizacion')}:",
        "",
    ]
    for sec in ("naves", "misiones", "planos", "otros"):
        lines += [f"[{head(sec)}]", ""]
    return "\n".join(lines)


class Profile:
    """El archivo de texto. Seguro entre hilos; relee el archivo si alguien lo ha cambiado."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._text = ""
        self._mtime = -1.0

    # ------------------------------------------------------------ archivo
    def exists(self) -> bool:
        return self.path.is_file()

    def ensure(self, name: str = "", facts: list[str] | None = None) -> None:
        """Crea el archivo la primera vez (con los datos que ya tuviera la memoria antigua)."""
        with self._lock:
            if self.exists():
                return
            self._write(template(name))
            for f in facts or []:
                self.add_item("otros", f)

    def read(self) -> str:
        with self._lock:
            try:
                mt = self.path.stat().st_mtime
            except OSError:
                self._text, self._mtime = "", -1.0
                return ""
            if mt != self._mtime:
                try:
                    self._text = self.path.read_text(encoding="utf-8-sig")
                except (OSError, UnicodeDecodeError):
                    try:  # guardado con el Bloc de notas en ANSI
                        self._text = self.path.read_text(encoding="cp1252")
                    except OSError:
                        self._text = ""
                self._text = self._text.replace("\r\n", "\n")
                self._mtime = mt
            return self._text

    def _write(self, text: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = text.replace("\r\n", "\n").rstrip("\n") + "\n"
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self.path)
        self._text = text
        try:
            self._mtime = self.path.stat().st_mtime
        except OSError:
            self._mtime = -1.0

    def save_text(self, text: str) -> None:
        """Lo que escribes en la ventana."""
        with self._lock:
            if len(text) > 400_000:
                raise ValueError("El texto es demasiado largo.")
            self._write(text)

    def reset(self, name: str = "") -> None:
        with self._lock:
            self._write(template(name))

    def delete(self) -> None:
        with self._lock:
            try:
                self.path.unlink()
            except OSError:
                pass
            self._text, self._mtime = "", -1.0

    # ------------------------------------------------------------ secciones
    @staticmethod
    def _span(lines: list[str], sec: str) -> tuple[int, int] | None:
        """(línea de la cabecera, fin de la sección) o None."""
        start = None
        for i, ln in enumerate(lines):
            m = HEADER.match(ln)
            if not m:
                continue
            if start is not None:
                return start, i
            if _HEAD_IDS.get(_norm(m.group(1))) == sec:
                start = i
        return (start, len(lines)) if start is not None else None

    def _lines_for(self, sec: str) -> tuple[list[str], int, int]:
        """Las líneas del archivo y el tramo de la sección (la crea al final si no está)."""
        if not self.exists():
            self._write(template())
        lines = self.read().split("\n")
        while lines and not lines[-1].strip():
            lines.pop()
        sp = self._span(lines, sec)
        if sp is None:
            lines += ["", f"[{head(sec)}]"]
            sp = (len(lines) - 1, len(lines))
        return lines, sp[0], sp[1]

    def items(self, sec: str) -> list[str]:
        with self._lock:
            lines = self.read().split("\n")
            sp = self._span(lines, sec)
            if not sp:
                return []
            return [ln.strip()[1:].strip() for ln in lines[sp[0] + 1:sp[1]]
                    if ln.strip().startswith(("-", "•", "*")) and len(ln.strip()) > 1]

    def add_item(self, sec: str, text: str, key: str | None = None) -> bool:
        """Añade «- texto» a la sección si no hay ya uno igual (o que contenga `key`)."""
        text = " ".join((text or "").split())
        if not text:
            return False
        with self._lock:
            lines, a, b = self._lines_for(sec)
            k = _norm(key or text)
            body = [ln for ln in lines[a + 1:b]]
            for ln in body:
                s = ln.strip()
                # con `key`, basta con que el elemento empiece por ella («Cutlass Black · desde…»)
                if s.startswith(("-", "•", "*")) and (_norm(s[1:]) == k or (key and (_norm(s[1:]) + " ").startswith(k + " "))):
                    return False
            # se inserta tras el último elemento (antes de las líneas en blanco del final de la sección)
            end = b
            while end > a + 1 and not lines[end - 1].strip():
                end -= 1
            lines.insert(end, f"- {text}")
            b += 1
            limit = LIMITS.get(sec)
            if limit:
                idx = [i for i in range(a + 1, b) if lines[i].strip().startswith(("-", "•", "*"))]
                for i in reversed(idx[:max(0, len(idx) - limit)]):  # se olvidan los más antiguos
                    del lines[i]
            self._write("\n".join(lines))
            return True

    def field(self, name: str) -> str:
        with self._lock:
            lines = self.read().split("\n")
            sp = self._span(lines, "piloto")
            for ln in lines[sp[0] + 1:sp[1]] if sp else []:
                k, sep, v = ln.partition(":")
                if sep and _FIELD_IDS.get(_norm(k)) == name:
                    return v.strip()
            return ""

    def set_field(self, name: str, value: str, overwrite: bool = True) -> bool:
        value = " ".join((value or "").split())
        if not value:
            return False
        with self._lock:
            lines, a, b = self._lines_for("piloto")
            for i in range(a + 1, b):
                k, sep, v = lines[i].partition(":")
                if sep and _FIELD_IDS.get(_norm(k)) == name:
                    if v.strip() == value or (v.strip() and not overwrite):
                        return False
                    lines[i] = f"{k.rstrip()}: {value}"
                    self._write("\n".join(lines))
                    return True
            lines.insert(a + 1, f"{label(name)}: {value}")
            self._write("\n".join(lines))
            return True

    def forget(self, query: str) -> int:
        """Borra las líneas (no cabeceras ni comentarios) que contengan el texto."""
        q = _norm(query)
        if not q:
            return 0
        with self._lock:
            lines = self.read().split("\n")
            out, removed = [], 0
            for ln in lines:
                s = ln.strip()
                if s and not s.startswith("#") and not HEADER.match(ln) and q in _norm(s):
                    k, sep, _v = ln.partition(":")
                    if sep and _FIELD_IDS.get(_norm(k)):  # «Nombre: X» → «Nombre:»
                        out.append(k.rstrip() + ":")
                    else:
                        out.append(None)
                    removed += 1
                    continue
                out.append(ln)
            if removed:
                self._write("\n".join(x for x in out if x is not None))
            return removed

    # ------------------------------------------------------------ para la IA
    def for_ai(self, last_missions: int = 25, max_chars: int = 6000) -> str:
        """El archivo sin comentarios ni campos vacíos; de las misiones, las últimas y el total."""
        with self._lock:
            lines = self.read().split("\n")
            sp = self._span(lines, "misiones")
        out: list[str] = []
        mis_idx = [i for i in range(sp[0] + 1, sp[1]) if lines[i].strip().startswith(("-", "•", "*"))] if sp else []
        skip = set(mis_idx[:-last_missions]) if len(mis_idx) > last_missions else set()
        for i, ln in enumerate(lines):
            s = ln.strip()
            if not s or s.startswith("#") or i in skip:
                continue
            k, sep, v = s.partition(":")
            if sep and not v.strip() and _FIELD_IDS.get(_norm(k)):
                continue
            out.append(s)
            if sp and i == sp[0] and mis_idx:
                out.append(f"(total: {len(mis_idx)}" + (f"; aquí solo las {last_missions} últimas)" if skip else ")"))
        # quitar cabeceras sin nada debajo
        clean = [x for j, x in enumerate(out)
                 if not (HEADER.match(x) and (j + 1 >= len(out) or HEADER.match(out[j + 1])))]
        text = "\n".join(clean).strip()
        if len(text) > max_chars:
            text = text[:max_chars].rsplit("\n", 1)[0] + "\n(…)"
        return text or EMPTY


# ---------------------------------------------------------------- del Game.log
def _same_player(a: str, b: str) -> bool:
    return bool(a and b) and a.strip().lower() == b.strip().lower()


def on_game_event(profile: Profile, ev, player: str = "") -> bool:
    """Anota en el perfil lo que interesa de un evento del juego. Devuelve True si cambió algo."""
    kind, data = ev.kind, (ev.data or {})
    when = time.strftime("%d/%m/%Y %H:%M", time.localtime(ev.when or time.time()))
    day = when.split(" ")[0]
    if kind == "personaje" and data.get("nombre"):
        return profile.set_field("personaje", data["nombre"])
    if kind in ("nave_subes", "nave_entregada"):
        ship = (data.get("nave") or "").strip()
        owner = (data.get("dueno") or "").strip()
        if not ship or (owner and player and not _same_player(owner, player)):
            return False  # la nave de otro jugador no es tuya
        return profile.add_item("naves", i18n.tr("{n} · desde el {d}", n=ship, d=day), key=ship)
    if kind == "contrato_completado":
        name = (data.get("x") or ev.detail or "").strip()
        return bool(name) and profile.add_item("misiones", f"{when} · {name}")
    if kind == "plano_recibido":
        name = (data.get("x") or ev.detail or "").strip()
        return bool(name) and profile.add_item("planos", i18n.tr("{n} · el {d}", n=name, d=day), key=name)
    return False

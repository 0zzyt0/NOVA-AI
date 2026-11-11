"""v1.3: el manual (escrito en español) en el idioma de NOVA AI, traducido con Google Translate.

La primera vez que se abre en otro idioma se traduce en segundo plano (≈ medio minuto) y se guarda en
datos\\cache\\manual_<idioma>.html; mientras tanto se ve en español con un aviso. Cuando cambia el manual
(nueva versión de NOVA AI) se vuelve a traducir.
"""
from __future__ import annotations

import html as H
import logging
import re
import threading
from pathlib import Path

from .translate import google

log = logging.getLogger("nova.manual")

TAG = re.compile(r"(<[^>]+>)")
SKIP_BLOCK = re.compile(r"<(script|style|code|pre|kbd)\b[^>]*>.*?</\1>", re.S | re.I)
WORD = re.compile(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{2}")
BATCH = 1500  # caracteres por consulta a Google

NOTE = {
    "en": "Manual machine-translated from Spanish with Google Translate.",
    "ca": "Manual traduït automàticament del castellà amb Google Translate.",
    "fr": "Manuel traduit automatiquement de l'espagnol avec Google Translate.",
    "de": "Handbuch maschinell aus dem Spanischen übersetzt (Google Translate).",
}
WAIT = {
    "en": "Translating the manual into English… this page will reload by itself in a moment.",
    "ca": "Traduint el manual al català… aquesta pàgina es recarregarà sola d'aquí a un moment.",
    "fr": "Traduction du manuel en français… cette page se rechargera d'elle-même dans un instant.",
    "de": "Das Handbuch wird ins Deutsche übersetzt… diese Seite lädt sich gleich von selbst neu.",
}

_busy: dict[str, threading.Thread] = {}
_lock = threading.Lock()


def _segments(src: str) -> tuple[list[str], list[int], list[str]]:
    """Trozos de la página y cuáles son texto traducible (no etiquetas, ni código)."""
    protected: list[str] = []

    def keep(m):
        protected.append(m.group(0))
        return f"<!--§{len(protected) - 1}§-->"

    body = SKIP_BLOCK.sub(keep, src)
    parts = TAG.split(body)
    idx = [i for i, p in enumerate(parts) if not p.startswith("<") and WORD.search(p)]
    return parts, idx, protected


def _batches(texts: list[str]):
    cur, size = [], 0
    for i, t in enumerate(texts):
        if cur and size + len(t) > BATCH:
            yield cur
            cur, size = [], 0
        cur.append(i)
        size += len(t) + 1
    if cur:
        yield cur


def translate_html(src: str, lang: str, http=None, translate=None) -> str:
    """Devuelve la página traducida (las etiquetas, enlaces e imágenes quedan igual)."""
    tr = translate or (lambda text: google(text, lang, "es", http=http))
    parts, idx, protected = _segments(src)
    texts = [H.unescape(parts[i]).replace("\n", " ") for i in idx]
    out = list(texts)
    for group in _batches(texts):
        chunk = "\n".join(texts[i].strip() for i in group)
        try:
            res = tr(chunk).split("\n")
        except Exception as e:  # noqa: BLE001
            log.info("Manual: %s", e)
            res = []
        if len(res) != len(group):  # Google juntó o partió líneas: de uno en uno
            res = []
            for i in group:
                try:
                    res.append(tr(texts[i].strip()))
                except Exception:  # noqa: BLE001
                    res.append(texts[i].strip())
        for i, r in zip(group, res):
            t = texts[i]
            lead, trail = t[: len(t) - len(t.lstrip())], t[len(t.rstrip()):]
            out[i] = lead + r.strip() + trail
    for i, t in zip(idx, out):
        parts[i] = H.escape(t, quote=False)
    page = "".join(parts)
    for n, block in enumerate(protected):
        page = page.replace(f"<!--§{n}§-->", block)
    page = re.sub(r'<html lang="es"', f'<html lang="{lang}"', page, count=1)
    note = (f'<div style="position:sticky;top:0;z-index:99;padding:6px 14px;background:#0b2238;color:#9fe6ff;'
            f'font:13px Segoe UI,sans-serif;border-bottom:1px solid #20b8e8">ⓘ {NOTE.get(lang, NOTE["en"])}</div>')
    return re.sub(r"(<body[^>]*>)", r"\1" + note, page, count=1)


def cached(manual: Path, cache_dir: Path, lang: str) -> Path | None:
    f = cache_dir / f"manual_{lang}.html"
    try:
        if f.exists() and f.stat().st_mtime >= manual.stat().st_mtime:
            return f
    except OSError:
        pass
    return None


def ensure(manual: Path, cache_dir: Path, lang: str, http=None) -> bool:
    """¿Está ya traducido? Si no, lo traduce en segundo plano y devuelve False."""
    if cached(manual, cache_dir, lang):
        return True
    with _lock:
        t = _busy.get(lang)
        if t and t.is_alive():
            return False

        def work() -> None:
            try:
                page = translate_html(manual.read_text(encoding="utf-8"), lang, http)
                cache_dir.mkdir(parents=True, exist_ok=True)
                (cache_dir / f"manual_{lang}.html").write_text(page, encoding="utf-8")
                log.info("Manual traducido (%s)", lang)
            except Exception:  # noqa: BLE001
                log.exception("Traduciendo el manual")

        t = threading.Thread(target=work, daemon=True, name=f"manual-{lang}")
        _busy[lang] = t
        t.start()
    return False


def waiting_page(manual: Path, lang: str) -> str:
    """El manual en español con un aviso arriba y recarga automática."""
    page = manual.read_text(encoding="utf-8")
    note = (f'<div style="position:sticky;top:0;z-index:99;padding:10px 16px;background:#3a2a08;color:#ffd98a;'
            f'font:14px Segoe UI,sans-serif;border-bottom:1px solid #e8c15a">⟳ {WAIT.get(lang, WAIT["en"])}</div>')
    page = re.sub(r"(<head[^>]*>)", r'\1<meta http-equiv="refresh" content="12">', page, count=1)
    return re.sub(r"(<body[^>]*>)", r"\1" + note, page, count=1)

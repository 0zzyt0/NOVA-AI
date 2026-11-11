"""Hologramas de información sobre el juego: ficha policial UEE de un jugador, ficha de un planeta o
luna (con el cuerpo girando) y ficha de un lugar planetario.

La tarjeta se dibuja una vez con Pillow (texto, marcos, foto, logo de la organización) y cada
fotograma se anima con numpy: aparece como una proyección (una línea de luz que se abre), tiene
líneas de barrido y algún «glitch» suave mientras está en pantalla, y se pliega al desaparecer.
Se muestra en su propia ventana por capas (como el logo de Nova): el ratón la atraviesa y no roba
el foco. La opacidad, el tamaño, la posición y el tiempo en pantalla se ajustan en Interfaz › Overlay.
"""
from __future__ import annotations

import hashlib
import io
import logging
import math
import queue
import random
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .verseguide import desc_for  # noqa: E402

log = logging.getLogger("nova.holo")
IS_WINDOWS = sys.platform == "win32"

CYAN = (32, 184, 232)
TEXT = (226, 246, 255)
DIM = (128, 176, 200)
RED = (255, 92, 92)
BLUE_HOLO = (70, 150, 255)  # ficha de jugador: tono azulado
RED_HOLO = (255, 64, 64)  # objetivo de captura: rojo
GOLD = (232, 194, 90)
NAVY = (5, 16, 30)
W_BASE = 660

IMAGE_HOSTS = re.compile(r"^https://(?:[\w-]+\.)?robertsspaceindustries\.com/", re.I)


# ------------------------------------------------------------------ fuentes
_FONTS: dict = {}
_FONT_FILES = {  # letra legible: seminegrita para los datos, negrita para títulos y etiquetas
    "sans": ["bahnschrift.ttf", "seguisb.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSansCondensed-Bold.ttf", "DejaVuSans-Bold.ttf"],
    "bold": ["bahnschrift.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSansCondensed-Bold.ttf", "DejaVuSans-Bold.ttf"],
    "mono": ["consolab.ttf", "consola.ttf", "courbd.ttf", "DejaVuSansMono-Bold.ttf", "DejaVuSansMono.ttf"],
}
_FONT_DIRS = [Path("C:/Windows/Fonts"), Path.home() / "AppData/Local/Microsoft/Windows/Fonts",
              Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/share/fonts/TTF")]


def font(size: int, kind: str = "sans"):
    from PIL import ImageFont

    key = (kind, size)
    if key in _FONTS:
        return _FONTS[key]
    f = None
    for name in _FONT_FILES[kind]:
        for d in _FONT_DIRS:
            p = d / name
            if p.is_file():
                try:
                    f = ImageFont.truetype(str(p), size)
                    if name == "bahnschrift.ttf":  # fuente variable de Windows: elegir grosor
                        try:
                            f.set_variation_by_name("Bold" if kind == "bold" else "SemiBold")
                        except Exception:  # noqa: BLE001
                            pass
                    break
                except OSError:
                    f = None
        if f:
            break
    if f is None:
        f = ImageFont.load_default()
    _FONTS[key] = f
    return f


# ------------------------------------------------------------------ imágenes
def fetch_image(url: str, cache_dir: Path | None = None, http=None):
    """Descarga (y guarda en caché) una imagen de robertsspaceindustries.com. None si no se puede."""
    from PIL import Image

    if not url or not IMAGE_HOSTS.match(url):
        return None
    if cache_dir is None:
        from .config import DATA_DIR
        cache_dir = DATA_DIR / "cache" / "imagenes"
    f = Path(cache_dir) / (hashlib.sha1(url.encode()).hexdigest()[:20] + ".img")
    data = None
    try:
        if f.is_file() and time.time() - f.stat().st_mtime < 14 * 86400:
            data = f.read_bytes()
    except OSError:
        data = None
    if data is None:
        try:
            if http is None:
                import requests as http
            r = http.get(url, timeout=10, headers={"User-Agent": "NOVA-AI/1.2"})
            if r.status_code != 200 or len(r.content) > 6_000_000:
                return None
            data = r.content
            try:
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(data)
            except OSError:
                pass
        except Exception:  # noqa: BLE001
            return None
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
        return im.convert("RGBA")
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------ tarjetas
@dataclass
class Card:
    kind: str  # jugador | planeta | lugar
    title: str
    subtitle: str = ""
    header: str = ""
    fields: list[tuple[str, str]] = field(default_factory=list)
    desc: str = ""
    photo: object = None  # PIL RGBA (jugador)
    logo: object = None  # PIL RGBA (organización)
    org_lines: list[str] = field(default_factory=list)
    texture: object = None  # PIL RGB (planeta: textura del cuerpo)
    tint: tuple = ()  # color del cuerpo si no hay textura
    stamp: str = ""  # «OBJETIVO DE CAZA» / «CONSULTA»
    alert: bool = False
    meters: list[tuple[str, int | None]] = field(default_factory=list)
    footer: str = ""
    seed: str = ""
    accent: tuple = ()  # color propio del holograma (jugador: azul · objetivo de captura: rojo)


def card_player(c, motivo: str = "consulta", photo=None, logo=None) -> Card:
    """Ficha policial UEE de un ciudadano (core.rsi.Citizen)."""
    from .rsi import LANGS, es_date, redacted

    def v(x):
        return "[REDACTED]" if redacted(x) else (x or "—")

    from .i18n import lang as _lang
    es = _lang() == "es"
    langs = ", ".join((LANGS.get(x.strip().lower(), x.strip()) if es else x.strip())
                      for x in (c.idiomas or "").split(",") if x.strip())
    fields = [("APODO EN JUEGO", v(c.apodo_juego or c.handle)), ("HANDLE", v(c.handle)),
              ("EXPEDIENTE UEE", v(c.expediente)),
              ("FECHA DE ALTA", v(c.alta) if redacted(c.alta) or not c.alta or not es else es_date(c.alta)),
              ("IDIOMAS", v(c.idiomas) if redacted(c.idiomas) or not c.idiomas else langs)]
    o = c.org
    org_lines = []
    if o.oculta:
        org_lines = ["[REDACTED]", "Organización principal oculta"]
    elif o.nombre or o.sid:
        extra = " · ".join(x for x in ((f"{o.miembros} miembros" if o.miembros and not redacted(o.miembros) else ""),
                                       " · ".join(t for t in o.etiquetas[:2] if not redacted(t))) if x)
        org_lines = [f"{o.nombre or o.sid}", f"[{o.sid}]" + (f" · rango {o.rango}" if o.rango else ""), extra]
    else:
        org_lines = ["Sin organización principal"]
    bounty = motivo == "recompensa"
    return Card(kind="jugador", title=(c.handle or "").upper(), accent=RED_HOLO if bounty else BLUE_HOLO,
                header="ORDEN DE BÚSQUEDA · CAZARRECOMPENSAS" if bounty else "REGISTRO DE CIUDADANO",
                subtitle="UEE · OFICINA DEL ADVOCACY", fields=fields, photo=photo, logo=logo,
                org_lines=[x for x in org_lines if x], stamp="OBJETIVO DE CAZA" if bounty else "CONSULTA",
                alert=bounty, footer="Fuente: robertsspaceindustries.com", seed=c.handle or "")


def parent_name(sistema: str, codigo: str) -> str:
    from .verseguide import BODY_TABLE

    m = re.fullmatch(r"(\d)([A-F])", codigo or "")
    if not m:
        return ""
    roman = ["I", "II", "III", "IV", "V", "VI"][int(m.group(1)) - 1]
    for s, c, n, _a in BODY_TABLE:
        if s == sistema and c == roman:
            return n
    return ""


def card_body(b, texture=None) -> Card:
    from .verseguide import SYSTEM_ES

    parent = parent_name(b.sistema, b.codigo)
    kind_txt = b.tipo_es()
    sub = f"{kind_txt} de {parent}" if parent and kind_txt == "Luna" else kind_txt
    sub += f" · sistema {SYSTEM_ES.get(b.sistema, b.sistema)}"
    fields = [(k.upper(), v) for k, v in b.campos() if k not in ("Tipo", "Sistema", "Peligro · Economía · Población")]
    meters = [("PELIGRO", b.peligro), ("ECONOMÍA", b.economia), ("POBLACIÓN", b.poblacion)] \
        if any(x is not None for x in (b.peligro, b.economia, b.poblacion)) else []
    return Card(kind="planeta", title=b.nombre.upper(), subtitle=sub,
                header=(b.designacion or b.codigo).upper(), fields=fields, desc=desc_for(b),
                texture=texture, tint=tuple(int(x * 255) for x in (b.color or [])[:3]), meters=meters,
                footer="Fuente: verseguide.com · robertsspaceindustries.com", seed=b.nombre)


def card_place(b, p, texture=None) -> Card:
    from .verseguide import SYSTEM_ES, _fmt

    fields = [("TIPO", p.tipo_es()), ("SITUADO EN", f"{b.nombre} · {SYSTEM_ES.get(b.sistema, b.sistema)}")]
    if p.temp_media is not None:
        t = f"{_fmt(p.temp_media)} °C"
        if p.temp_min is not None and p.temp_max is not None and p.temp_min != p.temp_max:
            t += f"  ({_fmt(p.temp_min)} a {_fmt(p.temp_max)} °C)"
        fields.append(("TEMPERATURA", t))
    return Card(kind="lugar", title=p.nombre.upper(), subtitle="Lugar planetario", header="UBICACIÓN DE SUPERFICIE",
                fields=fields, desc=desc_for(p), texture=texture,
                tint=tuple(int(x * 255) for x in (b.color or [])[:3]), footer="Fuente: verseguide.com", seed=p.nombre)


# ------------------------------------------------------------------ dibujo
def _wrap(draw, text: str, fnt, width: int, max_lines: int) -> list[str]:
    words, lines, cur = (text or "").replace("\n", " ").split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and len(" ".join(lines)) < len((text or "").strip()):
        last = lines[-1]
        while last and draw.textlength(last + "…", font=fnt) > width:
            last = last[:-1]
        lines[-1] = last.rstrip(" ,.;") + "…"
    return lines


def _fit(draw, text: str, fnt, width: int) -> str:
    if draw.textlength(text, font=fnt) <= width:
        return text
    while text and draw.textlength(text + "…", font=fnt) > width:
        text = text[:-1]
    return text + "…"


def _emblem(draw, cx: int, cy: int, r: int, color, s: float) -> None:
    """Emblema geométrico propio (no es ningún logotipo oficial)."""
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color + (230,), width=max(1, int(2 * s)))
    draw.ellipse((cx - r * 0.62, cy - r * 0.62, cx + r * 0.62, cy + r * 0.62), outline=color + (150,), width=max(1, int(s)))
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r * (0.55 if k % 2 == 0 else 0.24)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    draw.polygon(pts, fill=color + (235,))


def _holo_photo(im, size: tuple[int, int], accent) -> "Image":
    """Foto ajustada al recuadro (recortada al centro) con tono de holograma."""
    from PIL import Image, ImageOps

    im = ImageOps.fit(im.convert("RGB"), size, Image.LANCZOS, centering=(0.5, 0.35))
    a = np.asarray(im, dtype=np.float32) / 255.0
    lum = (0.3 * a[..., 0] + 0.59 * a[..., 1] + 0.11 * a[..., 2])[..., None]
    col = np.array(accent, dtype=np.float32) / 255.0
    out = a * 0.55 + lum * col * 0.75 + 0.03
    rows = (np.arange(size[1]) % 3 == 0)[:, None, None]
    out = np.where(rows, out * 0.82, out)
    return Image.fromarray(np.clip(out * 255, 0, 255).astype(np.uint8), "RGB")


class Planet:
    """Esfera texturizada que gira (proyección ortográfica, luz lateral y halo)."""

    def __init__(self, diameter: int, texture=None, tint=(), seed: str = "") -> None:
        from PIL import Image, ImageFilter

        self.d = d = int(diameter)
        if texture is None:
            rnd = np.random.default_rng(int(hashlib.md5(seed.encode()).hexdigest()[:8], 16))
            noise = Image.fromarray((rnd.random((96, 192)) * 255).astype(np.uint8), "L").resize((384, 192), Image.BICUBIC)
            noise = noise.filter(ImageFilter.GaussianBlur(3))
            n = np.asarray(noise, dtype=np.float32)[..., None] / 255.0
            base = np.array(tint if len(tint) == 3 and sum(tint) > 60 else (150, 160, 175), dtype=np.float32)
            tex = np.clip(base * (0.45 + n * 0.9), 0, 255)
        else:
            t = texture.convert("RGB")
            if t.width < t.height * 1.6:  # textura cuadrada de RSI: se repite para dar la vuelta
                t = t.resize((256, 256))
                both = Image.new("RGB", (512, 256))
                both.paste(t, (0, 0))
                both.paste(t.transpose(Image.FLIP_LEFT_RIGHT), (256, 0))
                t = both
            tex = np.asarray(t.resize((512, 256)), dtype=np.float32)
        self.tex = tex
        y, x = np.mgrid[0:d, 0:d].astype(np.float32)
        nx, ny = (x + 0.5) / d * 2 - 1, (y + 0.5) / d * 2 - 1
        r2 = nx * nx + ny * ny
        self.inside = r2 <= 1.0
        nz = np.sqrt(np.clip(1 - r2, 0, 1))
        lat = np.arcsin(np.clip(ny, -1, 1))
        self.lon = np.arctan2(nx, nz)
        self.v = ((lat / math.pi + 0.5) * (tex.shape[0] - 1)).astype(np.int32)
        light = np.clip(-0.55 * nx - 0.45 * ny + 0.7 * nz, 0, 1)
        self.shade = (0.18 + 0.95 * light)[..., None]
        self.rim = np.clip((np.sqrt(np.clip(r2, 0, 1)) - 0.72) / 0.28, 0, 1)[..., None] ** 2
        edge = np.clip((1.0 - np.sqrt(r2)) * d / 2.0, 0, 1)
        self.alpha = edge[..., None].astype(np.float32)

    def frame(self, rot: float, accent) -> np.ndarray:
        """RGBA float 0..1 (sin premultiplicar)."""
        w = self.tex.shape[1]
        u = (((self.lon / (2 * math.pi)) + rot) % 1.0 * (w - 1)).astype(np.int32)
        col = self.tex[self.v, u] / 255.0
        acc = np.array(accent, dtype=np.float32) / 255.0
        lum = col.mean(axis=2, keepdims=True)
        c = (col * 0.62 + lum * acc * 0.55) * self.shade + self.rim * acc * 0.9
        out = np.concatenate([np.clip(c, 0, 1), self.alpha], axis=2)
        out[~self.inside] = 0
        return out


@dataclass
class Layout:
    image: object  # PIL RGBA de la tarjeta (sin el planeta)
    planet: Planet | None = None
    planet_xy: tuple[int, int] = (0, 0)
    scale: float = 1.0
    marker: bool = False  # lugar planetario: punto que late sobre el planeta


def _t(x: str) -> str:
    """Etiqueta en mayúsculas traducida («PELIGRO» → «DANGER»)."""
    from .i18n import lang, tr
    if lang() == "es":
        return x
    out = tr(x)
    if out == x:
        low = tr(x.capitalize())
        out = low.upper() if low != x.capitalize() else x
    return out


def _localized(card: Card) -> Card:
    """v1.3: etiquetas y textos fijos del holograma en el idioma de NOVA AI (los datos no se tocan)."""
    from dataclasses import replace

    from .i18n import lang, tr
    if lang() == "es":
        return card

    def t(x: str) -> str:
        if not x:
            return x
        out = tr(x)
        if out == x and x.isupper():  # «APODO EN JUEGO» → busca «Apodo en juego»
            low = tr(x.capitalize())
            out = low.upper() if low != x.capitalize() else x
        return out

    def tv(x):  # valores: solo frases fijas (tipo de lugar, «Organización principal oculta»…)
        return " · ".join(tr(part) for part in x.split(" · ")) if isinstance(x, str) else x

    return replace(card, header=t(card.header), subtitle=" · ".join(t(x) for x in card.subtitle.split(" · ")),
                   stamp=t(card.stamp), footer=card.footer.replace("Fuente:", tr("Fuente:")),
                   fields=[(t(k), tv(v)) for k, v in card.fields], meters=[(t(k), v) for k, v in card.meters],
                   org_lines=[tv(x) for x in card.org_lines])


def render(card: Card, scale: float = 1.0, accent=CYAN) -> Layout:
    from PIL import Image, ImageDraw, ImageFilter

    card = _localized(card)

    s = max(0.5, min(scale, 2.5))
    W = int(W_BASE * s)
    acc = tuple(int(x) for x in (card.accent or accent))
    warn = (255, 205, 205) if card.alert else acc
    pad = int(20 * s)
    # Medir la altura según el contenido
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    f_title = font(int(30 * s), "bold")
    f_head = font(int(13 * s), "mono")
    f_lab = font(int(12 * s), "mono")
    f_val = font(int(18 * s), "sans")
    f_desc = font(int(15 * s), "sans")
    f_small = font(int(12 * s), "sans")
    header_h = int(78 * s)
    if card.kind == "jugador":
        body_h = int(292 * s)
    else:
        rows = len(card.fields) + (1 if card.meters else 0)
        body_h = max(int(214 * s), int((rows * 44 + 10) * s))
    desc_lines = _wrap(tmp, card.desc, f_desc, W - 2 * pad, 4) if card.desc else []
    desc_h = int((len(desc_lines) * 21 + 16) * s) if desc_lines else 0
    H = header_h + body_h + desc_h + int(34 * s)

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # Fondo: cristal oscuro con degradado y rejilla fina
    bg = np.zeros((H, W, 4), dtype=np.float32)
    gy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    base = np.array(NAVY, dtype=np.float32) * 0.8 + np.array(acc, dtype=np.float32) * 0.07  # fondo teñido del color
    top_glow = np.array(acc, dtype=np.float32) * 0.13
    bg[..., 0] = base[0] + top_glow[0] * (1 - gy)
    bg[..., 1] = base[1] + top_glow[1] * (1 - gy)
    bg[..., 2] = base[2] + top_glow[2] * (1 - gy)
    bg[..., 3] = 200
    grid = int(18 * s)
    yy, xx = np.mgrid[0:H, 0:W]
    on = ((yy % grid) == 0) | ((xx % grid) == 0)
    bg[on, 0:3] += np.array(acc, dtype=np.float32) * 0.08
    img = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(img)
    _plain_text = d.text

    def _text(xy, text, fill=None, font=None, anchor=None, **kw):  # contorno oscuro: se lee sobre cualquier fondo
        kw.setdefault("stroke_width", max(1, int(1.2 * s)))
        kw.setdefault("stroke_fill", (0, 6, 14, 215))
        return _plain_text(xy, text, fill=fill, font=font, anchor=anchor, **kw)
    d.text = _text
    lw = max(1, int(1.4 * s))
    d.rectangle((0, 0, W - 1, H - 1), outline=acc + (120,), width=lw)
    # Esquinas tipo HUD
    L = int(26 * s)
    t = max(2, int(3 * s))
    for (x0, y0, dx, dy) in ((0, 0, 1, 1), (W - 1, 0, -1, 1), (0, H - 1, 1, -1), (W - 1, H - 1, -1, -1)):
        d.line((x0, y0, x0 + dx * L, y0), fill=acc + (255,), width=t)
        d.line((x0, y0, x0, y0 + dy * L), fill=acc + (255,), width=t)
    # Cabecera
    d.rectangle((lw, lw, W - lw - 1, header_h), fill=acc + (34,))
    d.line((pad, header_h, W - pad, header_h), fill=acc + (170,), width=lw)
    _emblem(d, pad + int(18 * s), int(39 * s), int(18 * s), warn if card.alert else acc, s)
    x0 = pad + int(46 * s)
    d.text((x0, int(13 * s)), card.header or card.subtitle, font=f_head, fill=(warn if card.alert else acc) + (255,))
    d.text((x0, int(28 * s)), _fit(d, card.title, f_title, W - x0 - pad - int(140 * s)), font=f_title, fill=TEXT + (255,))
    year = int(time.strftime("%Y")) + 930
    d.text((W - pad, int(14 * s)), time.strftime(f"{year}-%m-%d %H:%M"), font=f_head, fill=DIM + (230,), anchor="ra")
    if card.kind != "jugador" and card.subtitle:
        d.text((W - pad, int(56 * s)), _fit(d, card.subtitle, f_small, int(300 * s)), font=f_small, fill=DIM + (255,),
               anchor="ra")
    elif card.subtitle:
        d.text((W - pad, int(56 * s)), card.subtitle, font=f_head, fill=DIM + (230,), anchor="ra")

    top = header_h + int(14 * s)
    layout = Layout(image=img, scale=s)
    if card.kind == "jugador":
        _draw_player(img, d, card, s, top, W, pad, acc, warn, f_lab, f_val, f_small)
    else:
        _draw_body(img, d, card, s, top, W, pad, acc, f_lab, f_val, layout)
    if desc_lines:
        y = header_h + body_h + int(2 * s)
        d.line((pad, y, W - pad, y), fill=acc + (90,), width=lw)
        for i, line in enumerate(desc_lines):
            d.text((pad, y + int((8 + i * 21) * s)), line, font=f_desc, fill=(214, 236, 248, 255))
    # Pie: fuente y «código de barras»
    fy = H - int(22 * s)
    d.text((pad, fy), card.footer, font=f_small, fill=DIM + (220,))
    h = hashlib.sha1((card.seed or card.title).encode()).digest()
    bx = W - pad
    for byte in h[:22]:
        wbar = 1 + byte % 3
        bx -= wbar + 2
        d.rectangle((bx, fy + 2, bx + wbar, fy + int(12 * s)), fill=acc + (150,))
    # Brillo exterior suave en los bordes
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rectangle((0, 0, W - 1, H - 1), outline=acc + (160,), width=max(2, int(4 * s)))
    glow = glow.filter(ImageFilter.GaussianBlur(4 * s))
    layout.image = Image.alpha_composite(glow, img)
    return layout


def _draw_player(img, d, card, s, top, W, pad, acc, warn, f_lab, f_val, f_small) -> None:
    from PIL import Image, ImageDraw

    pw, ph = int(176 * s), int(226 * s)
    px, py = pad, top
    # Recuadro de la foto con escala de altura de comisaría
    d.rectangle((px, py, px + pw, py + ph), fill=(8, 26, 44, 230), outline=acc + (170,), width=max(1, int(1.4 * s)))
    f_tiny = font(int(9 * s), "mono")
    for k in range(9):
        y = py + int((14 + k * 24) * s)
        d.line((px + int(4 * s), y, px + pw - int(4 * s), y), fill=acc + (45 if k % 2 else 80,), width=1)
        d.text((px + pw - int(5 * s), y - int(11 * s)), f"{200 - k * 10}", font=f_tiny, fill=acc + (120,), anchor="ra")
    box = (pw - int(24 * s), ph - int(58 * s))
    if card.photo is not None:
        photo = _holo_photo(card.photo, box, acc)
        img.paste(photo, (px + int(12 * s), py + int(12 * s)))
    else:  # silueta
        cx, cy = px + pw // 2, py + int(90 * s)
        d.ellipse((cx - int(34 * s), cy - int(52 * s), cx + int(34 * s), cy + int(16 * s)), fill=acc + (90,))
        d.pieslice((cx - int(70 * s), cy + int(20 * s), cx + int(70 * s), cy + int(160 * s)), 180, 360, fill=acc + (90,))
    d.rectangle((px + int(12 * s), py + ph - int(42 * s), px + pw - int(12 * s), py + ph - int(10 * s)),
                fill=(2, 10, 18, 235), outline=acc + (130,))
    rec = next((v for k, v in card.fields if k in ("EXPEDIENTE UEE", _t("EXPEDIENTE UEE"))), "")
    d.text((px + pw // 2, py + ph - int(26 * s)), f"Nº {rec}" if rec not in ("—", "[REDACTED]") else "Nº ——",
           font=font(int(13 * s), "mono"), fill=TEXT + (255,), anchor="mm")
    # Sello
    if card.stamp:
        col = warn if card.alert else acc
        f_st = font(int(17 * s if card.alert else 13 * s), "bold")
        tw = int(d.textlength(card.stamp, font=f_st)) + int(18 * s)
        th = int(30 * s)
        st = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        sd = ImageDraw.Draw(st)
        sd.rectangle((1, 1, tw - 2, th - 2), outline=col + (235,), width=max(2, int(2.4 * s)))
        sd.text((tw // 2, th // 2), card.stamp, font=f_st, fill=col + (240,), anchor="mm")
        st = st.rotate(-9 if card.alert else -6, expand=True, resample=Image.BICUBIC)
        img.alpha_composite(st, (px + (pw - st.width) // 2, py + ph - int(92 * s)))
    # Datos
    x = px + pw + int(22 * s)
    colw = W - x - pad
    y = top - int(2 * s)
    for label, value in card.fields:
        d.text((x, y), label, font=f_lab, fill=DIM + (255,))
        if value == "[REDACTED]":
            vw = int(150 * s)
            d.rectangle((x, y + int(15 * s), x + vw, y + int(36 * s)), fill=(0, 0, 0, 240))
            d.text((x + int(6 * s), y + int(17 * s)), "REDACTED", font=font(int(13 * s), "mono"), fill=RED + (230,))
        else:
            d.text((x, y + int(14 * s)), _fit(d, value, f_val, colw), font=f_val, fill=TEXT + (255,))
        y += int(41 * s)
    # Organización: panel propio bajo los datos
    oy = top + int(216 * s)
    oh = int(62 * s)
    d.rectangle((x, oy, W - pad, oy + oh), fill=(2, 10, 18, 170), outline=GOLD + (120,))
    d.text((x, oy - int(17 * s)), _t("ORGANIZACIÓN PRINCIPAL"), font=f_lab, fill=DIM + (255,))
    lx = x + int(6 * s)
    tx = lx + int(8 * s)
    if card.logo is not None:
        logo = card.logo.copy()
        logo.thumbnail((int(50 * s), int(50 * s)))
        img.alpha_composite(logo, (lx + (int(50 * s) - logo.width) // 2, oy + (oh - logo.height) // 2))
        tx = lx + int(62 * s)
    for i, line in enumerate(card.org_lines[:3]):
        if line == "[REDACTED]":
            d.rectangle((tx, oy + int(8 * s), tx + int(150 * s), oy + int(28 * s)), fill=(0, 0, 0, 240))
            d.text((tx + int(6 * s), oy + int(10 * s)), "REDACTED", font=font(int(13 * s), "mono"), fill=RED + (230,))
            continue
        fnt = font(int(16 * s), "bold") if i == 0 else f_small
        d.text((tx, oy + int((7 + (0 if i == 0 else 6 + i * 15)) * s)), _fit(d, line, fnt, W - pad - tx - int(8 * s)),
               font=fnt, fill=(GOLD if i == 0 else DIM) + (255,))


def _draw_body(img, d, card, s, top, W, pad, acc, f_lab, f_val, layout: Layout) -> None:
    diam = int((190 if card.kind == "planeta" else 150) * s)
    px, py = pad + int(10 * s), top + int(8 * s)
    cx, cy = px + diam // 2, py + diam // 2
    # Anillos de órbita detrás del planeta
    for k, a in ((1.32, 70), (1.12, 120)):
        rx, ry = diam * k / 2, diam * k * 0.28
        d.ellipse((cx - rx, cy - ry + diam * 0.08, cx + rx, cy + ry + diam * 0.08), outline=acc + (a,),
                  width=max(1, int(s)))
    d.ellipse((cx - diam * 0.56, cy - diam * 0.56, cx + diam * 0.56, cy + diam * 0.56), outline=acc + (60,),
              width=max(1, int(s)))
    layout.planet = Planet(diam, card.texture, card.tint, card.seed)
    layout.planet_xy = (px, py)
    layout.marker = card.kind == "lugar"
    x = px + diam + int(36 * s)
    colw = W - x - pad
    y = top - int(4 * s)
    for label, value in card.fields:
        d.text((x, y), label, font=f_lab, fill=DIM + (255,))
        d.text((x, y + int(14 * s)), _fit(d, value, f_val, colw), font=f_val, fill=TEXT + (255,))
        y += int(44 * s)
    if card.meters:
        seg = max(3, int(9 * s))
        mx = x
        for label, val in card.meters:
            d.text((mx, y), label, font=f_lab, fill=DIM + (255,))
            for k in range(10):
                on = val is not None and k < val
                col = (RED if k >= 7 else GOLD if k >= 4 else acc) if label in ("PELIGRO", _t("PELIGRO")) else acc
                d.rectangle((mx + k * (seg + 2), y + int(16 * s), mx + k * (seg + 2) + seg, y + int(28 * s)),
                            fill=col + ((235,) if on else (40,)))
            mx += int(10 * (seg + 2) + 20 * s)


# ------------------------------------------------------------------ animación
def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


class Animation:
    """Fotogramas de una tarjeta: aparición (proyección), estado en pantalla y salida (pliegue)."""

    APPEAR, LEAVE = 0.95, 0.55

    def __init__(self, layout: Layout, accent=CYAN, opacity: float = 0.9, duration: float = 14.0,
                 level: str = "cine") -> None:
        self.level = level if level in ("cine", "ligero", "ninguno") else "cine"
        if self.level == "ligero":
            self.APPEAR, self.LEAVE = 0.35, 0.3
        elif self.level == "ninguno":
            self.APPEAR, self.LEAVE = 0.0, 0.0
        self._static = None
        self.layout = layout
        base = np.asarray(layout.image, dtype=np.float32) / 255.0
        self.base = base
        self.h, self.w = base.shape[:2]
        self.acc = np.array(accent, dtype=np.float32) / 255.0
        self.opacity = max(0.15, min(1.0, opacity))
        self.duration = max(4.0, duration)
        self.start = None
        self.leave_at = None
        self.rows = np.arange(self.h, dtype=np.float32)[:, None]
        self._glitch_until = 0.0
        self._next_glitch = 0.0
        self._rnd = random.Random()

    def begin(self, now: float) -> None:
        self.start = now
        self.leave_at = now + self.duration

    def leave(self, now: float) -> None:
        if self.leave_at is None or self.leave_at > now:
            self.leave_at = now

    def done(self, now: float) -> bool:
        return self.leave_at is not None and now >= self.leave_at + self.LEAVE

    def frame(self, now: float) -> np.ndarray:
        """BGRA premultiplicado uint8. Tres niveles: cine (todo), ligero (fundidos) y ninguno (estático)."""
        if self.level == "ninguno":
            if self._static is None:
                self._static = self._plain(1.0, 0.1)
            return self._static
        if self.level == "ligero":
            t = now - (self.start if self.start is not None else now)
            k = _ease(t / self.APPEAR) if t < self.APPEAR else 1.0
            if self.leave_at is not None and now >= self.leave_at:
                k *= 1 - _ease((now - self.leave_at) / self.LEAVE)
            return self._plain(k, t)
        return self._cine(now)

    def _plain(self, k: float, t: float) -> np.ndarray:
        """Tarjeta sin efectos (el planeta gira despacio en «ligero»)."""
        img = self.base.copy()
        lay = self.layout
        if lay.planet is not None:
            p = lay.planet.frame(t * 0.018 + 0.1, tuple(self.acc * 255))
            x, y = lay.planet_xy
            hh, ww = p.shape[:2]
            region = img[y:y + hh, x:x + ww]
            a = p[..., 3:4]
            region[..., :3] = p[..., :3] * a + region[..., :3] * (1 - a)
            region[..., 3:4] = a + region[..., 3:4] * (1 - a)
        a = np.clip(img[..., 3:4] * self.opacity * k, 0, 1)
        return self._pack(img[..., :3] * a, a)

    @staticmethod
    def _pack(c: np.ndarray, a: np.ndarray) -> np.ndarray:
        h, w = a.shape[:2]
        out = np.empty((h, w, 4), dtype=np.uint8)
        out[..., 0] = (c[..., 2] * 255).astype(np.uint8)
        out[..., 1] = (c[..., 1] * 255).astype(np.uint8)
        out[..., 2] = (c[..., 0] * 255).astype(np.uint8)
        out[..., 3] = (a[..., 0] * 255).astype(np.uint8)
        return out

    def _sparks(self, t: float) -> np.ndarray:
        """v1.3 «cinematográfico»: motas de luz que suben por la tarjeta."""
        if not hasattr(self, "_pts"):
            r = self._rnd
            self._pts = [(r.uniform(0, self.w), r.uniform(0, self.h), r.uniform(10, 34), r.uniform(0.6, 1.6),
                          r.uniform(0, 6.28)) for _ in range(max(12, self.w // 22))]
        glow = np.zeros((self.h, self.w), dtype=np.float32)
        for x0, y0, speed, size, ph in self._pts:
            y = (y0 - t * speed) % self.h
            x = x0 + 4 * np.sin(t * 1.3 + ph)
            xi, yi = int(x), int(y)
            if 1 <= xi < self.w - 2 and 1 <= yi < self.h - 2:
                tw = 0.55 + 0.45 * np.sin(t * 5 + ph)
                glow[yi - 1:yi + 2, xi - 1:xi + 2] += 0.25 * tw * size
                glow[yi, xi] += 0.6 * tw
        return np.clip(glow, 0, 1)[..., None]

    def _cine(self, now: float) -> np.ndarray:
        t = now - (self.start if self.start is not None else now)
        img = self.base.copy()
        lay = self.layout
        if lay.planet is not None:
            p = lay.planet.frame(t * 0.018 + 0.1, tuple(self.acc * 255))
            x, y = lay.planet_xy
            hh, ww = p.shape[:2]
            region = img[y:y + hh, x:x + ww]
            a = p[..., 3:4]
            region[..., :3] = p[..., :3] * a + region[..., :3] * (1 - a)
            region[..., 3:4] = a + region[..., 3:4] * (1 - a)
            if lay.marker:  # señal que late donde está el lugar
                yy, xx = np.mgrid[0:hh, 0:ww]
                mx, my = ww * 0.42, hh * 0.38
                dist = np.sqrt((xx - mx) ** 2 + (yy - my) ** 2)
                ring_r = (t * 26) % (hh * 0.32)
                ring = np.exp(-((dist - ring_r) / 2.2) ** 2) * (1 - ring_r / (hh * 0.32))
                dot = np.clip(1 - dist / (hh * 0.035), 0, 1)
                glow = np.clip(ring + dot, 0, 1)[..., None]
                warm = np.array([1.0, 0.85, 0.35], dtype=np.float32)
                region[..., :3] = np.clip(region[..., :3] * (1 - glow) + warm * glow, 0, 1)
                region[..., 3:4] = np.maximum(region[..., 3:4], glow)
        # Líneas de barrido que bajan y una banda de luz cada pocos segundos
        scan = 0.9 + 0.1 * np.sin((self.rows + t * 40) * 0.9)
        band_y = ((t % 3.2) / 3.2) * (self.h + 120) - 60
        band = np.exp(-((self.rows - band_y) / 22.0) ** 2) * 0.22
        img[..., :3] = np.clip(img[..., :3] * scan[..., None] + band[..., None] * self.acc * img[..., 3:4], 0, 1)
        alpha = img[..., 3:4] * scan[..., None]
        # Aparición: una línea brillante que se abre desde el centro
        k = 1.0
        if t < self.APPEAR:
            e = _ease(t / self.APPEAR)
            half = e * self.h / 2
            dist = np.abs(self.rows - self.h / 2)
            mask = np.clip((half - dist) / 6.0 + 0.5, 0, 1)[..., None]
            edge = np.exp(-((dist - half) / 3.0) ** 2)[..., None] * (1 - e * 0.6)
            alpha = alpha * mask + edge * 0.9
            img[..., :3] = np.clip(img[..., :3] + edge * self.acc, 0, 1)
            k = 0.35 + 0.65 * e
            if self._rnd.random() < 0.25:  # parpadeo de proyector
                k *= 0.6
        # Salida: se pliega hacia una línea y se apaga
        if self.leave_at is not None and now >= self.leave_at:
            e = _ease((now - self.leave_at) / self.LEAVE)
            half = (1 - e) * self.h / 2
            dist = np.abs(self.rows - self.h / 2)
            mask = np.clip((half - dist) / 4.0 + 0.5, 0, 1)[..., None]
            line = np.exp(-(dist / 2.0) ** 2)[..., None] * (1 - e)
            alpha = alpha * mask + line
            img[..., :3] = np.clip(img[..., :3] + line * self.acc, 0, 1)
            k *= 1 - e * 0.4
        # Glitch ocasional: una franja se desplaza un instante
        if now >= self._next_glitch:
            self._glitch_until = now + self._rnd.uniform(0.05, 0.11)
            self._next_glitch = now + self._rnd.uniform(2.5, 6.0)
            self._g = (self._rnd.randrange(0, max(1, self.h - 30)), self._rnd.randrange(6, 26), self._rnd.choice((-1, 1)) * self._rnd.randrange(4, 14))
        if now < self._glitch_until and t > self.APPEAR:
            gy, gh, dx = self._g
            img[gy:gy + gh] = np.roll(img[gy:gy + gh], dx, axis=1)
            alpha[gy:gy + gh] = np.roll(alpha[gy:gy + gh], dx, axis=1)
        # Aberración cromática (rojo y azul separados) al proyectarse y durante los glitches
        shift = 0
        if t < self.APPEAR:
            shift = int(round(6 * (1 - _ease(t / self.APPEAR))))
        elif now < self._glitch_until:
            shift = 3
        if shift:
            img[..., 0] = np.roll(img[..., 0], shift, axis=1)
            img[..., 2] = np.roll(img[..., 2], -shift, axis=1)
        # Motas de luz flotando dentro de la tarjeta
        sp = self._sparks(t) * img[..., 3:4]
        img[..., :3] = np.clip(img[..., :3] + sp * (0.5 + 0.5 * self.acc), 0, 1)
        alpha = np.clip(alpha + sp * 0.5, 0, 1)
        a = np.clip(alpha * self.opacity * k, 0, 1)
        return self._pack(img[..., :3] * a, a)


def to_rgba_image(bgra: np.ndarray):
    """BGRA premultiplicado -> PIL RGBA (para vistas previas y pruebas)."""
    from PIL import Image

    a = bgra[..., 3:4].astype(np.float32) / 255.0
    rgb = bgra[..., [2, 1, 0]].astype(np.float32)
    rgb = np.where(a > 0, rgb / np.maximum(a, 1e-6), 0)
    out = np.concatenate([np.clip(rgb, 0, 255), bgra[..., 3:4]], axis=2).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def preview_png(card: Card, accent=CYAN, scale: float = 1.0, background: bool = True) -> bytes:
    """La tarjeta ya aparecida, como PNG (para la ventana de NOVA y el manual)."""
    from PIL import Image

    acc = card.accent or accent
    anim = Animation(render(card, scale, acc), acc, opacity=1.0)
    anim._next_glitch = 1e18
    anim.begin(0.0)
    im = to_rgba_image(anim.frame(2.0))
    if background:
        bg = Image.new("RGBA", im.size, (4, 10, 18, 255))
        im = Image.alpha_composite(bg, im)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


# ------------------------------------------------------------------ ventana sobre el juego
HOLO_POSITIONS = ("centro-derecha", "arriba-derecha", "abajo-derecha", "centro-izquierda", "arriba-izquierda",
                  "abajo-izquierda", "arriba-centro", "centro")


def placement(pos: str, rect, w: int, h: int, margin: int) -> tuple[int, int]:
    left, top, right, bottom = rect
    v, _, hz = (pos if pos in HOLO_POSITIONS else "centro-derecha").partition("-")
    hz = hz or "centro"
    xs = {"izquierda": left + margin, "centro": (left + right - w) // 2, "derecha": right - w - margin}
    ys = {"arriba": top + margin, "centro": (top + bottom - h) // 2, "abajo": bottom - h - margin}
    return xs[hz], ys[v]


class HoloOverlay(threading.Thread):
    """Cola de hologramas: muestra uno detrás de otro sobre el juego."""

    def __init__(self, settings) -> None:
        super().__init__(daemon=True, name="hologramas")
        self.settings = settings
        self.q: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._skip = threading.Event()
        self.status = "inactivo"
        self.current: Card | None = None
        self.play = lambda name: None  # efectos de sonido (los pone el asistente)

    def show(self, card: Card, force: bool = False) -> None:
        """force: se ve aunque el juego no esté delante (botón «Probar»)."""
        if not self.settings.get("holo_activo", True) and not force:
            return
        self.q.put((card, force))
        if not self.is_alive() and IS_WINDOWS:
            try:
                self.start()
            except RuntimeError:
                pass

    def dismiss(self) -> None:
        self._skip.set()

    def stop(self) -> None:
        self._stop.set()
        self._skip.set()

    def _accent(self):
        from .overlay import _hex
        return _hex(self.settings.get("overlay_color"))

    def run(self) -> None:
        if not IS_WINDOWS:
            self.status = "solo disponible en Windows"
            return
        from .overlay import _LayeredWindow, _game_foreground, _game_window_rect, scale_for, target_area

        try:
            win = _LayeredWindow()
        except Exception as e:  # noqa: BLE001
            log.exception("Hologramas")
            self.status = f"error: {e}"
            return
        self.status = "activo"
        while not self._stop.is_set():
            try:
                card, force = self.q.get(timeout=0.3)
            except queue.Empty:
                win.pump()
                continue
            try:
                rect, _src = target_area(self.settings)
                k = scale_for(rect[3] - rect[1]) * float(self.settings.get("holo_escala", 1.0))
                acc = card.accent or self._accent()
                lay = render(card, k, acc)
                fx = self.settings.get("efectos_nivel", "cine")
                anim = Animation(lay, acc, float(self.settings.get("holo_opacidad", 0.85)),
                                 float(self.settings.get("holo_segundos", 14)), level=fx)
                self.current = card
                self._skip.clear()
                if card.alert:
                    self.play("alerta")  # objetivo de captura: advertencia antes de la ficha
                    time.sleep(0.5)
                self.play("holo_on")
                anim.begin(time.time())
                shown = False
                off_played = False
                margin = int(28 * scale_for(rect[3] - rect[1]))
                while not self._stop.is_set():
                    now = time.time()
                    if self._skip.is_set():
                        anim.leave(now)
                        self._skip.clear()
                    if not off_played and anim.leave_at is not None and now >= anim.leave_at:
                        off_played = True
                        self.play("holo_off")
                    if anim.done(now):
                        break
                    visible = force or not self.settings.get("overlay_solo_juego") or (
                        _game_window_rect() is not None and _game_foreground())
                    win.pump()
                    if not visible:
                        if shown:
                            win.hide()
                            shown = False
                        time.sleep(0.2)
                        continue
                    x, y = placement(self.settings.get("holo_posicion", "centro-derecha"), rect, anim.w, anim.h, margin)
                    win.update(anim.frame(now), x, y)
                    if not shown:
                        win.show()
                        shown = True
                    time.sleep(1 / 30 if fx == "cine" else 1 / 20 if fx == "ligero" else 1 / 8)
                win.hide()
                self.current = None
            except Exception as e:  # noqa: BLE001 — una tarjeta rota no tumba los hologramas
                log.exception("Holograma")
                self.status = f"error: {e}"
                time.sleep(1)
        win.destroy()

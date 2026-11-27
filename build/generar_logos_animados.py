"""NOVA AI 2.1.7 · genera los logos animados del overlay (diseños propios) en recursos/logos/animados/*.webp.

Se dibujan con PIL a 3× y se reducen (bordes suaves). Formato WebP animado: a diferencia del GIF, tiene
transparencia de verdad (256 niveles), así que el logo no se ve dentado encima del juego.
Todas las animaciones cierran el ciclo sin saltos. Uso:  python build/generar_logos_animados.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "recursos" / "logos" / "animados"
SIZE = 256          # tamaño final (como los logos fijos)
SS = 3              # superposición de muestras
N = 48              # fotogramas por ciclo
MS = 50             # ms por fotograma (ciclo de 2,4 s)
W = SIZE * SS
C = W / 2

CY = (111, 216, 255)
CY2 = (32, 184, 232)
WHITE = (226, 248, 255)
FAINT = (70, 150, 190)
DARK = (8, 22, 38, 235)


def lw(px: float) -> int:
    return max(1, round(px * SS))


def P(x: float, y: float) -> tuple[float, float]:
    """Coordenadas en «unidades de 256» (como los logos fijos) a píxeles del lienzo grande."""
    k = W / 256
    return x * k, y * k


def R(r: float) -> float:
    return r * W / 256


def circle(d: ImageDraw.ImageDraw, r: float, fill=None, outline=None, width=1.0, cx=128, cy=128):
    x, y = P(cx, cy)
    rr = R(r)
    d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=fill, outline=outline, width=lw(width) if outline else 0)


def arc(d, r, a0, a1, color, width, cx=128, cy=128):
    x, y = P(cx, cy)
    rr = R(r)
    d.arc((x - rr, y - rr, x + rr, y + rr), a0, a1, fill=color, width=lw(width))


def polar(r, ang, cx=128, cy=128):
    return P(cx + r * math.cos(ang), cy + r * math.sin(ang))


def base_disc(d, ring=True):
    circle(d, 118, fill=DARK)
    if ring:
        circle(d, 118, outline=CY, width=3.2)


def glow(img: Image.Image, amount: float = 0.55, radius: float = 5) -> Image.Image:
    """Halo suave de las partes brillantes (solo dentro del lienzo)."""
    a = img.getchannel("A")
    lum = img.convert("L")
    bright = Image.eval(lum, lambda v: 255 if v > 150 else 0)
    mask = Image.composite(a, Image.new("L", img.size, 0), bright).filter(ImageFilter.GaussianBlur(R(radius)))
    halo = Image.new("RGBA", img.size, CY + (0,))
    halo.putalpha(Image.eval(mask, lambda v: int(v * amount)))
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(halo)
    out.alpha_composite(img)
    return out


def finish(img: Image.Image, g: float = 0.5) -> Image.Image:
    return glow(img, g).resize((SIZE, SIZE), Image.LANCZOS)


def new():
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def mix(c1, c2, k):
    return tuple(int(a + (b - a) * k) for a, b in zip(c1, c2))


# ------------------------------------------------------------------ diseños
def nova_pulso(t: float) -> Image.Image:
    """El logo de NOVA respirando, con un arco que gira y un punto de luz que recorre el anillo."""
    img, d = new()
    logo = Image.open(ROOT / "recursos" / "nova.png").convert("RGBA")
    breath = 0.5 - 0.5 * math.cos(2 * math.pi * t)
    s = int(W * (0.80 + 0.035 * breath))
    lg = logo.resize((s, s), Image.LANCZOS)
    img.alpha_composite(lg, ((W - s) // 2, (W - s) // 2))
    d = ImageDraw.Draw(img)
    rot = 360 * t
    for k in range(3):
        a0 = rot + k * 120
        arc(d, 121, a0, a0 + 52, CY, 3.0)
    ang = -2 * math.pi * t
    x, y = polar(121, ang)
    rr = R(4.5)
    d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=WHITE)
    return finish(img, 0.45 + 0.25 * breath)


def nucleo(t: float) -> Image.Image:
    """Núcleo de energía que late y lanza ondas hacia fuera."""
    img, d = new()
    base_disc(d)
    circle(d, 106, outline=FAINT, width=1.2)
    for k in range(10):  # remaches que giran despacio
        ang = 2 * math.pi * (k / 10 + t / 10)
        x, y = polar(112, ang)
        rr = R(2.3)
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=CY)
    for ph in (0.0, 0.5):  # dos ondas desfasadas
        u = (t + ph) % 1.0
        r = 30 + 72 * u
        col = mix(WHITE, FAINT, u)
        a = int(255 * (1 - u) ** 1.3)
        circle(d, r, outline=col + (a,), width=2.4 * (1 - u) + 0.8)
    beat = 0.5 - 0.5 * math.cos(2 * math.pi * t)
    beat = beat ** 2
    rcore = 38 + 8 * beat
    for i in range(14, 0, -1):  # degradado del núcleo
        k = i / 14
        circle(d, rcore * k, fill=mix(WHITE, CY2, k ** 1.4) + (int(60 + 195 * (1 - k * 0.7)),))
    return finish(img, 0.5 + 0.3 * beat)


def radar(t: float) -> Image.Image:
    """Radar con barrido giratorio, estela y ecos que se encienden al paso del haz."""
    img, d = new()
    base_disc(d)
    for r in (36, 72, 104):
        circle(d, r, outline=FAINT, width=1.3)
    x0, y0 = P(128, 14); x1, y1 = P(128, 242)
    d.line((x0, y0, x1, y1), fill=FAINT, width=lw(1.2))
    x0, y0 = P(14, 128); x1, y1 = P(242, 128)
    d.line((x0, y0, x1, y1), fill=FAINT, width=lw(1.2))
    sweep = 360 * t - 90
    trail = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    td = ImageDraw.Draw(trail)
    x, y = P(128, 128)
    rr = R(114)
    steps = 40
    for i in range(steps):  # estela: sectores cada vez más tenues
        a1 = sweep - i * 2.0
        alpha = int(170 * (1 - i / steps) ** 1.6)
        td.pieslice((x - rr, y - rr, x + rr, y + rr), a1 - 2.2, a1, fill=CY2 + (alpha,))
    img.alpha_composite(trail)
    d = ImageDraw.Draw(img)
    ex, ey = polar(114, math.radians(sweep))
    d.line((x, y, ex, ey), fill=WHITE, width=lw(2.4))
    for (r, deg) in ((58, 35), (88, 160), (44, 250), (96, 300)):
        since = (sweep - deg) % 360
        k = max(0.0, 1 - since / 300)
        bx, by = polar(r, math.radians(deg))
        rb = R(3.2 + 2.0 * k)
        d.ellipse((bx - rb, by - rb, bx + rb, by + rb), fill=mix(FAINT, WHITE, k) + (int(80 + 175 * k),))
    circle(d, 4, fill=WHITE)
    return finish(img, 0.5)


def onda(t: float) -> Image.Image:
    """Ecualizador de voz: barras que suben y bajan como al hablar."""
    img, d = new()
    base_disc(d)
    circle(d, 104, outline=FAINT, width=1.2)
    n = 11
    tau = 2 * math.pi
    for i in range(n):
        x = 128 + (i - (n - 1) / 2) * 15
        env = math.cos((i - (n - 1) / 2) / (n / 2) * math.pi / 2) ** 0.8
        v = (0.55 + 0.25 * math.sin(tau * (2 * t + i * 0.17)) + 0.2 * math.sin(tau * (3 * t - i * 0.31)))
        h = 14 + 64 * env * max(0.05, v)
        x0, y0 = P(x - 4.2, 128 - h)
        x1, y1 = P(x + 4.2, 128 + h)
        col = WHITE if i in (4, 5, 6) else CY
        d.rounded_rectangle((x0, y0, x1, y1), radius=R(4.2), fill=col)
    return finish(img, 0.5)


def orbitas(t: float) -> Image.Image:
    """Giroscopio: tres órbitas inclinadas con satélites alrededor de un núcleo."""
    img, d = new()
    base_disc(d)
    tau = 2 * math.pi
    for k, (rot, sp, ph) in enumerate(((0, 1, 0.0), (60, 2, 0.33), (120, -1, 0.66))):
        rr = math.radians(rot)
        pts = []
        for j in range(121):
            a = tau * j / 120
            x, y = 92 * math.cos(a), 34 * math.sin(a)
            pts.append(P(128 + x * math.cos(rr) - y * math.sin(rr), 128 + x * math.sin(rr) + y * math.cos(rr)))
        d.line(pts, fill=FAINT, width=lw(1.4))
        a = tau * (sp * t + ph)
        x, y = 92 * math.cos(a), 34 * math.sin(a)
        px, py = P(128 + x * math.cos(rr) - y * math.sin(rr), 128 + x * math.sin(rr) + y * math.cos(rr))
        rb = R(5.2)
        d.ellipse((px - rb, py - rb, px + rb, py + rb), fill=WHITE)
    beat = 0.5 - 0.5 * math.cos(tau * 2 * t)
    for i in range(10, 0, -1):
        k = i / 10
        circle(d, (17 + 3 * beat) * k, fill=mix(WHITE, CY2, k) + (255,))
    return finish(img, 0.5)


def hexagono(t: float) -> Image.Image:
    """Escudo hexagonal: el anillo del medio gira, el centro late y una línea de escaneo lo recorre."""
    img, d = new()
    tau = 2 * math.pi

    def hexpts(r, rot=0.0):
        return [P(128 + r * math.cos(rot + tau * k / 6 - math.pi / 2), 128 + r * math.sin(rot + tau * k / 6 - math.pi / 2))
                for k in range(6)]

    d.polygon(hexpts(120), fill=DARK)
    d.line(hexpts(120) + [hexpts(120)[0]], fill=CY, width=lw(3.2), joint="curve")
    for x, y in hexpts(108):
        rr = R(2.6)
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=CY)
    rot = (tau / 6) * t  # 60°: el hexágono vuelve a coincidir al final del ciclo
    mid = hexpts(84, rot)
    d.line(mid + [mid[0]], fill=FAINT, width=lw(1.6), joint="curve")
    for x, y in mid:
        rr = R(3.4)
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=WHITE)
    beat = 0.5 - 0.5 * math.cos(tau * t)
    r1 = 38 + 4 * beat
    d.polygon(hexpts(r1), fill=CY)
    d.polygon(hexpts(r1 * 0.55), fill=DARK[:3] + (255,))
    d.polygon(hexpts(r1 * 0.32), fill=mix(CY, WHITE, beat))
    scan = Image.new("RGBA", (W, W), (0, 0, 0, 0))  # línea de escaneo recortada al hexágono
    sd = ImageDraw.Draw(scan)
    yy = 10 + 236 * t
    for i in range(10):
        a = int(150 * (1 - i / 10))
        _, y0 = P(0, yy - i * 1.6)
        sd.line((0, y0, W, y0), fill=WHITE + (a,), width=lw(1.6))
    mask = Image.new("L", (W, W), 0)
    ImageDraw.Draw(mask).polygon(hexpts(116), fill=255)
    img.paste(Image.alpha_composite(img, scan), (0, 0), mask)
    return finish(img, 0.5)


def reticula(t: float) -> Image.Image:
    """Retícula de fijar objetivo: las esquinas se cierran, el anillo de marcas gira y el rombo late."""
    img, d = new()
    circle(d, 112, fill=DARK)
    tau = 2 * math.pi
    close = 0.5 - 0.5 * math.cos(tau * t)
    off = 120 - 12 * close
    L = 34
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = 128 + sx * off, 128 + sy * off
            d.line((P(cx, cy), P(cx - sx * L, cy)), fill=CY, width=lw(4.2))
            d.line((P(cx, cy), P(cx, cy - sy * L)), fill=CY, width=lw(4.2))
    rot = tau * t / 4  # 24 marcas: a 1/4 de vuelta el dibujo se repite
    for k in range(24):
        a = rot + tau * k / 24
        r0 = 84 if k % 6 else 76
        d.line((polar(r0, a), polar(92, a)), fill=CY if k % 6 else WHITE, width=lw(1.6 if k % 6 else 2.6))
    s = 1 + 0.1 * close
    dia = [P(128, 128 - 42 * s), P(128 + 26 * s, 128), P(128, 128 + 42 * s), P(128 - 26 * s, 128)]
    d.line(dia + [dia[0]], fill=WHITE, width=lw(4), joint="curve")
    inner = [P(128, 128 - 24 * s), P(128 + 15 * s, 128), P(128, 128 + 24 * s), P(128 - 15 * s, 128)]
    d.polygon(inner, fill=mix(CY, WHITE, close))
    return finish(img, 0.45 + 0.3 * close)


DESIGNS = {"nova_pulso": nova_pulso, "nucleo_latido": nucleo, "radar_barrido": radar, "onda_voz": onda,
           "orbitas": orbitas, "escudo_hex": hexagono, "reticula_fijando": reticula}


def main(only: list[str] | None = None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in DESIGNS.items():
        if only and name not in only:
            continue
        frames = [fn(i / N) for i in range(N)]
        dest = OUT / f"{name}.webp"
        frames[0].save(dest, save_all=True, append_images=frames[1:], duration=MS, loop=0,
                       lossless=False, quality=78, alpha_quality=80, method=4, kmax=N)
        print(f"{dest.name}: {dest.stat().st_size // 1024} KB")


if __name__ == "__main__":
    import sys

    main(sys.argv[1:] or None)

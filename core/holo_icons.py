"""2.1.1 · Iconos de los hologramas de alerta de la telemetría (dibujos propios, vectoriales).

Cada icono se dibuja en un lienzo 4 veces más grande y se reduce (bordes suaves). Los que tienen nivel
(gota de agua, depósito de hidrógeno) se rellenan hasta el porcentaje actual. Ninguno copia logotipos
ni iconos del juego: son figuras genéricas (gota, cubiertos, O₂, corazón, depósito, átomo, escudo,
casco, triángulo de avería, misil en la mira).
"""
from __future__ import annotations

import math

SS = 4  # supermuestreo

ICONS = ("sed", "hambre", "oxigeno", "salud", "hidrogeno", "cuantico", "escudos", "casco", "averia", "misil")


def _font(size: int):
    from .holo import font
    return font(size, "bold")


def draw_icon(name: str, size: int, color: tuple, level: float | None = None, broken: bool = False):
    """PIL RGBA de size×size con el icono `name` en `color` (RGB). level 0-1 rellena gota/depósito;
    broken dibuja el escudo o el casco roto."""
    from PIL import Image, ImageDraw

    S = max(16, int(size)) * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    col = tuple(int(c) for c in color[:3])
    lw = max(2, int(S * 0.045))
    soft = col + (70,)
    full = col + (255,)
    white = (236, 248, 255, 255)

    def P(x: float, y: float) -> tuple[float, float]:
        return (x * S, y * S)

    def poly(points, fill=None, outline=None, width=lw):
        pts = [P(x, y) for x, y in points]
        if fill:
            d.polygon(pts, fill=fill)
        if outline:
            d.line(pts + [pts[0]], fill=outline, width=width, joint="curve")

    def fill_level(points, lvl: float, top: float, bottom: float, fill) -> None:
        """Rellena la figura hasta el nivel (de abajo arriba), con una ola en la superficie."""
        if lvl is None:
            return
        lvl = max(0.0, min(1.0, lvl))
        mask = Image.new("L", (S, S), 0)
        ImageDraw.Draw(mask).polygon([P(x, y) for x, y in points], fill=255)
        y_surf = bottom - (bottom - top) * lvl
        water = Image.new("L", (S, S), 0)
        wd = ImageDraw.Draw(water)
        wave = [P(x / 40, y_surf + 0.012 * math.sin(x / 40 * 18)) for x in range(41)]
        wd.polygon(wave + [P(1, 1), P(0, 1)], fill=255)
        from PIL import ImageChops
        m = ImageChops.multiply(mask, water)
        layer = Image.new("RGBA", (S, S), fill)
        img.paste(layer, (0, 0), m)

    if name == "sed":  # gota de agua
        pts = []
        for k in range(121):
            t = 2 * math.pi * k / 120
            pts.append((0.5 + 0.33 * math.sin(t) * abs(math.sin(t / 2)) ** 1.25, 0.52 - 0.42 * math.cos(t)))
        poly(pts, fill=soft)
        fill_level(pts, level, 0.10, 0.94, col + (215,))
        poly(pts, outline=full)
        d.arc([*P(0.33, 0.56), *P(0.55, 0.80)], 110, 200, fill=white, width=max(2, lw // 2))
    elif name == "hambre":  # tenedor y cuchillo
        for x in (0.27, 0.335, 0.40):  # púas
            d.rounded_rectangle([*P(x - 0.018, 0.12), *P(x + 0.018, 0.38)], radius=lw, fill=full)
        d.rounded_rectangle([*P(0.25, 0.33), *P(0.42, 0.44)], radius=int(S * 0.05), fill=full)
        d.rounded_rectangle([*P(0.305, 0.40), *P(0.365, 0.90)], radius=int(S * 0.03), fill=full)
        blade = [(0.60, 0.54), (0.60, 0.16), (0.64, 0.11), (0.71, 0.20), (0.73, 0.36), (0.72, 0.54)]
        poly(blade, fill=full)
        d.rounded_rectangle([*P(0.60, 0.50), *P(0.71, 0.90)], radius=int(S * 0.035), fill=full)
        d.line([P(0.645, 0.18), P(0.645, 0.48)], fill=soft, width=max(1, lw // 2))
    elif name == "oxigeno":  # burbuja con O₂
        d.ellipse([*P(0.10, 0.18), *P(0.78, 0.86)], fill=soft, outline=full, width=lw)
        for cx, cy, r in ((0.80, 0.16, 0.07), (0.88, 0.32, 0.045), (0.70, 0.06, 0.035)):
            d.ellipse([*P(cx - r, cy - r), *P(cx + r, cy + r)], outline=full, width=max(2, lw * 2 // 3))
        f = _font(int(S * 0.30))
        d.text(P(0.42, 0.53), "O", font=f, fill=white, anchor="mm")
        f2 = _font(int(S * 0.16))
        d.text(P(0.60, 0.64), "2", font=f2, fill=white, anchor="mm")
    elif name == "salud":  # corazón con electrocardiograma
        pts = []
        for k in range(121):
            t = 2 * math.pi * k / 120
            x = 16 * math.sin(t) ** 3
            y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
            pts.append((0.5 + x / 38, 0.47 - y / 38))
        poly(pts, fill=soft, outline=full)
        ecg = [(0.08, 0.52), (0.30, 0.52), (0.37, 0.40), (0.44, 0.68), (0.52, 0.24), (0.59, 0.60), (0.64, 0.52),
               (0.92, 0.52)]
        d.line([P(x, y) for x, y in ecg], fill=white, width=max(2, int(lw * 0.8)), joint="curve")
    elif name == "hidrogeno":  # depósito de combustible con H₂
        body = [(0.26, 0.28), (0.74, 0.28), (0.74, 0.86), (0.26, 0.86)]
        d.rounded_rectangle([*P(0.26, 0.24), *P(0.74, 0.90)], radius=int(S * 0.08), fill=soft)
        fill_level(body, level, 0.26, 0.88, col + (215,))
        d.rounded_rectangle([*P(0.26, 0.24), *P(0.74, 0.90)], radius=int(S * 0.08), outline=full, width=lw)
        d.rounded_rectangle([*P(0.40, 0.10), *P(0.60, 0.24)], radius=int(S * 0.03), fill=full)
        d.line([P(0.60, 0.17), P(0.80, 0.17), P(0.80, 0.30)], fill=full, width=lw, joint="curve")
        f = _font(int(S * 0.24))
        d.text(P(0.47, 0.58), "H", font=f, fill=white, anchor="mm")
        d.text(P(0.61, 0.65), "2", font=_font(int(S * 0.13)), fill=white, anchor="mm")
    elif name == "cuantico":  # átomo: tres órbitas y núcleo
        for rot in (0, 60, 120):
            a = math.radians(rot)
            pts = []
            for k in range(73):
                t = 2 * math.pi * k / 72
                x, y = 0.40 * math.cos(t), 0.15 * math.sin(t)
                pts.append((0.5 + x * math.cos(a) - y * math.sin(a), 0.5 + x * math.sin(a) + y * math.cos(a)))
            d.line([P(x, y) for x, y in pts], fill=full, width=max(2, int(lw * 0.8)), joint="curve")
        d.ellipse([*P(0.42, 0.42), *P(0.58, 0.58)], fill=white)
        for rot, t in ((0, 0.7), (60, 2.6), (120, 4.6)):  # electrones
            a = math.radians(rot)
            x, y = 0.40 * math.cos(t), 0.15 * math.sin(t)
            cx, cy = 0.5 + x * math.cos(a) - y * math.sin(a), 0.5 + x * math.sin(a) + y * math.cos(a)
            d.ellipse([*P(cx - 0.035, cy - 0.035), *P(cx + 0.035, cy + 0.035)], fill=full)
    elif name == "escudos":  # escudo (roto si han caído)
        def bez(p0, p1, p2, n=20):
            return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                     (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in (k / n for k in range(n + 1))]
        pts = [(0.5, 0.08)] + bez((0.5, 0.08), (0.70, 0.18), (0.84, 0.18)) + bez((0.84, 0.18), (0.86, 0.68), (0.5, 0.92)) \
            + bez((0.5, 0.92), (0.14, 0.68), (0.16, 0.18)) + bez((0.16, 0.18), (0.30, 0.18), (0.5, 0.08))
        if broken:
            left = [p for p in pts if p[0] <= 0.5]
            crack = [(0.5, 0.08), (0.44, 0.30), (0.55, 0.45), (0.45, 0.62), (0.52, 0.92)]
            poly(pts, fill=col + (40,))
            d.line([P(x, y) for x, y in pts + [pts[0]]], fill=col + (150,), width=max(2, lw * 2 // 3), joint="curve")
            d.line([P(x - 0.03, y) for x, y in crack], fill=white, width=lw, joint="curve")
            d.line([P(x + 0.03, y) for x, y in crack], fill=white, width=lw, joint="curve")
            del left
        else:
            poly(pts, fill=soft, outline=full)
            inner = [(0.5 + (x - 0.5) * 0.7, 0.5 + (y - 0.5) * 0.7) for x, y in pts]
            d.line([P(x, y) for x, y in inner + [inner[0]]], fill=col + (180,), width=max(2, lw // 2), joint="curve")
    elif name == "casco":  # nave vista desde arriba (con grieta si está dañada)
        ship = [(0.5, 0.06), (0.60, 0.34), (0.88, 0.60), (0.88, 0.72), (0.60, 0.66), (0.58, 0.88), (0.5, 0.82),
                (0.42, 0.88), (0.40, 0.66), (0.12, 0.72), (0.12, 0.60), (0.40, 0.34)]
        poly(ship, fill=soft, outline=full)
        d.ellipse([*P(0.45, 0.24), *P(0.55, 0.40)], fill=white)
        if broken:
            crack = [(0.24, 0.62), (0.34, 0.56), (0.40, 0.64), (0.50, 0.52), (0.58, 0.62), (0.66, 0.56), (0.76, 0.64)]
            d.line([P(x, y) for x, y in crack], fill=white, width=lw, joint="curve")
    elif name == "averia":  # triángulo de advertencia
        tri = [(0.5, 0.08), (0.94, 0.88), (0.06, 0.88)]
        poly(tri, fill=soft)
        d.line([P(x, y) for x, y in tri + [tri[0]]], fill=full, width=int(lw * 1.3), joint="curve")
        d.rounded_rectangle([*P(0.46, 0.34), *P(0.54, 0.64)], radius=int(S * 0.03), fill=white)
        d.ellipse([*P(0.455, 0.70), *P(0.545, 0.79)], fill=white)
    elif name == "misil":  # misil en la mira
        d.ellipse([*P(0.08, 0.08), *P(0.92, 0.92)], outline=full, width=lw)
        d.ellipse([*P(0.22, 0.22), *P(0.78, 0.78)], outline=col + (130,), width=max(2, lw // 2))
        for (x0, y0, x1, y1) in ((0.5, 0.0, 0.5, 0.16), (0.5, 0.84, 0.5, 1.0), (0.0, 0.5, 0.16, 0.5), (0.84, 0.5, 1.0, 0.5)):
            d.line([P(x0, y0), P(x1, y1)], fill=full, width=lw)
        a = math.radians(-45)

        def rot(x, y):
            x, y = x - 0.5, y - 0.5
            return (0.5 + x * math.cos(a) - y * math.sin(a), 0.5 + x * math.sin(a) + y * math.cos(a))
        missile = [(0.5, 0.18), (0.56, 0.28), (0.56, 0.66), (0.64, 0.76), (0.64, 0.82), (0.56, 0.78), (0.56, 0.82),
                   (0.44, 0.82), (0.44, 0.78), (0.36, 0.82), (0.36, 0.76), (0.44, 0.66), (0.44, 0.28)]
        poly([rot(x, y) for x, y in missile], fill=white)
    else:
        d.ellipse([*P(0.15, 0.15), *P(0.85, 0.85)], outline=full, width=lw)
    return img.resize((size, size), Image.LANCZOS)

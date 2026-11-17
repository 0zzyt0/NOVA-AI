"""v2.0: temas de color de la ventana.

La interfaz está pintada en tonos cian. Un tema gira el tono de todos esos colores (los de acento y los azules
oscuros del fondo) hacia otro color, conservando su luz y transparencia; los colores de estado (verde de «bien»,
amarillo de aviso, rojo de error, morado de memoria) no se tocan para que sigan significando lo mismo.
"""
from __future__ import annotations

import colorsys
import re

# id: (nombre, tono de destino en grados o None = sin cambio, factor de saturación)
THEMES: dict[str, tuple[str, float | None, float]] = {
    "cian": ("Cian holográfico", None, 1.0),
    "ambar": ("Ámbar de cabina", 36, 1.0),
    "verde": ("Verde táctico", 145, 0.9),
    "carmesi": ("Carmesí", 352, 0.95),
    "violeta": ("Violeta cuántico", 272, 0.95),
    "oro": ("Oro de la UEE", 46, 0.8),
    "plata": ("Plata y hielo", 205, 0.22),
}
BASE_HUE = 196  # el cian de NOVA (#20b8e8)

_HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
_RGB = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(,\s*[\d.]+\s*)?\)")


def _shift(r: int, g: int, b: int, hue: float | None, sat: float) -> tuple[int, int, int] | None:
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    deg = h * 360
    if s < 0.12 or not (165 <= deg <= 228):  # solo la familia cian/azul de la interfaz
        return None
    new_h = ((hue if hue is not None else deg) + (deg - BASE_HUE) * 0.35) % 360
    rr, gg, bb = colorsys.hls_to_rgb(new_h / 360, l, max(0.0, min(1.0, s * sat)))
    return round(rr * 255), round(gg * 255), round(bb * 255)


def recolor(css: str, theme: str) -> str:
    """Cambia los colores cian del CSS por los del tema."""
    name, hue, sat = THEMES.get(theme, THEMES["cian"])
    if hue is None and sat == 1.0:
        return css

    def hex_sub(m: re.Match) -> str:
        v = m.group(1)
        if len(v) == 3:
            v = "".join(c * 2 for c in v)
        r, g, b = (int(v[i:i + 2], 16) for i in (0, 2, 4))
        out = _shift(r, g, b, hue, sat)
        return m.group(0) if out is None else "#%02x%02x%02x" % out

    def rgb_sub(m: re.Match) -> str:
        r, g, b = (int(m.group(i)) for i in (1, 2, 3))
        out = _shift(r, g, b, hue, sat)
        if out is None:
            return m.group(0)
        alpha = m.group(4) or ""
        return f"rgba({out[0]},{out[1]},{out[2]}{alpha})" if alpha else f"rgb({out[0]},{out[1]},{out[2]})"

    return _RGB.sub(rgb_sub, _HEX.sub(hex_sub, css))


def recolor_html(html: str, theme: str) -> str:
    """En el HTML solo se tocan los bloques <style> y los atributos style="…" (no los enlaces #ancla)."""
    if theme not in THEMES or THEMES[theme][1] is None and THEMES[theme][2] == 1.0:
        return html
    html = re.sub(r"(<style[^>]*>)(.*?)(</style>)", lambda m: m.group(1) + recolor(m.group(2), theme) + m.group(3),
                  html, flags=re.S | re.I)
    return re.sub(r'(style=")([^"]*)(")', lambda m: m.group(1) + recolor(m.group(2), theme) + m.group(3), html)


def theme_list() -> list[dict]:
    from .i18n import tr

    out = []
    for k, (name, hue, sat) in THEMES.items():
        sample = "#20b8e8" if hue is None else recolor("#20b8e8", k)
        out.append({"id": k, "nombre": tr(name), "muestra": sample})
    return out

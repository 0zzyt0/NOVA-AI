"""Iconos de NOVA AI: programa, instalador (flecha) y desinstalador (aspa roja)."""
import sys, importlib.util
from PIL import Image, ImageDraw, ImageFilter
spec = importlib.util.spec_from_file_location("mk", __file__.replace("make_icons2.py", "make_icon.py"))
src = open(spec.origin, encoding="utf-8").read().split("img = render()")[0]
ns = {}; exec(src, ns); render = ns["render"]; S = ns["S"]
SIZES = [(16,16),(20,20),(24,24),(32,32),(40,40),(48,48),(64,64),(128,128),(256,256)]

def badge(base, kind):
    img = base.copy()
    r = S * 0.25; cx = cy = S - r - S*0.015
    sh = Image.new("RGBA", (S, S), (0,0,0,0)); d = ImageDraw.Draw(sh)
    d.ellipse([cx-r-S*0.03, cy-r-S*0.03, cx+r+S*0.03, cy+r+S*0.03], fill=(2, 6, 12, 255))
    img = Image.alpha_composite(img, sh)
    b = Image.new("RGBA", (S, S), (0,0,0,0)); d = ImageDraw.Draw(b)
    if kind == "x":
        fill, ring = (214, 52, 70, 255), (255, 140, 150, 255)
    else:
        fill, ring = (24, 150, 205, 255), (150, 230, 255, 255)
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=fill, outline=ring, width=int(S*0.018))
    w = int(S*0.06); k = r*0.48; white = (255, 255, 255, 255)
    if kind == "x":
        d.line([cx-k, cy-k, cx+k, cy+k], fill=white, width=w)
        d.line([cx-k, cy+k, cx+k, cy-k], fill=white, width=w)
    else:
        d.line([cx, cy-k*1.15, cx, cy+k*0.35], fill=white, width=w)
        d.polygon([(cx-k*0.95, cy-k*0.05), (cx+k*0.95, cy-k*0.05), (cx, cy+k*1.05)], fill=white)
    return Image.alpha_composite(img, b)

out = sys.argv[1]
base = render()
for name, im in (("nova", base), ("nova_instalar", badge(base, "arrow")), ("nova_desinstalar", badge(base, "x"))):
    im256 = im.resize((256, 256), Image.LANCZOS)
    im256.save(f"{out}/{name}.ico", sizes=SIZES)
    im256.save(f"/tmp/{name}_256.png")
print("ok")

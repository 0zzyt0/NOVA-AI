import math, sys
from PIL import Image, ImageDraw, ImageFilter
S = 1024
def render():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = S / 2
    # disco de fondo
    for r in range(int(S*0.48), 0, -4):
        t = r / (S*0.48)
        col = (int(6 + 14*(1-t)), int(14 + 40*(1-t)), int(26 + 60*(1-t)), 255)
        d.ellipse([c-r, c-r, c+r, c+r], fill=col)
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0)); g = ImageDraw.Draw(glow)
    cyan = (32, 184, 232, 255); soft = (111, 216, 255, 255)
    # anillo exterior y marcas
    g.ellipse([c-S*0.44, c-S*0.44, c+S*0.44, c+S*0.44], outline=cyan, width=int(S*0.018))
    for i in range(48):
        a = i / 48 * 2 * math.pi
        r1, r2 = S*0.36, S*(0.40 if i % 4 else 0.415)
        g.line([c+r1*math.sin(a), c-r1*math.cos(a), c+r2*math.sin(a), c-r2*math.cos(a)], fill=soft, width=int(S*0.008))
    # arco de progreso
    g.arc([c-S*0.30, c-S*0.30, c+S*0.30, c+S*0.30], start=-90, end=200, fill=soft, width=int(S*0.035))
    # rombo central
    k = S*0.17
    g.polygon([(c, c-k), (c+k*0.72, c), (c, c+k), (c-k*0.72, c)], fill=soft)
    g.polygon([(c, c-k*0.45), (c+k*0.32, c), (c, c+k*0.45), (c-k*0.32, c)], fill=(10, 30, 50, 255))
    blur = glow.filter(ImageFilter.GaussianBlur(S*0.02))
    img = Image.alpha_composite(img, blur)
    img = Image.alpha_composite(img, glow)
    # recorte circular limpio
    mask = Image.new("L", (S, S), 0); ImageDraw.Draw(mask).ellipse([S*0.02, S*0.02, S*0.98, S*0.98], fill=255)
    img.putalpha(Image.composite(img.getchannel("A"), Image.new("L", (S, S), 0), mask))
    return img
img = render()
out = sys.argv[1]
img.resize((256, 256), Image.LANCZOS).save(out + "/nova.ico", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
img.resize((256, 256), Image.LANCZOS).save(out + "/nova.png")
print("ok")

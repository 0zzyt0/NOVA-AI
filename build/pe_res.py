"""Lee los recursos de un .exe (PE32+) para comprobar icono, manifiesto y versión."""
import struct, sys, io, re

def parse(path):
    d = open(path, "rb").read()
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    assert d[pe:pe+4] == b"PE\0\0"
    nsec = struct.unpack_from("<H", d, pe+6)[0]; optsz = struct.unpack_from("<H", d, pe+20)[0]
    opt = pe + 24; magic = struct.unpack_from("<H", d, opt)[0]; assert magic == 0x20B
    subsystem = struct.unpack_from("<H", d, opt+68)[0]
    dd = opt + 112
    rva, size = struct.unpack_from("<II", d, dd + 8*2)
    secs = []
    for i in range(nsec):
        s = pe + 24 + optsz + 40*i
        name = d[s:s+8].rstrip(b"\0").decode(); vs, va, rs, rp = struct.unpack_from("<IIII", d, s+8)
        secs.append((name, va, max(vs, rs), rp))
    def off(r):
        for n, va, sz, rp in secs:
            if va <= r < va+sz: return rp + r - va
        raise ValueError(hex(r))
    base = off(rva); res = {}
    def walk(o, path):
        _, _, _, _, nn, ni = struct.unpack_from("<IIHHHH", d, base+o)
        for k in range(nn+ni):
            name, ofs = struct.unpack_from("<II", d, base+o+16+8*k)
            if ofs & 0x80000000: walk(ofs & 0x7FFFFFFF, path+[name])
            else:
                drva, dsz = struct.unpack_from("<II", d, base+ofs)
                res[tuple(path+[name])] = d[off(drva):off(drva)+dsz]
    walk(0, [])
    return subsystem, [s[0] for s in secs], res

def ico_from(res):
    g = next(v for k, v in res.items() if k[0] == 14)
    _, _, n = struct.unpack_from("<HHH", g, 0)
    ents = [struct.unpack_from("<BBBBHHIH", g, 6+14*i) for i in range(n)]
    icons = {k[1]: v for k, v in res.items() if k[0] == 3}
    out = struct.pack("<HHH", 0, 1, n); data = b""; o = 6 + 16*n
    for w, h, cc, r, pl, bpp, sz, iid in ents:
        blob = icons[iid]; assert len(blob) == sz
        out += struct.pack("<BBBBHHII", w, h, cc, r, pl, bpp, sz, o + len(data)); data += blob
    return out + data

def version_strings(v):
    s = v.decode("utf-16-le", "ignore")
    keys = ["CompanyName","FileDescription","FileVersion","OriginalFilename","ProductName","ProductVersion"]
    out = {}
    for k in keys:
        m = re.search(k + r"\x00+([^\x00]+)", s)
        if m: out[k] = m.group(1)
    fixed = v.find(struct.pack("<I", 0xFEEF04BD))
    ms, ls = struct.unpack_from("<II", v, fixed+8)
    out["fixed"] = f"{ms>>16}.{ms&0xFFFF}.{ls>>16}.{ls&0xFFFF}"
    out["wLength_ok"] = struct.unpack_from("<H", v, 0)[0] == len(v)
    return out

if __name__ == "__main__":
    from PIL import Image
    for p in sys.argv[1:]:
        sub, secs, res = parse(p)
        man = next(v for k, v in res.items() if k[0] == 24).decode()
        lvl = re.search(r'level="(\w+)"', man).group(1)
        ico = ico_from(res)
        im = Image.open(io.BytesIO(ico)); 
        print(p, "| subsistema", "GUI" if sub == 2 else sub, "| secciones", secs)
        print("   tipos:", sorted({k[0] for k in res}), "| idioma", hex(next(iter(res))[2]), "| icono tamaños", sorted(im.info["sizes"]), "| manifiesto", lvl)
        print("   versión:", version_strings(next(v for k, v in res.items() if k[0] == 16)))
        open("/tmp/" + p.split("/")[-1] + ".ico", "wb").write(ico)

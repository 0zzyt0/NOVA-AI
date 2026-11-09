"""Generador propio de recursos de Windows (.syso COFF) para enlazar con Go.

Escribe un objeto COFF amd64 con una sección .rsrc que contiene:
  RT_ICON + RT_GROUP_ICON (desde un .ico), RT_MANIFEST y RT_VERSION.
Las direcciones de los datos se resuelven con relocalizaciones IMAGE_REL_AMD64_ADDR32NB
(igual que hacen los generadores habituales), el enlazador de Go las aplica al montar el .exe.

Uso:  python3 winres.py salida.syso icono.ico manifest.xml version.json
"""
import json, struct, sys

RT_ICON, RT_GROUP_ICON, RT_VERSION, RT_MANIFEST = 3, 14, 16, 24
LANG = 0x0C0A  # español (alfabetización internacional)


def read_ico(path):
    data = open(path, "rb").read()
    _, typ, count = struct.unpack_from("<HHH", data, 0)
    assert typ == 1, "no es un .ico"
    imgs = []
    for i in range(count):
        w, h, cc, res, planes, bpp, size, off = struct.unpack_from("<BBBBHHII", data, 6 + 16 * i)
        imgs.append(((w, h, cc, res, planes, bpp), data[off:off + size]))
    return imgs


def group_icon(imgs):
    out = struct.pack("<HHH", 0, 1, len(imgs))
    for i, ((w, h, cc, res, planes, bpp), blob) in enumerate(imgs, 1):
        out += struct.pack("<BBBBHHIH", w, h, cc, res, planes or 1, bpp or 32, len(blob), i)
    return out


# ------------------------------------------------------------------ VERSIONINFO
def _pad4(b):
    return b + b"\0" * (-len(b) % 4)


def _block(key, value=b"", children=(), wtype=1, vlen=None):
    """Bloque de VS_VERSIONINFO: wLength, wValueLength, wType, szKey, relleno, Value, relleno, hijos."""
    b = b"\0" * 6 + (key + "\0").encode("utf-16-le")
    b = _pad4(b) + value
    for ch in children:
        b = _pad4(b) + ch
    if vlen is None:
        vlen = len(value)
    return struct.pack("<HHH", len(b), vlen, wtype) + b[6:]


def _ver4(s):
    p = [int(x) for x in (s.split(".") + ["0"] * 4)[:4]]
    return (p[0] << 16) | p[1], (p[2] << 16) | p[3]


def version_info(v):
    fms, fls = _ver4(v["file_version"])
    pms, pls = _ver4(v.get("product_version", v["file_version"]))
    fixed = struct.pack("<13I", 0xFEEF04BD, 0x00010000, fms, fls, pms, pls,
                        0x3F, 0, 0x00040004, 0x1, 0, 0, 0)  # VOS_NT_WINDOWS32, VFT_APP
    cp = "%04X04B0" % LANG
    strings = []
    for key in ("CompanyName", "FileDescription", "FileVersion", "InternalName", "LegalCopyright",
                "OriginalFilename", "ProductName", "ProductVersion", "Comments"):
        if v.get(key):
            val = (v[key] + "\0").encode("utf-16-le")
            strings.append(_block(key, val, wtype=1, vlen=len(val) // 2))
    table = _block(cp, children=strings, wtype=1)
    sfi = _block("StringFileInfo", children=[table], wtype=1)
    var = _block("Translation", struct.pack("<HH", LANG, 0x04B0), wtype=0)
    vfi = _block("VarFileInfo", children=[var], wtype=1)
    return _block("VS_VERSION_INFO", fixed, [sfi, vfi], wtype=0)


# ------------------------------------------------------------------ .rsrc + COFF
def build_rsrc(resources):
    """resources: {type: {id: bytes}} -> (sección, [offsets a relocalizar])."""
    types = sorted(resources)
    # tamaños del árbol: raíz + un directorio por tipo + uno por id (nivel idioma)
    n_ids = sum(len(resources[t]) for t in types)
    dir_size = 16 + 8 * len(types) + sum(16 + 8 * len(resources[t]) for t in types) + n_ids * (16 + 8)
    entries_off = dir_size
    data_off = entries_off + 16 * n_ids
    tree = bytearray()
    leaves, blobs, relocs = [], bytearray(), []
    # raíz
    tree += struct.pack("<IIHHHH", 0, 0, 0, 0, 0, len(types))
    type_dirs_off = 16 + 8 * len(types)
    cur = type_dirs_off
    type_offs = []
    for t in types:
        type_offs.append(cur)
        cur += 16 + 8 * len(resources[t])
    lang_off = cur
    for t, off in zip(types, type_offs):
        tree += struct.pack("<II", t, 0x80000000 | off)
    leaf_i = 0
    lang_dirs = []
    for t in types:
        ids = sorted(resources[t])
        tree += struct.pack("<IIHHHH", 0, 0, 0, 0, 0, len(ids))
        for rid in ids:
            tree += struct.pack("<II", rid, 0x80000000 | (lang_off + 24 * len(lang_dirs)))
            lang_dirs.append((t, rid))
    for t, rid in lang_dirs:
        tree += struct.pack("<IIHHHH", 0, 0, 0, 0, 0, 1)
        tree += struct.pack("<II", LANG, entries_off + 16 * leaf_i)
        blob = resources[t][rid]
        pos = data_off + len(blobs)
        leaves.append(struct.pack("<IIII", pos, len(blob), 0, 0))
        relocs.append(entries_off + 16 * leaf_i)
        blobs += blob + b"\0" * (-len(blob) % 8)
        leaf_i += 1
    assert len(tree) == dir_size, (len(tree), dir_size)
    return bytes(tree) + b"".join(leaves) + bytes(blobs), relocs


def coff(section, relocs):
    hdr_size, sec_hdr = 20, 40
    raw_ptr = hdr_size + sec_hdr
    rel_ptr = raw_ptr + len(section)
    sym_ptr = rel_ptr + 10 * len(relocs)
    out = struct.pack("<HHIIIHH", 0x8664, 1, 0, sym_ptr, 1, 0, 0)
    out += struct.pack("<8sIIIIIIHHI", b".rsrc", 0, 0, len(section), raw_ptr, rel_ptr, 0,
                       len(relocs), 0, 0x40000040)
    out += section
    for r in relocs:
        out += struct.pack("<IIH", r, 0, 0x0003)  # IMAGE_REL_AMD64_ADDR32NB contra el símbolo 0 (.rsrc)
    out += struct.pack("<8sIhHBB", b".rsrc", 0, 1, 0, 3, 0)  # símbolo de sección, IMAGE_SYM_CLASS_STATIC
    out += struct.pack("<I", 4)  # tabla de cadenas vacía
    return out


def build(out, ico, manifest, version):
    imgs = read_ico(ico)
    res = {
        RT_ICON: {i: blob for i, (_, blob) in enumerate(imgs, 1)},
        RT_GROUP_ICON: {1: group_icon(imgs)},
        RT_MANIFEST: {1: open(manifest, "rb").read()},
        RT_VERSION: {1: version_info(version)},
    }
    sec, rel = build_rsrc(res)
    open(out, "wb").write(coff(sec, rel))
    return len(imgs)


if __name__ == "__main__":
    o, ico, man, ver = sys.argv[1:5]
    n = build(o, ico, man, json.load(open(ver, encoding="utf-8")))
    print(f"{o}: {n} iconos + manifiesto + versión")

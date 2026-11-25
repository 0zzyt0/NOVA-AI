"""Esquema de la telemetría local de Star Citizen, sacado del propio StarCitizen.exe.

El juego no publica el .proto ni ofrece «reflection» en su servidor gRPC, pero lleva dentro del
ejecutable los descriptores protobuf serializados (los genera el compilador de C++). Aquí se buscan,
se validan con la librería protobuf y se guardan en un FileDescriptorSet en caché por build, así
NOVA siempre usa los nombres de campo de la versión que tienes instalada (LIVE o PTU).

Solo se lee el ejecutable: no se modifica nada del juego.
"""
from __future__ import annotations

import hashlib
import json
import logging
import mmap
import re
from pathlib import Path

log = logging.getLogger("nova.telemetry")

SERVICE = "sc.game.telemetry.v1.GameTelemetryService"
PACKAGE_PREFIX = b"sc.game.telemetry"
# Campos válidos de FileDescriptorProto: número -> tipo de cable (0 varint, 2 bytes con longitud)
_FDP_FIELDS = {1: 2, 2: 2, 3: 2, 4: 2, 5: 2, 6: 2, 7: 2, 8: 2, 9: 2, 10: 0, 11: 0, 12: 2, 14: 0}
_NAME_RX = re.compile(rb"\x0a([\x05-\x7f])([A-Za-z0-9_/.\-]{1,126}?\.proto)\x12")


def _varint(buf, pos: int, end: int) -> tuple[int, int]:
    val = shift = 0
    while pos < end:
        b = buf[pos]
        pos += 1
        val |= (b & 0x7F) << shift
        if not b & 0x80:
            return val, pos
        shift += 7
        if shift > 63:
            break
    raise ValueError("varint")


def _scan_fdp(buf, start: int, limit: int = 4_000_000) -> int:
    """Recorre campos de un FileDescriptorProto desde start y devuelve dónde deja de ser válido."""
    end = min(len(buf), start + limit)
    pos = start
    last_ok = start
    while pos < end:
        try:
            tag, p = _varint(buf, pos, end)
        except ValueError:
            break
        field, wt = tag >> 3, tag & 7
        if _FDP_FIELDS.get(field) != wt:
            break
        try:
            if wt == 0:
                _, p = _varint(buf, p, end)
            else:
                ln, p = _varint(buf, p, end)
                if ln > end - p:
                    break
                p += ln
        except ValueError:
            break
        pos = last_ok = p
    return last_ok


def _candidates(data) -> list[bytes]:
    """Trozos del ejecutable que parecen FileDescriptorProto de la telemetría o de sus dependencias."""
    out: list[bytes] = []
    for m in _NAME_RX.finditer(data):
        if int(m.group(1)[0]) != len(m.group(2)):
            continue
        start = m.start()
        stop = _scan_fdp(data, start)
        if stop - start > 40:
            out.append(bytes(data[start:stop]))
    return out


def extract(exe: Path) -> bytes:
    """Devuelve un FileDescriptorSet serializado con los .proto de la telemetría (y sus dependencias)."""
    from google.protobuf import descriptor_pb2

    with open(exe, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as data:
        raw = _candidates(data)
    files: dict[str, descriptor_pb2.FileDescriptorProto] = {}
    for blob in raw:
        fdp = descriptor_pb2.FileDescriptorProto()
        # El escaneo puede pasarse unos bytes: se recorta hasta que protobuf lo acepte.
        for cut in range(len(blob), max(len(blob) - 64, 0), -1):
            try:
                fdp.ParseFromString(blob[:cut])
                break
            except Exception:
                fdp.Clear()
        if fdp.name and fdp.name not in files:
            files[fdp.name] = fdp
    wanted = {n for n, f in files.items() if f.package.startswith(PACKAGE_PREFIX.decode())}
    if not wanted:
        raise RuntimeError("No se ha encontrado el esquema de telemetría en el ejecutable")
    # Cierre de dependencias (los tipos bien conocidos de Google los aporta la propia librería).
    todo = list(wanted)
    while todo:
        for dep in files[todo.pop()].dependency:
            if dep in files and dep not in wanted and not dep.startswith("google/protobuf/"):
                wanted.add(dep)
                todo.append(dep)
    fds = descriptor_pb2.FileDescriptorSet()
    done: set[str] = set()

    def add(name: str) -> None:
        if name in done or name not in wanted:
            return
        done.add(name)
        for dep in files[name].dependency:
            add(dep)
        fds.file.append(files[name])

    for n in sorted(wanted):
        add(n)
    return fds.SerializeToString()


def build_id(channel_dir: Path) -> str:
    """Identificador de la build (versión del manifiesto o, si no hay, huella del exe)."""
    try:
        d = json.loads((channel_dir / "build_manifest.id").read_text(encoding="utf-8", errors="replace"))["Data"]
        return f"{d.get('Version', '')}-{d.get('RequestedP4ChangeNum', '')}".strip("-") or "desconocida"
    except Exception:
        exe = channel_dir / "Bin64" / "StarCitizen.exe"
        st = exe.stat()
        return hashlib.sha1(f"{st.st_size}-{int(st.st_mtime)}".encode()).hexdigest()[:12]


def load_or_extract(channel_dir: Path, cache_dir: Path) -> tuple[bytes, str]:
    """FileDescriptorSet para el canal (LIVE/PTU…) indicado, con caché por build."""
    bid = re.sub(r"[^A-Za-z0-9_.\-]", "_", build_id(channel_dir))
    cache = cache_dir / f"sc_telemetry_{bid}.desc"
    if cache.exists() and cache.stat().st_size > 100:
        return cache.read_bytes(), bid
    exe = channel_dir / "Bin64" / "StarCitizen.exe"
    blob = extract(exe)
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(blob)
        for old in cache_dir.glob("sc_telemetry_*.desc"):
            if old != cache and old.stat().st_mtime < cache.stat().st_mtime - 30 * 86400:
                old.unlink(missing_ok=True)
    except OSError:
        log.warning("No se pudo guardar la caché del esquema de telemetría")
    return blob, bid


def to_proto_text(blob: bytes) -> str:
    """Vista legible (tipo .proto) del esquema: para diagnóstico y para el informe."""
    from google.protobuf import descriptor_pb2

    fds = descriptor_pb2.FileDescriptorSet()
    fds.ParseFromString(blob)
    lab = {1: "optional ", 2: "required ", 3: "repeated "}
    types = {1: "double", 2: "float", 3: "int64", 4: "uint64", 5: "int32", 6: "fixed64", 7: "fixed32", 8: "bool",
             9: "string", 12: "bytes", 13: "uint32", 15: "sfixed32", 16: "sfixed64", 17: "sint32", 18: "sint64"}
    lines: list[str] = []

    def msg(m, ind: str) -> None:
        lines.append(f"{ind}message {m.name} {{")
        for e in m.enum_type:
            enum(e, ind + "  ")
        for n in m.nested_type:
            if n.options.map_entry:
                continue
            msg(n, ind + "  ")
        for fl in m.field:
            t = fl.type_name.rsplit(".", 1)[-1] if fl.type_name else types.get(fl.type, str(fl.type))
            oneof = f"  // oneof {m.oneof_decl[fl.oneof_index].name}" if fl.HasField("oneof_index") and not fl.proto3_optional else ""
            label = "optional " if fl.proto3_optional else (lab.get(fl.label, "") if fl.label == 3 else "")
            lines.append(f"{ind}  {label}{t} {fl.name} = {fl.number};{oneof}")
        lines.append(f"{ind}}}")

    def enum(e, ind: str) -> None:
        lines.append(f"{ind}enum {e.name} {{ " + ", ".join(f"{v.name}={v.number}" for v in e.value) + " }")

    for f in fds.file:
        lines.append(f"// {f.name}  (package {f.package})")
        for e in f.enum_type:
            enum(e, "")
        for m in f.message_type:
            msg(m, "")
        for s in f.service:
            lines.append(f"service {s.name} {{")
            for r in s.method:
                ss = "stream " if r.server_streaming else ""
                lines.append(f"  rpc {r.name}({r.input_type.rsplit('.', 1)[-1]}) returns ({ss}{r.output_type.rsplit('.', 1)[-1]});")
            lines.append("}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":  # python -m core.telemetry_schema "E:\...\StarCitizen\PTU"
    import sys

    ch = Path(sys.argv[1])
    b, bid = load_or_extract(ch, Path(sys.argv[2]) if len(sys.argv) > 2 else Path("."))
    print(f"build {bid}: {len(b)} bytes")
    print(to_proto_text(b))

"""Cofre de las claves de fábrica de NOVA AI.

Las claves gratuitas que trae el programa base van cifradas en `recursos/claves_iniciales.enc`:
- cifrado autenticado hecho solo con la biblioteca estándar: flujo HMAC-SHA256 en modo contador
  (como un CTR) + etiqueta HMAC-SHA256 sobre todo el archivo (cifrar y después autenticar);
- la llave se deriva con PBKDF2-HMAC-SHA256 (200 000 vueltas) a partir de la llave maestra
  `recursos/llave_claves.bin`, que NO está en el repositorio: solo viaja dentro del instalador oficial.

Sin la llave maestra, el archivo cifrado no sirve de nada (por eso el código puede ser público).
Aviso honesto: el programa necesita poder usar las claves, así que quien tenga el instalador oficial
tiene también la llave. Ningún programa puede esconder del todo una clave que él mismo usa.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path

MAGIC = b"NOVAK1"
ITER = 200_000


def _keys(master: bytes, salt: bytes) -> tuple[bytes, bytes]:
    root = hashlib.pbkdf2_hmac("sha256", master, salt, ITER, dklen=32)
    return hmac.new(root, b"cifrado", hashlib.sha256).digest(), hmac.new(root, b"autenticacion", hashlib.sha256).digest()


def _stream(key: bytes, nonce: bytes, n: int) -> bytes:
    out = bytearray()
    i = 0
    while len(out) < n:
        out += hmac.new(key, nonce + i.to_bytes(8, "big"), hashlib.sha256).digest()
        i += 1
    return bytes(out[:n])


def encrypt(data: bytes, master: bytes) -> bytes:
    salt, nonce = os.urandom(16), os.urandom(16)
    ek, mk = _keys(master, salt)
    ct = bytes(a ^ b for a, b in zip(data, _stream(ek, nonce, len(data))))
    body = MAGIC + salt + nonce + ct
    return body + hmac.new(mk, body, hashlib.sha256).digest()


def decrypt(blob: bytes, master: bytes) -> bytes:
    if len(blob) < len(MAGIC) + 32 + 32 or not blob.startswith(MAGIC):
        raise ValueError("formato desconocido")
    body, tag = blob[:-32], blob[-32:]
    salt, nonce = body[6:22], body[22:38]
    ek, mk = _keys(master, salt)
    if not hmac.compare_digest(tag, hmac.new(mk, body, hashlib.sha256).digest()):
        raise ValueError("llave incorrecta o archivo dañado")
    ct = body[38:]
    return bytes(a ^ b for a, b in zip(ct, _stream(ek, nonce, len(ct))))


def load(enc_file: Path, master_file: Path) -> dict:
    """Claves de fábrica descifradas, o {} si falta el archivo, falta la llave o no cuadra."""
    try:
        return json.loads(decrypt(enc_file.read_bytes(), master_file.read_bytes()).decode("utf-8"))
    except (OSError, ValueError):
        return {}


def save(keys: dict, enc_file: Path, master_file: Path) -> None:
    """Cifra las claves. Crea la llave maestra si aún no existe."""
    if not master_file.exists():
        master_file.write_bytes(os.urandom(32))
    enc_file.write_bytes(encrypt(json.dumps(keys).encode("utf-8"), master_file.read_bytes()))

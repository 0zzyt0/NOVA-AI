"""Efectos de sonido de los hologramas, generados al vuelo (sin archivos):
encendido (barrido ascendente con destellos), apagado (barrido que cae) y alerta (sirena de dos tonos)."""
from __future__ import annotations

import math

import numpy as np

RATE = 24000
_CACHE: dict[str, np.ndarray] = {}


def _env(n: int, attack: float, release: float) -> np.ndarray:
    t = np.linspace(0, 1, n, dtype=np.float32)
    a = np.clip(t / max(attack, 1e-3), 0, 1)
    r = np.clip((1 - t) / max(release, 1e-3), 0, 1)
    return a * r


def _sweep(f0: float, f1: float, dur: float, shape: float = 1.0) -> np.ndarray:
    n = int(RATE * dur)
    t = np.linspace(0, 1, n, dtype=np.float64)
    f = f0 + (f1 - f0) * t ** shape
    phase = 2 * math.pi * np.cumsum(f) / RATE
    return (np.sin(phase) * 0.6 + np.sin(phase * 2) * 0.22 + np.sin(phase * 3) * 0.1).astype(np.float32)


def holo_on() -> np.ndarray:
    base = _sweep(180, 920, 0.62, 0.6) * _env(int(RATE * 0.62), 0.04, 0.45)
    rnd = np.random.default_rng(7)
    shimmer = (rnd.standard_normal(len(base)).astype(np.float32) * 0.08) * np.linspace(0.2, 1, len(base), dtype=np.float32)
    out = np.zeros(int(RATE * 0.95), dtype=np.float32)
    out[:len(base)] += base + shimmer * _env(len(base), 0.3, 0.3)
    for k, (start, f) in enumerate(((0.52, 1320), (0.62, 1760), (0.72, 2350))):  # destellos finales
        n = int(RATE * 0.12)
        t = np.arange(n) / RATE
        blip = np.sin(2 * math.pi * f * t).astype(np.float32) * 0.25 * np.exp(-t * 28).astype(np.float32)
        i = int(RATE * start)
        out[i:i + n] += blip[:len(out) - i]
    return out * 0.55


def holo_off() -> np.ndarray:
    base = _sweep(760, 120, 0.5, 0.7) * _env(int(RATE * 0.5), 0.02, 0.7)
    n = len(base)
    crackle = np.random.default_rng(3).standard_normal(n).astype(np.float32) * 0.05 * np.linspace(1, 0, n, dtype=np.float32)
    return (base + crackle) * 0.5


def alert() -> np.ndarray:
    parts = []
    for k in range(3):
        for f in (880, 660):
            n = int(RATE * 0.17)
            t = np.arange(n) / RATE
            wave = np.tanh(np.sin(2 * math.pi * f * t) * 3.0).astype(np.float32) * 0.5
            parts.append(wave * _env(n, 0.06, 0.15))
        parts.append(np.zeros(int(RATE * 0.06), dtype=np.float32))
    return np.concatenate(parts) * 0.95


SOUNDS = {"holo_on": holo_on, "holo_off": holo_off, "alerta": alert}


def get(name: str) -> np.ndarray | None:
    if name not in SOUNDS:
        return None
    if name not in _CACHE:
        _CACHE[name] = SOUNDS[name]()
    return _CACHE[name]


def to_wav(name: str) -> bytes:
    """El efecto en WAV (para escucharlo en la ventana de NOVA)."""
    import io
    import wave

    data = get(name)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(data, -1, 1) * 32000).astype("<i2").tobytes())
    return buf.getvalue()

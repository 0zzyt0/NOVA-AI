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


def _tone(f: float, dur: float, shape: str = "sine", decay: float = 0.0) -> np.ndarray:
    n = int(RATE * dur)
    t = np.arange(n) / RATE
    ph = 2 * math.pi * f * t
    if shape == "square":
        w = np.tanh(np.sin(ph) * 4.0)
    elif shape == "bell":  # campana: parciales inarmónicos
        w = np.sin(ph) + 0.5 * np.sin(ph * 2.76) + 0.25 * np.sin(ph * 5.4)
        w /= 1.75
    else:
        w = np.sin(ph) + 0.15 * np.sin(ph * 2)
    if decay:
        w = w * np.exp(-t * decay)
    return (w * _env(n, 0.03, 0.25)).astype(np.float32)


def _seq(parts: list[tuple[float, np.ndarray]], total: float) -> np.ndarray:
    out = np.zeros(int(RATE * total), dtype=np.float32)
    for start, wave in parts:
        i = int(RATE * start)
        if i >= len(out):
            continue
        n = min(len(wave), len(out) - i)
        out[i:i + n] += wave[:n]
    return out


def _noise_sweep(f0: float, f1: float, dur: float, seed: int) -> np.ndarray:
    n = int(RATE * dur)
    noise = np.random.default_rng(seed).standard_normal(n).astype(np.float32)
    t = np.linspace(0, 1, n, dtype=np.float64)
    f = f0 + (f1 - f0) * t
    ph = 2 * math.pi * np.cumsum(f) / RATE
    return (noise * 0.35 * (0.5 + 0.5 * np.sin(ph))).astype(np.float32)


# --- encendido
def on_pulse() -> np.ndarray:
    return _seq([(0.0, _tone(660, 0.09)), (0.1, _tone(880, 0.09)), (0.2, _tone(1320, 0.16, decay=8))], 0.45) * 0.5


def on_scanner() -> np.ndarray:
    sweep = _noise_sweep(300, 2600, 0.55, 11) * _env(int(RATE * 0.55), 0.2, 0.3)
    return _seq([(0.0, sweep), (0.5, _tone(1568, 0.3, "bell", 7) * 0.6)], 0.9) * 0.6


def on_chime() -> np.ndarray:
    return _seq([(0.0, _tone(784, 0.5, "bell", 5)), (0.16, _tone(1175, 0.6, "bell", 5))], 0.85) * 0.45


def on_hum() -> np.ndarray:
    base = _sweep(55, 140, 0.8, 0.5) * _env(int(RATE * 0.8), 0.25, 0.25)
    return _seq([(0.0, base), (0.62, _tone(1046, 0.18, decay=14) * 0.4)], 0.9) * 0.7


# --- apagado
def off_pulse() -> np.ndarray:
    return _seq([(0.0, _tone(1320, 0.08)), (0.1, _tone(880, 0.08)), (0.2, _tone(520, 0.16, decay=10))], 0.42) * 0.5


def off_disconnect() -> np.ndarray:
    click = np.random.default_rng(5).standard_normal(int(RATE * 0.02)).astype(np.float32) * 0.4
    thump = _sweep(160, 45, 0.3, 0.6) * _env(int(RATE * 0.3), 0.01, 0.8)
    return _seq([(0.0, click), (0.02, thump)], 0.4) * 0.7


def off_chime() -> np.ndarray:
    return _seq([(0.0, _tone(1175, 0.45, "bell", 6)), (0.15, _tone(784, 0.55, "bell", 6))], 0.8) * 0.45


def off_hum() -> np.ndarray:
    return _sweep(150, 40, 0.75, 0.6) * _env(int(RATE * 0.75), 0.02, 0.6) * 0.7


# --- alerta de objetivo de captura
def alert_klaxon() -> np.ndarray:
    parts = []
    for k in range(3):
        parts.append((k * 0.42, _tone(330, 0.3, "square") * 0.45))
    return _seq(parts, 1.3) * 0.9


def alert_beeps() -> np.ndarray:
    return _seq([(k * 0.13, _tone(1760, 0.08, "square") * 0.35) for k in range(8)], 1.1)


def alert_wail() -> np.ndarray:
    up = _sweep(500, 1300, 0.55, 1.0) * _env(int(RATE * 0.55), 0.05, 0.1)
    return _seq([(0.0, up), (0.6, up)], 1.2) * 0.6


def alert_bell() -> np.ndarray:
    return _seq([(k * 0.32, _tone(988 if k % 2 == 0 else 698, 0.45, "bell", 4)) for k in range(4)], 1.5) * 0.55


# Sonidos que se pueden elegir para cada momento (Interfaz › Overlay NOVA AI › Sonido)
PRESETS: dict[str, dict[str, tuple[str, object]]] = {
    "holo_on": {"proyector": ("Proyector holográfico", holo_on), "pulso": ("Pulso digital", on_pulse),
                "escaner": ("Escáner", on_scanner), "campanilla": ("Campanilla", on_chime),
                "zumbido": ("Arranque de motor", on_hum)},
    "holo_off": {"proyector": ("Proyector holográfico", holo_off), "pulso": ("Pulso digital", off_pulse),
                 "desconexion": ("Desconexión", off_disconnect), "campanilla": ("Campanilla", off_chime),
                 "zumbido": ("Apagado de motor", off_hum)},
    "alerta": {"sirena": ("Sirena de dos tonos", alert), "klaxon": ("Klaxon", alert_klaxon),
               "pitidos": ("Pitidos rápidos", alert_beeps), "aullido": ("Alarma de proximidad", alert_wail),
               "campana": ("Campana de combate", alert_bell)},
}
DEFAULT_PRESET = {"holo_on": "proyector", "holo_off": "proyector", "alerta": "sirena"}
SOUNDS = {"holo_on": holo_on, "holo_off": holo_off, "alerta": alert}
EVENTS = tuple(PRESETS)
MAX_CUSTOM_S = 6.0  # un sonido propio se corta a 6 segundos
CUSTOM_EXT = (".wav", ".mp3", ".ogg", ".flac")


def presets() -> dict[str, list[dict]]:
    return {ev: [{"id": k, "nombre": v[0]} for k, v in items.items()] for ev, items in PRESETS.items()}


def preset(event: str, choice: str) -> np.ndarray | None:
    items = PRESETS.get(event)
    if not items:
        return None
    key = choice if choice in items else DEFAULT_PRESET[event]
    ck = f"{event}:{key}"
    if ck not in _CACHE:
        _CACHE[ck] = items[key][1]()
    return _CACHE[ck]


def decode_file(path) -> np.ndarray:
    """WAV, MP3, OGG o FLAC propio -> muestras mono a RATE (máx. 6 s). Lanza ValueError si no se puede."""
    try:
        import miniaudio
        dec = miniaudio.decode_file(str(path), output_format=miniaudio.SampleFormat.FLOAT32, nchannels=1,
                                    sample_rate=RATE)
        data = np.frombuffer(dec.samples, dtype=np.float32).copy()
    except ImportError:  # sin miniaudio (pruebas): solo WAV PCM de 16 bits
        import wave
        try:
            with wave.open(str(path), "rb") as w:
                if w.getsampwidth() != 2:
                    raise ValueError("WAV no compatible")
                raw = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
                ch = w.getnchannels()
                rate = w.getframerate()
            if ch > 1:
                raw = raw.reshape(-1, ch).mean(axis=1)
            if rate != RATE and len(raw):
                x = np.linspace(0, len(raw) - 1, int(len(raw) * RATE / rate))
                raw = np.interp(x, np.arange(len(raw)), raw).astype(np.float32)
            data = raw
        except (wave.Error, EOFError) as e:
            raise ValueError("No es un archivo de audio válido") from e
    except Exception as e:  # noqa: BLE001
        raise ValueError("No es un archivo de audio válido (usa WAV, MP3, OGG o FLAC)") from e
    if not len(data):
        raise ValueError("El archivo de audio está vacío")
    data = data[:int(RATE * MAX_CUSTOM_S)]
    peak = float(np.max(np.abs(data))) or 1.0
    if peak > 1.0:
        data = data / peak
    fade = min(len(data), int(RATE * 0.02))  # sin chasquido al cortar
    data[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    return data.astype(np.float32)


_FILE_CACHE: dict[str, tuple[float, np.ndarray]] = {}


def custom(path) -> np.ndarray | None:
    import os
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    hit = _FILE_CACHE.get(str(path))
    if hit and hit[0] == mtime:
        return hit[1]
    try:
        data = decode_file(path)
    except ValueError:
        return None
    _FILE_CACHE[str(path)] = (mtime, data)
    return data


def get(name: str, choice: str = "", path: str = "") -> np.ndarray | None:
    """El sonido de un momento (holo_on, holo_off, alerta) según lo elegido: un sonido de la lista,
    'archivo' (el tuyo) o 'ninguno'."""
    if name not in PRESETS:
        return None
    if choice == "ninguno":
        return None
    if choice == "archivo" and path:
        data = custom(path)
        if data is not None:
            return data
        choice = ""  # el archivo ya no está: se usa el de fábrica
    return preset(name, choice)


def to_wav(name: str, choice: str = "", path: str = "") -> bytes:
    """El efecto en WAV (para escucharlo en la ventana de NOVA)."""
    import io
    import wave

    data = get(name, choice, path)
    if data is None:
        data = np.zeros(int(RATE * 0.05), dtype=np.float32)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(data, -1, 1) * 32000).astype("<i2").tobytes())
    return buf.getvalue()

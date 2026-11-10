"""Voz de Nova (TTS): Microsoft Edge (gratis, muy natural), Piper (gratis, sin
internet) o la voz de Windows. Incluye un filtro opcional de 'IA de cabina'.

La salida de audio es UN único flujo abierto todo el tiempo que se alimenta de
una cola. Para callar a Nova solo se vacía la cola: nunca se para ni se cierra
el dispositivo desde otro hilo (eso era lo que cerraba el programa de golpe).
"""
from __future__ import annotations

import asyncio
import collections
import io
import logging
import queue
import re
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Callable

import numpy as np

from .config import MODELS_DIR

log = logging.getLogger("nova.tts")

OUT_RATE = 48000

# Respaldo si no hay internet para pedir la lista completa.
EDGE_VOICES_ES = [
    "es-ES-XimenaNeural", "es-ES-ElviraNeural", "es-ES-AlvaroNeural",
    "es-ES-ArabellaMultilingualNeural", "es-ES-IsidoraMultilingualNeural",
    "es-ES-TristanMultilingualNeural", "es-ES-XimenaMultilingualNeural",
    "es-MX-DaliaNeural", "es-MX-JorgeNeural", "es-AR-ElenaNeural", "es-AR-TomasNeural",
    "es-CO-SalomeNeural", "es-CO-GonzaloNeural", "es-US-PalomaNeural", "es-US-AlonsoNeural",
]
PIPER_VOICES = {
    "es_ES-davefx-medium": "es/es_ES/davefx/medium",
    "es_ES-sharvard-medium": "es/es_ES/sharvard/medium",
    "es_ES-carlfm-x_low": "es/es_ES/carlfm/x_low",
    "es_MX-ald-medium": "es/es_MX/ald/medium",
    "es_MX-claude-high": "es/es_MX/claude/high",
}
PIPER_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/{path}/{name}.onnx"


def list_edge_voices() -> list[str]:
    try:
        import edge_tts

        voices = asyncio.run(edge_tts.list_voices())
        names = sorted(v["ShortName"] for v in voices if v["Locale"].startswith("es-"))
        return names or EDGE_VOICES_ES
    except Exception as e:
        log.info("Lista de voces Edge no disponible (%s); uso la lista básica", e)
        return EDGE_VOICES_ES


def speakable(text: str) -> str:
    """Quita lo que no se debe leer en voz alta."""
    t = re.sub(r"https?://\S+", "", text)
    t = re.sub(r"[*_#`>|]+", "", t)
    t = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", t)
    for a, b in (("aUEC", "a U E C"), ("SCU", "S C U"), ("UEX", "U E X"), ("ATC", "A T C"),
                 ("QT", "cuántico"), ("km/s", "kilómetros por segundo"), ("m/s", "metros por segundo")):
        t = re.sub(rf"\b{re.escape(a)}\b", b, t)
    return re.sub(r"\s+", " ", t).strip()


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+", text)
    out, cur = [], ""
    for p in parts:  # junta frases muy cortas para que no suene entrecortado
        cur = f"{cur} {p}".strip()
        if len(cur) > 60:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return [s for s in out if s.strip()]


def cockpit_filter(samples: np.ndarray, rate: int) -> np.ndarray:
    """Toque de 'IA de nave': banda telefónica suave + leve saturación, mezclado con la voz limpia."""
    if len(samples) < 64:
        return samples
    spec = np.fft.rfft(samples)
    freqs = np.fft.rfftfreq(len(samples), 1 / rate)
    band = np.where((freqs > 280) & (freqs < 4200), 1.0, 0.15)
    filtered = np.fft.irfft(spec * band, n=len(samples))
    filtered = np.tanh(filtered * 1.8) / 1.6
    out = 0.55 * samples + 0.6 * filtered
    peak = np.max(np.abs(out)) or 1.0
    return (out / peak * 0.9).astype(np.float32)


def resample(samples: np.ndarray, rate: int, target: int = OUT_RATE) -> np.ndarray:
    if rate == target or len(samples) < 2:
        return samples.astype(np.float32)
    n = int(round(len(samples) * target / rate))
    x_old = np.linspace(0.0, 1.0, num=len(samples), endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=n, endpoint=False)
    return np.interp(x_new, x_old, samples).astype(np.float32)


def _wav_to_np(data: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(data)) as w:
        rate, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    dtype = {1: np.int8, 2: np.int16, 4: np.int32}[width]
    a = np.frombuffer(raw, dtype=dtype).astype(np.float32) / float(np.iinfo(dtype).max)
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    return a, rate


class AudioOut:
    """Un flujo de salida permanente alimentado por una cola de trozos de audio."""

    def __init__(self, settings) -> None:
        self.settings = settings
        self._lock = threading.Lock()
        self._chunks: collections.deque = collections.deque()
        self._pos = 0
        self._stream = None
        self._device_name = object()
        self.level = 0.0  # volumen actual de la voz (para el overlay y la ventana)
        self.last_sound = 0.0
        self._fx: list[list] = []  # efectos de sonido (hologramas): se mezclan encima de la voz

    def _ensure_stream(self) -> None:
        import sounddevice as sd
        from .audio import find_device

        name = self.settings.get("dispositivo_salida")
        if self._stream is not None and name == self._device_name:
            return
        old = self._stream
        self._stream = None
        if old is not None:
            try:
                old.abort()
                old.close()
            except Exception:
                pass
        stream = sd.OutputStream(samplerate=OUT_RATE, channels=1, dtype="float32", blocksize=960,
                                 device=find_device(name, False), callback=self._callback)
        stream.start()
        self._stream, self._device_name = stream, name
        log.info("Salida de audio abierta (%s)", name or "predeterminada")

    def _callback(self, outdata, frames, t, status) -> None:  # hilo de audio: rápido y sin excepciones
        out = outdata[:, 0]
        filled = 0
        with self._lock:
            while filled < frames and self._chunks:
                chunk = self._chunks[0]
                take = min(len(chunk) - self._pos, frames - filled)
                out[filled:filled + take] = chunk[self._pos:self._pos + take]
                filled += take
                self._pos += take
                if self._pos >= len(chunk):
                    self._chunks.popleft()
                    self._pos = 0
        if filled < frames:
            out[filled:] = 0.0
        if filled:
            rms = float(np.sqrt(np.mean(out[:filled] * out[:filled])))
            self.level = min(1.0, max(rms * 5.0, self.level * 0.7))
            self.last_sound = time.time()
        else:
            self.level *= 0.6
        if self._fx:  # efectos: se suman sin esperar a que termine la voz
            with self._lock:
                keep = []
                for item in self._fx:
                    data, pos = item
                    take = min(len(data) - pos, frames)
                    out[:take] += data[pos:pos + take]
                    item[1] = pos + take
                    if item[1] < len(data):
                        keep.append(item)
                self._fx = keep
            np.clip(out, -1.0, 1.0, out=out)

    def push(self, samples: np.ndarray, rate: int, still_valid: Callable[[], bool] = lambda: True) -> bool:
        """Encola audio. `still_valid` se comprueba con la cola bloqueada, así un
        'silencio' que llegue a la vez nunca deja escapar la frase."""
        self._ensure_stream()
        data = resample(np.asarray(samples, dtype=np.float32), rate)
        with self._lock:
            if not still_valid():
                return False
            self._chunks.append(data)
            return True

    def play_fx(self, samples: np.ndarray, rate: int) -> None:
        """Efecto de sonido corto mezclado con lo que suene (no hace cola detrás de la voz)."""
        try:
            self._ensure_stream()
        except Exception:  # noqa: BLE001
            return
        data = resample(np.asarray(samples, dtype=np.float32), rate)
        with self._lock:
            self._fx.append([data, 0])

    def clear(self, before: Callable[[], None] | None = None) -> None:
        with self._lock:
            if before:
                before()
            self._chunks.clear()
            self._pos = 0

    def pending(self) -> bool:
        with self._lock:
            return bool(self._chunks)

    def close(self) -> None:
        self.clear()
        if self._stream is not None:
            try:
                self._stream.abort()
                self._stream.close()
            except Exception:
                pass
            self._stream = None


class TextToSpeech:
    def __init__(self, settings, on_start: Callable[[], None] | None = None,
                 on_end: Callable[[], None] | None = None) -> None:
        self.settings = settings
        self.on_start, self.on_end = on_start, on_end
        self.out = AudioOut(settings)
        self._text_q: "queue.Queue[tuple[int, str]]" = queue.Queue()
        self._generation = 0  # cambia al interrumpir: descarta lo pendiente
        self._synthesizing = False
        self._piper = None
        self._piper_name = None
        self.speaking = False
        self.ended_at = 0.0
        threading.Thread(target=self._synth_loop, daemon=True, name="tts-synth").start()
        threading.Thread(target=self._watch_loop, daemon=True, name="tts-watch").start()

    # ------------------------------------------------------------------ público
    def say(self, text: str) -> None:
        text = speakable(text)
        if text:
            gen = self._generation
            for s in split_sentences(text):
                self._text_q.put((gen, s))

    def stop(self) -> None:
        """Calla inmediatamente. Seguro desde cualquier hilo."""
        def bump() -> None:
            self._generation += 1
        self.out.clear(before=bump)  # cambia la generación con la cola de audio bloqueada
        try:
            while True:
                self._text_q.get_nowait()
        except queue.Empty:
            pass

    def busy(self) -> bool:
        return self._synthesizing or not self._text_q.empty() or self.out.pending()

    def preview(self, text: str) -> bool:
        """Botón de prueba: si ya está hablando, calla (no se acumula ni se repite)."""
        if self.busy():
            self.stop()
            return False
        self.say(text)
        return True

    # ------------------------------------------------------------------ motores
    def _edge(self, text: str) -> tuple[np.ndarray, int]:
        import edge_tts
        import miniaudio

        rate = int(self.settings.get("tts_velocidad"))
        pitch = int(self.settings.get("tts_tono"))
        com = edge_tts.Communicate(text, self.settings.get("tts_voz_edge"),
                                   rate=f"{rate:+d}%", pitch=f"{pitch:+d}Hz")

        async def grab() -> bytes:
            buf = bytearray()
            async for chunk in com.stream():
                if chunk.get("type") == "audio":
                    buf.extend(chunk["data"])
            return bytes(buf)

        mp3 = asyncio.run(grab())
        if not mp3:
            raise RuntimeError("Edge no devolvió audio")
        dec = miniaudio.decode(mp3, output_format=miniaudio.SampleFormat.FLOAT32, nchannels=1, sample_rate=24000)
        return np.asarray(dec.samples, dtype=np.float32), 24000

    def piper_model_path(self, name: str) -> Path:
        return MODELS_DIR / "piper" / f"{name}.onnx"

    def download_piper(self, name: str) -> Path:
        import requests

        path = self.piper_model_path(name)
        if path.exists() and path.with_suffix(".onnx.json").exists():
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        base = PIPER_URL.format(path=PIPER_VOICES[name], name=name)
        for url, dest in ((base, path), (base + ".json", path.with_suffix(".onnx.json"))):
            log.info("Descargando voz Piper %s…", dest.name)
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            dest.write_bytes(r.content)
        return path

    def _piper_synth(self, text: str) -> tuple[np.ndarray, int]:
        from piper import PiperVoice

        name = self.settings.get("tts_voz_piper")
        if self._piper is None or self._piper_name != name:
            self._piper = PiperVoice.load(str(self.download_piper(name)))
            self._piper_name = name
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            if hasattr(self._piper, "synthesize_wav"):  # piper-tts >= 1.3
                self._piper.synthesize_wav(text, w)
            else:
                self._piper.synthesize(text, w)
        return _wav_to_np(buf.getvalue())

    def _windows(self, text: str) -> tuple[np.ndarray, int]:
        import pyttsx3

        eng = pyttsx3.init()
        for v in eng.getProperty("voices"):
            if "spanish" in v.name.lower() or "es-" in str(v.id).lower() or "helena" in v.name.lower():
                eng.setProperty("voice", v.id)
                break
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "v.wav"
            eng.save_to_file(text, str(f))
            eng.runAndWait()
            return _wav_to_np(f.read_bytes())

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        engine = self.settings.get("tts_motor")
        order = [engine] + [e for e in ("edge", "piper", "windows") if e != engine]
        last = None
        for e in order:
            try:
                fn = {"edge": self._edge, "piper": self._piper_synth, "windows": self._windows}[e]
                samples, rate = fn(text)
                if e != engine:
                    log.warning("Voz '%s' falló; usando '%s'", engine, e)
                if self.settings.get("tts_efecto_radio"):
                    samples = cockpit_filter(samples, rate)
                return samples * float(self.settings.get("volumen")), rate
            except Exception as ex:
                last = ex
                log.debug("TTS %s falló: %s", e, ex)
        raise RuntimeError(f"Ninguna voz disponible: {last}")

    # ------------------------------------------------------------------- hilos
    def _synth_loop(self) -> None:
        while True:
            gen, text = self._text_q.get()
            if gen != self._generation:
                continue
            self._synthesizing = True
            try:
                samples, rate = self.synthesize(text)
                self.out.push(samples, rate, still_valid=lambda: gen == self._generation)
            except Exception as e:
                log.error("No pude hablar: %s", e)
            finally:
                self._synthesizing = False

    def _watch_loop(self) -> None:
        """Detecta cuándo empieza y termina de hablar (para el micrófono y el overlay)."""
        while True:
            playing = self.out.pending() or (time.time() - self.out.last_sound < 0.15)
            if playing and not self.speaking:
                self.speaking = True
                if self.on_start:
                    self.on_start()
            elif not playing and self.speaking and not self.busy():
                self.speaking = False
                self.ended_at = time.time()
                if self.on_end:
                    self.on_end()
            time.sleep(0.04)

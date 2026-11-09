"""Micrófono: pulsar para hablar y escucha continua con detector de voz (VAD)."""
from __future__ import annotations

import collections
import logging
import queue
import threading
import time
from typing import Callable

import numpy as np

log = logging.getLogger("nova.audio")

SAMPLE_RATE = 16000
FRAME = 480  # 30 ms


def list_devices() -> tuple[list[str], list[str]]:
    """(entradas, salidas) por nombre."""
    try:
        import sounddevice as sd

        devs = sd.query_devices()
        ins = [d["name"] for d in devs if d["max_input_channels"] > 0]
        outs = [d["name"] for d in devs if d["max_output_channels"] > 0]
        return sorted(set(ins)), sorted(set(outs))
    except Exception as e:
        log.warning("No se pudieron listar dispositivos: %s", e)
        return [], []


def find_device(name: str | None, want_input: bool):
    if not name or name.startswith("("):
        return None
    import sounddevice as sd

    for i, d in enumerate(sd.query_devices()):
        ch = d["max_input_channels"] if want_input else d["max_output_channels"]
        if d["name"] == name and ch > 0:
            return i
    return None


class EnergyVAD:
    """Detector de voz por energía con suelo de ruido adaptativo. Sin dependencias."""

    def __init__(self, sensitivity: float = 0.5) -> None:
        self.floor = 0.003
        self.set_sensitivity(sensitivity)

    def set_sensitivity(self, s: float) -> None:
        s = min(max(s, 0.0), 1.0)
        self.factor = 3.5 - 2.3 * s  # 0.5 -> x2.35 sobre el ruido de fondo
        self.min_level = 0.012 - 0.009 * s

    def is_speech(self, rms: float, speaking: bool) -> bool:
        threshold = max(self.floor * self.factor, self.min_level)
        voiced = rms > (threshold * 0.7 if speaking else threshold)
        if not voiced:  # solo aprende del silencio
            self.floor = 0.95 * self.floor + 0.05 * rms
        return voiced


class Listener:
    def __init__(self, settings, on_utterance: Callable[[np.ndarray, str], None]) -> None:
        self.settings = settings
        self.on_utterance = on_utterance
        self.vad = EnergyVAD(settings.get("sensibilidad_vad"))
        self.level = 0.0  # para el medidor de la ventana
        self.suppressed = False  # True mientras Nova habla (evita oírse a sí misma)
        self.is_suppressed: Callable[[], bool] = lambda: False
        self.capturing = False  # hay una frase en curso (para el overlay)
        self._capture_q: "queue.Queue[np.ndarray] | None" = None  # entrenamiento: frases sueltas
        self._q: "queue.Queue[np.ndarray]" = queue.Queue()
        self._stream = None
        self._ptt = False
        self._ptt_buf: list[np.ndarray] = []
        self._preroll: collections.deque = collections.deque(maxlen=10)
        self._vad_buf: list[np.ndarray] = []
        self._speaking = False
        self._silence_ms = 0
        self._voiced_ms = 0
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._loop, daemon=True, name="mic")

    # ----------------------------------------------------------------- control
    def start(self) -> None:
        import sounddevice as sd

        device = find_device(self.settings.get("dispositivo_entrada"), True)
        self._stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                                      blocksize=FRAME, device=device, callback=self._cb)
        self._stream.start()
        if not self._worker.is_alive():
            self._worker.start()
        log.info("Micrófono abierto (%s)", self.settings.get("dispositivo_entrada") or "predeterminado")

    def restart(self) -> None:
        self.close()
        self.vad.set_sensitivity(self.settings.get("sensibilidad_vad"))
        self.start()

    def close(self) -> None:
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def capture(self, wait_s: float = 6.0, max_s: float = 9.0, end_silence_ms: int = 900):
        """Graba UNA frase (para el entrenamiento): espera a que empieces a hablar y para cuando
        te callas. Devuelve (audio o None, {"ruido": rms, "voz": rms})."""
        q: "queue.Queue[np.ndarray]" = queue.Queue()
        vad = EnergyVAD(self.settings.get("sensibilidad_vad"))
        vad.floor = self.vad.floor
        frame_ms = FRAME * 1000 // SAMPLE_RATE
        pre: collections.deque = collections.deque(maxlen=12)
        buf: list[np.ndarray] = []
        noise: list[float] = []
        voice: list[float] = []
        started, voiced_run, silence = False, 0, 0
        t0 = time.time()
        self._capture_q = q
        try:
            while True:
                elapsed = time.time() - t0
                if not started and elapsed > wait_s:
                    break
                if started and len(buf) * frame_ms > max_s * 1000:
                    break
                try:
                    frame = q.get(timeout=0.5)
                except queue.Empty:
                    continue
                rms = float(np.sqrt(np.mean(frame * frame)) + 1e-9)
                voiced = vad.is_speech(rms, started)
                if not started:
                    pre.append(frame)
                    if not voiced:
                        noise.append(rms)
                        voiced_run = 0
                        continue
                    voiced_run += 1
                    if voiced_run >= 3:
                        started = True
                        buf = list(pre)
                    continue
                buf.append(frame)
                if voiced:
                    voice.append(rms)
                    silence = 0
                else:
                    silence += frame_ms
                    if silence >= end_silence_ms:
                        break
        finally:
            self._capture_q = None
        stats = {"ruido": float(np.median(noise)) if noise else 0.0,
                 "voz": float(np.median(voice)) if voice else 0.0}
        if not started or len(buf) * frame_ms < 300:
            return None, stats
        return np.concatenate(buf), stats

    def ptt_down(self) -> None:
        self._ptt = True
        self._ptt_buf = list(self._preroll)
        self._reset_vad()

    def ptt_up(self) -> None:
        if not self._ptt:
            return
        self._ptt = False
        audio = np.concatenate(self._ptt_buf) if self._ptt_buf else np.zeros(0, np.float32)
        self._ptt_buf = []
        if len(audio) > SAMPLE_RATE * 0.35:
            self.on_utterance(audio, "ptt")

    # ------------------------------------------------------------------ interno
    def _cb(self, indata, frames, t, status) -> None:  # hilo de audio: mínimo trabajo
        self._q.put(indata[:, 0].copy())

    def _reset_vad(self) -> None:
        self._vad_buf, self._speaking, self._silence_ms, self._voiced_ms = [], False, 0, 0

    def _loop(self) -> None:
        frame_ms = FRAME * 1000 // SAMPLE_RATE
        while not self._stop.is_set():
            try:
                frame = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            rms = float(np.sqrt(np.mean(frame * frame)) + 1e-9)
            self.level = 0.8 * self.level + 0.2 * min(rms * 12, 1.0)

            cap = self._capture_q
            if cap is not None:
                cap.put(frame)
                continue

            if self._ptt:
                self._ptt_buf.append(frame)
                if len(self._ptt_buf) * frame_ms > 60_000:  # tope de 60 s
                    self.ptt_up()
                continue

            wake = self.settings.get("palabra_clave_activa")
            if self.suppressed or self.is_suppressed():
                # Nova está hablando: no se guarda nada de lo que entra (sería su propia voz).
                self._preroll.clear()
                if self._speaking:
                    self._reset_vad()
                self.capturing = False
                continue
            if not wake:
                self._preroll.append(frame)
                continue

            voiced = self.vad.is_speech(rms, self._speaking)
            if not self._speaking:
                self._preroll.append(frame)
                if voiced:
                    self._voiced_ms += frame_ms
                    if self._voiced_ms >= 90:  # 3 tramas seguidas con voz
                        self._speaking = True
                        self.capturing = True
                        self._vad_buf = list(self._preroll)
                        self._silence_ms = 0
                else:
                    self._voiced_ms = 0
                continue

            self._vad_buf.append(frame)
            self._silence_ms = 0 if voiced else self._silence_ms + frame_ms
            total_ms = len(self._vad_buf) * frame_ms
            if self._silence_ms >= self.settings.get("silencio_fin_ms") or total_ms > 20_000:
                audio = np.concatenate(self._vad_buf)
                self._reset_vad()
                self.capturing = False
                self._preroll.clear()
                if total_ms >= 500:
                    self.on_utterance(audio, "vad")

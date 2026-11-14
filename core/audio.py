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
    """Índice del primer dispositivo con ese nombre (compatibilidad). Ver find_devices()."""
    c = find_devices(name, want_input)
    return c[0] if c else None


# Windows ofrece cada micrófono varias veces, una por «API de audio». MME convierte cualquier
# frecuencia (16 kHz incluidos) y es la más tolerante; WASAPI solo abre a la frecuencia del
# dispositivo; WDM-KS da problemas con muchos auriculares USB e inalámbricos.
_API_ORDER = ("mme", "directsound", "wasapi")
MME_MAX = 31  # MME recorta los nombres a 31 caracteres


def _api_rank(api_name: str) -> int:
    a = (api_name or "").lower()
    for i, k in enumerate(_API_ORDER):
        if k in a:
            return i
    return 9 if "wdm" in a else len(_API_ORDER)


def find_devices(name: str | None, want_input: bool) -> list[int]:
    """Todas las variantes de ese dispositivo (una por API de audio), de la más fiable a la menos.
    Reconoce también el nombre recortado de MME («Micrófono (G435 Wireless Gaming»)."""
    if not name or name.startswith("("):
        return []
    import sounddevice as sd

    try:
        apis = sd.query_hostapis()
    except Exception:
        apis = []
    out = []
    for i, d in enumerate(sd.query_devices()):
        ch = d["max_input_channels"] if want_input else d["max_output_channels"]
        if ch <= 0:
            continue
        dn = d["name"]
        same = dn == name or (len(dn) >= MME_MAX - 1 and name.startswith(dn)) or \
            (len(name) >= MME_MAX - 1 and dn.startswith(name))
        if not same:
            continue
        h = d.get("hostapi")
        api = apis[h]["name"] if isinstance(h, int) and 0 <= h < len(apis) else ""
        out.append((_api_rank(api), 0 if dn == name else 1, i))
    return [i for _, _, i in sorted(out)]


def _describe(sd, index) -> str:
    try:
        d = sd.query_devices(index, "input") if index is None else sd.query_devices(index)
        api = sd.query_hostapis(d["hostapi"])["name"]
        return f"{d['name']} · {api}"
    except Exception:
        return "?"


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
        self.force_wake = False  # 1.4: en reposo «por su nombre» se escucha aunque «sin tecla» esté apagado
        self._worker = threading.Thread(target=self._loop, daemon=True, name="mic")
        # estado del micrófono, para avisar al usuario en vez de «no oigo nada» sin más
        self.ok = False  # hay un micrófono abierto
        self.device_text = ""  # cuál se abrió de verdad
        self.fallback = False  # no se pudo abrir el elegido y se usa el predeterminado
        self.open_error = ""
        self.rate = SAMPLE_RATE
        self.frames_in = 0
        self.zero_frames = 0  # tramas seguidas en silencio digital absoluto (0.0)
        self.peak = 0.0  # pico reciente (decae poco a poco)

    # ----------------------------------------------------------------- control
    @property
    def muted(self) -> bool:
        """Botón MUTE: con el micrófono silenciado no se oye nada, ni con la tecla ni por su nombre."""
        return bool(self.settings.get("microfono_silenciado"))

    def start(self) -> None:
        """Abre el micrófono elegido; si no se deja (frecuencia no admitida, API exigente…) prueba
        sus otras variantes, después a su frecuencia propia remuestreando a 16 kHz y, como último
        recurso, el micrófono predeterminado de Windows."""
        import sounddevice as sd

        name = self.settings.get("dispositivo_entrada")
        cands = find_devices(name, True)
        chosen = bool(name) and not str(name).startswith("(")
        tries = [(i, False) for i in cands] + [(None, chosen)]
        errors = []
        for dev, is_fallback in tries:
            for rate in self._rates(sd, dev):
                try:
                    self._open(sd, dev, rate)
                except Exception as e:  # PortAudioError y compañía
                    errors.append(f"{_describe(sd, dev)} @ {rate} Hz: {e}")
                    continue
                self.ok, self.fallback, self.rate, self.open_error = True, is_fallback, rate, ""
                self.device_text = _describe(sd, dev) + ("" if rate == SAMPLE_RATE else f" · {rate} Hz → 16 kHz")
                self.frames_in, self.zero_frames, self.peak = 0, 0, 0.0
                if not self._worker.is_alive():
                    self._worker.start()
                if errors:
                    log.warning("Micrófono: intentos fallidos antes de abrirlo:\n  %s", "\n  ".join(errors))
                if is_fallback:
                    log.warning("No pude abrir el micrófono «%s»; uso el predeterminado de Windows", name)
                log.info("Micrófono abierto: %s", self.device_text)
                return
        self.ok = False
        self.open_error = errors[-1] if errors else "no hay micrófonos"
        log.error("No pude abrir ningún micrófono:\n  %s", "\n  ".join(errors))
        raise RuntimeError("No pude abrir el micrófono. Elige otro en la lista o revisa que esté conectado y activado en Windows.")

    @staticmethod
    def _rates(sd, dev) -> list[int]:
        """16 kHz primero; si no, la frecuencia propia del dispositivo (48000, 44100…)."""
        rates = [SAMPLE_RATE]
        try:
            d = sd.query_devices(dev, "input") if dev is None else sd.query_devices(dev)
            r = int(round(d.get("default_samplerate") or 0))
            if r and r != SAMPLE_RATE:
                rates.append(r)
        except Exception:
            pass
        for r in (48000, 44100):
            if r not in rates:
                rates.append(r)
        return rates

    def _open(self, sd, dev, rate: int) -> None:
        block = int(round(FRAME * rate / SAMPLE_RATE))
        src = np.linspace(0.0, 1.0, block, endpoint=False)
        dst = np.linspace(0.0, 1.0, FRAME, endpoint=False)

        def resample(indata, frames, t, status):  # cada bloque nativo → 480 muestras (30 ms a 16 kHz)
            x = indata[:, 0] if indata.shape[1] == 1 else indata.mean(axis=1)
            if len(x) == block:
                self._q.put(np.interp(dst, src, x).astype(np.float32))
            else:
                n = max(1, int(round(len(x) * SAMPLE_RATE / rate)))
                self._q.put(np.interp(np.linspace(0.0, 1.0, n, endpoint=False),
                                      np.linspace(0.0, 1.0, len(x), endpoint=False), x).astype(np.float32))

        stream, last = None, None
        for ch in (1, 2):
            cb = resample if rate != SAMPLE_RATE else (self._cb if ch == 1 else self._cb_stereo)
            try:
                stream = sd.InputStream(samplerate=rate, channels=ch, dtype="float32", blocksize=block,
                                        device=dev, callback=cb)
                break
            except Exception as e:
                last = e
        if stream is None:
            raise last or RuntimeError("no se pudo abrir")
        try:
            stream.start()
        except Exception:
            try:
                stream.close()
            except Exception:
                pass
            raise
        self._stream = stream

    def health(self) -> str:
        """ok · silenciado (MUTE) · sin_audio (no llega nada) · silencio (ceros: silenciado en los
        auriculares o bloqueado por Windows) · cerrado"""
        if not self.ok or self._stream is None:
            return "cerrado"
        if self.muted:
            return "silenciado"
        if self.frames_in == 0:
            return "sin_audio"
        if self.zero_frames >= 50:  # 1,5 s de ceros exactos
            return "silencio"
        return "ok"

    def restart(self) -> None:
        self.close()
        self.vad.set_sensitivity(self.settings.get("sensibilidad_vad"))
        self.start()

    def close(self) -> None:
        self.ok = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def shutdown(self) -> None:
        """Cierra el micrófono y su hilo (modo reposo: Windows deja de mostrarlo en uso)."""
        self.close()
        self._stop.set()

    def capture(self, wait_s: float = 6.0, max_s: float = 9.0, end_silence_ms: int = 900):
        """Graba UNA frase (para el entrenamiento): espera a que empieces a hablar y para cuando
        te callas. Devuelve (audio o None, {"ruido": rms, "voz": rms})."""
        q: "queue.Queue[np.ndarray]" = queue.Queue()
        vad = EnergyVAD(self.settings.get("sensibilidad_vad"))
        vad.floor = self.vad.floor
        vad.min_level = min(vad.min_level, 0.004)  # en el entrenamiento manda el ruido de fondo medido
        got, zeros, loud = 0, 0, 0.0
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
                got += 1
                zeros += 0 if frame.any() else 1
                rms = float(np.sqrt(np.mean(frame * frame)) + 1e-9)
                loud = max(loud, rms)
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
                 "voz": float(np.median(voice)) if voice else 0.0, "pico": loud, "diag": ""}
        if not started or len(buf) * frame_ms < 300:
            n = stats["ruido"]
            if self.muted:
                stats["diag"] = "silenciado"
            elif got == 0:
                stats["diag"] = "sin_audio"
            elif zeros >= got * 0.95:
                stats["diag"] = "silencio"
            elif loud > max(3.0 * n, 0.0006):
                stats["diag"] = "bajo"  # se oye algo por encima del ruido, pero muy flojo
            return None, stats
        return np.concatenate(buf), stats

    def ptt_down(self) -> None:
        if self.muted:
            return
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

    def _cb_stereo(self, indata, frames, t, status) -> None:
        self._q.put(indata.mean(axis=1).astype(np.float32))

    def _reset_vad(self) -> None:
        self._vad_buf, self._speaking, self._silence_ms, self._voiced_ms = [], False, 0, 0

    def _loop(self) -> None:
        frame_ms = FRAME * 1000 // SAMPLE_RATE
        while not self._stop.is_set():
            try:
                frame = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            self.frames_in += 1
            self.zero_frames = self.zero_frames + 1 if not frame.any() else 0
            if self.muted:  # MUTE: no se oye ni se guarda nada
                self.level *= 0.8
                self._preroll.clear()
                if self._speaking:
                    self._reset_vad()
                    self.capturing = False
                if self._ptt:
                    self._ptt_buf = []
                continue
            gain = float(self.settings.get("ganancia_mic") or 1.0)
            if gain != 1.0:
                frame = np.clip(frame * gain, -1.0, 1.0)
            rms = float(np.sqrt(np.mean(frame * frame)) + 1e-9)
            self.peak = max(rms, self.peak * 0.985)
            # medidor en decibelios: también se mueve con micrófonos de nivel bajo
            db = 20.0 * np.log10(rms)
            self.level = 0.8 * self.level + 0.2 * min(max((db + 62.0) / 50.0, 0.0), 1.0)

            cap = self._capture_q
            if cap is not None:
                cap.put(frame)
                continue

            if self._ptt:
                self._ptt_buf.append(frame)
                if len(self._ptt_buf) * frame_ms > 60_000:  # tope de 60 s
                    self.ptt_up()
                continue

            wake = self.settings.get("palabra_clave_activa") or self.force_wake
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

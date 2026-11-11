"""Reconocimiento de voz (Whisper): en tu PC (faster-whisper) o en la nube gratis (Groq)."""
from __future__ import annotations

import io
import logging
import re
import threading
import wave

import numpy as np

from .config import MODELS_DIR

log = logging.getLogger("nova.stt")

# Palabras que Whisper no conoce: se las "enseñamos" como contexto.
VOCAB = (
    "Star Citizen, Stanton, Pyro, Nyx, Hurston, Crusader, ArcCorp, microTech, Lorville, "
    "Orison, Área 18, New Babbage, Port Olisar, Everus Harbor, Baijini Point, Seraphim, Grim HEX, "
    "Ruin Station, Checkmate, Levski, aUEC, UEC, SCU, cuántico, Quantum, SCM, NAV, mobiGlas, "
    "Drake, Anvil, Aegis, RSI, MISC, Origin, Crusader, Argo, Cutlass, Carrack, Constellation, "
    "Freelancer, Gladius, Arrow, Prospector, MOLE, Vulture, Hammerhead, Polaris, Caterpillar, "
    "Banu, Vanduul, Xi'an, Tevarin, UEE, Nine Tails, XenoThreat, CrimeStat, ATC, VTOL, gimbal, chaff."
)

# Frases que Whisper "se inventa" con ruido o silencio.
_HALLUCINATIONS = re.compile(
    r"(subt[ií]tulos|amara\.org|gracias por ver|suscr[ií]bete|www\.|\.com|m[uú]sica|"
    r"thanks? for watching|subscribe|subtitles by|sous-titres|merci d'avoir regardé|abonnez-vous|"
    r"untertitel|danke fürs zuschauen|abonniert|subtítols|gràcies per veure|"
    r"^\W*(gracias|thank you|thanks|merci|danke|gràcies|ok|okay|hmm+|mm+|eh|ah)\W*$)",
    re.IGNORECASE,
)


def _stt_lang(settings) -> str:
    from .i18n import info
    return info(settings.get("idioma") or "es")["stt"]


def prompt_for(settings) -> str:
    """Contexto para Whisper con el nombre de la IA y del piloto, para que los escriba bien."""
    names = [settings.get("nombre_asistente") or "Nova", settings.get("nombre_piloto") or ""]
    return ", ".join(n for n in names if n) + ", " + VOCAB


def to_wav_bytes(audio: np.ndarray, rate: int = 16000) -> bytes:
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def clean(text: str) -> str:
    text = (text or "").strip()
    if not text or _HALLUCINATIONS.search(text):
        return ""
    return text


class SpeechToText:
    def __init__(self, settings) -> None:
        self.settings = settings
        self._local = None
        self._local_name = None
        self._local_lock = threading.Lock()
        self.status = ""

    # ---------------------------------------------------------------- elección
    def mode(self) -> str:
        m = self.settings.get("stt_motor")
        if m == "auto":
            return "groq" if self.settings.key_for("groq") else "local"
        return m

    def warm_up(self) -> None:
        """Carga el modelo local en segundo plano para que la 1ª orden sea rápida."""
        if self.mode() == "local":
            threading.Thread(target=self._get_local, daemon=True).start()

    # ------------------------------------------------------------------ local
    @staticmethod
    def _add_cuda_dlls() -> None:
        """En Windows, las DLL de CUDA instaladas con pip (nvidia-cublas/cudnn) no están en el PATH."""
        import os
        import site
        import sys

        if sys.platform != "win32":
            return
        for sp in site.getsitepackages():
            nv = os.path.join(sp, "nvidia")
            if os.path.isdir(nv):
                for sub in os.listdir(nv):
                    b = os.path.join(nv, sub, "bin")
                    if os.path.isdir(b):
                        os.add_dll_directory(b)
                        os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")

    def _get_local(self):
        name = self.settings.get("stt_modelo_local")
        with self._local_lock:
            if self._local is not None and self._local_name == name:
                return self._local
            self._add_cuda_dlls()
            from faster_whisper import WhisperModel

            self.status = f"Cargando Whisper '{name}'… (la primera vez se descarga)"
            log.info(self.status)
            try:
                model = WhisperModel(name, device="cuda", compute_type="float16",
                                     download_root=str(MODELS_DIR / "whisper"))
                where = "GPU NVIDIA"
            except Exception as e:
                log.info("Sin GPU para Whisper (%s); uso la CPU", str(e)[:120])
                model = WhisperModel(name, device="cpu", compute_type="int8",
                                     download_root=str(MODELS_DIR / "whisper"))
                where = "CPU"
            self._local, self._local_name = model, name
            self.status = f"Whisper '{name}' listo ({where})"
            log.info(self.status)
            return model

    def _transcribe_local(self, audio: np.ndarray) -> str:
        model = self._get_local()
        segments, _ = model.transcribe(
            audio, language=_stt_lang(self.settings), initial_prompt=prompt_for(self.settings), beam_size=1, temperature=0.0,
            vad_filter=True, vad_parameters={"min_silence_duration_ms": 300},
            condition_on_previous_text=False,
        )
        return " ".join(s.text for s in segments)

    # ------------------------------------------------------------------- groq
    def _transcribe_groq(self, audio: np.ndarray) -> str:
        import requests

        r = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {self.settings.key_for('groq')}"},
            files={"file": ("voz.wav", to_wav_bytes(audio), "audio/wav")},
            data={"model": "whisper-large-v3-turbo", "language": _stt_lang(self.settings), "prompt": prompt_for(self.settings),
                  "temperature": "0", "response_format": "json"},
            timeout=20,
        )
        if r.status_code != 200:
            raise RuntimeError(f"Groq Whisper {r.status_code}: {r.text[:200]}")
        return r.json().get("text", "")

    # ----------------------------------------------------------------- público
    def transcribe(self, audio: np.ndarray) -> str:
        mode = self.mode()
        try:
            text = self._transcribe_groq(audio) if mode == "groq" else self._transcribe_local(audio)
        except Exception as e:
            if mode == "groq":
                log.warning("Groq falló (%s); pruebo Whisper local", e)
                try:
                    text = self._transcribe_local(audio)
                except Exception as e2:
                    log.error("Whisper local tampoco: %s", e2)
                    return ""
            else:
                log.error("Error de reconocimiento: %s", e)
                return ""
        return clean(text)

from __future__ import annotations

import io
import json
import threading
import wave
from pathlib import Path

from .config import settings

try:
    from vosk import KaldiRecognizer, Model, SetLogLevel

    SetLogLevel(-1)
    _vosk_import_error: str | None = None
except ImportError as exc:  # pragma: no cover - depends on environment packages
    KaldiRecognizer = None  # type: ignore[assignment]
    Model = None  # type: ignore[assignment]
    _vosk_import_error = str(exc)

_model_lock = threading.Lock()
_model: Model | None = None  # type: ignore[type-arg]


def _resolve_model_path() -> Path:
    configured = Path(settings.stt_model_path)
    if configured.is_absolute():
        return configured
    return Path(__file__).resolve().parents[2] / configured


def _get_model() -> Model:
    global _model
    if _vosk_import_error:
        raise RuntimeError(
            "Offline STT dependency 'vosk' is not installed. "
            "Run: py -m pip install -r backend/requirements.txt"
        )
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        model_path = _resolve_model_path()
        if not model_path.exists():
            raise RuntimeError(
                f"Offline STT model not found at '{model_path}'. "
                "Download a Vosk English model and place/extract it there."
            )
        _model = Model(str(model_path))
        return _model


def transcribe_wav_bytes(audio_bytes: bytes) -> str:
    if not audio_bytes:
        raise ValueError("No audio payload provided.")

    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            frame_rate = wav_file.getframerate()
            compression = wav_file.getcomptype()

            if channels != 1:
                raise ValueError("Audio must be mono (1 channel).")
            if sample_width != 2:
                raise ValueError("Audio must be 16-bit PCM.")
            if compression != "NONE":
                raise ValueError("Audio must be uncompressed PCM WAV.")

            recognizer = KaldiRecognizer(_get_model(), float(frame_rate))
            recognizer.SetWords(False)
            while True:
                chunk = wav_file.readframes(4000)
                if not chunk:
                    break
                recognizer.AcceptWaveform(chunk)

            final = json.loads(recognizer.FinalResult())
            return str(final.get("text", "")).strip()
    except wave.Error as exc:
        raise ValueError(f"Invalid WAV audio: {exc}") from exc

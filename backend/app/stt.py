from __future__ import annotations

import io
import json
import logging
import time
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

try:
    import numpy as np

    _numpy_import_error: str | None = None
except ImportError as exc:  # pragma: no cover - depends on environment packages
    np = None  # type: ignore[assignment]
    _numpy_import_error = str(exc)

try:
    from faster_whisper import WhisperModel

    _whisper_import_error: str | None = None
except ImportError as exc:  # pragma: no cover - depends on environment packages
    WhisperModel = None  # type: ignore[assignment]
    _whisper_import_error = str(exc)

_model_lock = threading.Lock()
_model: Model | None = None  # type: ignore[type-arg]
_whisper_model_lock = threading.Lock()
_whisper_model = None
logger = logging.getLogger(__name__)


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


def _resolve_whisper_model() -> str:
    configured = (settings.stt_whisper_model_path or "").strip()
    if not configured:
        return settings.stt_whisper_model_size
    candidate = Path(configured)
    if candidate.is_absolute():
        return str(candidate)
    return str(Path(__file__).resolve().parents[2] / candidate)


def _get_whisper_model():
    global _whisper_model
    if _whisper_import_error:
        raise RuntimeError(
            "Whisper dependency 'faster-whisper' is not installed. "
            "Run: py -m pip install -r backend/requirements.txt"
        )
    if _whisper_model is not None:
        return _whisper_model
    with _whisper_model_lock:
        if _whisper_model is not None:
            return _whisper_model
        model_id = _resolve_whisper_model()
        _whisper_model = WhisperModel(
            model_size_or_path=model_id,
            device=settings.stt_whisper_device,
            compute_type=settings.stt_whisper_compute_type,
        )
        return _whisper_model


def _wav_bytes_to_float32(audio_bytes: bytes) -> tuple["np.ndarray", int]:
    if _numpy_import_error:
        raise RuntimeError(
            "Numpy dependency is not installed. Run: py -m pip install -r backend/requirements.txt"
        )
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

            frames = wav_file.readframes(wav_file.getnframes())
            audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            return audio, frame_rate
    except wave.Error as exc:
        raise ValueError(f"Invalid WAV audio: {exc}") from exc


def _transcribe_with_vosk(audio_bytes: bytes, started: float, model_load_ms: float) -> str:
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
            text = str(final.get("text", "")).strip()
            logger.debug(
                "stt provider=vosk model_load_ms=%.1f total_ms=%.1f bytes=%d frame_rate=%d chars=%d",
                model_load_ms,
                (time.perf_counter() - started) * 1000,
                len(audio_bytes),
                frame_rate,
                len(text),
            )
            return text
    except wave.Error as exc:
        raise ValueError(f"Invalid WAV audio: {exc}") from exc


def _transcribe_with_whisper(audio_bytes: bytes, started: float, model_load_ms: float) -> str:
    decode_started = time.perf_counter()
    audio, frame_rate = _wav_bytes_to_float32(audio_bytes)
    decode_ms = (time.perf_counter() - decode_started) * 1000
    model = _get_whisper_model()
    infer_started = time.perf_counter()
    segments, _info = model.transcribe(
        audio=audio,
        language=settings.stt_whisper_language or None,
        beam_size=settings.stt_whisper_beam_size,
        vad_filter=settings.stt_whisper_vad_filter,
    )
    infer_ms = (time.perf_counter() - infer_started) * 1000
    text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
    logger.info(
        "stt provider=whisper model_load_ms=%.1f decode_ms=%.1f infer_ms=%.1f total_ms=%.1f bytes=%d frame_rate=%d chars=%d",
        model_load_ms,
        decode_ms,
        infer_ms,
        (time.perf_counter() - started) * 1000,
        len(audio_bytes),
        frame_rate,
        len(text),
    )
    return text


def transcribe_wav_bytes(audio_bytes: bytes) -> str:
    if not audio_bytes:
        raise ValueError("No audio payload provided.")

    load_started = time.perf_counter()
    provider = (settings.stt_provider or "vosk").strip().lower()
    if provider == "faster_whisper":
        _get_whisper_model()
    elif provider == "vosk":
        _get_model()
    else:
        raise RuntimeError(f"Unsupported STT provider '{settings.stt_provider}'.")
    model_load_ms = (time.perf_counter() - load_started) * 1000
    started = time.perf_counter()
    if provider == "faster_whisper":
        return _transcribe_with_whisper(audio_bytes, started, model_load_ms)
    text = _transcribe_with_vosk(audio_bytes, started, model_load_ms)
    logger.info(
        "stt provider=vosk model_load_ms=%.1f total_ms=%.1f bytes=%d chars=%d",
        model_load_ms,
        (time.perf_counter() - started) * 1000,
        len(audio_bytes),
        len(text),
    )
    return text


def warmup_model() -> None:
    started = time.perf_counter()
    provider = (settings.stt_provider or "vosk").strip().lower()
    if provider == "faster_whisper":
        _get_whisper_model()
    elif provider == "vosk":
        _get_model()
    else:
        raise RuntimeError(f"Unsupported STT provider '{settings.stt_provider}'.")
    logger.info("stt provider=%s warmup complete in %.1fms", provider, (time.perf_counter() - started) * 1000)

from __future__ import annotations

import io
import logging
import time
import threading
import wave
from pathlib import Path

from .config import settings

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

_whisper_model_lock = threading.Lock()
_whisper_model = None
logger = logging.getLogger(__name__)


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


def _transcribe_with_whisper(audio_bytes: bytes, started: float, model_load_ms: float) -> str:
    decode_started = time.perf_counter()
    audio, frame_rate = _wav_bytes_to_float32(audio_bytes)
    max_seconds = max(0.5, float(settings.stt_max_audio_seconds))
    max_samples = int(frame_rate * max_seconds)
    if audio.size > max_samples:
        audio = audio[-max_samples:]
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
    _get_whisper_model()
    model_load_ms = (time.perf_counter() - load_started) * 1000
    started = time.perf_counter()
    return _transcribe_with_whisper(audio_bytes, started, model_load_ms)


def warmup_model() -> None:
    started = time.perf_counter()
    _get_whisper_model()
    logger.info(
        "stt provider=faster_whisper warmup complete in %.1fms",
        (time.perf_counter() - started) * 1000,
    )

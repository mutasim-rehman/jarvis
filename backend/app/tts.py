from __future__ import annotations

import io
import sys
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
    from kokoro import KPipeline

    _kokoro_import_error: str | None = None
except ImportError as exc:  # pragma: no cover - depends on environment packages
    KPipeline = None  # type: ignore[assignment]
    _kokoro_import_error = str(exc)

_pipeline_lock = threading.Lock()
_pipeline = None


def _resolve_model_path() -> Path:
    configured = Path(settings.tts_kokoro_model_path)
    if configured.is_absolute():
        return configured
    return Path(__file__).resolve().parents[2] / configured


def _ensure_model_available(model_path: Path) -> None:
    if not model_path.exists():
        raise RuntimeError(
            f"Kokoro model path '{model_path}' does not exist. "
            "Clone/download model files to this path."
        )
    has_weights = any(model_path.glob("*.pth")) or any(model_path.glob("*.safetensors"))
    if not has_weights:
        raise RuntimeError(
            f"Kokoro model weights not found in '{model_path}'. "
            "Run 'git lfs pull' in backend/models/Kokoro-82M to fetch weight files."
        )


def _get_pipeline():
    global _pipeline
    if sys.version_info >= (3, 13):
        raise RuntimeError(
            "Kokoro TTS currently requires Python 3.12 or lower. "
            "Use a Python 3.12 backend environment to enable Kokoro voice."
        )
    if _kokoro_import_error:
        raise RuntimeError(
            "Kokoro dependency is not installed. Run: py -m pip install -r backend/requirements.txt"
        )
    if _numpy_import_error:
        raise RuntimeError(
            "Numpy dependency is not installed. Run: py -m pip install -r backend/requirements.txt"
        )

    if _pipeline is not None:
        return _pipeline

    with _pipeline_lock:
        if _pipeline is not None:
            return _pipeline

        model_path = _resolve_model_path()
        _ensure_model_available(model_path)

        kwargs = {"lang_code": settings.tts_kokoro_lang_code}
        # Prefer local model clone first when API supports repo_id.
        try:
            _pipeline = KPipeline(**kwargs, repo_id=str(model_path))  # type: ignore[misc]
        except TypeError:
            _pipeline = KPipeline(**kwargs)  # type: ignore[misc]
        return _pipeline


def _text_chunks(text: str, max_chars: int = 260) -> list[str]:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return [normalized]

    chunks: list[str] = []
    current = ""
    for sentence in normalized.replace("!", ".").replace("?", ".").split("."):
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = sentence if not current else f"{current}. {sentence}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current + ".")
            current = sentence
    if current:
        chunks.append(current + ".")
    return chunks if chunks else [normalized]


def _wav_from_float32(audio: np.ndarray, sample_rate: int) -> bytes:
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())
    return buf.getvalue()


def synthesize_kokoro_wav(text: str, voice: str | None = None, speed: float | None = None) -> tuple[bytes, int]:
    clean_text = (text or "").strip()
    if not clean_text:
        raise ValueError("Text is required for TTS.")

    pipeline = _get_pipeline()
    selected_voice = (voice or settings.tts_kokoro_voice).strip() or settings.tts_kokoro_voice
    selected_speed = speed if speed is not None else settings.tts_speed
    sample_rate = settings.tts_sample_rate

    segments = _text_chunks(clean_text)
    generated: list[np.ndarray] = []
    pause = np.zeros(int(sample_rate * 0.06), dtype=np.float32)

    for idx, segment in enumerate(segments):
        try:
            generator = pipeline(segment, voice=selected_voice, speed=selected_speed)
        except TypeError:
            generator = pipeline(segment, voice=selected_voice)

        segment_added = False
        for _gs, _ps, audio in generator:
            arr = np.asarray(audio, dtype=np.float32).flatten()
            if arr.size == 0:
                continue
            generated.append(arr)
            segment_added = True

        if segment_added and idx < len(segments) - 1:
            generated.append(pause)

    if not generated:
        raise RuntimeError("Kokoro did not generate any audio for this text.")

    combined = np.concatenate(generated)
    return _wav_from_float32(combined, sample_rate), sample_rate

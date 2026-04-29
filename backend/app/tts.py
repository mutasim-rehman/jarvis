from __future__ import annotations

import io
import json
import logging
import shutil
import subprocess
import sys
import threading
import tempfile
import time
import wave
from collections.abc import Iterator
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
_piper_lock = threading.Lock()
_piper_voice = None
logger = logging.getLogger(__name__)

try:
    from piper.voice import PiperVoice

    _piper_import_error: str | None = None
except ImportError as exc:  # pragma: no cover - depends on environment packages
    PiperVoice = None  # type: ignore[assignment]
    _piper_import_error = str(exc)


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


def _resolve_path(path_value: str) -> Path:
    configured = Path(path_value)
    if configured.is_absolute():
        return configured
    return Path(__file__).resolve().parents[2] / configured


def _resolve_piper_model_path() -> Path:
    return _resolve_path(settings.tts_piper_model_path)


def _resolve_piper_config_path(model_path: Path) -> Path | None:
    configured = (settings.tts_piper_config_path or "").strip()
    if configured:
        return _resolve_path(configured)
    candidate = model_path.with_suffix(model_path.suffix + ".json")
    return candidate if candidate.exists() else None


def _validate_piper_model() -> tuple[Path, Path | None]:
    model_path = _resolve_piper_model_path()
    if not model_path.exists():
        raise RuntimeError(
            f"Piper model path '{model_path}' does not exist. "
            "Download a compatible Piper .onnx voice model to this path."
        )
    config_path = _resolve_piper_config_path(model_path)
    if config_path is not None and not config_path.exists():
        raise RuntimeError(f"Piper config path '{config_path}' does not exist.")
    return model_path, config_path


def _get_piper_voice():
    global _piper_voice
    if _piper_import_error:
        raise RuntimeError(_piper_import_error)
    if _piper_voice is not None:
        return _piper_voice
    with _piper_lock:
        if _piper_voice is not None:
            return _piper_voice
        model_path, config_path = _validate_piper_model()
        kwargs: dict[str, object] = {}
        if config_path is not None:
            kwargs["config_path"] = str(config_path)
        _piper_voice = PiperVoice.load(str(model_path), **kwargs)  # type: ignore[misc]
        return _piper_voice


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


def _synthesize_piper_python(text: str, speed: float | None = None) -> tuple[bytes, int]:
    if _numpy_import_error:
        raise RuntimeError(
            "Numpy dependency is not installed. Run: py -m pip install -r backend/requirements.txt"
        )
    voice = _get_piper_voice()
    selected_speed = speed if speed is not None else settings.tts_speed
    selected_speed = selected_speed if selected_speed > 0 else 1.0
    audio_chunks: list["np.ndarray"] = []
    for sentence in _text_chunks(text):
        for chunk in voice.synthesize(
            sentence,
            speaker_id=settings.tts_piper_speaker,
            length_scale=max(0.1, settings.tts_piper_length_scale / selected_speed),
            noise_scale=settings.tts_piper_noise_scale,
            noise_w=settings.tts_piper_noise_w,
        ):
            audio_chunks.append(np.asarray(chunk.audio_float_array, dtype=np.float32))
    if not audio_chunks:
        raise RuntimeError("Piper did not generate any audio for this text.")
    sample_rate = int(getattr(voice.config, "sample_rate", settings.tts_sample_rate))
    return _wav_from_float32(np.concatenate(audio_chunks), sample_rate), sample_rate


def _resolve_piper_executable() -> str:
    configured = (settings.tts_piper_executable or "").strip()
    if configured:
        candidate = Path(configured)
        if candidate.is_absolute() or candidate.exists():
            return str(candidate)
        return configured
    return "piper"


def _synthesize_piper_cli(text: str, speed: float | None = None) -> tuple[bytes, int]:
    model_path, config_path = _validate_piper_model()
    executable = _resolve_piper_executable()
    if shutil.which(executable) is None and not Path(executable).exists():
        raise RuntimeError(
            f"Piper executable '{executable}' not found. Install Piper or set tts_piper_executable."
        )

    selected_speed = speed if speed is not None else settings.tts_speed
    selected_speed = selected_speed if selected_speed > 0 else 1.0
    length_scale = max(0.1, settings.tts_piper_length_scale / selected_speed)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as out_file:
        out_path = Path(out_file.name)
    try:
        command = [
            executable,
            "--model",
            str(model_path),
            "--output_file",
            str(out_path),
            "--length_scale",
            str(length_scale),
            "--noise_scale",
            str(settings.tts_piper_noise_scale),
            "--noise_w",
            str(settings.tts_piper_noise_w),
            "--json-input",
        ]
        if config_path is not None:
            command.extend(["--config", str(config_path)])

        payload = {"text": text}
        if settings.tts_piper_speaker is not None:
            payload["speaker"] = settings.tts_piper_speaker
        proc = subprocess.run(  # noqa: S603
            command,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            stderr = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(f"Piper CLI synthesis failed: {stderr or 'unknown error'}")
        wav_bytes = out_path.read_bytes()
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
        return wav_bytes, sample_rate
    finally:
        out_path.unlink(missing_ok=True)


def synthesize_piper_wav(text: str, speed: float | None = None) -> tuple[bytes, int]:
    clean_text = (text or "").strip()
    if not clean_text:
        raise ValueError("Text is required for TTS.")

    if _piper_import_error is None:
        try:
            return _synthesize_piper_python(clean_text, speed=speed)
        except Exception as exc:
            # Fall through to CLI runtime when python runtime is unavailable at execution time.
            if "Piper executable" in str(exc):
                raise
    return _synthesize_piper_cli(clean_text, speed=speed)


def synthesize_tts_wav(text: str, voice: str | None = None, speed: float | None = None) -> tuple[bytes, int]:
    provider = (settings.tts_provider or "kokoro").strip().lower()
    started = time.perf_counter()
    if provider == "piper":
        wav_bytes, sample_rate = synthesize_piper_wav(text=text, speed=speed)
        logger.info(
            "tts provider=%s synth_ms=%.1f chars=%d sample_rate=%d",
            provider,
            (time.perf_counter() - started) * 1000,
            len((text or "").strip()),
            sample_rate,
        )
        return wav_bytes, sample_rate
    if provider == "kokoro":
        wav_bytes, sample_rate = synthesize_kokoro_wav(text=text, voice=voice, speed=speed)
        logger.info(
            "tts provider=%s synth_ms=%.1f chars=%d sample_rate=%d",
            provider,
            (time.perf_counter() - started) * 1000,
            len((text or "").strip()),
            sample_rate,
        )
        return wav_bytes, sample_rate
    raise RuntimeError(f"Unsupported TTS provider '{settings.tts_provider}'.")


def iter_tts_wav_chunks(
    text: str, voice: str | None = None, speed: float | None = None, max_chars: int | None = None
) -> Iterator[tuple[bytes, int]]:
    clean_text = (text or "").strip()
    if not clean_text:
        raise ValueError("Text is required for TTS.")

    chunk_chars = max_chars if max_chars is not None else settings.tts_stream_chunk_chars
    chunk_chars = max(60, int(chunk_chars))
    for segment in _text_chunks(clean_text, max_chars=chunk_chars):
        yield synthesize_tts_wav(segment, voice=voice, speed=speed)


def warmup_tts() -> None:
    # Keep warmup tiny to reduce startup impact.
    synthesize_tts_wav(text="ready", speed=1.0)

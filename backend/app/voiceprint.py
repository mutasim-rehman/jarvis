from __future__ import annotations

import io
import json
import logging
import threading
import time
import wave
from itertools import combinations
from pathlib import Path

import numpy as np

from .config import settings

try:
    import torch
    import torch.nn.functional as torch_functional
    from speechbrain.inference.speaker import EncoderClassifier

    _voice_import_error: str | None = None
except ImportError as exc:  # pragma: no cover
    torch = None  # type: ignore[assignment]
    torch_functional = None  # type: ignore[assignment]
    EncoderClassifier = None  # type: ignore[assignment]
    _voice_import_error = str(exc)

try:
    import torchaudio.functional as torchaudio_functional
except Exception:  # pragma: no cover
    torchaudio_functional = None  # type: ignore[assignment]

_lock = threading.Lock()
_classifier = None

_STORE_DIR = Path(__file__).resolve().parents[1] / "data" / "voiceprint"
_PROFILE_PATH = _STORE_DIR / "profile.json"
_PENDING_PATH = _STORE_DIR / "pending.json"
# Distinct phrases improve phonetic coverage and make a single replay clip less useful.
_STANDARD_ENROLLMENT_PHRASES: tuple[str, ...] = (
    "Jarvis, my voice secures this assistant.",
    "Open the calendar, dim the lights, and play soft jazz.",
    "The quick brown fox jumps over the lazy dog at midnight.",
    "I prefer warm coffee, fresh bread, and quiet mornings.",
    "Route nine twenty-one to the airport, please.",
)
_ENVIRONMENT_ENROLLMENT_PHRASES: tuple[str, ...] = (
    "Jarvis, recognize me while the room is noisy.",
    "This is my normal speak mode environment.",
)
_ENROLLMENT_PHRASES = _STANDARD_ENROLLMENT_PHRASES + _ENVIRONMENT_ENROLLMENT_PHRASES
_MIN_ENROLL_SAMPLES = len(_STANDARD_ENROLLMENT_PHRASES)
_TARGET_ENROLL_SAMPLES = len(_ENROLLMENT_PHRASES)
_VERIFY_THRESHOLD = 0.72
_PROFILE_VERSION = 2
_BLEND_MAX_WEIGHT = 0.7
logger = logging.getLogger(__name__)


def _ensure_store_dir() -> None:
    _STORE_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    _ensure_store_dir()
    path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")


def _get_classifier():
    global _classifier
    if _voice_import_error:
        raise RuntimeError(
            "Voiceprint dependencies are missing. Install backend requirements including speechbrain."
        )
    if _classifier is not None:
        return _classifier
    with _lock:
        if _classifier is not None:
            return _classifier
        _classifier = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb")
        return _classifier


def _wav_bytes_to_float32(audio_bytes: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        compression = wav_file.getcomptype()
        if channels != 1:
            raise ValueError("Voiceprint audio must be mono WAV.")
        if sample_width != 2:
            raise ValueError("Voiceprint audio must be 16-bit PCM WAV.")
        if compression != "NONE":
            raise ValueError("Voiceprint audio must be uncompressed PCM WAV.")
        frames = wav_file.readframes(wav_file.getnframes())
    arr = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    min_samples = sample_rate * max(0.1, float(settings.voiceprint_min_probe_seconds))
    if arr.size < min_samples:
        raise ValueError("Voice sample too short. Please speak for at least half a second.")
    return arr, sample_rate


def _resample_to_16khz(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    if sample_rate == 16000:
        return audio.astype(np.float32, copy=False)
    if audio.size == 0:
        return audio.astype(np.float32)
    if torch is not None and torchaudio_functional is not None:
        wav = torch.tensor(audio, dtype=torch.float32).unsqueeze(0)  # type: ignore[union-attr]
        resampled = torchaudio_functional.resample(wav, sample_rate, 16000).squeeze(0)
        return resampled.detach().cpu().numpy().astype(np.float32)
    if torch is not None and torch_functional is not None:
        wav = torch.tensor(audio, dtype=torch.float32).view(1, 1, -1)  # type: ignore[union-attr]
        output_len = max(1, int(round(audio.size * 16000 / sample_rate)))
        resampled = torch_functional.interpolate(wav, size=output_len, mode="linear", align_corners=False).view(-1)
        return resampled.detach().cpu().numpy().astype(np.float32)
    x_old = np.linspace(0.0, 1.0, num=audio.size, endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=max(1, int(audio.size * 16000 / sample_rate)), endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def _trim_to_voice(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    frame_size = max(1, int(sample_rate * 0.03))
    hop_size = max(1, int(sample_rate * 0.015))
    if audio.size < frame_size:
        return audio
    rms_values: list[float] = []
    starts: list[int] = []
    for start in range(0, audio.size - frame_size + 1, hop_size):
        frame = audio[start : start + frame_size]
        rms_values.append(float(np.sqrt(np.mean(frame * frame))))
        starts.append(start)
    if not rms_values:
        return audio
    rms = np.array(rms_values, dtype=np.float32)
    noise_floor = float(np.percentile(rms, 20))
    threshold = max(noise_floor * 2.2, 0.008)
    active = np.where(rms >= threshold)[0]
    if active.size == 0:
        raise ValueError("Voice sample is too quiet or mostly background noise.")
    pad = int(sample_rate * 0.12)
    start = max(0, starts[int(active[0])] - pad)
    end = min(audio.size, starts[int(active[-1])] + frame_size + pad)
    trimmed = audio[start:end]
    min_samples = int(sample_rate * max(0.1, float(settings.voiceprint_min_probe_seconds)))
    if trimmed.size < min_samples:
        raise ValueError("Voice sample too short after trimming background noise.")
    return trimmed.astype(np.float32, copy=False)


def _normalize_rms(audio: np.ndarray) -> np.ndarray:
    rms = float(np.sqrt(np.mean(audio * audio))) if audio.size else 0.0
    target = max(0.01, min(0.2, float(settings.voiceprint_target_rms)))
    if rms <= 1e-6:
        raise ValueError("Voice sample is too quiet.")
    gain = min(8.0, target / rms)
    return np.clip(audio * gain, -1.0, 1.0).astype(np.float32)


def _prepare_audio(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    conditioned = _trim_to_voice(audio, sample_rate)
    conditioned = _normalize_rms(conditioned)
    return _resample_to_16khz(conditioned, sample_rate)


def _to_embedding(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    classifier = _get_classifier()
    audio = _prepare_audio(audio, sample_rate)
    wav = torch.tensor(audio, dtype=torch.float32).unsqueeze(0)  # type: ignore[union-attr]
    with torch.no_grad():  # type: ignore[union-attr]
        emb = classifier.encode_batch(wav).squeeze().detach().cpu().numpy()
    norm = np.linalg.norm(emb)
    if norm <= 1e-8:
        raise RuntimeError("Unable to compute a stable voice embedding.")
    return emb / norm


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def _normalized_rows(values: list[list[float]]) -> np.ndarray:
    stack = np.array(values, dtype=np.float32)
    if stack.ndim == 1:
        stack = stack.reshape(1, -1)
    norms = np.linalg.norm(stack, axis=1, keepdims=True)
    if np.any(norms <= 1e-8):
        raise RuntimeError("Voiceprint profile contains an invalid embedding.")
    return stack / norms


def _profile_embeddings(profile: dict) -> np.ndarray | None:
    embeddings = profile.get("embeddings")
    if isinstance(embeddings, list) and embeddings:
        return _normalized_rows(embeddings)
    embedding = profile.get("embedding") or profile.get("centroid")
    if isinstance(embedding, list) and embedding:
        return _normalized_rows([embedding])
    return None


def _profile_centroid(profile: dict, embeddings: np.ndarray) -> np.ndarray:
    centroid = profile.get("centroid") or profile.get("embedding")
    if isinstance(centroid, list) and centroid:
        vector = np.array(centroid, dtype=np.float32)
    else:
        vector = np.mean(embeddings, axis=0)
    norm = np.linalg.norm(vector)
    if norm <= 1e-8:
        raise RuntimeError("Voiceprint profile contains an invalid centroid.")
    return vector / norm


def _pairwise_scores(embeddings: np.ndarray) -> list[float]:
    return [
        round(_cosine(embeddings[left], embeddings[right]), 4)
        for left, right in combinations(range(len(embeddings)), 2)
    ]


def _clamp(value: float, floor: float, ceiling: float) -> float:
    return max(floor, min(ceiling, value))


def _calibrated_threshold(embeddings: np.ndarray) -> tuple[float, dict]:
    pairwise = _pairwise_scores(embeddings)
    if pairwise:
        intra_min = min(pairwise)
        intra_p10 = float(np.percentile(np.array(pairwise, dtype=np.float32), 10))
        raw_threshold = intra_min * float(settings.voiceprint_calibration_margin)
    else:
        intra_min = _VERIFY_THRESHOLD
        intra_p10 = _VERIFY_THRESHOLD
        raw_threshold = _VERIFY_THRESHOLD
    configured = float(settings.voiceprint_verify_threshold)
    if configured > 0:
        threshold = configured
    else:
        threshold = _clamp(
            raw_threshold,
            float(settings.voiceprint_threshold_floor),
            float(settings.voiceprint_threshold_ceiling),
        )
    return round(threshold, 4), {
        "min": round(intra_min, 4),
        "p10": round(intra_p10, 4),
        "pairs": pairwise,
    }


def _score_probe(probe: np.ndarray, embeddings: np.ndarray, centroid: np.ndarray) -> tuple[float, dict]:
    gallery_scores = np.array([_cosine(probe, enrolled) for enrolled in embeddings], dtype=np.float32)
    max_score = float(np.max(gallery_scores))
    centroid_score = _cosine(probe, centroid)
    mode = settings.voiceprint_score_mode.lower().strip()
    if mode == "centroid":
        score = centroid_score
    elif mode == "max":
        score = max_score
    else:
        score = (_BLEND_MAX_WEIGHT * max_score) + ((1 - _BLEND_MAX_WEIGHT) * centroid_score)
    return score, {
        "mode": mode if mode in {"centroid", "max", "blend"} else "blend",
        "max_score": round(max_score, 4),
        "centroid_score": round(centroid_score, 4),
        "gallery_size": int(len(embeddings)),
    }


def get_voiceprint_status() -> dict:
    profile = _read_json(_PROFILE_PATH)
    enabled = _profile_embeddings(profile) is not None
    pending = _read_json(_PENDING_PATH)
    embeddings = pending.get("embeddings") or []
    collected = len(embeddings) if embeddings else int(pending.get("samples_collected", 0))
    phrases = list(_ENROLLMENT_PHRASES)
    next_phrase = ""
    if (
        not enabled
        and _PENDING_PATH.exists()
        and collected < _TARGET_ENROLL_SAMPLES
        and phrases
    ):
        idx = min(collected, len(phrases) - 1)
        next_phrase = phrases[idx]
    return {
        "enabled": enabled,
        "samples_collected": collected,
        "min_required_samples": _MIN_ENROLL_SAMPLES,
        "target_samples": _TARGET_ENROLL_SAMPLES,
        "threshold": float(profile.get("threshold", _VERIFY_THRESHOLD)),
        "enrollment_phrases": phrases,
        "next_enrollment_phrase": next_phrase,
    }


def reset_voiceprint() -> dict:
    if _PROFILE_PATH.exists():
        _PROFILE_PATH.unlink()
    _write_json(_PENDING_PATH, {"samples_collected": 0, "embeddings": []})
    return get_voiceprint_status()


def enroll_voiceprint_sample(audio_bytes: bytes) -> dict:
    audio, sample_rate = _wav_bytes_to_float32(audio_bytes)
    emb = _to_embedding(audio, sample_rate).tolist()
    pending = _read_json(_PENDING_PATH)
    embeddings = pending.get("embeddings", [])
    embeddings.append(emb)
    payload = {
        "samples_collected": len(embeddings),
        "embeddings": embeddings,
    }
    _write_json(_PENDING_PATH, payload)
    n = len(embeddings)
    phrases = list(_ENROLLMENT_PHRASES)
    next_phrase = ""
    if n < _TARGET_ENROLL_SAMPLES and phrases:
        idx = min(n, len(phrases) - 1)
        next_phrase = phrases[idx]
    return {
        "samples_collected": n,
        "min_required_samples": _MIN_ENROLL_SAMPLES,
        "target_samples": _TARGET_ENROLL_SAMPLES,
        "ready_to_finalize": n >= _MIN_ENROLL_SAMPLES,
        "enrollment_phrases": phrases,
        "next_enrollment_phrase": next_phrase,
    }


def finalize_voiceprint() -> dict:
    pending = _read_json(_PENDING_PATH)
    embeddings = pending.get("embeddings", [])
    if len(embeddings) < _MIN_ENROLL_SAMPLES:
        raise ValueError(f"Need at least {_MIN_ENROLL_SAMPLES} samples before finalize.")
    stack = _normalized_rows(embeddings)
    mean = np.mean(stack, axis=0)
    norm = np.linalg.norm(mean)
    if norm <= 1e-8:
        raise RuntimeError("Enrollment failed due to invalid voice embedding.")
    mean = mean / norm
    threshold, enrollment_scores = _calibrated_threshold(stack)
    profile = {
        "version": _PROFILE_VERSION,
        "embeddings": stack.tolist(),
        "centroid": mean.tolist(),
        "embedding": mean.tolist(),
        "threshold": threshold,
        "enrollment_scores": enrollment_scores,
        "score_mode": settings.voiceprint_score_mode,
    }
    _write_json(_PROFILE_PATH, profile)
    if _PENDING_PATH.exists():
        _PENDING_PATH.unlink()
    return get_voiceprint_status()


def warmup_voiceprint() -> None:
    started = time.perf_counter()
    _get_classifier()
    logger.info(
        "voiceprint warmup complete in %.1fms",
        (time.perf_counter() - started) * 1000,
    )


def verify_voiceprint(audio_bytes: bytes) -> dict:
    profile = _read_json(_PROFILE_PATH)
    embeddings = _profile_embeddings(profile)
    if embeddings is None:
        return {"matched": False, "score": 0.0, "threshold": _VERIFY_THRESHOLD, "enabled": False}
    audio, sample_rate = _wav_bytes_to_float32(audio_bytes)
    probe = _to_embedding(audio, sample_rate)
    centroid = _profile_centroid(profile, embeddings)
    score, score_details = _score_probe(probe, embeddings, centroid)
    threshold = float(profile.get("threshold", _VERIFY_THRESHOLD))
    return {
        "matched": score >= threshold,
        "score": round(score, 4),
        "threshold": threshold,
        "enabled": True,
        "details": score_details,
    }

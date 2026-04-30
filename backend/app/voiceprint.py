from __future__ import annotations

import io
import json
import threading
import wave
from pathlib import Path

import numpy as np

try:
    import torch
    from speechbrain.inference.speaker import EncoderClassifier

    _voice_import_error: str | None = None
except ImportError as exc:  # pragma: no cover
    torch = None  # type: ignore[assignment]
    EncoderClassifier = None  # type: ignore[assignment]
    _voice_import_error = str(exc)

_lock = threading.Lock()
_classifier = None

_STORE_DIR = Path(__file__).resolve().parents[1] / "data" / "voiceprint"
_PROFILE_PATH = _STORE_DIR / "profile.json"
_PENDING_PATH = _STORE_DIR / "pending.json"
_MIN_ENROLL_SAMPLES = 3
_VERIFY_THRESHOLD = 0.72


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
    if arr.size < sample_rate * 0.45:
        raise ValueError("Voice sample too short. Please speak for at least half a second.")
    return arr, sample_rate


def _to_embedding(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    classifier = _get_classifier()
    if sample_rate != 16000:
        x_old = np.linspace(0.0, 1.0, num=audio.size, endpoint=False)
        x_new = np.linspace(0.0, 1.0, num=max(1, int(audio.size * 16000 / sample_rate)), endpoint=False)
        audio = np.interp(x_new, x_old, audio).astype(np.float32)
    wav = torch.tensor(audio, dtype=torch.float32).unsqueeze(0)  # type: ignore[union-attr]
    with torch.no_grad():  # type: ignore[union-attr]
        emb = classifier.encode_batch(wav).squeeze().detach().cpu().numpy()
    norm = np.linalg.norm(emb)
    if norm <= 1e-8:
        raise RuntimeError("Unable to compute a stable voice embedding.")
    return emb / norm


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def get_voiceprint_status() -> dict:
    profile = _read_json(_PROFILE_PATH)
    pending = _read_json(_PENDING_PATH)
    return {
        "enabled": bool(profile.get("embedding")),
        "samples_collected": int(pending.get("samples_collected", 0)),
        "min_required_samples": _MIN_ENROLL_SAMPLES,
        "threshold": float(profile.get("threshold", _VERIFY_THRESHOLD)),
    }


def reset_voiceprint() -> dict:
    if _PROFILE_PATH.exists():
        _PROFILE_PATH.unlink()
    if _PENDING_PATH.exists():
        _PENDING_PATH.unlink()
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
    return {
        "samples_collected": len(embeddings),
        "min_required_samples": _MIN_ENROLL_SAMPLES,
        "ready_to_finalize": len(embeddings) >= _MIN_ENROLL_SAMPLES,
    }


def finalize_voiceprint() -> dict:
    pending = _read_json(_PENDING_PATH)
    embeddings = pending.get("embeddings", [])
    if len(embeddings) < _MIN_ENROLL_SAMPLES:
        raise ValueError(f"Need at least {_MIN_ENROLL_SAMPLES} samples before finalize.")
    stack = np.array(embeddings, dtype=np.float32)
    mean = np.mean(stack, axis=0)
    norm = np.linalg.norm(mean)
    if norm <= 1e-8:
        raise RuntimeError("Enrollment failed due to invalid voice embedding.")
    mean = mean / norm
    profile = {
        "embedding": mean.tolist(),
        "threshold": _VERIFY_THRESHOLD,
    }
    _write_json(_PROFILE_PATH, profile)
    if _PENDING_PATH.exists():
        _PENDING_PATH.unlink()
    return get_voiceprint_status()


def verify_voiceprint(audio_bytes: bytes) -> dict:
    profile = _read_json(_PROFILE_PATH)
    if not profile.get("embedding"):
        return {"matched": False, "score": 0.0, "threshold": _VERIFY_THRESHOLD, "enabled": False}
    audio, sample_rate = _wav_bytes_to_float32(audio_bytes)
    probe = _to_embedding(audio, sample_rate)
    enrolled = np.array(profile["embedding"], dtype=np.float32)
    score = _cosine(probe, enrolled)
    threshold = float(profile.get("threshold", _VERIFY_THRESHOLD))
    return {
        "matched": score >= threshold,
        "score": round(score, 4),
        "threshold": threshold,
        "enabled": True,
    }

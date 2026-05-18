import io
import json
import math
import os
import sys
import wave

import numpy as np
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.config import settings
from backend.app import voiceprint


def _wav_bytes(seconds: float = 0.7, sample_rate: int = 16000, amplitude: float = 0.3) -> bytes:
    frames = int(seconds * sample_rate)
    samples = []
    for i in range(frames):
        value = amplitude * math.sin(2 * math.pi * 220 * (i / sample_rate))
        samples.append(int(max(-1.0, min(1.0, value)) * 32767))
    pcm = np.array(samples, dtype=np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())
    return buf.getvalue()


@pytest.fixture()
def isolated_voiceprint_store(tmp_path, monkeypatch):
    profile = tmp_path / "profile.json"
    pending = tmp_path / "pending.json"
    monkeypatch.setattr(voiceprint, "_STORE_DIR", tmp_path)
    monkeypatch.setattr(voiceprint, "_PROFILE_PATH", profile)
    monkeypatch.setattr(voiceprint, "_PENDING_PATH", pending)
    monkeypatch.setattr(settings, "voiceprint_verify_threshold", 0.0)
    monkeypatch.setattr(settings, "voiceprint_score_mode", "blend")
    monkeypatch.setattr(settings, "voiceprint_calibration_margin", 0.85)
    monkeypatch.setattr(settings, "voiceprint_threshold_floor", 0.58)
    monkeypatch.setattr(settings, "voiceprint_threshold_ceiling", 0.78)
    monkeypatch.setattr(settings, "voiceprint_min_probe_seconds", 0.45)
    monkeypatch.setattr(settings, "voiceprint_target_rms", 0.07)
    return profile, pending


def test_finalize_stores_embedding_gallery_and_calibrated_threshold(isolated_voiceprint_store):
    profile_path, pending_path = isolated_voiceprint_store
    embeddings = [
        [1.0, 0.0],
        [0.9, math.sqrt(1 - 0.9**2)],
        [0.8, 0.6],
        [0.95, math.sqrt(1 - 0.95**2)],
        [0.88, math.sqrt(1 - 0.88**2)],
    ]
    pending_path.write_text(json.dumps({"samples_collected": 5, "embeddings": embeddings}), encoding="utf-8")

    status = voiceprint.finalize_voiceprint()
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    assert status["enabled"] is True
    assert len(profile["embeddings"]) == 5
    assert "centroid" in profile
    assert profile["threshold"] == 0.68
    assert profile["enrollment_scores"]["min"] == 0.8
    assert not pending_path.exists()


def test_verify_uses_gallery_score_over_centroid(isolated_voiceprint_store, monkeypatch):
    profile_path, _pending_path = isolated_voiceprint_store
    monkeypatch.setattr(settings, "voiceprint_score_mode", "max")
    monkeypatch.setattr(
        voiceprint,
        "_to_embedding",
        lambda _audio, _sample_rate: np.array([0.0, 1.0], dtype=np.float32),
    )
    profile_path.write_text(
        json.dumps(
            {
                "embeddings": [[1.0, 0.0], [0.0, 1.0]],
                "centroid": [0.7071, 0.7071],
                "threshold": 0.9,
            }
        ),
        encoding="utf-8",
    )

    result = voiceprint.verify_voiceprint(_wav_bytes())

    assert result["matched"] is True
    assert result["score"] == 1.0
    assert result["details"]["gallery_size"] == 2


def test_old_single_embedding_profile_still_verifies(isolated_voiceprint_store, monkeypatch):
    profile_path, _pending_path = isolated_voiceprint_store
    monkeypatch.setattr(settings, "voiceprint_score_mode", "max")
    monkeypatch.setattr(
        voiceprint,
        "_to_embedding",
        lambda _audio, _sample_rate: np.array([1.0, 0.0], dtype=np.float32),
    )
    profile_path.write_text(json.dumps({"embedding": [1.0, 0.0], "threshold": 0.95}), encoding="utf-8")

    result = voiceprint.verify_voiceprint(_wav_bytes())

    assert result["matched"] is True
    assert result["details"]["gallery_size"] == 1


def test_configured_threshold_overrides_calibration(isolated_voiceprint_store, monkeypatch):
    profile_path, pending_path = isolated_voiceprint_store
    monkeypatch.setattr(settings, "voiceprint_verify_threshold", 0.73)
    pending_path.write_text(
        json.dumps(
            {
                "samples_collected": 5,
                "embeddings": [[1.0, 0.0], [0.8, 0.6], [0.9, 0.43589], [0.95, 0.31225], [0.88, 0.475]],
            }
        ),
        encoding="utf-8",
    )

    voiceprint.finalize_voiceprint()
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    assert profile["threshold"] == 0.73


def test_too_short_voiceprint_audio_is_rejected(isolated_voiceprint_store):
    profile_path, _pending_path = isolated_voiceprint_store
    profile_path.write_text(json.dumps({"embedding": [1.0, 0.0], "threshold": 0.95}), encoding="utf-8")

    with pytest.raises(ValueError, match="too short"):
        voiceprint.verify_voiceprint(_wav_bytes(seconds=0.1))

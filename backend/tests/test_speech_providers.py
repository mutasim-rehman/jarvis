import base64
import json
import os
import sys

from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.config import settings
from backend.app.main import app

client = TestClient(app)


def test_transcribe_endpoint_uses_provider_dispatch(monkeypatch):
    import backend.app.main

    def mock_transcribe_wav_bytes(audio_bytes: bytes) -> str:
        assert audio_bytes == b"fake-wav-payload"
        return "hello world"

    monkeypatch.setattr(settings, "stt_provider", "faster_whisper")
    monkeypatch.setattr(backend.app.main, "transcribe_wav_bytes", mock_transcribe_wav_bytes)

    response = client.post("/api/transcribe", content=b"fake-wav-payload")
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "hello world"
    assert "timing_ms" in data["meta"]


def test_transcribe_runtime_error_maps_to_503(monkeypatch):
    import backend.app.main

    def mock_transcribe_wav_bytes(_audio_bytes: bytes) -> str:
        raise RuntimeError("stt provider unavailable")

    monkeypatch.setattr(backend.app.main, "transcribe_wav_bytes", mock_transcribe_wav_bytes)
    response = client.post("/api/transcribe", content=b"fake-wav-payload")
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]


def test_tts_endpoint_uses_provider_dispatch(monkeypatch):
    import backend.app.main

    def mock_synthesize_tts_wav(text: str, voice: str | None, speed: float | None):
        assert text == "hello"
        assert voice == "voice-x"
        assert speed == 1.1
        return b"RIFFxxxxWAVE", 22050

    monkeypatch.setattr(settings, "tts_provider", "piper")
    monkeypatch.setattr(backend.app.main, "synthesize_tts_wav", mock_synthesize_tts_wav)

    response = client.post("/api/tts", json={"text": "hello", "voice": "voice-x", "speed": 1.1})
    assert response.status_code == 200
    data = response.json()
    assert data["sample_rate"] == 22050
    assert data["format"] == "wav"
    assert data["provider"] == "piper"
    assert data["voice"] == "voice-x"
    assert base64.b64decode(data["audio_base64"]) == b"RIFFxxxxWAVE"


def test_tts_runtime_error_maps_to_503(monkeypatch):
    import backend.app.main

    def mock_synthesize_tts_wav(text: str, voice: str | None, speed: float | None):
        raise RuntimeError("tts provider unavailable")

    monkeypatch.setattr(backend.app.main, "synthesize_tts_wav", mock_synthesize_tts_wav)
    response = client.post("/api/tts", json={"text": "hello"})
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]


def test_tts_stream_endpoint_emits_chunks_and_done(monkeypatch):
    import backend.app.main

    def mock_iter_tts_wav_chunks(text: str, voice: str | None, speed: float | None):
        assert text == "hello world"
        assert voice is None
        assert speed is None
        yield (b"RIFFchunk1WAVE", 22050)
        yield (b"RIFFchunk2WAVE", 22050)

    monkeypatch.setattr(settings, "voice_streaming_enabled", True)
    monkeypatch.setattr(settings, "tts_provider", "piper")
    monkeypatch.setattr(backend.app.main, "iter_tts_wav_chunks", mock_iter_tts_wav_chunks)

    response = client.post("/api/tts/stream", json={"text": "hello world"})
    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.strip()]
    assert len(lines) == 3

    first = json.loads(lines[0])
    second = json.loads(lines[1])
    done = json.loads(lines[2])
    assert first["type"] == "audio_chunk"
    assert second["type"] == "audio_chunk"
    assert done["type"] == "done"
    assert done["provider"] == "piper"


def test_tts_stream_endpoint_returns_404_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "voice_streaming_enabled", False)
    response = client.post("/api/tts/stream", json={"text": "hello world"})
    assert response.status_code == 404

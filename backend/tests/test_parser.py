import pytest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fastapi.testclient import TestClient

from backend.app.main import app
from shared.schema import RouteKind, SCHEMA_VERSION

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["schema_version"] == SCHEMA_VERSION


def test_parse_api_mock(monkeypatch):
    from backend.app.parser import ActionCommand
    from shared.schema import AssistantResponse, IntentType

    async def mock_parse_intent(text: str):
        return AssistantResponse(
            message="Opening Chrome now.",
            command=ActionCommand(intent=IntentType.OPEN_APP, target="chrome"),
            route=RouteKind.DESKTOP_EXECUTION,
        )

    import backend.app.main

    monkeypatch.setattr(backend.app.main, "parse_intent", mock_parse_intent)

    response = client.post("/api/parse", json={"text": "open chrome"})
    assert response.status_code == 200
    data = response.json()
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["command"]["message"] == "Opening Chrome now."
    assert data["command"]["route"] == "desktop_execution"
    assert data["command"]["command"]["intent"] == "OPEN_APP"
    assert data["command"]["command"]["target"] == "chrome"
    assert data["original_text"] == "open chrome"


def test_parse_requires_api_key_when_enabled(monkeypatch):
    from backend.app.config import settings

    monkeypatch.setattr(settings, "api_require_auth", True)
    monkeypatch.setattr(settings, "api_dev_token", "secret-key")

    response = client.post("/api/parse", json={"text": "hi"})
    assert response.status_code == 401

    async def mock_parse_intent(text: str):
        from shared.schema import AssistantResponse

        return AssistantResponse(message="Hi.", command=None, route=RouteKind.INFORMATIONAL)

    import backend.app.main

    monkeypatch.setattr(backend.app.main, "parse_intent", mock_parse_intent)

    response = client.post(
        "/api/parse",
        json={"text": "hi"},
        headers={"X-API-Key": "secret-key"},
    )
    assert response.status_code == 200

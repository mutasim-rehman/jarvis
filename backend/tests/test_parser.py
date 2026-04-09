import pytest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_parse_api_mock(monkeypatch):
    from backend.app.parser import ActionCommand
    from shared.schema import IntentType
    
    async def mock_parse_intent(text: str):
        return ActionCommand(intent=IntentType.OPEN_APP, target="chrome")
        
    import backend.app.main
    monkeypatch.setattr(backend.app.main, "parse_intent", mock_parse_intent)
    
    response = client.post("/api/parse", json={"text": "open chrome"})
    assert response.status_code == 200
    data = response.json()
    assert data["command"]["intent"] == "OPEN_APP"
    assert data["command"]["target"] == "chrome"
    assert data["original_text"] == "open chrome"

import os
import sys
import time

from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.main import app


client = TestClient(app)


def test_parse_heuristic_path_under_budget():
    from backend.app.parser import parse_intent
    import asyncio

    started = time.perf_counter()
    result = asyncio.run(parse_intent("play some music"))
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert result.command is not None
    assert result.command.intent == "PLAY_MUSIC"
    assert elapsed_ms < 350


def test_interact_endpoint_fast_path_under_budget(monkeypatch):
    from shared.schema import AssistantResponse, RouteKind
    import backend.app.main as main_module

    async def fake_parse_intent(text: str, chat_provider: str | None = None):
        del text, chat_provider
        return AssistantResponse(message="Done.", command=None, route=RouteKind.INFORMATIONAL)

    monkeypatch.setattr(main_module, "parse_intent", fake_parse_intent)

    started = time.perf_counter()
    response = client.post("/api/interact", json={"text": "hello"})
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert response.status_code == 200
    assert response.json()["assistant_response"]["message"] == "Done."
    assert elapsed_ms < 800

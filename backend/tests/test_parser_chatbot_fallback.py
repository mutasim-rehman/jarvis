"""Parser no longer routes through chatbot; orchestrator handles planning."""
import asyncio
import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from shared.schema import OrchestratorPlan


@pytest.mark.asyncio
async def test_orchestrator_chat_only_response(monkeypatch):
    import backend.app.parser as parser_module

    async def fake_plan(text, catalog=None):
        return (
            OrchestratorPlan(
                goal="joke",
                reasoning="Here is a light-hearted reply, Sir.",
                steps=[],
            ),
            {"orchestrator_provider": "gemini"},
        )

    monkeypatch.setattr(parser_module, "orchestrator_plan", fake_plan)
    monkeypatch.setattr("backend.app.config.settings.orchestrator_disabled", False)

    response = await parser_module.parse_intent("tell me a joke")
    assert response.command is None
    assert response.route.value == "informational"
    assert "Sir" in response.message or response.message


@pytest.mark.asyncio
async def test_chat_provider_param_ignored(monkeypatch):
    import backend.app.parser as parser_module

    seen = {"called": False}

    async def fake_plan(text, catalog=None):
        seen["called"] = True
        return (
            OrchestratorPlan(goal="hi", reasoning="Hello.", steps=[]),
            {"orchestrator_provider": "gemini"},
        )

    monkeypatch.setattr(parser_module, "orchestrator_plan", fake_plan)
    response = await parser_module.parse_intent("hello there", chat_provider="ollama")
    assert seen["called"] is True
    assert response.message

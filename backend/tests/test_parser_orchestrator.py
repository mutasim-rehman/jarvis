import asyncio
import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.parser import parse_intent
from shared.schema import OrchestratorPlan, RouteKind, Task


@pytest.mark.asyncio
async def test_parse_orchestrator_plan(monkeypatch):
    async def fake_plan(text, catalog=None):
        return (
            OrchestratorPlan(
                goal="open cursor",
                reasoning="Opening Cursor for you.",
                steps=[Task(action="OPEN_APP", target="cursor")],
            ),
            {"orchestrator_provider": "gemini", "plan_steps": 1},
        )

    monkeypatch.setattr("backend.app.parser.orchestrator_plan", fake_plan)
    monkeypatch.setattr("backend.app.config.settings.orchestrator_disabled", False)

    result = await parse_intent("open cursor")
    assert result.route == RouteKind.DESKTOP_EXECUTION
    assert result.command is not None
    assert result.command.intent == "ORCHESTRATED"
    assert result.command.tasks[0].action == "OPEN_APP"


@pytest.mark.asyncio
async def test_parse_legacy_rollback(monkeypatch):
    monkeypatch.setattr("backend.app.config.settings.orchestrator_disabled", True)
    result = await parse_intent("play some music")
    assert result.command is not None
    assert result.command.intent == "PLAY_MUSIC"
    assert result.meta.get("path") == "legacy_heuristic_forced"


def test_parse_quick_greeting():
    result = asyncio.run(parse_intent("hello"))
    assert result.command is None
    assert result.route == RouteKind.INFORMATIONAL

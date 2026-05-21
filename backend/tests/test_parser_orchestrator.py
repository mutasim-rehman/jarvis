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
    result = await parse_intent("open cursor")
    assert result.route == RouteKind.DESKTOP_EXECUTION
    assert result.command is not None
    assert result.command.intent == "ORCHESTRATED"
    assert result.command.tasks[0].action == "OPEN_APP"


def test_parse_quick_greeting():
    result = asyncio.run(parse_intent("hello"))
    assert result.command is None
    assert result.route == RouteKind.INFORMATIONAL

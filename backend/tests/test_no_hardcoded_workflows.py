"""Ensure routing uses runtime orchestrator plans only (no WORKFLOWS / legacy router)."""

import importlib
import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


def test_workflows_module_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("shared.workflows")


def test_legacy_router_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("backend.app.legacy_router")


@pytest.mark.asyncio
async def test_action_request_uses_orchestrator_plan(monkeypatch):
    from backend.app import parser as parser_mod
    from shared.schema import OrchestratorPlan, RouteKind, Task

    async def fake_plan(text, catalog=None):
        return (
            OrchestratorPlan(
                goal="play",
                reasoning="Playing music.",
                steps=[Task(action="PLAY_MUSIC", target="jazz")],
            ),
            {"orchestrator_provider": "gemini", "path": "test"},
        )

    monkeypatch.setattr(parser_mod, "orchestrator_plan", fake_plan)
    result = await parser_mod.parse_intent("play jazz")
    assert result.meta.get("path") == "orchestrator_plan"
    assert result.command is not None
    assert result.command.intent == "ORCHESTRATED"
    assert result.route == RouteKind.DESKTOP_EXECUTION

"""parse_intent behavior with mocked orchestrator (no live LLM)."""
import asyncio
import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from shared.schema import OrchestratorPlan, Task


@pytest.fixture
def parser_module():
    import backend.app.parser as p

    return p


def _mock_plan(monkeypatch, parser_module, plan: OrchestratorPlan, meta=None):
    async def fake_plan(text, catalog=None):
        return plan, meta or {"orchestrator_provider": "gemini"}

    monkeypatch.setattr(parser_module, "orchestrator_plan", fake_plan)


def test_orchestrator_play_music(parser_module, monkeypatch):
    _mock_plan(
        monkeypatch,
        parser_module,
        OrchestratorPlan(
            goal="play music",
            reasoning="Playing music.",
            steps=[Task(action="PLAY_MUSIC", target=None)],
        ),
    )
    r = asyncio.run(parser_module.parse_intent("play some music"))
    assert r.command is not None
    assert r.command.intent == "ORCHESTRATED"
    assert r.command.tasks[0].action == "PLAY_MUSIC"


def test_quick_path_hello_no_command(parser_module, monkeypatch):
    _mock_plan(
        monkeypatch,
        parser_module,
        OrchestratorPlan(goal="x", steps=[Task(action="HANDLE_ASSIGNMENTS")]),
    )
    r = asyncio.run(parser_module.parse_intent("hello"))
    assert r.command is None


def test_misconduct_no_command(parser_module, monkeypatch):
    _mock_plan(
        monkeypatch,
        parser_module,
        OrchestratorPlan(
            goal="homework",
            steps=[Task(action="HANDLE_ASSIGNMENTS")],
        ),
    )
    r = asyncio.run(parser_module.parse_intent("please do my homework for me"))
    assert r.command is None


def test_orchestrator_focus_mode(parser_module, monkeypatch):
    _mock_plan(
        monkeypatch,
        parser_module,
        OrchestratorPlan(
            goal="focus",
            reasoning="Entering focus mode.",
            steps=[Task(action="OPEN_APP", target="cursor")],
        ),
    )
    r = asyncio.run(parser_module.parse_intent("set the mood"))
    assert r.command is not None
    assert r.command.tasks[0].action == "OPEN_APP"

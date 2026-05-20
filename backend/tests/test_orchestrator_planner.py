import json
import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.orchestrator.planner import _parse_plan_json, plan
from shared.schema import OrchestratorPlan, Task, ToolCatalog, ToolCapability, ToolDefinition


def _sample_catalog() -> ToolCatalog:
    tools = [
        ToolDefinition(name="OPEN_APP", category="app", description="Launch app", parameters=[]),
        ToolDefinition(name="PLAY_MUSIC", category="music", description="Play music", requires=["spotify_auth"]),
    ]
    return ToolCatalog(
        capabilities=[
            ToolCapability(tool=t, available=True) for t in tools
        ],
        discovered_apps=["cursor", "spotify"],
        capability_tags=["spotify_auth"],
    )


def test_parse_plan_json_valid():
    raw = json.dumps(
        {
            "goal": "coding setup",
            "reasoning": "Opening Cursor and starting focus music.",
            "steps": [
                {"action": "OPEN_APP", "target": "cursor"},
                {"action": "PLAY_MUSIC", "target": "lo-fi"},
            ],
        }
    )
    plan_obj = _parse_plan_json(raw, _sample_catalog())
    assert len(plan_obj.steps) == 2
    assert plan_obj.steps[0].action == "OPEN_APP"
    assert plan_obj.steps[1].target == "lo-fi"


def test_parse_plan_json_skips_unavailable_action():
    raw = json.dumps(
        {
            "goal": "x",
            "steps": [{"action": "NOT_A_REAL_TOOL", "target": "x"}],
        }
    )
    plan_obj = _parse_plan_json(raw, _sample_catalog())
    assert plan_obj.steps == []


@pytest.mark.asyncio
async def test_plan_uses_gemini_mock(monkeypatch):
    catalog = _sample_catalog()

    async def fake_fetch(force=False):
        return catalog

    async def fake_gemini(system, user):
        payload = {
            "goal": "play music",
            "reasoning": "Playing your music now.",
            "steps": [{"action": "PLAY_MUSIC", "target": None}],
        }
        return json.dumps(payload), {"provider": "gemini", "timing_ms": 10}

    monkeypatch.setattr("backend.app.orchestrator.catalog_client.fetch_catalog", fake_fetch)
    monkeypatch.setattr("backend.app.orchestrator.planner.gemini_plan.generate_plan_json", fake_gemini)
    monkeypatch.setattr("backend.app.config.settings.orchestrator_provider", "gemini")
    monkeypatch.setattr("backend.app.config.settings.orchestrator_max_steps", 8)

    plan_obj, meta = await plan("play some music")
    assert len(plan_obj.steps) == 1
    assert plan_obj.steps[0].action == "PLAY_MUSIC"
    assert meta["orchestrator_provider"] == "gemini"


@pytest.mark.asyncio
async def test_plan_falls_back_to_ollama_on_gemini_error(monkeypatch):
    catalog = _sample_catalog()

    async def fake_fetch(force=False):
        return catalog

    async def fail_gemini(system, user):
        raise RuntimeError("no gemini key")

    async def fake_ollama(system, user):
        payload = {
            "goal": "open app",
            "reasoning": "Opening Chrome.",
            "steps": [{"action": "OPEN_APP", "target": "chrome"}],
        }
        return json.dumps(payload), {"provider": "ollama", "timing_ms": 5}

    monkeypatch.setattr("backend.app.orchestrator.catalog_client.fetch_catalog", fake_fetch)
    monkeypatch.setattr("backend.app.orchestrator.planner.gemini_plan.generate_plan_json", fail_gemini)
    monkeypatch.setattr("backend.app.orchestrator.planner.ollama_plan.generate_plan_json", fake_ollama)
    monkeypatch.setattr("backend.app.config.settings.orchestrator_provider", "gemini")

    plan_obj, meta = await plan("open chrome")
    assert plan_obj.steps[0].action == "OPEN_APP"
    assert meta["orchestrator_provider"] == "ollama"


@pytest.mark.asyncio
async def test_plan_json_repair_retry(monkeypatch):
    catalog = _sample_catalog()
    calls = {"n": 0}

    async def fake_fetch(force=False):
        return catalog

    async def flaky_gemini(system, user):
        calls["n"] += 1
        if calls["n"] == 1:
            return "not json", {"provider": "gemini"}
        return json.dumps(
            {
                "goal": "music",
                "reasoning": "On it.",
                "steps": [{"action": "PLAY_MUSIC"}],
            }
        ), {"provider": "gemini"}

    monkeypatch.setattr("backend.app.orchestrator.catalog_client.fetch_catalog", fake_fetch)
    monkeypatch.setattr("backend.app.orchestrator.planner.gemini_plan.generate_plan_json", flaky_gemini)
    monkeypatch.setattr("backend.app.config.settings.orchestrator_provider", "gemini")

    plan_obj, _meta = await plan("play jazz")
    assert len(plan_obj.steps) == 1

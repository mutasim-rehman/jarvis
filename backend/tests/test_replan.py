import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from shared.schema import TaskResult


@pytest.mark.asyncio
async def test_replan_after_failure(monkeypatch):
    from backend.app.orchestrator import replan as replan_mod
    from shared.schema import OrchestratorPlan, Task, ToolCatalog, ToolCapability, ToolDefinition

    catalog = ToolCatalog(
        capabilities=[
            ToolCapability(
                tool=ToolDefinition(name="WATCH_VIDEO", category="video", description="yt"),
                available=True,
            ),
        ],
    )

    async def fake_fetch(force=False):
        return catalog

    async def fake_provider(system, user):
        import json

        payload = {
            "goal": "music fallback",
            "reasoning": "Trying YouTube instead.",
            "steps": [{"id": "step1", "action": "WATCH_VIDEO", "target": "lo-fi music"}],
        }
        return json.dumps(payload), {"provider": "gemini"}

    monkeypatch.setattr(replan_mod.catalog_client, "fetch_catalog", fake_fetch)
    monkeypatch.setattr(replan_mod, "_call_provider", fake_provider)

    prior = [
        TaskResult(action="PLAY_MUSIC", success=False, error_code="X", message="Spotify failed"),
    ]
    plan, meta = await replan_mod.replan(
        original_request="play music",
        goal="play music",
        prior_results=prior,
        catalog=catalog,
        replan_attempt=1,
    )
    assert len(plan.steps) == 1
    assert plan.steps[0].action == "WATCH_VIDEO"
    assert meta.get("replan_attempt") == 1

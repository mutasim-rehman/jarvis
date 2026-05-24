"""Replan after partial execution failure."""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.app.config import settings
from backend.app.orchestrator import catalog_client
from backend.app.orchestrator.planner import _call_provider, _parse_plan_json
from backend.app.orchestrator.prompt import build_orchestrator_system_prompt
from backend.app.orchestrator.telemetry import log_plan
from shared.schema import OrchestratorPlan, Task, TaskResult, ToolCatalog

logger = logging.getLogger(__name__)


def _format_failed_steps(results: list[TaskResult]) -> str:
    lines: list[str] = []
    for r in results:
        status = "ok" if r.success else "FAILED"
        lines.append(
            f"- {r.task_id or r.action}: {status} "
            f"({r.error_code or 'none'}) {r.message[:200]}"
        )
    return "\n".join(lines)


def build_replan_user_prompt(
    *,
    original_request: str,
    goal: str,
    completed_results: list[TaskResult],
    failed_from_index: int,
) -> str:
    failed = _format_failed_steps(completed_results[failed_from_index:])
    succeeded = _format_failed_steps(completed_results[:failed_from_index])
    return (
        f"Original user request:\n{original_request.strip()}\n\n"
        f"Goal: {goal}\n\n"
        f"Completed steps:\n{succeeded or '(none)'}\n\n"
        f"Failed/skipped from step {failed_from_index + 1}:\n{failed}\n\n"
        "Produce a NEW plan to finish the user's goal. You may:\n"
        "- Retry failed steps with different tools/targets if available\n"
        "- Use fallback_steps style alternatives (e.g. WATCH_VIDEO if PLAY_MUSIC failed)\n"
        "- Skip already-succeeded work\n"
        "Return ONLY valid JSON with the same schema as initial planning."
    )


async def replan(
    *,
    original_request: str,
    goal: str,
    prior_results: list[TaskResult],
    catalog: ToolCatalog | None = None,
    replan_attempt: int = 1,
    preference_context: str | None = None,
) -> tuple[OrchestratorPlan, dict[str, Any]]:
    cat = catalog or await catalog_client.fetch_catalog(force=True)
    system = build_orchestrator_system_prompt(
        cat,
        settings.orchestrator_max_steps,
        preference_context=preference_context,
    )

    failed_idx = next((i for i, r in enumerate(prior_results) if not r.success), len(prior_results))
    user = build_replan_user_prompt(
        original_request=original_request,
        goal=goal,
        completed_results=prior_results,
        failed_from_index=failed_idx,
    )

    meta: dict[str, Any] = {"replan_attempt": replan_attempt}
    try:
        raw, provider_meta = await _call_provider(system, user)
        meta.update(provider_meta)
        plan_obj = _parse_plan_json(raw, cat)
        meta["orchestrator_provider"] = provider_meta.get("provider", settings.orchestrator_provider)
        meta["plan_steps"] = len(plan_obj.steps)
        log_plan(
            goal=plan_obj.goal,
            steps=[s.model_dump(exclude_none=True) for s in plan_obj.steps],
            meta=meta,
            event="replan",
        )
        return plan_obj, meta
    except (json.JSONDecodeError, ValueError, RuntimeError) as exc:
        logger.warning("Replan failed: %s", exc)
        return (
            OrchestratorPlan(
                goal=goal,
                steps=[],
                reasoning="I could not recover from that failure automatically, Sir.",
            ),
            {**meta, "replan_error": str(exc)},
        )

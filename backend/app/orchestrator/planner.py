"""Orchestrator planner: goal → OrchestratorPlan via Gemini (Ollama fallback)."""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.app.config import settings
from backend.app.orchestrator import catalog_client, gemini_plan, ollama_plan
from backend.app.orchestrator.prompt import build_orchestrator_system_prompt, build_repair_prompt
from backend.app.orchestrator.telemetry import log_plan
from shared.schema import OrchestratorPlan, Task, ToolCatalog

logger = logging.getLogger(__name__)

_ALLOWED_ACTIONS: set[str] | None = None


def _allowed_actions(catalog: ToolCatalog) -> set[str]:
    return {c.tool.name for c in catalog.capabilities if c.available}


def _parse_step(item: dict, allowed: set[str]) -> Task | None:
    action = str(item.get("action", "")).strip().upper()
    if not action:
        return None
    if action == "OPEN_WEBSITE":
        action = "OPEN_URL"
    if allowed and action not in allowed:
        logger.warning("Planner proposed unavailable action %s — skipping", action)
        return None
    target = item.get("target")
    if isinstance(target, str):
        target = target.strip() or None
    else:
        target = None
    params = item.get("parameters") if isinstance(item.get("parameters"), dict) else {}
    step_id = item.get("id")
    if isinstance(step_id, str):
        step_id = step_id.strip() or None
    else:
        step_id = None
    depends_on = item.get("depends_on") if isinstance(item.get("depends_on"), list) else []
    depends_on = [str(d).strip() for d in depends_on if str(d).strip()]
    inputs_from = item.get("inputs_from") if isinstance(item.get("inputs_from"), dict) else {}
    inputs_from = {str(k): str(v) for k, v in inputs_from.items()}
    return Task(
        action=action,
        target=target,
        parameters=params,
        id=step_id,
        depends_on=depends_on,
        inputs_from=inputs_from,
    )


def _parse_plan_json(raw: str, catalog: ToolCatalog) -> OrchestratorPlan:
    data = json.loads(raw)
    steps_raw = data.get("steps") or []
    if not isinstance(steps_raw, list):
        raise ValueError("steps must be a list")

    allowed = _allowed_actions(catalog)
    steps: list[Task] = []
    for item in steps_raw[: settings.orchestrator_max_steps]:
        if not isinstance(item, dict):
            continue
        step = _parse_step(item, allowed)
        if step:
            steps.append(step)

    fallback_raw = data.get("fallback_steps") or []
    fallback_steps: list[Task] = []
    if isinstance(fallback_raw, list):
        for item in fallback_raw[: settings.orchestrator_max_steps]:
            if isinstance(item, dict):
                step = _parse_step(item, allowed)
                if step:
                    fallback_steps.append(step)

    return OrchestratorPlan(
        goal=str(data.get("goal") or "").strip() or "user request",
        steps=steps,
        fallback_steps=fallback_steps,
        reasoning=(str(data.get("reasoning")).strip() if data.get("reasoning") else None),
        clarification_question=(
            str(data.get("clarification_question")).strip()
            if data.get("clarification_question")
            else None
        ),
    )


async def _call_provider(system: str, user: str) -> tuple[str, dict[str, Any]]:
    provider = (settings.orchestrator_provider or "gemini").strip().lower()
    if provider == "ollama":
        return await ollama_plan.generate_plan_json(system, user)
    try:
        return await gemini_plan.generate_plan_json(system, user)
    except RuntimeError as exc:
        logger.warning("Gemini orchestrator failed (%s), trying Ollama", exc)
        return await ollama_plan.generate_plan_json(system, user)


async def plan(
    user_text: str,
    *,
    catalog: ToolCatalog | None = None,
    preference_context: str | None = None,
) -> tuple[OrchestratorPlan, dict[str, Any]]:
    """
    Build an execution plan for the user goal.
    Returns (plan, meta) where meta includes orchestrator_provider and timing.
    """
    cat = catalog or await catalog_client.fetch_catalog()
    system = build_orchestrator_system_prompt(
        cat,
        settings.orchestrator_max_steps,
        preference_context=preference_context,
    )
    user = f"User request:\n{user_text.strip()}"

    meta: dict[str, Any] = {}
    last_error = ""
    raw = ""

    for attempt in range(2):
        try:
            raw, provider_meta = await _call_provider(
                system if attempt == 0 else system,
                user if attempt == 0 else build_repair_prompt(raw, last_error),
            )
            meta.update(provider_meta)
            plan_obj = _parse_plan_json(raw, cat)
            meta["orchestrator_provider"] = provider_meta.get("provider", settings.orchestrator_provider)
            meta["plan_steps"] = len(plan_obj.steps)
            meta["goal"] = plan_obj.goal
            log_plan(
                goal=plan_obj.goal,
                steps=[s.model_dump(exclude_none=True) for s in plan_obj.steps],
                meta=meta,
            )
            return plan_obj, meta
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = str(exc)
            logger.warning("Orchestrator JSON parse failed (attempt %d): %s", attempt + 1, exc)
            if attempt == 1:
                break
        except RuntimeError as exc:
            last_error = str(exc)
            logger.error("Orchestrator provider error: %s", exc)
            break

    return (
        OrchestratorPlan(
            goal=user_text.strip()[:200] or "request",
            steps=[],
            reasoning="I could not build a plan right now. Please try again, Sir.",
        ),
        {"orchestrator_provider": settings.orchestrator_provider, "orchestrator_error": last_error},
    )

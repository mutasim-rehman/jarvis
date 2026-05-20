"""Lightweight orchestrator plan/execution telemetry (NDJSON log file)."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LOG_PATH = Path(__file__).resolve().parents[3] / "data" / "orchestrator_events.jsonl"


def _append(event: dict[str, Any]) -> None:
    event.setdefault("ts", int(time.time() * 1000))
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")
    except OSError as exc:
        logger.debug("telemetry write skipped: %s", exc)


def log_plan(
    *,
    goal: str,
    steps: list[dict[str, Any]],
    meta: dict[str, Any],
    event: str = "plan",
) -> None:
    _append(
        {
            "event": event,
            "goal": goal,
            "step_count": len(steps),
            "steps": steps,
            "provider": meta.get("orchestrator_provider"),
            "model": meta.get("model"),
        }
    )


def log_execution(
    *,
    goal: str,
    overall_success: bool,
    results: list[dict[str, Any]],
    replan_attempt: int = 0,
) -> None:
    _append(
        {
            "event": "execution",
            "goal": goal,
            "overall_success": overall_success,
            "replan_attempt": replan_attempt,
            "results": results,
        }
    )

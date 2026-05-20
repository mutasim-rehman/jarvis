"""Emergency rollback router when ORCHESTRATOR_DISABLED=true."""

from __future__ import annotations

from shared.schema import ActionCommand, AssistantResponse, RouteKind, Task
from shared.workflows import WORKFLOWS

from backend.app.legacy_heuristics import UserTextClassification, classify_user_text


def _build_command(intent: str, target: str | None) -> ActionCommand | None:
    if intent in ("UNKNOWN", "GENERAL_CHAT"):
        return None
    command = ActionCommand(intent=intent, target=target)
    if intent in WORKFLOWS:
        tasks_to_add = []
        for t in WORKFLOWS[intent]:
            task_data = t.copy()
            if task_data.get("target") is None:
                task_data["target"] = target
            tasks_to_add.append(Task(**task_data))
        command.tasks = tasks_to_add
    return command


def _forced_intent_message(intent: str) -> str:
    if intent == "MORNING_RITUAL":
        return "Good morning. Powering up your ritual now."
    return "On it."


def parse_legacy(text: str) -> AssistantResponse:
    cls: UserTextClassification = classify_user_text(text)
    if cls.suppress_structured_command:
        return AssistantResponse(
            message="Sure — what would you like to do?",
            command=None,
            route=RouteKind.INFORMATIONAL,
            meta={"path": "legacy_heuristic_suppressed"},
        )
    if cls.force_intent:
        cmd = _build_command(cls.force_intent, cls.force_target)
        return AssistantResponse(
            message=_forced_intent_message(cls.force_intent),
            command=cmd,
            route=RouteKind.DESKTOP_EXECUTION if cmd else RouteKind.INFORMATIONAL,
            meta={"path": "legacy_heuristic_forced", "intent": cls.force_intent},
        )
    return AssistantResponse(
        message="I'm not sure how to help with that, Sir. (Legacy mode — orchestrator disabled.)",
        command=None,
        route=RouteKind.INFORMATIONAL,
        meta={"path": "legacy_no_match"},
    )

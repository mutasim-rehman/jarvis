import logging
import os
import re
import sys
import time
from typing import Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from shared.schema import ActionCommand, AssistantResponse, RouteKind, Task

from backend.app.config import settings
from backend.app.heuristics import should_suppress_structured_command
from backend.app.orchestrator import plan as orchestrator_plan

logger = logging.getLogger(__name__)

_IDENTITY_RESPONSE = (
    "I am JARVIS — your advanced AI systems assistant. "
    "I can execute desktop commands, play music, manage assignments, fetch news, and more. "
    "How may I assist you today, Sir?"
)

_CAPABILITY_RESPONSE = (
    "I can play music, open apps, watch videos, fetch tech or world news, manage assignments, "
    "start projects, run focus or morning rituals, and answer general questions. "
    "What would you like me to do, Sir?"
)


def quick_conversational_response(user_text: str) -> str | None:
    t = user_text.strip().lower()
    if not t:
        return None

    normalized = re.sub(r"[^a-z0-9\s]", " ", t)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    words = normalized.split()
    greeting_words = {"hello", "hi", "hey", "yo", "sup"}

    if re.fullmatch(r"(wake\s*up|wake up jarvis|jarvis|hey jarvis|hello|hi|good (morning|afternoon|evening))", t):
        return "At your service, Sir. How may I assist you today?"
    if len(words) <= 5 and any(word in greeting_words for word in words):
        if "jarvis" in words or (len(words) == 1 and words[0] in greeting_words):
            return "At your service, Sir. How may I assist you today?"
    if normalized in {"good morning jarvis", "good afternoon jarvis", "good evening jarvis"}:
        return "At your service, Sir. How may I assist you today?"

    identity_patterns = re.compile(
        r"\b(who are you|what are you|introduce yourself|your name|what is your name"
        r"|are you (ai|an ai|a bot|jarvis)|what('s| is) jarvis)\b"
    )
    if identity_patterns.search(normalized):
        return _IDENTITY_RESPONSE

    capability_patterns = re.compile(
        r"\b(what can you do|what (do|can) you (help|assist)|your (capabilities|features|functions|abilities)"
        r"|how (do you|can you) help|what are your (skills|abilities))\b"
    )
    if capability_patterns.search(normalized):
        return _CAPABILITY_RESPONSE

    online_patterns = re.compile(
        r"\b(are you online|you online|status check|systems online|come online"
        r"|back online|are you there|are you awake|are you working)\b"
    )
    if online_patterns.search(normalized):
        return "Yes, Sir. I am online and ready to assist."

    if normalized in {
        "thank you",
        "thanks",
        "thank you jarvis",
        "thanks jarvis",
        "ok",
        "okay",
        "got it",
        "alright",
        "sure",
        "cool",
        "nice",
        "great",
    }:
        return "Of course, Sir. Anything else?"

    return None


def _wrap(
    message: str,
    command: ActionCommand | None,
    meta: dict[str, Any] | None = None,
) -> AssistantResponse:
    route = RouteKind.DESKTOP_EXECUTION if command else RouteKind.INFORMATIONAL
    return AssistantResponse(message=message, command=command, route=route, meta=meta or {})


async def parse_intent(text: str, chat_provider: str | None = None) -> AssistantResponse:
    del chat_provider  # orchestrator uses ORCHESTRATOR_PROVIDER, not chat router
    started = time.perf_counter()

    def _finish(result: AssistantResponse, path: str) -> AssistantResponse:
        logger.info(
            "parse_intent timing path=%s total_ms=%.1f route=%s has_command=%s",
            path,
            (time.perf_counter() - started) * 1000,
            result.route,
            bool(result.command),
        )
        return result

    quick = quick_conversational_response(text)
    if quick:
        return _finish(_wrap(quick, None, {"path": "quick_path"}), "quick_path")

    if should_suppress_structured_command(text):
        return _finish(
            _wrap(
                "I cannot complete graded work on your behalf, Sir. I can help you organize and start assignments instead.",
                None,
                {"path": "orchestrator_suppressed"},
            ),
            "orchestrator_suppressed",
        )

    plan_obj, meta = await orchestrator_plan(text)

    if plan_obj.clarification_question:
        return _finish(
            _wrap(
                plan_obj.clarification_question,
                None,
                {**meta, "path": "orchestrator_clarification"},
            ),
            "orchestrator_clarification",
        )

    if not plan_obj.steps:
        msg = plan_obj.reasoning or "How may I assist you further, Sir?"
        return _finish(_wrap(msg, None, {**meta, "path": "orchestrator_chat"}), "orchestrator_chat")

    command = ActionCommand(
        intent="ORCHESTRATED",
        target=None,
        tasks=plan_obj.steps,
    )
    message = plan_obj.reasoning or "On it."
    return _finish(
        _wrap(message, command, {**meta, "path": "orchestrator_plan"}),
        "orchestrator_plan",
    )

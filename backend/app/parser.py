import json
import logging
import re
import sys
import os
import time
from typing import Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from shared.schema import ActionCommand, AssistantResponse, RouteKind, Task
from shared.workflows import WORKFLOWS
from .heuristics import (
    classify_user_text,
    reconcile_llm_intent,
    should_drop_workflow_without_domain,
)
from backend.chatbot import ProviderUnavailableError, generate_chat
from backend.chatbot.personality import build_base_system_message

ALLOWED_INTENTS = set(WORKFLOWS.keys()) | {"GENERAL_CHAT", "UNKNOWN"}
SUPPORTED_INTENTS_TEXT = "\n".join(
    f"   - {intent}" for intent in sorted(ALLOWED_INTENTS) if intent != "UNKNOWN"
)

BASE_SYSTEM_PROMPT = build_base_system_message()
logger = logging.getLogger(__name__)


SYSTEM_PROMPT = f"""
{BASE_SYSTEM_PROMPT}

CRITICAL RULES:
1. You MUST ONLY output intents from this list:
{SUPPORTED_INTENTS_TEXT}
   - UNKNOWN

2. NEVER include "tasks", "type", or "multi_step" in your JSON.
3. Intent must be a plain string (e.g., "HANDLE_ASSIGNMENTS").
4. If no action is required (e.g., greetings, general questions), DO NOT output JSON.
5. If the user mentions assignments, homework, or a coding/project setup, choose the matching intent.
6. For listening to music, use PLAY_MUSIC (not START_PROJECT). For opening an app by name, prefer OPEN_APP with target set to that app.
7. Never output action JSON if the user asks you to complete their graded homework, essays, or exams for them — answer conversationally only (no workflow).
8. For PLAY_MUSIC: omit "target" (or null) when the user wants generic music — that plays their Liked Songs on Spotify. Treat "start music", "begin music", and "play music" the same. For **music by an artist**, set "target" to `artist:ArtistName` (e.g. `artist:The Beatles`). For **a specific song**, use `track:Song title` (e.g. `track:Duur`). Otherwise set "target" to a style/genre text (e.g. "jazz", "lo-fi") or plain artist/song search text.
9. For **Tech News**, use `FETCH_TECH_NEWS`.
10. For **World News**, use `FETCH_WORLD_NEWS`.
11. For **DO_ASSIGNMENT**: use when the user wants to START or WORK ON a specific assignment from their list. Set "target" to the assignment number or name. If the user mentions "gemini" or "antigravity", append "|gemini" or "|antigravity" to the target (e.g. "17|gemini"). Default to "gemini" if unspecified.
12. For **WATCH_VIDEO**: search and play YouTube videos. Set "target" to the query (e.g. "brooklyn 99 clips").

FORMAT FOR ACTIONS:
<Conversational message>

{{
  "intent": "...",
  "target": "optional"
}}

EXAMPLES:
Input: "hello"
Output: "Hello! How can I help you today?"

Input: "what's happening in tech?"
Output: "I'll pull up the latest tech news and highlights for you.
{{
  "intent": "FETCH_TECH_NEWS"
}}"

Input: "show me some world news"
Output: "Looking up the global headlines right now.
{{
  "intent": "FETCH_WORLD_NEWS"
}}"

Input: "watch the latest trailer"
Output: "Sure, pulling that video up for you.
{{
  "intent": "WATCH_VIDEO",
  "target": "latest trailer"
}}"

Input: "do my assignment"
Output: "Alright, I'll set everything up for your assignments.
{{
  "intent": "HANDLE_ASSIGNMENTS"
}}"

Input: "start assignment 5 with gemini"
Output: "Setting up assignment 5 with Gemini.
{{
  "intent": "DO_ASSIGNMENT",
  "target": "5|gemini"
}}"

Input: "do assignment 17"
Output: "Opening assignment 17 for you.
{{
  "intent": "DO_ASSIGNMENT",
  "target": "17|gemini"
}}"

Input: "start the data structures project with antigravity"
Output: "Opening that in Antigravity for you.
{{
  "intent": "DO_ASSIGNMENT",
  "target": "data structures project|antigravity"
}}"

Input: "play some music"
Output: "Playing music for you.
{{
  "intent": "PLAY_MUSIC"
}}"

Input: "start music"
Output: "Starting music for you.
{{
  "intent": "PLAY_MUSIC"
}}"

Input: "play some jazz"
Output: "I'll queue that up in Spotify.
{{
  "intent": "PLAY_MUSIC",
  "target": "jazz"
}}"

Input: "play music by Radiohead"
Output: "Playing Radiohead on Spotify.
{{
  "intent": "PLAY_MUSIC",
  "target": "artist:Radiohead"
}}"

Input: "play the song Duur"
Output: "Playing that track.
{{
  "intent": "PLAY_MUSIC",
  "target": "track:Duur"
}}"

Input: "play brooklyn 99 clips"
Output: "Starting Brooklyn Nine-Nine clips on YouTube for you.
{{
  "intent": "WATCH_VIDEO",
  "target": "brooklyn 99 clips"
}}"
"""


def _normalize_assistant_message(message: str) -> str:
    m = message.strip()
    if len(m) >= 2 and m[0] == m[-1] and m[0] in "\"'":
        m = m[1:-1].strip()
    return m


def _structured_start(content: str) -> int | None:
    positions: list[int] = []
    for sep in ("{", "("):
        j = content.find(sep)
        if j != -1:
            positions.append(j)
    return min(positions) if positions else None


def _extract_conversational_message(content: str) -> str:
    idx = _structured_start(content)
    if idx is not None and idx > 0:
        return _normalize_assistant_message(content[:idx].strip())
    return _normalize_assistant_message(content)


_INTENT_LABEL_ALIASES = {
    "generalized chat": "GENERAL_CHAT",
    "general chat": "GENERAL_CHAT",
}


def _canonicalize_intent_label(raw: str) -> str | None:
    low = re.sub(r"\s+", " ", raw.strip().lower())
    if not low:
        return None
    if low in _INTENT_LABEL_ALIASES:
        return _INTENT_LABEL_ALIASES[low]
    compact = re.sub(r"\s+", "_", low).upper()
    if compact in ALLOWED_INTENTS:
        return compact
    return None


def _extract_intent_from_text(content: str) -> str | None:
    intent_match = re.search(r'"intent"\s*:\s*"([A-Z_]+)"', content)
    if intent_match:
        intent = intent_match.group(1).strip()
        if intent in ALLOWED_INTENTS:
            return intent

    loose = re.search(r"intent\s*:\s*\"([^\"]*)\"", content, re.IGNORECASE)
    if loose:
        cand = _canonicalize_intent_label(loose.group(1))
        if cand and cand in ALLOWED_INTENTS:
            return cand

    bare_intent_match = re.fullmatch(r'["\']?\s*([A-Z_]+)\s*["\']?', content.strip())
    if bare_intent_match:
        intent = bare_intent_match.group(1).strip()
        if intent in ALLOWED_INTENTS:
            return intent

    return None


def _quick_conversational_response(user_text: str) -> str | None:
    t = user_text.strip().lower()
    if not t:
        return None

    normalized = re.sub(r"[^a-z0-9\s]", " ", t)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    words = normalized.split()
    greeting_words = {"hello", "hi", "hey", "yo", "sup"}
    # Fast conversational wake/greeting path: avoids unnecessary LLM latency.
    if re.fullmatch(r"(wake\s*up|wake up jarvis|jarvis|hey jarvis|hello|hi|good (morning|afternoon|evening))", t):
        return "At your service, Sir. How may I assist you today?"
    if len(words) <= 5 and any(word in greeting_words for word in words):
        if "jarvis" in words or (len(words) == 1 and words[0] in greeting_words):
            return "At your service, Sir. How may I assist you today?"
    if normalized in {"good morning jarvis", "good afternoon jarvis", "good evening jarvis"}:
        return "At your service, Sir. How may I assist you today?"
    return None


def _fallback_intent_from_user_text(text: str) -> tuple[str | None, str | None]:
    """Last-resort when JSON is invalid; mirrors heuristics for assignment/project."""
    h = classify_user_text(text)
    if h.force_intent:
        return h.force_intent, h.force_target
    return None, None


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


def _provider_unavailable_meta(provider: str, reason: str) -> dict[str, Any]:
    return {
        "chatbot_provider": provider,
        "status": "unavailable",
        "reason": reason,
        "fallback_options": [
            {"id": "retry_huggingface", "label": "Wait and retry Hugging Face"},
            {"id": "run_local_ollama", "label": "Run locally with Ollama"},
        ],
    }


def _forced_intent_message(intent: str) -> str:
    if intent == "MORNING_RITUAL":
        return "Good morning. Powering up your ritual now."
    return "On it."


def _wrap(message: str, command: ActionCommand | None, meta: dict[str, Any] | None = None) -> AssistantResponse:
    route = RouteKind.DESKTOP_EXECUTION if command else RouteKind.INFORMATIONAL
    return AssistantResponse(message=message, command=command, route=route, meta=meta or {})


async def parse_intent(text: str, chat_provider: str | None = None) -> AssistantResponse:
    started = time.perf_counter()
    def _finish(result: AssistantResponse, path: str, llm_ms: float = 0.0) -> AssistantResponse:
        logger.info(
            "parse_intent timing path=%s llm_ms=%.1f total_ms=%.1f route=%s has_command=%s",
            path,
            llm_ms,
            (time.perf_counter() - started) * 1000,
            result.route,
            bool(result.command),
        )
        return result

    quick = _quick_conversational_response(text)
    if quick:
        return _finish(_wrap(quick, None), "quick_path")

    cls = classify_user_text(text)

    # Fast-path deterministic intents so common desktop commands still work
    # even if LLM/Ollama is unavailable.
    if cls.suppress_structured_command:
        return _finish(_wrap("Sure — what would you like to do?", None), "heuristic_suppressed")

    if cls.force_intent:
        cmd = _build_command(cls.force_intent, cls.force_target)
        return _finish(_wrap(_forced_intent_message(cls.force_intent), cmd), "heuristic_forced")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.strip()},
        {"role": "user", "content": text},
    ]

    base_message = ""
    content = ""
    try:
        llm_started = time.perf_counter()
        if chat_provider:
            response = await generate_chat(messages=messages, preferred_provider=chat_provider)
        else:
            response = await generate_chat(messages=messages)
        llm_ms = (time.perf_counter() - llm_started) * 1000
        logger.debug("parse_intent llm_ms=%.1f provider=%s", llm_ms, chat_provider or "default")
        content = response.get("message", {}).get("content", "").strip()
        base_message = _extract_conversational_message(content) if content else ""
    except ProviderUnavailableError as exc:
        fb_intent, fb_target = _fallback_intent_from_user_text(text)
        if fb_intent and fb_intent not in {"GENERAL_CHAT", "UNKNOWN"}:
            cmd = _build_command(fb_intent, fb_target)
            return _finish(_wrap("On it.", cmd), "provider_unavailable_fallback")
        provider_name = exc.provider.capitalize()
        return _finish(_wrap(
            f"{provider_name} chatbot is unavailable right now. Choose whether to wait/retry or run locally with Ollama.",
            None,
            meta=_provider_unavailable_meta(exc.provider, exc.reason),
        ), "provider_unavailable")
    except RuntimeError:
        # Graceful fallback when the configured provider fails unexpectedly.
        fb_intent, fb_target = _fallback_intent_from_user_text(text)
        if fb_intent and fb_intent not in {"GENERAL_CHAT", "UNKNOWN"}:
            cmd = _build_command(fb_intent, fb_target)
            return _finish(_wrap("On it.", cmd), "provider_runtime_fallback")
        return _finish(_wrap(
            "I couldn't reach the chatbot provider right now. Please try again.",
            None,
        ), "provider_runtime_error")

    json_start = content.find("{")
    if json_start != -1:
        json_part = content[json_start:].strip()

        try:
            if json_part.startswith("```json"):
                json_part = json_part[7:-3].strip()
            elif json_part.startswith("```"):
                json_part = json_part[3:-3].strip()

            data = json.loads(json_part)
            intent = str(data.get("intent", "UNKNOWN")).strip()
            target = data.get("target")
            if isinstance(target, str):
                target = target.strip() or None

            if intent not in ALLOWED_INTENTS:
                normalized = _canonicalize_intent_label(intent)
                intent = normalized if normalized else "UNKNOWN"

            intent, target = reconcile_llm_intent(text, intent, target)

            if intent in ("UNKNOWN", "GENERAL_CHAT"):
                msg = base_message or _normalize_assistant_message(content[:json_start].strip()) or "Okay."
                return _finish(_wrap(msg, None), "llm_general_chat", llm_ms)

            if should_drop_workflow_without_domain(text, intent):
                msg = base_message or "What should I help you with?"
                return _finish(_wrap(msg, None), "llm_dropped_without_domain", llm_ms)

            cmd = _build_command(intent, target)
            msg = base_message or "Done."
            return _finish(_wrap(msg, cmd), "llm_json_command", llm_ms)
        except json.JSONDecodeError:
            extracted = _extract_intent_from_text(content)
            if extracted and extracted not in {"GENERAL_CHAT", "UNKNOWN"}:
                extracted, _t = reconcile_llm_intent(text, extracted, None)
                if should_drop_workflow_without_domain(text, extracted):
                    return _finish(_wrap(base_message or content, None), "llm_text_dropped_without_domain", llm_ms)
                if extracted in ("GENERAL_CHAT", "UNKNOWN"):
                    return _finish(_wrap(base_message or content, None), "llm_text_general_chat", llm_ms)
                cmd = _build_command(extracted, None)
                return _finish(_wrap(base_message or "On it.", cmd), "llm_text_command", llm_ms)
            fb_intent, fb_target = _fallback_intent_from_user_text(text)
            if fb_intent and fb_intent not in {"GENERAL_CHAT", "UNKNOWN"}:
                cmd = _build_command(fb_intent, fb_target)
                return _finish(_wrap(base_message or "On it.", cmd), "llm_json_invalid_fallback", llm_ms)
            return _finish(_wrap(base_message or content, None), "llm_json_invalid_informational", llm_ms)

    extracted = _extract_intent_from_text(content)
    if extracted and extracted not in {"GENERAL_CHAT", "UNKNOWN"}:
        extracted, ext_target = reconcile_llm_intent(text, extracted, None)
        if should_drop_workflow_without_domain(text, extracted):
            return _finish(_wrap(base_message or content, None), "llm_no_json_dropped_without_domain", llm_ms)
        if extracted in ("GENERAL_CHAT", "UNKNOWN"):
            return _finish(_wrap(base_message or content, None), "llm_no_json_general_chat", llm_ms)
        cmd = _build_command(extracted, ext_target)
        return _finish(_wrap(base_message or "On it.", cmd), "llm_no_json_command", llm_ms)

    fb_intent, fb_target = _fallback_intent_from_user_text(text)
    if fb_intent and fb_intent not in {"GENERAL_CHAT", "UNKNOWN"}:
        cmd = _build_command(fb_intent, fb_target)
        return _finish(_wrap(base_message or content or "On it.", cmd), "fallback_intent")

    result = _wrap(base_message or content, None)
    return _finish(result, "fallback_informational")

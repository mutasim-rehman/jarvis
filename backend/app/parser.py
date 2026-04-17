import json
import re
import sys
import os

# Add parent directory to path so we can import shared
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from shared.schema import ActionCommand, AssistantResponse, Task
from shared.workflows import WORKFLOWS
from .llm import generate_chat

ALLOWED_INTENTS = set(WORKFLOWS.keys()) | {"GENERAL_CHAT", "UNKNOWN"}
SUPPORTED_INTENTS_TEXT = "\n".join(
    f"   - {intent}"
    for intent in sorted(ALLOWED_INTENTS)
    if intent != "UNKNOWN"
)

SYSTEM_PROMPT = f"""
You are JARVIS, a professional and proactive AI assistant.
Your goal is to understand user intent and provide a natural response followed by a structural command IF an action is required.

CRITICAL RULES:
1. You MUST ONLY output intents from this list:
{SUPPORTED_INTENTS_TEXT}
   - UNKNOWN

2. NEVER include "tasks", "type", or "multi_step" in your JSON.
3. Intent must be a plain string (e.g., "HANDLE_ASSIGNMENTS").
4. If no action is required (e.g., greetings, general questions), DO NOT output JSON.
5. If the user mentions assignments or projects, BE PROACTIVE and trigger the appropriate intent.

FORMAT FOR ACTIONS:
<Conversational message>

{{
  "intent": "...",
  "target": "optional"
}}

EXAMPLES:
Input: "hello"
Output: "Hello! How can I help you today?"

Input: "do my assignment"
Output: "Alright, I'll set everything up for your assignments.
{{
  "intent": "HANDLE_ASSIGNMENTS"
}}"

Input: "ive got assignments due"
Output: "I see those assignments. I'll get your environment ready so you can start working right away.
{{
  "intent": "HANDLE_ASSIGNMENTS"
}}"
"""


def _extract_intent_from_text(content: str) -> str | None:
    intent_match = re.search(r'"intent"\s*:\s*"([A-Z_]+)"', content)
    if intent_match:
        intent = intent_match.group(1).strip()
        if intent in ALLOWED_INTENTS:
            return intent

    bare_intent_match = re.fullmatch(r'["\']?\s*([A-Z_]+)\s*["\']?', content.strip())
    if bare_intent_match:
        intent = bare_intent_match.group(1).strip()
        if intent in ALLOWED_INTENTS:
            return intent

    return None


def _fallback_intent_from_user_text(text: str) -> tuple[str | None, str | None]:
    lowered = text.lower()

    assignment_keywords = ("assignment", "homework", "classwork", "coursework", "due")
    if any(k in lowered for k in assignment_keywords):
        if any(k in lowered for k in ("check", "what do i have", "what's due", "pending")):
            return "CHECK_ASSIGNMENTS", None
        return "HANDLE_ASSIGNMENTS", None

    if any(k in lowered for k in ("start project", "work on project", "continue project", "resume project")):
        if "create" in lowered or "new project" in lowered:
            return "CREATE_PROJECT", None
        if "resume" in lowered or "continue" in lowered:
            return "RESUME_PROJECT", None
        return "START_PROJECT", None

    return None, None


def _build_command(intent: str, target: str | None) -> ActionCommand:
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


async def parse_intent(text: str) -> AssistantResponse:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.strip()},
        {"role": "user", "content": text}
    ]
    
    # We no longer use strict JSON format from Ollama because we want Text + JSON
    response = await generate_chat(messages=messages)
    
    content = response.get("message", {}).get("content", "").strip()
    
    if "{" in content:
        # Split text and JSON
        json_start = content.index("{")
        message = content[:json_start].strip()
        json_part = content[json_start:].strip()
        
        try:
            # Clean up markdown if present
            if json_part.startswith("```json"):
                json_part = json_part[7:-3].strip()
            elif json_part.startswith("```"):
                json_part = json_part[3:-3].strip()
                
            data = json.loads(json_part)
            intent = str(data.get("intent", "UNKNOWN")).strip()
            target = data.get("target")

            if intent not in ALLOWED_INTENTS:
                intent = "UNKNOWN"

            return AssistantResponse(
                message=message or "Done.",
                command=_build_command(intent=intent, target=target),
            )
        except json.JSONDecodeError:
            extracted_intent = _extract_intent_from_text(content)
            if extracted_intent and extracted_intent not in {"GENERAL_CHAT", "UNKNOWN"}:
                return AssistantResponse(
                    message="Got it. Preparing that now.",
                    command=_build_command(intent=extracted_intent, target=None),
                )
            fallback_intent, fallback_target = _fallback_intent_from_user_text(text)
            if fallback_intent:
                return AssistantResponse(
                    message="Got it. I can handle that workflow.",
                    command=_build_command(intent=fallback_intent, target=fallback_target),
                )
            return AssistantResponse(message=content, command=None)
    else:
        extracted_intent = _extract_intent_from_text(content)
        if extracted_intent and extracted_intent not in {"GENERAL_CHAT", "UNKNOWN"}:
            return AssistantResponse(
                message="Got it. Preparing that now.",
                command=_build_command(intent=extracted_intent, target=None),
            )

        fallback_intent, fallback_target = _fallback_intent_from_user_text(text)
        if fallback_intent:
            return AssistantResponse(
                message="Got it. I can handle that workflow.",
                command=_build_command(intent=fallback_intent, target=fallback_target),
            )

        return AssistantResponse(
            message=content,
            command=None
        )



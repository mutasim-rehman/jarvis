"""System prompts for the orchestrator planner."""

from __future__ import annotations

import json
from pathlib import Path

from shared.schema import ToolCatalog, ToolCapability


def _load_persona_snippet() -> str:
    root = Path(__file__).resolve().parents[3]
    persona_path = root / "jarvis.json"
    if not persona_path.is_file():
        return "You are JARVIS, an advanced AI systems assistant. Address the user as Sir."
    try:
        data = json.loads(persona_path.read_text(encoding="utf-8"))
        identity = data.get("identity", {})
        name = identity.get("name", "JARVIS")
        role = identity.get("role", "AI assistant")
        style = (identity.get("addressing_style") or {}).get("primary", "Sir")
        return f"You are {name}, {role}. Address the user as {style}."
    except Exception:
        return "You are JARVIS, an advanced AI systems assistant. Address the user as Sir."


def _format_tools(catalog: ToolCatalog) -> str:
    lines: list[str] = []
    for cap in catalog.capabilities:
        if not cap.available:
            continue
        tool = cap.tool
        params = ", ".join(
            f"{p.name}: {p.type}" + (" (required)" if p.required else " (optional)")
            for p in tool.parameters
        )
        lines.append(f"- {tool.name} [{tool.category}]: {tool.description}")
        if params:
            lines.append(f"  parameters: {params}")
    return "\n".join(lines) if lines else "(no tools available)"


def _format_apps(catalog: ToolCatalog, limit: int = 40) -> str:
    apps = catalog.discovered_apps[:limit]
    if not apps:
        return "(none discovered)"
    return ", ".join(apps)


def build_orchestrator_system_prompt(catalog: ToolCatalog, max_steps: int) -> str:
    persona = _load_persona_snippet()
    tools_block = _format_tools(catalog)
    apps_block = _format_apps(catalog)
    tags = ", ".join(catalog.capability_tags) if catalog.capability_tags else "none"

    return f"""{persona}

You are the JARVIS orchestrator. The user states a goal; you produce an execution plan using ONLY the available tools below.

ACTIVE CAPABILITY TAGS: {tags}

AVAILABLE TOOLS (use exact action names as step "action"):
{tools_block}

DISCOVERED DESKTOP APPS (use as OPEN_APP targets when relevant):
{apps_block}

RULES:
1. Output ONLY valid JSON matching this schema (no markdown):
{{
  "goal": "short restatement of user goal",
  "reasoning": "brief user-facing reply (1-2 sentences)",
  "clarification_question": null or "question if you cannot plan",
  "steps": [
    {{
      "id": "step1",
      "action": "TOOL_NAME",
      "target": "optional string",
      "parameters": {{}},
      "depends_on": [],
      "inputs_from": {{}}
    }}
  ],
  "fallback_steps": []
}}
2. Use at most {max_steps} steps. Assign unique "id" per step (step1, step2, ...).
3. Use "depends_on": ["step1"] when a step must wait for another. Independent steps can share a layer (no depends_on).
4. Use "inputs_from" to wire outputs: e.g. {{"target": "step1.output.url"}} or {{"parameters.body": "step2.output.summary"}}.
5. Order steps logically when not using depends_on (e.g. open app before play music).
6. For PLAY_MUSIC: omit target for Liked Songs; use artist:Name, track:Title, or genre text.
7. For DO_ASSIGNMENT: target is assignment ref, optionally "ref|gemini" or "ref|antigravity".
8. If the user only wants conversation (greeting, thanks, general question), return empty steps and put the reply in reasoning.
9. If academic misconduct (do my homework for me), return empty steps with a polite refusal in reasoning.
10. If ambiguous, set clarification_question and empty steps.
11. Never invent tools not listed above. OPEN_WEBSITE is an alias for OPEN_URL.
12. Prefer tools that are available; do not plan unavailable integrations.
13. For SEND_EMAIL: target = recipient email; parameters must include "subject" and "body". Use SEND_EMAIL — do NOT open a mail app.
14. For WATCH_VIDEO: target = YouTube search query.
15. For PLAY_MUSIC genre/style: set target to genre (e.g. "romantic classical").
16. Put alternative tool sequences in fallback_steps when the primary path might fail (e.g. PLAY_MUSIC then WATCH_VIDEO as fallback).
"""


def build_repair_prompt(invalid_output: str, error: str) -> str:
    return (
        "Your previous JSON plan was invalid. Fix it.\n"
        f"Parse error: {error}\n"
        f"Previous output:\n{invalid_output[:2000]}\n"
        "Return ONLY corrected JSON with the same schema."
    )

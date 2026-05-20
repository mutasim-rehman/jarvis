"""Gemini structured JSON generation for orchestrator plans."""

from __future__ import annotations

import re
import time
from typing import Any

import httpx

from backend.app.config import settings as app_settings


def _model_url() -> str:
    model = app_settings.resolved_orchestrator_model()
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _request_target(api_key: str) -> tuple[str, dict[str, str]]:
    """
    Google Generative Language API:
    - API keys (AIza…, AQ.…) → ?key= query parameter
    - OAuth access tokens (ya29.…) → Authorization: Bearer
    """
    if api_key.startswith("ya29."):
        return _model_url(), {"Authorization": f"Bearer {api_key}"}
    return f"{_model_url()}?key={api_key}", {}


def _build_payload(system: str, user: str) -> dict[str, Any]:
    return {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "maxOutputTokens": 2048,
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }


def _extract_json_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def generate_plan_json(system_prompt: str, user_text: str) -> tuple[str, dict[str, Any]]:
    api_key = app_settings.resolved_orchestrator_gemini_key()
    if not api_key:
        raise RuntimeError(
            "Orchestrator Gemini key not configured. Set ORCHESTRATOR_GEMINI or GOOGLE_GEMINI_KEY in .env."
        )

    payload = _build_payload(system_prompt, user_text)
    url, headers = _request_target(api_key)
    model = app_settings.resolved_orchestrator_model()
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            raise RuntimeError(
                f"Gemini API error {response.status_code} (model={model}): {response.text[:400]}"
            )
        data = response.json()

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected Gemini response: {data}") from exc

    meta = {
        "provider": "gemini",
        "model": model,
        "timing_ms": round((time.perf_counter() - started) * 1000, 2),
    }
    return _extract_json_text(text), meta

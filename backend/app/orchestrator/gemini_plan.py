"""Gemini structured JSON generation for orchestrator plans."""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from backend.app.config import settings as app_settings


def _model_url() -> str:
    model = (app_settings.orchestrator_model or "gemini-2.0-flash-lite").strip()
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


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
    api_key = (app_settings.google_gemini_key or "").strip()
    if not api_key:
        raise RuntimeError("GOOGLE_GEMINI_KEY not configured for orchestrator.")

    payload = _build_payload(system_prompt, user_text)
    url = f"{_model_url()}?key={api_key}"
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"Gemini API error {response.status_code}: {response.text[:400]}")
        data = response.json()

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected Gemini response: {data}") from exc

    meta = {
        "provider": "gemini",
        "model": app_settings.orchestrator_model,
        "timing_ms": round((time.perf_counter() - started) * 1000, 2),
    }
    return _extract_json_text(text), meta

"""Ollama JSON fallback for orchestrator plans."""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from backend.chatbot.config import settings as chat_settings


def _extract_json_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


async def generate_plan_json(system_prompt: str, user_text: str) -> tuple[str, dict[str, Any]]:
    base = chat_settings.ollama_base_url.rstrip("/")
    model = chat_settings.ollama_model
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
        "format": "json",
    }
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{base}/api/chat", json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"Ollama error {response.status_code}: {response.text[:300]}")
        data = response.json()

    text = (data.get("message") or {}).get("content", "").strip()
    if not text:
        raise RuntimeError("Empty Ollama orchestrator response.")
    meta = {
        "provider": "ollama",
        "model": model,
        "timing_ms": round((time.perf_counter() - started) * 1000, 2),
    }
    return _extract_json_text(text), meta

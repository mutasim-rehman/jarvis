from __future__ import annotations

import time
from typing import Any

import httpx

from ..config import settings
from ..personality import build_base_system_message

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent"


def _build_payload(messages: list[dict[str, Any]]) -> dict[str, Any]:
    contents: list[dict[str, Any]] = []
    system_parts: list[dict[str, Any]] = []

    for msg in messages:
        role = (msg.get("role") or "").lower()
        text = str(msg.get("content") or "").strip()
        if not text:
            continue
        if role == "system":
            system_parts.append({"text": text})
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": text}]})
        else:
            contents.append({"role": "user", "parts": [{"text": text}]})

    if not contents:
        system_prompt = build_base_system_message()
        contents.append({"role": "user", "parts": [{"text": system_prompt}]})

    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": 512,
            "temperature": 0.7,
        },
    }
    if system_parts:
        payload["system_instruction"] = {"parts": system_parts}
    return payload


async def generate_chat_gemini(messages: list[dict[str, Any]], format: Any = None) -> dict[str, Any]:
    api_key = settings.google_gemini_key
    if not api_key:
        raise RuntimeError(
            "Gemini API key not configured. Set GOOGLE_GEMINI_KEY in .env."
        )

    payload = _build_payload(messages)
    url = f"{_GEMINI_URL}?key={api_key}"

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Gemini API error {response.status_code}: {response.text[:300]}"
                )
            data = response.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Gemini HTTP error: {exc}") from exc
    timing_ms = round((time.perf_counter() - started) * 1000, 2)

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected Gemini response shape: {data}") from exc

    return {
        "message": {"role": "assistant", "content": text},
        "meta": {
            "provider": "gemini",
            "model": "gemini-2.0-flash-lite",
            "timing_ms": timing_ms,
            "input_chars": sum(len(str(m.get("content", ""))) for m in messages),
        },
    }

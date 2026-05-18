from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

from ..config import settings
from ..personality import build_base_system_message

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent"
_DBG_LOG = os.path.join(os.path.dirname(__file__), "..", "..", "..", "debug-0394a8.log")


def _dbg(message: str, data: dict[str, Any]) -> None:
    # #region agent log
    try:
        with open(_DBG_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "0394a8",
                "location": "gemini.py",
                "message": message,
                "data": data,
                "timestamp": int(time.time() * 1000),
            }) + "\n")
    except Exception:
        pass
    # #endregion


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
    _dbg("[DBG-GEM1] entry", {"has_key": bool(api_key), "key_len": len(api_key), "key_prefix": api_key[:6] if api_key else ""})
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
            _dbg("[DBG-GEM2] http response", {"status": response.status_code, "body_preview": response.text[:500]})
            if response.status_code != 200:
                raise RuntimeError(
                    f"Gemini API error {response.status_code}: {response.text[:300]}"
                )
            data = response.json()
    except httpx.HTTPError as exc:
        _dbg("[DBG-GEM3] http error", {"err": str(exc), "type": type(exc).__name__})
        raise RuntimeError(f"Gemini HTTP error: {exc}") from exc
    timing_ms = round((time.perf_counter() - started) * 1000, 2)
    _dbg("[DBG-GEM4] parsed json", {"timing_ms": timing_ms, "keys": list(data.keys())})

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as exc:
        _dbg("[DBG-GEM5] shape error", {"data_preview": json.dumps(data)[:500]})
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

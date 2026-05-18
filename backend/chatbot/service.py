import json
import os
from typing import Any

import httpx
import time

from .config import settings

_DBG_LOG = os.path.join(os.path.dirname(__file__), "..", "..", "debug-0394a8.log")


_OLLAMA_HEALTH_TTL_SECONDS = 5.0
_ollama_health_cache: tuple[float, bool] = (0.0, False)


async def _is_ollama_available() -> bool:
    global _ollama_health_cache
    now = time.monotonic()
    cached_at, cached_value = _ollama_health_cache
    if now - cached_at <= _OLLAMA_HEALTH_TTL_SECONDS:
        return cached_value
    try:
        async with httpx.AsyncClient(timeout=0.35) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            is_ok = response.status_code == 200
    except Exception:
        is_ok = False
    _ollama_health_cache = (now, is_ok)
    return is_ok


async def _call_hf(messages: list[dict[str, Any]], format: Any = None) -> dict[str, Any]:
    from .providers.huggingface_space import generate_chat_hf_space

    return await generate_chat_hf_space(messages=messages, format=format)


async def _call_ollama(messages: list[dict[str, Any]], format: Any = None) -> dict[str, Any]:
    from .providers.ollama import generate_chat_ollama

    return await generate_chat_ollama(messages=messages, format=format)


async def _call_gemini(messages: list[dict[str, Any]], format: Any = None) -> dict[str, Any]:
    from .providers.gemini import generate_chat_gemini

    return await generate_chat_gemini(messages=messages, format=format)


async def generate_chat(
    messages: list[dict[str, Any]],
    format: Any = None,
    preferred_provider: str | None = None,
) -> dict[str, Any]:
    provider = (preferred_provider or settings.chat_primary_provider or "huggingface").strip().lower()
    # Auto-upgrade: prefer Gemini (fast cloud) then Ollama (local) when HuggingFace is the default
    if preferred_provider is None and provider == "huggingface":
        if settings.google_gemini_key:
            provider = "gemini"
        elif await _is_ollama_available():
            provider = "ollama"
    # #region agent log
    try:
        with open(_DBG_LOG, "a") as _f:
            _f.write(json.dumps({"sessionId": "0394a8", "location": "service.py:generate_chat", "message": "[DBG-PROVIDER] selected provider", "data": {"provider": provider, "configured": settings.chat_primary_provider, "has_gemini_key": bool(settings.google_gemini_key)}, "timestamp": int(time.time() * 1000)}) + "\n")
    except Exception:
        pass
    # #endregion
    if provider == "ollama":
        return await _call_ollama(messages=messages, format=format)
    if provider == "gemini":
        try:
            return await _call_gemini(messages=messages, format=format)
        except RuntimeError as exc:
            # #region agent log
            try:
                with open(_DBG_LOG, "a") as _f:
                    _f.write(json.dumps({"sessionId": "0394a8", "location": "service.py:generate_chat", "message": "[DBG-FALLBACK] gemini failed, trying ollama", "data": {"err": str(exc)[:200]}, "timestamp": int(time.time() * 1000)}) + "\n")
            except Exception:
                pass
            # #endregion
            # Auto-fallback to Ollama if available (no explicit provider requested)
            if preferred_provider is None and await _is_ollama_available():
                return await _call_ollama(messages=messages, format=format)
            raise
    if provider == "huggingface":
        return await _call_hf(messages=messages, format=format)
    raise RuntimeError(f"Unsupported chat provider: {provider}")

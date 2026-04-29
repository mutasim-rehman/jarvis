from typing import Any

import httpx
import time

from .config import settings


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


async def generate_chat(
    messages: list[dict[str, Any]],
    format: Any = None,
    preferred_provider: str | None = None,
) -> dict[str, Any]:
    provider = (preferred_provider or settings.primary_provider or "huggingface").strip().lower()
    if preferred_provider is None and provider == "huggingface":
        if await _is_ollama_available():
            provider = "ollama"
    if provider == "ollama":
        return await _call_ollama(messages=messages, format=format)
    if provider == "huggingface":
        return await _call_hf(messages=messages, format=format)
    raise RuntimeError(f"Unsupported chat provider: {provider}")

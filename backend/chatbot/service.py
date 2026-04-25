from typing import Any

from .config import settings


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
    if provider == "ollama":
        return await _call_ollama(messages=messages, format=format)
    if provider == "huggingface":
        return await _call_hf(messages=messages, format=format)
    raise RuntimeError(f"Unsupported chat provider: {provider}")

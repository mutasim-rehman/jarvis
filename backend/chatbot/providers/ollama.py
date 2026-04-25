from typing import Any

import httpx

from ..config import settings
from ..types import ProviderUnavailableError


async def generate_chat_ollama(messages: list[dict[str, Any]], format: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "options": {"num_ctx": 4096},
    }
    if format:
        payload["format"] = format

    try:
        async with httpx.AsyncClient(timeout=settings.timeout_seconds) as client:
            response = await client.post(f"{settings.ollama_base_url}/api/chat", json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise ProviderUnavailableError(provider="ollama", reason=str(exc)) from exc

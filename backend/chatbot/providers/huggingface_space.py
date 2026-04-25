import asyncio
import json
from typing import Any

from gradio_client import Client

from ..config import settings
from ..personality import build_base_system_message
from ..types import ProviderUnavailableError


def _extract_system_message(messages: list[dict[str, Any]]) -> str:
    for message in messages:
        if message.get("role") == "system":
            content = str(message.get("content", "")).strip()
            if content:
                return content
    return build_base_system_message()


def _extract_user_message(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            content = str(message.get("content", "")).strip()
            if content:
                return content
    return ""


def _predict_with_client(
    *,
    message: str,
    system_message: str,
    max_tokens: float,
    temperature: float,
    top_p: float,
) -> Any:
    kwargs: dict[str, Any] = {}
    if settings.hf_token:
        kwargs["hf_token"] = settings.hf_token
    client = Client(settings.hf_space_id, **kwargs)
    return client.predict(
        message=message,
        system_message=system_message,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        api_name=settings.hf_api_name,
    )


async def generate_chat_hf_space(messages: list[dict[str, Any]], format: Any = None) -> dict[str, Any]:
    del format  # Reserved for compatibility with parser signature.
    user_message = _extract_user_message(messages)
    if not user_message:
        raise ProviderUnavailableError(provider="huggingface", reason="Missing user message for Space request")

    system_message = _extract_system_message(messages)
    try:
        result = await asyncio.to_thread(
            _predict_with_client,
            message=user_message,
            system_message=system_message,
            max_tokens=settings.hf_max_tokens,
            temperature=settings.hf_temperature,
            top_p=settings.hf_top_p,
        )
    except Exception as exc:
        raise ProviderUnavailableError(provider="huggingface", reason=str(exc)) from exc

    if isinstance(result, str):
        content = result
    else:
        content = json.dumps(result, ensure_ascii=True)

    return {"message": {"content": content}}

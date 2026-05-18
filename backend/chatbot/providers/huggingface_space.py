import asyncio
import json
import logging
import types
import threading
import time
from typing import Any

from gradio_client import Client

from ..config import settings
from ..personality import build_base_system_message
from ..types import ProviderUnavailableError

logger = logging.getLogger(__name__)

_client_lock = threading.Lock()
_client: Client | None = None
_client_space_id = ""
_client_warmed = False


def _resolve_space_id() -> str:
    space_id = settings.resolved_hf_space_id()
    if not space_id:
        raise ProviderUnavailableError(
            provider="huggingface",
            reason="HF_SPACE_ID is missing. Set HF_SPACE_ID or HF_SPACE_LINK in .env.",
        )
    return space_id


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


def _get_or_create_client() -> tuple[Client, bool]:
    """Return (client, created_new). Caller must hold _client_lock."""
    global _client, _client_space_id
    space_id = _resolve_space_id()
    created = _client is None or _client_space_id != space_id
    if created:
        kwargs: dict[str, Any] = {"verbose": False}
        if settings.hf_token:
            kwargs["hf_token"] = settings.hf_token
        _client = Client(space_id, **kwargs)
        _client_space_id = space_id
    return _client, created


def _predict_with_client(
    *,
    message: str,
    system_message: str,
    max_tokens: float,
    temperature: float,
    top_p: float,
) -> Any:
    # Compatibility shim for Python 3.13 when third-party deps still reference asyncio.coroutine.
    if not hasattr(asyncio, "coroutine"):
        asyncio.coroutine = types.coroutine  # type: ignore[attr-defined]

    with _client_lock:
        client, _ = _get_or_create_client()
    return client.predict(
        message=message,
        system_message=system_message,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        api_name=settings.hf_api_name,
    )


def warmup_hf_client() -> None:
    """Connect to the Space and run a tiny predict to wake GPU + Gradio queue."""
    global _client_warmed
    if _client_warmed:
        return
    system_message = settings.hf_system_message.strip() or build_base_system_message()
    init_started = time.perf_counter()
    with _client_lock:
        _, created = _get_or_create_client()
    init_ms = (time.perf_counter() - init_started) * 1000
    predict_started = time.perf_counter()
    _predict_with_client(
        message="ping",
        system_message=system_message,
        max_tokens=8,
        temperature=0.1,
        top_p=0.9,
    )
    predict_ms = (time.perf_counter() - predict_started) * 1000
    _client_warmed = True
    logger.info(
        "hf client warmup init_ms=%.1f predict_ms=%.1f created_client=%s",
        init_ms,
        predict_ms,
        created,
    )


async def generate_chat_hf_space(messages: list[dict[str, Any]], format: Any = None) -> dict[str, Any]:
    del format  # Reserved for compatibility with parser signature.
    user_message = _extract_user_message(messages)
    if not user_message:
        raise ProviderUnavailableError(provider="huggingface", reason="Missing user message for Space request")

    system_message = _extract_system_message(messages)
    if settings.hf_system_message.strip():
        system_message = settings.hf_system_message.strip()
    started = time.perf_counter()
    init_ms = 0.0
    predict_ms = 0.0
    try:
        init_started = time.perf_counter()
        with _client_lock:
            _, created = _get_or_create_client()
        init_ms = (time.perf_counter() - init_started) * 1000
        predict_started = time.perf_counter()
        result = await asyncio.wait_for(
            asyncio.to_thread(
                _predict_with_client,
                message=user_message,
                system_message=system_message,
                max_tokens=settings.hf_max_tokens,
                temperature=settings.hf_temperature,
                top_p=settings.hf_top_p,
            ),
            timeout=max(0.05, settings.timeout_seconds),
        )
        predict_ms = (time.perf_counter() - predict_started) * 1000
    except asyncio.TimeoutError as exc:
        raise ProviderUnavailableError(
            provider="huggingface",
            reason=f"Hugging Face request timed out after {settings.timeout_seconds:.1f}s",
        ) from exc
    except Exception as exc:
        raise ProviderUnavailableError(provider="huggingface", reason=str(exc)) from exc

    if isinstance(result, str):
        content = result
    else:
        content = json.dumps(result, ensure_ascii=True)

    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "message": {"content": content},
        "meta": {
            "provider": "huggingface",
            "timing_ms": round(elapsed_ms, 2),
            "init_ms": round(init_ms, 2),
            "predict_ms": round(predict_ms, 2),
            "input_chars": len(user_message),
            "system_chars": len(system_message),
        },
    }

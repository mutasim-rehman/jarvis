from typing import Any

from backend.chatbot.service import generate_chat as generate_chat_via_provider


async def generate_chat(messages: list[dict[str, Any]], format: Any = None) -> dict[str, Any]:
    """Compatibility wrapper. Prefer backend.chatbot.generate_chat."""
    return await generate_chat_via_provider(messages=messages, format=format)

import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.chatbot.types import ProviderUnavailableError


def test_parser_returns_fallback_meta_when_hf_unavailable(monkeypatch):
    import backend.app.parser as parser_module

    async def fake_chat(messages, format=None):
        raise ProviderUnavailableError(provider="huggingface", reason="space timeout")

    monkeypatch.setattr(parser_module, "generate_chat", fake_chat)
    response = asyncio.run(parser_module.parse_intent("tell me a joke"))

    assert response.command is None
    assert response.route.value == "informational"
    assert response.meta["status"] == "unavailable"
    assert response.meta["chatbot_provider"] == "huggingface"
    option_ids = [opt["id"] for opt in response.meta.get("fallback_options", [])]
    assert "retry_huggingface" in option_ids
    assert "run_local_ollama" in option_ids


def test_parser_uses_requested_provider_override(monkeypatch):
    import backend.app.parser as parser_module

    observed = {"provider": None}

    async def fake_chat(messages, format=None, preferred_provider=None):
        observed["provider"] = preferred_provider
        return {"message": {"content": "Sure."}}

    monkeypatch.setattr(parser_module, "generate_chat", fake_chat)
    response = asyncio.run(parser_module.parse_intent("hello there", chat_provider="ollama"))

    assert observed["provider"] == "ollama"
    assert response.message

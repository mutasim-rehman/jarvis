import asyncio
import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.chatbot.service import generate_chat
from backend.chatbot.types import ProviderUnavailableError


def test_generate_chat_defaults_to_huggingface(monkeypatch):
    async def fake_hf(messages, format=None):
        return {"message": {"content": "hf ok"}}

    monkeypatch.setattr("backend.chatbot.service._call_hf", fake_hf)
    result = asyncio.run(generate_chat(messages=[{"role": "user", "content": "hello"}]))
    assert result["message"]["content"] == "hf ok"


def test_generate_chat_honors_ollama_override(monkeypatch):
    async def fake_ollama(messages, format=None):
        return {"message": {"content": "ollama ok"}}

    monkeypatch.setattr("backend.chatbot.service._call_ollama", fake_ollama)
    result = asyncio.run(
        generate_chat(
            messages=[{"role": "user", "content": "hello"}],
            preferred_provider="ollama",
        )
    )
    assert result["message"]["content"] == "ollama ok"


def test_generate_chat_hf_failure_bubbles_up(monkeypatch):
    async def fake_hf(messages, format=None):
        raise ProviderUnavailableError(provider="huggingface", reason="network down")

    monkeypatch.setattr("backend.chatbot.service._call_hf", fake_hf)
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(generate_chat(messages=[{"role": "user", "content": "hello"}]))


def test_generate_chat_rejects_unknown_provider():
    with pytest.raises(RuntimeError):
        asyncio.run(
            generate_chat(
                messages=[{"role": "user", "content": "hello"}],
                preferred_provider="some-other-provider",
            )
        )

import asyncio
import os
import sys
import time

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


def test_parse_intent_fallback_when_provider_unavailable(monkeypatch):
    import backend.app.parser as parser_module
    from backend.chatbot.types import ProviderUnavailableError

    async def fake_chat(messages, format=None, preferred_provider=None):
        del messages, format, preferred_provider
        raise ProviderUnavailableError(provider="huggingface", reason="timeout")

    monkeypatch.setattr(parser_module, "generate_chat", fake_chat)
    result = asyncio.run(parser_module.parse_intent("play some music"))

    assert result.command is not None
    assert result.command.intent == "PLAY_MUSIC"


@pytest.mark.asyncio
async def test_hf_provider_timeout_is_enforced(monkeypatch):
    import backend.chatbot.providers.huggingface_space as hf_provider
    from backend.chatbot.types import ProviderUnavailableError

    def slow_predict(**kwargs):
        del kwargs
        time.sleep(0.05)
        return {"intent": "UNKNOWN"}

    monkeypatch.setattr(hf_provider, "_predict_with_client", slow_predict)
    monkeypatch.setattr(hf_provider.settings, "timeout_seconds", 0.01)

    with pytest.raises(ProviderUnavailableError, match="timed out"):
        await hf_provider.generate_chat_hf_space(
            [{"role": "user", "content": "hello"}]
        )

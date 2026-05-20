import asyncio
import os
import sys
import time

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


def test_parse_intent_orchestrator_plan_on_music(monkeypatch):
    import backend.app.parser as parser_module
    from shared.schema import OrchestratorPlan, Task

    async def fake_plan(text, catalog=None):
        return (
            OrchestratorPlan(
                goal="music",
                reasoning="On it.",
                steps=[Task(action="PLAY_MUSIC", target=None)],
            ),
            {"orchestrator_provider": "gemini"},
        )

    monkeypatch.setattr(parser_module, "orchestrator_plan", fake_plan)
    monkeypatch.setattr("backend.app.config.settings.orchestrator_disabled", False)
    result = asyncio.run(parser_module.parse_intent("play some music"))

    assert result.command is not None
    assert result.command.intent == "ORCHESTRATED"
    assert result.command.tasks[0].action == "PLAY_MUSIC"


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

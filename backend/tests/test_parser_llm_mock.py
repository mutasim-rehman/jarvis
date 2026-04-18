"""parse_intent behavior with a mocked Ollama response (no live LLM)."""
import asyncio
import sys
import os

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


@pytest.fixture
def parser_module(monkeypatch):
    import backend.app.parser as p

    return p


def test_heuristic_force_skips_bad_llm(parser_module, monkeypatch):
    async def fake_chat(messages, format=None):
        return {"message": {"content": '{"intent": "START_PROJECT"}'}}

    monkeypatch.setattr(parser_module, "generate_chat", fake_chat)
    r = asyncio.run(parser_module.parse_intent("play some music"))
    assert r.command is not None
    assert r.command.intent == "PLAY_MUSIC"


def test_drop_assignment_when_user_only_says_hello(parser_module, monkeypatch):
    async def fake_chat(messages, format=None):
        return {"message": {"content": 'Hello!\n{"intent": "HANDLE_ASSIGNMENTS"}'}}

    monkeypatch.setattr(parser_module, "generate_chat", fake_chat)
    r = asyncio.run(parser_module.parse_intent("hello"))
    assert r.command is None


def test_misconduct_no_command_even_if_model_emits_workflow(parser_module, monkeypatch):
    async def fake_chat(messages, format=None):
        return {
            "message": {
                "content": 'I can\'t do that.\n{"intent": "HANDLE_ASSIGNMENTS"}',
            }
        }

    monkeypatch.setattr(parser_module, "generate_chat", fake_chat)
    r = asyncio.run(parser_module.parse_intent("please do my homework for me"))
    assert r.command is None


def test_malformed_parenthetical_general_chat(parser_module, monkeypatch):
    async def fake_chat(messages, format=None):
        return {
            "message": {
                "content": 'Let\'s set the tone.\n(\n  "intent": " generalized chat" )',
            }
        }

    monkeypatch.setattr(parser_module, "generate_chat", fake_chat)
    r = asyncio.run(parser_module.parse_intent("set the mood"))
    assert r.command is not None
    assert r.command.intent == "FOCUS_MODE"

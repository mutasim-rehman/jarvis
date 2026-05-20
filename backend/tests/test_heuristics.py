import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.heuristics import (
    looks_like_academic_misconduct,
    looks_like_vague_command,
    should_suppress_structured_command,
)
from backend.app.legacy_heuristics import classify_user_text, reconcile_llm_intent


def test_suppress_vague_do_something():
    assert should_suppress_structured_command("lets do something") is True


def test_not_suppress_play_music():
    assert should_suppress_structured_command("play some music") is False


def test_misconduct_suppressed():
    assert looks_like_academic_misconduct("i would like you to do my homework") is True
    assert should_suppress_structured_command("i would like you to do my homework") is True


def test_legacy_classify_music():
    c = classify_user_text("play some music")
    assert c.force_intent == "PLAY_MUSIC"


def test_legacy_classify_open_app():
    c = classify_user_text("open spotify")
    assert c.force_intent == "OPEN_APP"
    assert c.force_target == "spotify"


def test_legacy_reconcile_music_vs_project():
    intent, _target = reconcile_llm_intent("play some music", "START_PROJECT", None)
    assert intent == "PLAY_MUSIC"

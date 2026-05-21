import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.heuristics import (
    looks_like_academic_misconduct,
    looks_like_vague_command,
    should_suppress_structured_command,
)


def test_suppress_vague_do_something():
    assert should_suppress_structured_command("lets do something") is True


def test_not_suppress_play_music():
    assert should_suppress_structured_command("play some music") is False


def test_misconduct_suppressed():
    assert looks_like_academic_misconduct("i would like you to do my homework") is True
    assert should_suppress_structured_command("i would like you to do my homework") is True


def test_vague_without_domain():
    assert looks_like_vague_command("lets do something") is True

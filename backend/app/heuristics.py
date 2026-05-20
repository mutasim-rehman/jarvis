"""Deterministic safety checks for the orchestrator (suppression only)."""

from __future__ import annotations

import re


def _lower(s: str) -> str:
    return s.strip().lower()


def looks_like_academic_misconduct(text: str) -> bool:
    """User asks the assistant to do graded work for them — no execution workflow."""
    t = _lower(text)
    if re.search(r"\b(do|finish|complete|write|solve)\s+(my|the|our)\s+(homework|hw)\b", t):
        return True
    if re.search(r"\b(do|write|complete)\s+my\s+(assignment|paper|essay|report)\b", t):
        return True
    if re.search(r"\bhomework\b", t) and re.search(
        r"\b(you|jarvis|please)\b.{0,40}\b(do|finish|write|complete|solve)\b", t
    ):
        return True
    if re.search(r"\b(do|finish|write)\s+.{0,20}\bhomework\b", t) and re.search(
        r"\b(i would like you|can you|could you|please)\b", t
    ):
        return True
    return False


def looks_like_vague_command(text: str) -> bool:
    t = _lower(text)
    if re.search(r"\b(let's|lets)\s+do\s+something\b", t):
        return True
    if re.fullmatch(r"do\s+something\s*", t):
        return True
    return False


def _has_domain_signal(t: str) -> bool:
    """Minimal domain cues so vague 'do something' is not suppressed when specific."""
    markers = (
        "assignment",
        "homework",
        "music",
        "spotify",
        "youtube",
        "project",
        "open ",
        "launch ",
        "news",
        "video",
        "playlist",
        "classroom",
    )
    return any(m in t for m in markers)


def should_suppress_structured_command(text: str) -> bool:
    """Block execution plans for misconduct or vague requests without domain cues."""
    t = _lower(text)
    if not t:
        return False
    if looks_like_academic_misconduct(text):
        return True
    if looks_like_vague_command(text) and not _has_domain_signal(t):
        return True
    return False

"""
Legacy deterministic NL → intent classification.

Used only when ORCHESTRATOR_DISABLED=true (emergency rollback).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Re-export classification helpers for rollback tests.
from backend.app.heuristics import looks_like_academic_misconduct, should_suppress_structured_command

_KNOWN_APPS = frozenset(
    {
        "spotify",
        "chrome",
        "cursor",
        "notion",
        "edge",
        "firefox",
        "terminal",
        "code",
        "vscode",
        "slack",
        "discord",
    }
)

_ASSIGNMENT_MARKERS = (
    "assignment",
    "homework",
    "classwork",
    "coursework",
    "due",
    "lms",
    "canvas",
    "moodle",
    "assingment",
    "assingments",
)

_DO_ASSIGNMENT_VERBS = re.compile(
    r"\b(do|start|begin|work\s+on|open|code|work|complete)\s+(assignment|task|number|the|it|that)\b"
    r"|\bstart\s+number\b"
    r"|\b(do|start|begin|work\s+on|complete)\s+#?\d+\b",
    re.I,
)

_PROJECT_START_MARKERS = (
    "start project",
    "project setup",
    "my project setup",
    "coding setup",
    "dev environment",
    "start my project",
)

_PROJECT_CREATE_MARKERS = ("create project", "new project", "initialize project")

_PROJECT_RESUME_MARKERS = (
    "resume project",
    "continue project",
    "open last project",
    "complete this project",
    "complete the project",
    "finish this project",
    "finish the project",
    "wrap up this project",
    "wrap up the project",
    "finish up",
)

_MOOD_PHRASES = (
    "set the mood",
    "set a mood",
    "change the mood",
    "get in the zone",
    "chill vibe",
    "focus vibe",
)

_NEWS_TECH_MARKERS = ("tech news", "technology news", "it news", "silicon valley", "gadget news")
_NEWS_WORLD_MARKERS = ("world news", "global news", "international news", "headlines", "happening in the world")
_VIDEO_MARKERS = ("video", "clip", "clips", "watch", "youtube", "tutorial", "episode")

_MORNING_RITUAL_PHRASES = (
    "power up",
    "we re back online",
    "were back online",
    "bring the house to life",
    "initialize morning protocol",
    "let s build something",
    "lets build something",
    "status check",
    "engage",
    "wake up daddy s home",
    "wake up daddy's home",
    "wake up we ve got work",
    "wake up we've got work",
    "let s make something dangerous",
    "lets make something dangerous",
    "time to cook",
    "start the engine",
    "we re not wasting today",
    "were not wasting today",
    "wake up and earn your electricity",
)


@dataclass(frozen=True)
class UserTextClassification:
    force_intent: str | None = None
    force_target: str | None = None
    suppress_structured_command: bool = False


def _lower(s: str) -> str:
    return s.strip().lower()


def _do_assignment_signal(t: str) -> bool:
    if _DO_ASSIGNMENT_VERBS.search(t):
        return True
    if re.search(r"\bassignment\s+(\d+|\w.{0,40})", t, re.I):
        return True
    return False


def _extract_assignment_ref(raw: str) -> str | None:
    t = raw.strip()
    m = re.search(r"\b(?:assignment|number|#)\s*#?(\d+)\b", t, re.I)
    if m:
        return m.group(1)
    m = re.search(
        r"\b(?:do|start|begin|work\s+on|complete)\s+(?:the\s+|number\s+)?(.{3,60})\b",
        t.rstrip("."),
        re.I,
    )
    if m:
        ref = m.group(1).strip()
        ref = re.sub(
            r"\s+(?:with|using|via|in)\s+(?:gemini|antigravity|vs\s*code|vscode)\s*$",
            "",
            ref,
            flags=re.I,
        ).strip()
        if len(ref) > 1:
            return ref
    return None


def _extract_ai_tool(t: str) -> str | None:
    if re.search(r"\b(antigravity|anti.gravity|antigrav)\b", t, re.I):
        return "antigravity"
    if re.search(r"\bgemini\b", t, re.I):
        return "gemini"
    return None


def _has_assignment_signal(t: str) -> bool:
    return any(m in t for m in _ASSIGNMENT_MARKERS)


def _morning_ritual_signal(raw_text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9\s]", " ", (raw_text or "").strip().lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized or "jarvis" not in normalized:
        return False
    return any(phrase in normalized for phrase in _MORNING_RITUAL_PHRASES)


def _music_play_signal(t: str) -> bool:
    if re.search(r"\b(stop|pause)\s+(the\s+)?(music|song|playlist)\b", t):
        return False
    if re.search(r"\b(start|begin)\s+(the\s+)?music\b", t):
        return True
    verbs = r"(play|listen\s+to|put\s+on|turn\s+on|queue)"
    nouns = r"(music|song|songs|playlist|album|track|tunes|radio)"
    if re.search(rf"\b{verbs}\b.{{0,40}}\b{nouns}\b", t):
        return True
    if re.search(rf"\b{nouns}\b.{{0,20}}\b{verbs}\b", t):
        return True
    if re.search(r"\bplay\s+some\b", t) and re.search(r"\b(music|tunes|songs)\b", t):
        return True
    return False


def _stop_music_signal(t: str) -> bool:
    return bool(re.search(r"\b(stop|pause)\s+(the\s+)?(music|song|playlist|spotify)\b", t))


def _project_signal(t: str) -> bool:
    if any(m in t for m in _PROJECT_CREATE_MARKERS + _PROJECT_RESUME_MARKERS + _PROJECT_START_MARKERS):
        return True
    if re.search(r"\bwork\s+on\s+(the\s+)?project\b", t):
        return True
    return False


def _video_play_signal(t: str) -> bool:
    if any(m in t for m in ("play clips of", "play clips", "show videos of", "show video of", "videos of")):
        return True
    if re.search(r"\bplay\b.{0,40}\b(clips?|videos?|youtube)\b", t):
        return True
    if re.search(r"\bwatch\b", t) and not re.search(r"\b(song|music|album|track|spotify)\b", t):
        if "play" not in t or any(w in t for w in ("video", "youtube", "clip")):
            return True
    if "youtube" in t and not re.search(r"\b(song|music|album|track|spotify)\b", t):
        return True
    return False


def _open_app_match(t: str) -> tuple[str, str] | None:
    m = re.search(
        r"\b(open|launch|start)\s+([a-z][a-z0-9]*(?:\s+[a-z][a-z0-9]*)?)\b",
        t,
    )
    if not m:
        return None
    app = m.group(2).strip().lower()
    if app in _KNOWN_APPS:
        if app in ("code", "vscode"):
            return "OPEN_APP", "cursor"
        return "OPEN_APP", app
    return None


def _vague_do_something(t: str) -> bool:
    if re.search(r"\b(let's|lets)\s+do\s+something\b", t):
        return True
    if re.fullmatch(r"do\s+something\s*", t):
        return True
    return False


def _has_domain_signal(t: str) -> bool:
    if _has_assignment_signal(t) or _do_assignment_signal(t):
        return True
    if _music_play_signal(t) or _stop_music_signal(t):
        return True
    if _project_signal(t):
        return True
    if _video_play_signal(t):
        return True
    if _open_app_match(t):
        return True
    if any(m in t for m in _NEWS_TECH_MARKERS + _NEWS_WORLD_MARKERS):
        return True
    return False


def _music_app_target(t: str) -> str | None:
    if "spotify" in t:
        return "spotify"
    if "apple music" in t:
        return "apple music"
    if "youtube music" in t or "yt music" in t:
        return "youtube music"
    return None


def _strip_trailing_music_service(q: str) -> str:
    return re.sub(r"\s+on\s+(spotify|apple music|youtube music|yt music)\s*$", "", q, flags=re.I).strip()


def _music_spotify_target_from_text(raw_text: str) -> str | None:
    tl = (raw_text or "").strip()
    if not tl:
        return None

    def _clean(q: str) -> str | None:
        q = _strip_trailing_music_service(q).strip(" \t.-_,;:!?\"'")
        if len(q) < 1:
            return None
        low = q.lower()
        if low in ("music", "songs", "song", "some music", "the music", "tunes"):
            return None
        return q

    for pat in (
        r'\bplay\s+(?:the\s+|a\s+)?song\s+"([^"]+)"(?:\s+by\s+(.+))?',
        r"\bplay\s+(?:the\s+|a\s+)?song\s+'([^']+)'(?:\s+by\s+(.+))?",
        r"\bplay\s+(?:the\s+|a\s+)?song\s+(?!by\s)(.+)$",
        r"\bplay\s+the\s+track\s+(?!by\s)(.+)$",
    ):
        m = re.search(pat, tl, re.I | re.MULTILINE)
        if m:
            c = _clean(m.group(1))
            artist = _clean(m.group(2)) if len(m.groups()) > 1 and m.group(2) else None
            if c:
                return f"track:{c} {artist}" if artist else f"track:{c}"

    m = re.search(r"\b(?:play|listen\s+to|start|begin)\s+(?:some\s+|a\s+)?music\s+by\s+(.+)$", tl, re.I)
    if m:
        c = _clean(m.group(1))
        if c:
            return f"artist:{c}"

    m = re.search(r"\bplay\s+(?:some\s+|a\s+)?(?:songs?|tracks?|albums?)\s+by\s+(.+)$", tl, re.I)
    if m:
        c = _clean(m.group(1))
        if c:
            return f"artist:{c}"

    m = re.search(r"\bplay\s+(.+?)\s+on\s+spotify\s*$", tl, re.I)
    if m:
        c = _clean(m.group(1))
        if c and c.lower() not in ("some", "my"):
            return c

    m = re.search(r"\blisten\s+to\s+(.+)$", tl, re.I)
    if m:
        c = _clean(m.group(1))
        if c and c.lower() not in ("spotify", "apple music", "youtube music", "music"):
            return c

    m = re.search(r"\bput\s+on\s+(?:some\s+)?(.+)$", tl, re.I)
    if m:
        c = _clean(m.group(1))
        if c:
            return c

    m = re.search(r"\bplay\s+some\s+(.+?)\s+music\b", tl, re.I)
    if m:
        c = _clean(m.group(1))
        if c:
            return c

    m = re.search(r"\bplay\s+(?!some\s)([a-z0-9][a-z0-9\s,'-]{0,48})\s+music\b", tl, re.I)
    if m:
        c = _clean(m.group(1))
        if c:
            return c

    return None


def _extract_video_query(text: str) -> str | None:
    t = _lower(text)
    m = re.search(r"\b(play|watch|show|search\s+for)\s+(?:some\s+)?(.+?)(?:\s+on\s+youtube|\s+clips)?$", t)
    if m:
        return m.group(2).strip()
    return None


def classify_user_text(text: str) -> UserTextClassification:
    t = _lower(text)
    if not t:
        return UserTextClassification()

    if should_suppress_structured_command(text):
        return UserTextClassification(suppress_structured_command=True)

    if _morning_ritual_signal(text):
        return UserTextClassification(force_intent="MORNING_RITUAL", force_target=None)

    if any(p in t for p in _MOOD_PHRASES):
        return UserTextClassification(force_intent="FOCUS_MODE", force_target=None)

    if _stop_music_signal(t):
        return UserTextClassification(force_intent="STOP_MUSIC", force_target=None)

    if _music_play_signal(t) and not _project_signal(t) and not _video_play_signal(t):
        q = _music_spotify_target_from_text(text)
        if q:
            return UserTextClassification(force_intent="PLAY_MUSIC", force_target=q)
        return UserTextClassification(force_intent="PLAY_MUSIC", force_target=_music_app_target(t))

    if _has_assignment_signal(t) or _do_assignment_signal(t):
        if _do_assignment_signal(t):
            ref = _extract_assignment_ref(text) or _extract_assignment_ref(t)
            ai_tool = _extract_ai_tool(t)
            target = ref
            if target and ai_tool:
                target = f"{target}|{ai_tool}"
            elif ai_tool and not target:
                target = f"|{ai_tool}"
            return UserTextClassification(force_intent="DO_ASSIGNMENT", force_target=target)
        if any(k in t for k in ("check", "what's due", "whats due", "what is due", "pending", "do i have")):
            return UserTextClassification(force_intent="CHECK_ASSIGNMENTS", force_target=None)
        if _has_assignment_signal(t):
            return UserTextClassification(force_intent="HANDLE_ASSIGNMENTS", force_target=None)

    if _project_signal(t):
        if any(m in t for m in _PROJECT_RESUME_MARKERS):
            return UserTextClassification(force_intent="RESUME_PROJECT", force_target=None)
        if any(m in t for m in _PROJECT_CREATE_MARKERS):
            return UserTextClassification(force_intent="CREATE_PROJECT", force_target=None)
        return UserTextClassification(force_intent="START_PROJECT", force_target=None)

    open_hit = _open_app_match(t)
    if open_hit:
        return UserTextClassification(force_intent=open_hit[0], force_target=open_hit[1])

    if any(m in t for m in _NEWS_TECH_MARKERS):
        return UserTextClassification(force_intent="FETCH_TECH_NEWS", force_target=None)

    if any(m in t for m in _NEWS_WORLD_MARKERS):
        return UserTextClassification(force_intent="FETCH_WORLD_NEWS", force_target=None)

    if _video_play_signal(t):
        q = _extract_video_query(text)
        if q:
            return UserTextClassification(force_intent="WATCH_VIDEO", force_target=q)

    return UserTextClassification()


def reconcile_llm_intent(user_text: str, intent: str, target: str | None) -> tuple[str, str | None]:
    """Fix common LLM mistakes (legacy rollback / tests only)."""
    t = _lower(user_text)
    if intent in ("HANDLE_ASSIGNMENTS", "CHECK_ASSIGNMENTS") and looks_like_academic_misconduct(user_text):
        return "GENERAL_CHAT", None
    if intent == "START_PROJECT" and _music_play_signal(t) and not _project_signal(t):
        q = _music_spotify_target_from_text(user_text)
        if q:
            return "PLAY_MUSIC", q
        return "PLAY_MUSIC", _music_app_target(t)
    if intent == "PLAY_MUSIC":
        if _video_play_signal(t):
            return "WATCH_VIDEO", _extract_video_query(user_text)
        q = _music_spotify_target_from_text(user_text)
        if q:
            return "PLAY_MUSIC", q
    if intent in ("OPEN_WEBSITE", "SEARCH_WEB", "UNKNOWN"):
        open_hit = _open_app_match(t)
        if open_hit:
            return open_hit[0], open_hit[1]
    if intent == "HANDLE_ASSIGNMENTS" and _vague_do_something(t) and not _has_assignment_signal(t):
        return "GENERAL_CHAT", None
    if intent in ("UNKNOWN", "GENERAL_CHAT", "OPEN_WEBSITE", "SEARCH_WEB"):
        if _video_play_signal(t):
            return "WATCH_VIDEO", _extract_video_query(user_text)
        if any(m in t for m in _NEWS_TECH_MARKERS):
            return "FETCH_TECH_NEWS", None
        if any(m in t for m in _NEWS_WORLD_MARKERS):
            return "FETCH_WORLD_NEWS", None
    return intent, target

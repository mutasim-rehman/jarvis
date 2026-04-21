"""Deterministic NL → intent hints for Phase 1 (overrides flaky LLM output)."""
from __future__ import annotations

import re
from dataclasses import dataclass

# Apps we can map from user phrases to OPEN_APP targets (executor normalizes later).
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

# Patterns that mean "pick and work on a specific assignment"
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


def _requests_academic_misconduct(t: str) -> bool:
    """User asks the assistant to do graded work for them — no execution workflow."""
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


@dataclass(frozen=True)
class UserTextClassification:
    """If set, parser should prefer these over the LLM structured intent."""

    force_intent: str | None = None
    force_target: str | None = None
    suppress_structured_command: bool = False


def _lower(s: str) -> str:
    return s.strip().lower()


def _do_assignment_signal(t: str) -> bool:
    """True when user wants to start/work on a specific assignment."""
    if _DO_ASSIGNMENT_VERBS.search(t):
        return True
    # "assignment 5", "assignment: data structures"
    if re.search(r"\bassignment\s+(\d+|\w.{0,40})", t, re.I):
        return True
    return False


def _extract_assignment_ref(raw: str) -> str | None:
    """
    Extract the assignment reference (number or title fragment) from user text.
    Returns e.g. '17', 'CS2001-Project', 'data structures project'.
    """
    t = raw.strip()
    # "assignment 17", "number 17", "assignment #5"
    m = re.search(r"\b(?:assignment|number|#)\s*#?(\d+)\b", t, re.I)
    if m:
        return m.group(1)
    # "do the data structures project"
    m = re.search(
        r"\b(?:do|start|begin|work\s+on|complete)\s+(?:the\s+|number\s+)?(.{3,60})\b",
        t.rstrip("."),
        re.I,
    )
    if m:
        ref = m.group(1).strip()
        # strip trailing ai_tool mention
        ref = re.sub(r"\s+(?:with|using|via|in)\s+(?:gemini|antigravity|vs\s*code|vscode)\s*$", "", ref, flags=re.I).strip()
        if len(ref) > 1:
            return ref
    return None


def _extract_ai_tool(t: str) -> str | None:
    """Return 'gemini' or 'antigravity' if the user specifies a tool."""
    if re.search(r"\b(antigravity|anti.gravity|antigrav)\b", t, re.I):
        return "antigravity"
    if re.search(r"\bgemini\b", t, re.I):
        return "gemini"
    return None


def _has_assignment_signal(t: str) -> bool:
    return any(m in t for m in _ASSIGNMENT_MARKERS)


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


def _open_app_match(t: str) -> tuple[str, str] | None:
    m = re.search(
        r"\b(open|launch|start)\s+([a-z][a-z0-9]*(?:\s+[a-z][a-z0-9]*)?)\b",
        t,
    )
    if not m:
        return None
    app = m.group(2).strip().lower()
    if app in _KNOWN_APPS:
        if app == "code" or app == "vscode":
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
    """
    Build executor `target` for PLAY_MUSIC.

    Uses optional prefixes (executor parses them):
    - ``track:...`` — a song title (opens search biased to tracks; click lower in results).
    - ``artist:...`` — "music by …" / artist name (search ``artist:query``; click higher, avoid album tiles).
    - Unprefixed — genre/style or generic search text.
    """
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

    # --- Specific song / track (must run before broad "play …" / "music by …") ---
    for pat in (
        r'\bplay\s+the\s+song\s+"([^"]+)"',
        r"\bplay\s+the\s+song\s+'([^']+)'",
        r"\bplay\s+the\s+song\s+(.+)$",
        r'\bplay\s+song\s+"([^"]+)"',
        r"\bplay\s+song\s+'([^']+)'",
        r"\bplay\s+song\s+(.+)$",
        r"\bplay\s+the\s+track\s+(.+)$",
    ):
        m = re.search(pat, tl, re.I | re.MULTILINE)
        if m:
            c = _clean(m.group(1))
            if c:
                return f"track:{c}"

    # --- Artist: "music by …" / "songs by …" ---
    m = re.search(r"\b(?:play|listen\s+to|start|begin)\s+(?:some\s+)?music\s+by\s+(.+)$", tl, re.I)
    if m:
        c = _clean(m.group(1))
        if c:
            return f"artist:{c}"

    m = re.search(r"\bplay\s+(?:some\s+)?(?:songs?|tracks?|albums?)\s+by\s+(.+)$", tl, re.I)
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

    m = re.search(
        r"\bplay\s+(?!some\s)([a-z0-9][a-z0-9\s,'-]{0,48})\s+music\b",
        tl,
        re.I,
    )
    if m:
        c = _clean(m.group(1))
        if c:
            return c

    return None


def classify_user_text(text: str) -> UserTextClassification:
    t = _lower(text)
    if not t:
        return UserTextClassification()

    if _requests_academic_misconduct(t):
        return UserTextClassification(suppress_structured_command=True)

    if _vague_do_something(t) and not _has_domain_signal(t):
        return UserTextClassification(suppress_structured_command=True)

    if any(p in t for p in _MOOD_PHRASES):
        return UserTextClassification(force_intent="FOCUS_MODE", force_target=None)

    if _stop_music_signal(t):
        return UserTextClassification(force_intent="STOP_MUSIC", force_target=None)

    if _music_play_signal(t) and not _project_signal(t):
        q = _music_spotify_target_from_text(text)
        if q:
            return UserTextClassification(force_intent="PLAY_MUSIC", force_target=q)
        return UserTextClassification(
            force_intent="PLAY_MUSIC",
            force_target=_music_app_target(t),
        )

    if _has_assignment_signal(t) or _do_assignment_signal(t):
        # User is starting/working on a specific assignment
        if _do_assignment_signal(t):
            ref = _extract_assignment_ref(text) or _extract_assignment_ref(t)
            ai_tool = _extract_ai_tool(t)
            target = ref  # handler resolves by index or title
            # Encode ai_tool into target so it survives the single-field schema:
            # format: "<ref>|<tool>"  e.g. "17|gemini"  or  "CS2001-Project|antigravity"
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
        intent, target = open_hit
        return UserTextClassification(force_intent=intent, force_target=target)

    if any(m in t for m in _NEWS_TECH_MARKERS):
        return UserTextClassification(force_intent="FETCH_TECH_NEWS", force_target=None)
    
    if any(m in t for m in _NEWS_WORLD_MARKERS):
        return UserTextClassification(force_intent="FETCH_WORLD_NEWS", force_target=None)

    return UserTextClassification()


def should_drop_workflow_without_domain(user_text: str, intent: str) -> bool:
    """Safety net: block heavy workflows when user text has no domain cues."""
    heavy = {"HANDLE_ASSIGNMENTS", "CHECK_ASSIGNMENTS", "DO_ASSIGNMENT", "START_PROJECT", "CREATE_PROJECT", "RESUME_PROJECT"}
    if intent not in heavy:
        return False
    return not _has_domain_signal(_lower(user_text))


def reconcile_llm_intent(user_text: str, intent: str, target: str | None) -> tuple[str, str | None]:
    """Fix common LLM mistakes using the same signals as `classify_user_text`."""
    t = _lower(user_text)
    if intent in ("HANDLE_ASSIGNMENTS", "CHECK_ASSIGNMENTS") and _requests_academic_misconduct(t):
        return "GENERAL_CHAT", None
    if intent == "START_PROJECT" and _music_play_signal(t) and not _project_signal(t):
        q = _music_spotify_target_from_text(user_text)
        if q:
            return "PLAY_MUSIC", q
        return "PLAY_MUSIC", _music_app_target(t)
    if intent == "PLAY_MUSIC":
        q = _music_spotify_target_from_text(user_text)
        if q:
            return "PLAY_MUSIC", q
    if intent in ("OPEN_WEBSITE", "SEARCH_WEB", "UNKNOWN"):
        open_hit = _open_app_match(t)
        if open_hit:
            return open_hit[0], open_hit[1]
    if intent == "HANDLE_ASSIGNMENTS" and _vague_do_something(t) and not _has_assignment_signal(t):
        return "GENERAL_CHAT", None
    
    # News reconciliation
    if intent in ("UNKNOWN", "GENERAL_CHAT", "OPEN_WEBSITE", "SEARCH_WEB"):
        if any(m in t for m in _NEWS_TECH_MARKERS):
            return "FETCH_TECH_NEWS", None
        if any(m in t for m in _NEWS_WORLD_MARKERS):
            return "FETCH_WORLD_NEWS", None
            
    return intent, target

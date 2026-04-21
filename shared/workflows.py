"""
Intent templates for Phase 1 → executor handoff.

How WORKFLOWS is used (see ``backend.app.parser._build_command``):
  - Each intent maps to an ordered list of task *templates* (dicts).
  - Any template with ``\"target\": None`` is filled with the user/command ``target``
    from structured JSON (e.g. playlist name, app override, search string).
  - Intents not listed here still exist in ``IntentType`` / prompts but get no
    pre-expanded ``tasks`` unless the model or caller supplies them.

Executor reality (Phase 2 today — see ``executor.app.runner._HANDLERS``):
  - Implemented: ``OPEN_APP``, ``OPEN_URL`` / ``OPEN_WEBSITE``, ``CREATE_FOLDER``,
    ``PLAY_MUSIC`` (Spotify ``spotify:`` URIs — Liked Songs or in-app search).
  - Everything else returns ``NOT_IMPLEMENTED`` until later phases.

So each workflow should prefer those actions. Short placeholder steps that always
fail make the CLI noisy and hide real progress (e.g. LOGIN before a browser exists).
"""

from enum import Enum


class IntentType(str, Enum):
    GENERAL_CHAT = "GENERAL_CHAT"
    OPEN_APP = "OPEN_APP"
    CLOSE_APP = "CLOSE_APP"
    HANDLE_ASSIGNMENTS = "HANDLE_ASSIGNMENTS"
    CHECK_ASSIGNMENTS = "CHECK_ASSIGNMENTS"
    START_PROJECT = "START_PROJECT"
    CREATE_PROJECT = "CREATE_PROJECT"
    RESUME_PROJECT = "RESUME_PROJECT"
    STUDY_MODE = "STUDY_MODE"
    FOCUS_MODE = "FOCUS_MODE"
    SEARCH_WEB = "SEARCH_WEB"
    OPEN_WEBSITE = "OPEN_WEBSITE"
    PLAY_MUSIC = "PLAY_MUSIC"
    STOP_MUSIC = "STOP_MUSIC"
    SYSTEM_CONTROL = "SYSTEM_CONTROL"
    FILE_OPERATION = "FILE_OPERATION"
    FETCH_TECH_NEWS = "FETCH_TECH_NEWS"
    FETCH_WORLD_NEWS = "FETCH_WORLD_NEWS"
    UNKNOWN = "UNKNOWN"


# Human-readable intent summaries (docs, future UI, richer prompts).
WORKFLOW_DESCRIPTIONS: dict[str, str] = {
    "OPEN_APP": "Launch a desktop application by shortcut name (from allowlist) or path.",
    "CLOSE_APP": "Close or quit an application (handler TBD).",
    "CHECK_ASSIGNMENTS": "Open the LMS in a browser to review pending work.",
    "HANDLE_ASSIGNMENTS": "Open class workspace, ensure a local folder, and open the editor.",
    "START_PROJECT": "Jump into a coding session with your editor.",
    "CREATE_PROJECT": "Create a project directory under the executor workspace and open the editor.",
    "RESUME_PROJECT": "Jump back into the editor for ongoing work.",
    "STUDY_MODE": "Notes + browser + a simple focus timer in the browser.",
    "FOCUS_MODE": "Minimal distraction-free prep: foreground the editor.",
    "SEARCH_WEB": "Open a browser and a search entry point (full query automation later).",
    "OPEN_WEBSITE": "Open a specific URL or domain in the default browser.",
    "PLAY_MUSIC": "Spotify: Liked Songs when target is empty; otherwise search/play context for that query.",
    "STOP_MUSIC": "Bring Spotify to the foreground so you can pause/stop (OS media keys TBD).",
    "SYSTEM_CONTROL": "Volume, sleep, display — routed to SYSTEM_ACTION when implemented.",
    "FILE_OPERATION": "Copy/move/open files — routed to FILE_ACTION when implemented.",
    "FETCH_TECH_NEWS": "Open latest tech news and summarize highlights.",
    "FETCH_WORLD_NEWS": "Open global headlines and summarize highlights.",
}


WORKFLOWS: dict[str, list[dict]] = {
    # Single-slot intents: target None → user's app/query from JSON.
    "OPEN_APP": [
        {"action": "OPEN_APP", "target": None},
    ],
    "CLOSE_APP": [
        {"action": "CLOSE_APP", "target": None},
    ],
    # Use a real domain so OPEN_URL succeeds without a url_aliases entry ("gcr" alone fails).
    # Use Arc primary profile with account /u/1/
    "CHECK_ASSIGNMENTS": [
        {"action": "OPEN_APP", "target": "arc"},
        {"action": "OPEN_URL", "target": "https://classroom.google.com/u/1/a/not-turned-in/all"},
        {"action": "GET_ASSIGNMENTS", "target": "https://classroom.google.com/u/1/a/not-turned-in/all"},
    ],
    # Pragmatic path: browser → classroom → scrape assignments → workspace setup.
    "HANDLE_ASSIGNMENTS": [
        {"action": "OPEN_APP", "target": "arc"},
        {"action": "OPEN_URL", "target": "https://classroom.google.com/u/1/a/not-turned-in/all"},
        {"action": "GET_ASSIGNMENTS", "target": "https://classroom.google.com/u/1/a/not-turned-in/all"},
        {"action": "CREATE_FOLDER", "target": "assignments/latest"},
        {"action": "OPEN_APP", "target": "cursor"},
    ],
    "START_PROJECT": [
        {"action": "OPEN_APP", "target": "cursor"},
    ],
    "CREATE_PROJECT": [
        {"action": "OPEN_APP", "target": "cursor"},
        {"action": "CREATE_FOLDER", "target": "projects/new_project"},
    ],
    "RESUME_PROJECT": [
        {"action": "OPEN_APP", "target": "cursor"},
    ],
    "STUDY_MODE": [
        {"action": "OPEN_APP", "target": "notion"},
        {"action": "OPEN_APP", "target": "chrome"},
        {"action": "OPEN_URL", "target": "https://pomofocus.io"},
    ],
    "FOCUS_MODE": [
        {"action": "OPEN_APP", "target": "cursor"},
    ],
    # google.com as a stable entry; intent target can still name a preferred engine in copy.
    "SEARCH_WEB": [
        {"action": "OPEN_APP", "target": "chrome"},
        {"action": "OPEN_URL", "target": "google.com"},
    ],
    "OPEN_WEBSITE": [
        {"action": "OPEN_APP", "target": "chrome"},
        {"action": "OPEN_URL", "target": None},
    ],
    # Target None → Liked Songs; else Spotify in-app search for artist/song/style.
    "PLAY_MUSIC": [
        {"action": "PLAY_MUSIC", "target": None},
    ],
    "STOP_MUSIC": [
        {"action": "OPEN_APP", "target": "spotify"},
    ],
    "SYSTEM_CONTROL": [
        {"action": "SYSTEM_ACTION", "target": None},
    ],
    "FILE_OPERATION": [
        {"action": "FILE_ACTION", "target": None},
    ],
    "FETCH_TECH_NEWS": [
        {"action": "OPEN_URL", "target": "https://tech.worldmonitor.app"},
        {"action": "GET_HIGHLIGHTS", "target": "https://tech.worldmonitor.app"},
    ],
    "FETCH_WORLD_NEWS": [
        {"action": "OPEN_URL", "target": "https://www.worldmonitor.app"},
        {"action": "GET_HIGHLIGHTS", "target": "https://www.worldmonitor.app"},
    ],
}

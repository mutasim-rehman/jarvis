"""Declarative tool definitions — single source of truth for the orchestrator catalog."""

from __future__ import annotations

from shared.schema import ToolDefinition, ToolParameter

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="OPEN_APP",
        category="app",
        description="Launch a desktop application by shortcut name (allowlist) or discovered app name.",
        parameters=[
            ToolParameter(
                name="target",
                type="string",
                description="App name: cursor, chrome, spotify, arc, notion, etc.",
                required=True,
            ),
        ],
    ),
    ToolDefinition(
        name="OPEN_URL",
        category="web",
        description="Open a URL in the default or Arc browser.",
        parameters=[
            ToolParameter(
                name="target",
                type="string",
                description="Full URL or domain (e.g. classroom.google.com).",
                required=True,
            ),
        ],
    ),
    ToolDefinition(
        name="OPEN_WEBSITE",
        category="web",
        description="Alias for OPEN_URL — open a website.",
        parameters=[
            ToolParameter(
                name="target",
                type="string",
                description="URL or domain.",
                required=True,
            ),
        ],
        fallback_for=["OPEN_URL"],
    ),
    ToolDefinition(
        name="PLAY_MUSIC",
        category="music",
        description=(
            "Play music on Spotify. Omit target for Liked Songs; use artist:Name, track:Title, "
            "or genre/style text for search."
        ),
        parameters=[
            ToolParameter(
                name="target",
                type="string",
                description="Optional: artist:X, track:X, genre, or search query.",
                required=False,
            ),
        ],
        requires=["spotify_auth"],
        fallback_for=[],
    ),
    ToolDefinition(
        name="WATCH_VIDEO",
        category="video",
        description="Search YouTube and open the top result in the browser.",
        parameters=[
            ToolParameter(
                name="target",
                type="string",
                description="Video search query.",
                required=True,
            ),
        ],
        requires=["youtube_api"],
    ),
    ToolDefinition(
        name="GET_HIGHLIGHTS",
        category="web",
        description="Fetch and summarize news highlights from a news URL (Jina + Ollama).",
        parameters=[
            ToolParameter(
                name="target",
                type="string",
                description="News site URL (e.g. tech.worldmonitor.app).",
                required=True,
            ),
        ],
        requires=["ollama"],
    ),
    ToolDefinition(
        name="GET_ASSIGNMENTS",
        category="education",
        description="List pending Google Classroom assignments from a Classroom URL.",
        parameters=[
            ToolParameter(
                name="target",
                type="string",
                description="Classroom assignments URL.",
                required=True,
            ),
        ],
        requires=["google_auth"],
    ),
    ToolDefinition(
        name="DO_ASSIGNMENT",
        category="education",
        description=(
            "Start work on a specific assignment: fetch from Classroom, create workspace, "
            "generate starter files with Gemini or Antigravity. Target: assignment ref or "
            "'ref|gemini' / 'ref|antigravity'."
        ),
        parameters=[
            ToolParameter(
                name="target",
                type="string",
                description="Assignment number/name, optionally '|gemini' or '|antigravity'.",
                required=False,
            ),
        ],
        requires=["google_auth"],
    ),
    ToolDefinition(
        name="CREATE_FOLDER",
        category="fs",
        description="Create a folder under allowlisted roots (assignments/, projects/ prefixes).",
        parameters=[
            ToolParameter(
                name="target",
                type="string",
                description="Relative path e.g. assignments/latest or projects/my_app.",
                required=True,
            ),
        ],
    ),
    ToolDefinition(
        name="MORNING_RITUAL",
        category="routine",
        description="Morning startup: greeting, Liked Songs, and tech news briefing.",
        parameters=[],
        requires=["spotify_auth"],
    ),
    ToolDefinition(
        name="SEND_EMAIL",
        category="email",
        description=(
            "Send an email via configured SMTP (Gmail etc.). "
            "Set target to recipient address; put subject and body in parameters."
        ),
        parameters=[
            ToolParameter(
                name="target",
                type="string",
                description="Recipient email address.",
                required=True,
            ),
            ToolParameter(
                name="subject",
                type="string",
                description="Email subject line.",
                required=True,
            ),
            ToolParameter(
                name="body",
                type="string",
                description="Plain-text email body.",
                required=True,
            ),
        ],
        requires=["smtp"],
    ),
]

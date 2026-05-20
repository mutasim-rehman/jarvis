"""Discover runtime capability tags, installed apps, and service availability."""

from __future__ import annotations

import logging
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx

from executor.app.auth.token_store import load_token
from executor.app.capabilities.registry import TOOLS
from executor.app.config import settings as executor_settings
from shared.schema import ToolCapability, ToolCatalog, ToolDefinition

logger = logging.getLogger(__name__)

_APP_SCAN_TTL_SECONDS = 300.0
_PROBE_TIMEOUT = 0.3

_app_scan_cache: tuple[float, list[str]] = (0.0, [])
_tag_cache: tuple[float, set[str]] = (0.0, set())


def _env_present(*keys: str) -> bool:
    for key in keys:
        if (os.environ.get(key) or "").strip():
            return True
    return False


def _token_file_present(service: str) -> bool:
    data = load_token(service)
    return bool(data.get("access_token") or data.get("token"))


def _scan_env_tags() -> set[str]:
    tags: set[str] = set()
    if _env_present("Spotify_Client_ID", "SPOTIFY_CLIENT_ID"):
        tags.add("spotify_credentials")
    if _token_file_present("spotify"):
        tags.add("spotify_auth")
    if _env_present("GCR_CREDENTIALS_JSON", "GOOGLE_APPLICATION_CREDENTIALS"):
        tags.add("google_credentials")
    if _token_file_present("google_classroom"):
        tags.add("google_auth")
    if _env_present(
        "Google_Gemini_Key",
        "GOOGLE_GEMINI_KEY",
        "ORCHESTRATOR_GEMINI",
    ):
        tags.add("gemini_api")
    if _env_present("Youtube_Data_API_V3", "YOUTUBE_API_KEY") or (executor_settings.youtube_api_key or "").strip():
        tags.add("youtube_api")
    if (executor_settings.ollama_base_url or "").strip():
        tags.add("ollama_configured")
    return tags


def _probe_ollama() -> bool:
    base = (executor_settings.ollama_base_url or "http://127.0.0.1:11434").rstrip("/")
    try:
        with httpx.Client(timeout=_PROBE_TIMEOUT) as client:
            r = client.get(f"{base}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


def _probe_spotify_auth() -> bool:
    if not _token_file_present("spotify"):
        return False
    if not _env_present("Spotify_Client_ID", "SPOTIFY_CLIENT_ID"):
        return False
    return True


def _collect_service_tags(base_tags: set[str]) -> set[str]:
    tags = set(base_tags)
    if "spotify_credentials" in tags or "spotify_auth" in tags:
        if _probe_spotify_auth():
            tags.add("spotify_auth")
        elif "spotify_auth" in tags:
            tags.discard("spotify_auth")
    if "ollama_configured" in tags and _probe_ollama():
        tags.add("ollama")
    if "gemini_api" in tags:
        tags.add("gemini_api")
    if "youtube_api" in tags:
        tags.add("youtube_api")
    if "google_credentials" in tags or "google_auth" in tags:
        if _token_file_present("google_classroom"):
            tags.add("google_auth")
    return tags


def _read_registry_display_names() -> list[str]:
    if platform.system() != "Windows":
        return []
    try:
        import winreg
    except ImportError:
        return []

    names: list[str] = []
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, subkey in roots:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        child_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, child_name) as app_key:
                            try:
                                display, _ = winreg.QueryValueEx(app_key, "DisplayName")
                                if display and isinstance(display, str):
                                    names.append(display.strip())
                            except OSError:
                                pass
                    except OSError:
                        continue
        except OSError:
            continue
    return names


def _scan_start_menu_shortcuts() -> list[str]:
    if platform.system() != "Windows":
        return []
    names: list[str] = []
    roots = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for path in root.rglob("*.lnk"):
                names.append(path.stem.strip())
        except OSError:
            continue
    return names


def _normalize_app_name(name: str) -> str:
    n = name.strip().lower()
    for suffix in (" (x64)", " (x86)", " 64-bit", " 32-bit"):
        if n.endswith(suffix):
            n = n[: -len(suffix)].strip()
    return n


def _well_known_apps() -> list[str]:
    return [
        "spotify",
        "chrome",
        "google chrome",
        "cursor",
        "arc",
        "notion",
        "edge",
        "firefox",
        "code",
        "vscode",
        "visual studio code",
        "slack",
        "discord",
        "antigravity",
        "obs",
    ]


def discover_installed_apps(force: bool = False) -> list[str]:
    global _app_scan_cache
    now = time.monotonic()
    cached_at, cached = _app_scan_cache
    if not force and cached and (now - cached_at) < _APP_SCAN_TTL_SECONDS:
        return list(cached)

    seen: set[str] = set()
    ordered: list[str] = []

    def add(name: str) -> None:
        key = _normalize_app_name(name)
        if not key or len(key) < 2 or key in seen:
            return
        seen.add(key)
        ordered.append(key)

    for app in _well_known_apps():
        add(app)
    for name in _read_registry_display_names():
        add(name)
    for name in _scan_start_menu_shortcuts():
        add(name)

    _app_scan_cache = (now, ordered)
    return list(ordered)


def _tool_available(tool: ToolDefinition, tags: set[str]) -> tuple[bool, str | None]:
    if not tool.requires:
        return True, None
    missing = [r for r in tool.requires if r not in tags]
    if missing:
        return False, f"Missing capabilities: {', '.join(missing)}"
    return True, None


def discover_capability_tags(force: bool = False) -> set[str]:
    global _tag_cache
    now = time.monotonic()
    cached_at, cached = _tag_cache
    if not force and cached and (now - cached_at) < _APP_SCAN_TTL_SECONDS:
        return set(cached)

    base = _scan_env_tags()
    tags = _collect_service_tags(base)
    _tag_cache = (now, tags)
    return tags


def build_tool_catalog(force: bool = False) -> ToolCatalog:
    tags = discover_capability_tags(force=force)
    apps = discover_installed_apps(force=force)
    capabilities: list[ToolCapability] = []
    for tool in TOOLS:
        available, reason = _tool_available(tool, tags)
        capabilities.append(
            ToolCapability(tool=tool, available=available, reason=reason),
        )
    return ToolCatalog(
        capabilities=capabilities,
        discovered_apps=apps,
        capability_tags=sorted(tags),
        refreshed_at=datetime.now(timezone.utc),
    )

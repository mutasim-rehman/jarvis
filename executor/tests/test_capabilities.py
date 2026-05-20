import os
from unittest.mock import patch

import pytest

from executor.app.capabilities.discovery import (
    _scan_env_tags,
    _tool_available,
    build_tool_catalog,
    discover_installed_apps,
)
from executor.app.capabilities.registry import TOOLS


def test_registry_has_core_tools():
    names = {t.name for t in TOOLS}
    assert "OPEN_APP" in names
    assert "PLAY_MUSIC" in names
    assert "DO_ASSIGNMENT" in names


def test_env_scan_smtp_credentials(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "user@test.com")
    monkeypatch.setenv("SMTP_PASS", "secret")
    tags = _scan_env_tags()
    assert "smtp_credentials" in tags


def test_send_email_tool_requires_smtp():
    from executor.app.capabilities.discovery import _tool_available
    from executor.app.capabilities.registry import TOOLS

    tool = next(t for t in TOOLS if t.name == "SEND_EMAIL")
    ok, _ = _tool_available(tool, {"smtp"})
    assert ok is True
    ok2, reason2 = _tool_available(tool, set())
    assert ok2 is False
    assert "smtp" in (reason2 or "")


def test_env_scan_spotify_credentials(monkeypatch):
    monkeypatch.setenv("Spotify_Client_ID", "test-id")
    tags = _scan_env_tags()
    assert "spotify_credentials" in tags


def test_play_music_requires_spotify_auth():
    tool = next(t for t in TOOLS if t.name == "PLAY_MUSIC")
    ok, reason = _tool_available(tool, {"spotify_auth"})
    assert ok is True
    assert reason is None
    ok2, reason2 = _tool_available(tool, set())
    assert ok2 is False
    assert "spotify_auth" in (reason2 or "")


def test_build_tool_catalog_structure():
    catalog = build_tool_catalog(force=True)
    assert catalog.capabilities
    assert catalog.refreshed_at is not None
    assert isinstance(catalog.discovered_apps, list)
    assert isinstance(catalog.capability_tags, list)


@patch("executor.app.capabilities.discovery._read_registry_display_names", return_value=["Spotify", "Google Chrome"])
@patch("executor.app.capabilities.discovery._scan_start_menu_shortcuts", return_value=["Cursor"])
def test_discover_installed_apps_merges_sources(_menu, _reg):
    apps = discover_installed_apps(force=True)
    assert "spotify" in apps
    assert "cursor" in apps

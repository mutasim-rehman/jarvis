"""PLAY_MUSIC handler — Spotify URI construction (shell open is mocked)."""

import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from executor.app.handlers import music as music_mod
from executor.app.context import HandlerContext
from shared.schema import Task


@pytest.fixture
def ctx(tmp_path):
    return HandlerContext(path_roots=[tmp_path], apps={}, url_aliases={})


def test_play_music_liked_when_no_target(ctx, monkeypatch):
    opened = []

    def fake(uri: str) -> bool:
        opened.append(uri)
        return True

    monkeypatch.setattr(music_mod, "_open_spotify_uri", fake)
    monkeypatch.setattr(music_mod, "_resume_after_spotify_open", lambda **_: None)
    r = music_mod.handle_play_music(Task(action="PLAY_MUSIC", target=None), ctx)
    assert r.success is True
    assert opened == [music_mod.SPOTIFY_LIKED_URI]
    assert "Liked Songs" in r.message


def test_play_music_search_when_target(ctx, monkeypatch):
    opened = []

    def fake(uri: str) -> bool:
        opened.append(uri)
        return True

    monkeypatch.setattr(music_mod, "_open_spotify_uri", fake)
    monkeypatch.setattr(music_mod, "_resume_after_spotify_open", lambda **_: None)
    r = music_mod.handle_play_music(Task(action="PLAY_MUSIC", target="Queen"), ctx)
    assert r.success is True
    assert opened[0].startswith("spotify:search:")
    assert "Queen" in r.message


def test_spotify_uri_mapping():
    u = music_mod._spotify_uri_label_click_xy
    assert u(None)[0] == music_mod.SPOTIFY_LIKED_URI
    assert u(None)[2] is False
    assert u("spotify")[0] == music_mod.SPOTIFY_LIKED_URI
    assert "search" in u("lo-fi jazz")[0]
    assert u("lo-fi jazz")[2] is True
    assert u("lo-fi jazz")[5] == "generic"

    artist_uri, label, is_s, x, y, layout = u("artist:strings")
    assert is_s is True
    assert layout == "artist"
    assert "artist%3A" not in artist_uri
    assert "strings" in artist_uri
    assert (x, y) == music_mod.CLICK_ARTISTS_FIRST

    track_uri, _, _, x2, y2, layout2 = u("track:duur")
    assert layout2 == "track"
    assert "track%3A" not in track_uri
    assert "duur" in track_uri
    assert (x2, y2) == music_mod.CLICK_SEARCH_FIRST

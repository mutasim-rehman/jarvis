"""Spotify playback via the Web API — no mouse, no clicks, no coordinates.

Flow:
  1. Resolve query → search for track/artist/album URI  (GET /search)
  2. Ensure Spotify desktop is open and an active device exists
  3. Start playback  (PUT /me/player/play)

Falls back gracefully: if no active device is found, opens the Spotify app and
retries once after a short wait.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from urllib.parse import quote

import httpx

from shared.schema import Task, TaskResult
from executor.app.context import HandlerContext
from executor.app.auth.spotify import get_access_token

_API = "https://api.spotify.com/v1"

_NON_QUERY_APPS = frozenset({
    "spotify", "spotify.exe", "apple music", "youtube music", "yt music",
})

# Liked Songs collection URI — works directly without search
SPOTIFY_LIKED_URI = "spotify:collection:tracks"


# ---------------------------------------------------------------------------
# Spotify Web API helpers
# ---------------------------------------------------------------------------

def _headers() -> dict[str, str]:
    token = get_access_token()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _get_devices(client: httpx.Client) -> list[dict]:
    """Return all available Spotify devices."""
    resp = client.get(f"{_API}/me/player/devices", headers=_headers())
    if resp.status_code != 200:
        print(f"[JARVIS Spotify] /devices returned HTTP {resp.status_code}: {resp.text[:200]}")
        return []
    return resp.json().get("devices", [])


def _get_active_device(client: httpx.Client) -> str | None:
    """Return the device_id of the currently active (or any available) Spotify device."""
    devices = _get_devices(client)
    if devices:
        print(f"[JARVIS Spotify] Found {len(devices)} device(s): {[d.get('name') for d in devices]}")
    # Prefer the currently active one
    for d in devices:
        if d.get("is_active"):
            return d["id"]
    # Otherwise use any available device and transfer playback to it
    if devices:
        return devices[0]["id"]
    return None


def _open_spotify_app() -> None:
    """Launch the Spotify desktop app (no UI interaction)."""
    if sys.platform == "win32":
        import ctypes
        from executor.app.handlers.apps import _windows_well_known_exe, _windows_shell_open_no_ui
        well_known = _windows_well_known_exe("spotify")
        if well_known:
            try:
                os.startfile(str(well_known))  # type: ignore[attr-defined]
                return
            except OSError:
                pass
        _windows_shell_open_no_ui("spotify:")
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-a", "Spotify"], close_fds=True)
    else:
        subprocess.Popen(["spotify"], close_fds=True)


def _wait_for_device(client: httpx.Client, retries: int = 20, delay: float = 3.0) -> str | None:
    """Poll for up to ~60 s until Spotify registers a device with its servers."""
    for attempt in range(1, retries + 1):
        device_id = _get_active_device(client)
        if device_id:
            print(f"[JARVIS Spotify] Device found on attempt {attempt}.")
            return device_id
        print(f"[JARVIS Spotify] Waiting for Spotify device… ({attempt}/{retries})")
        time.sleep(delay)
    return None


def _search(client: httpx.Client, query: str, kind: str) -> str | None:
    """
    Search Spotify and return the best-match URI.
    kind: 'track' | 'artist' | 'album' | 'generic'
    For 'generic', tries track first, then artist.
    """
    search_types = {
        "track":   "track",
        "artist":  "artist",
        "album":   "album",
        "generic": "track,artist",
    }
    q_type = search_types.get(kind, "track,artist")

    resp = client.get(
        f"{_API}/search",
        headers=_headers(),
        params={"q": query, "type": q_type, "limit": 1},
    )
    if resp.status_code != 200:
        return None

    data = resp.json()

    # Track
    tracks = data.get("tracks", {}).get("items", [])
    if kind in ("track", "generic") and tracks:
        return tracks[0]["uri"]

    # Artist
    artists = data.get("artists", {}).get("items", [])
    if kind in ("artist", "generic") and artists:
        return artists[0]["uri"]

    # Album
    albums = data.get("albums", {}).get("items", [])
    if kind == "album" and albums:
        return albums[0]["uri"]

    return None


def _play(client: httpx.Client, device_id: str, context_uri: str | None, track_uri: str | None) -> bool:
    """
    Start playback on the given device.
    - context_uri: for playlists, albums, artists, collections
    - track_uri:   for a single track (uses 'uris' instead of 'context_uri')
    """
    body: dict = {"device_id": device_id}
    if context_uri:
        body["context_uri"] = context_uri
    elif track_uri:
        body["uris"] = [track_uri]

    resp = client.put(f"{_API}/me/player/play", headers=_headers(), json=body)
    return resp.status_code in (200, 204)


# ---------------------------------------------------------------------------
# Query resolver
# ---------------------------------------------------------------------------

def _resolve_query(raw: str) -> tuple[str, str, str]:
    """
    Parse the task target and return (query, kind, label).
    kind: 'liked' | 'artist' | 'track' | 'album' | 'generic'
    """
    raw = (raw or "").strip()
    if not raw or raw.lower() in _NON_QUERY_APPS:
        return ("", "liked", "Liked Songs")

    m = re.match(r"^(artist|track|album):\s*(.+)$", raw, re.I)
    if m:
        kind = m.group(1).lower()
        q = re.sub(r"\s+", " ", m.group(2)).strip()
        return (q, kind, f"{kind.title()}: {q}")

    q = re.sub(r"\s+", " ", raw).strip()
    return (q, "generic", f"Search: {q}")


# ---------------------------------------------------------------------------
# Public handler
# ---------------------------------------------------------------------------

def handle_play_music(task: Task, ctx: HandlerContext) -> TaskResult:
    del ctx

    query, kind, label = _resolve_query(task.target)

    try:
        with httpx.Client(timeout=15.0) as client:
            # 1. Get or wait for an active device
            device_id = _get_active_device(client)

            if not device_id:
                # Open Spotify and wait
                _open_spotify_app()
                print("[JARVIS] Waiting for Spotify to start…")
                device_id = _wait_for_device(client)

            if not device_id:
                return TaskResult(
                    action=task.action,
                    success=False,
                    error_code="NO_DEVICE",
                    message=(
                        "No active Spotify device found. "
                        "Please open Spotify and try again."
                    ),
                )

            # 2. Resolve what to play
            if kind == "liked":
                # Play Liked Songs collection
                success = _play(client, device_id, context_uri=SPOTIFY_LIKED_URI, track_uri=None)
                play_uri = SPOTIFY_LIKED_URI
            else:
                # Search for the track/artist/album
                uri = _search(client, query, kind)
                if not uri:
                    return TaskResult(
                        action=task.action,
                        success=False,
                        error_code="NOT_FOUND",
                        message=f"Could not find '{query}' on Spotify.",
                    )
                play_uri = uri
                # Tracks use 'uris', everything else uses 'context_uri'
                is_track = uri.startswith("spotify:track:")
                success = _play(
                    client, device_id,
                    context_uri=None if is_track else uri,
                    track_uri=uri if is_track else None,
                )

            if success:
                return TaskResult(
                    action=task.action,
                    success=True,
                    message=f"Now playing {label} on Spotify.",
                    artifacts={"spotify_uri": play_uri, "device_id": device_id, "label": label},
                )
            else:
                return TaskResult(
                    action=task.action,
                    success=False,
                    error_code="PLAYBACK_FAILED",
                    message=f"Spotify API rejected the play request for '{label}'.",
                )

    except Exception as e:
        return TaskResult(
            action=task.action,
            success=False,
            error_code="SPOTIFY_ERROR",
            message=str(e),
        )
"""Spotify playback via ``spotify:`` URIs (no Web API; uses the desktop protocol handler)."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import re
import subprocess
import sys
import time
from urllib.parse import quote

from shared.schema import Task, TaskResult

from executor.app.context import HandlerContext
from executor.app.handlers.apps import _windows_shell_open_no_ui

# Opens the user's Liked Songs in the Spotify app.
SPOTIFY_LIKED_URI = "spotify:collection:tracks"

_NON_QUERY_APPS = frozenset(
    {
        "spotify",
        "spotify.exe",
        "apple music",
        "youtube music",
        "yt music",
    }
)

VK_RETURN = 0x0D
VK_DOWN = 0x28
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_EXTENDEDKEY = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

# ---------------------------------------------------------------------------
# Click-coordinate constants
# ---------------------------------------------------------------------------
# Tuning history:
#   0.44  → landed on row ~6  (too low, below Top Result card)
#   0.22  → landed on row  2
#   0.18  → landed on row  2  (still too low)
#   0.13  → targets  row  1   ← current
#
# If it still drifts, tune without redeploying via env vars:
#   EXECUTOR_SPOTIFY_CLICK_X=0.14
#   EXECUTOR_SPOTIFY_CLICK_Y=0.13
#
# Each ~0.02 step in Y moves roughly one row up or down.

CLICK_ARTISTS_FIRST = (0.14, 0.13)   # raised from 0.22 → targets row 1
CLICK_SEARCH_FIRST  = CLICK_ARTISTS_FIRST

_DEFAULT_CLICK_X = CLICK_SEARCH_FIRST[0]
_CLICK_Y = {
    "artist":  CLICK_SEARCH_FIRST[1],
    "track":   CLICK_SEARCH_FIRST[1],
    "album":   CLICK_SEARCH_FIRST[1],
    "generic": CLICK_SEARCH_FIRST[1],
}


def _env_click_frac(var: str, default: float) -> float:
    raw = os.environ.get(var, "").strip()
    if not raw:
        return default
    try:
        v = float(raw)
        return min(max(v, 0.05), 0.95)
    except ValueError:
        return default


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left",   ctypes.c_long),
        ("top",    ctypes.c_long),
        ("right",  ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


# ---------------------------------------------------------------------------
# Low-level Windows helpers
# ---------------------------------------------------------------------------

def _win_send_extended_media(vk: int) -> None:
    u = ctypes.windll.user32
    u.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY, 0)
    u.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)


def _win_send_media_stop() -> None:
    """Stop current playback so we are not stuck on 'resume last session' / old queue."""
    VK_MEDIA_STOP = 0xB2
    _win_send_extended_media(VK_MEDIA_STOP)


def _win_send_media_play_pause() -> None:
    """Global media key — good for Liked Songs / continuing the current queue."""
    VK_MEDIA_PLAY_PAUSE = 0xB3
    _win_send_extended_media(VK_MEDIA_PLAY_PAUSE)


def _win_key_tap(vk: int) -> None:
    u = ctypes.windll.user32
    u.keybd_event(vk, 0, 0, 0)
    u.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def _win_find_spotify_hwnd() -> int | None:
    """First visible top-level window whose title contains 'Spotify' (Electron main window)."""
    user32 = ctypes.windll.user32
    found: list[wintypes.HWND] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n == 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        if "spotify" in buf.value.lower():
            found.append(hwnd)
        return True

    user32.EnumWindows(_cb, 0)
    return int(found[0]) if found else None


def _win_try_activate_spotify_window() -> None:
    user32 = ctypes.windll.user32
    hwnd = _win_find_spotify_hwnd()
    if hwnd:
        user32.SetForegroundWindow(hwnd)


def _win_screen_double_click(x: int, y: int) -> None:
    """Double left-click at absolute screen coordinates."""
    user32 = ctypes.windll.user32

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    old = POINT()
    user32.GetCursorPos(ctypes.byref(old))
    try:
        user32.SetCursorPos(int(x), int(y))
        time.sleep(0.04)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_LEFTUP,   0, 0, 0, 0)
        time.sleep(0.07)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_LEFTUP,   0, 0, 0, 0)
    finally:
        user32.SetCursorPos(old.x, old.y)


def _win_double_click_first_search_result(hwnd: int, x_fraction: float, y_fraction: float) -> None:
    """
    Double-click at (x_fraction, y_fraction) of the **client** rect.
    Fractions are clamped so we never hit the window chrome or below content.
    """
    user32 = ctypes.windll.user32
    rc = _RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rc)):
        return
    w = rc.right  - rc.left
    h = rc.bottom - rc.top
    if w < 80 or h < 80:
        return

    xf = min(max(x_fraction, 0.08), 0.92)
    yf = min(max(y_fraction, 0.10), 0.72)  # floor lowered to allow row-1 targeting
    cx = int(w * xf)
    cy = min(max(int(h * yf), 80), h - 40)

    pt = wintypes.POINT(cx, cy)
    if not user32.ClientToScreen(hwnd, ctypes.byref(pt)):
        return
    _win_screen_double_click(pt.x, pt.y)


# ---------------------------------------------------------------------------
# Resume helpers — per platform
# ---------------------------------------------------------------------------

def _resume_spotify_liked() -> None:
    """Liked Songs / empty query: media play/pause toggles the Liked queue."""
    if sys.platform == "win32":
        time.sleep(0.65)
        _win_try_activate_spotify_window()
        time.sleep(0.35)
        _win_send_media_play_pause()
        return
    if sys.platform == "darwin":
        time.sleep(0.5)
        subprocess.run(
            ["osascript", "-e", 'tell application "Spotify" to play'],
            capture_output=True,
            timeout=15,
            check=False,
        )
        return
    time.sleep(0.4)
    subprocess.run(["playerctl", "-p", "spotify", "play"], capture_output=True, timeout=10, check=False)
    subprocess.run(["playerctl", "play"],                  capture_output=True, timeout=10, check=False)


def _resume_spotify_search_win(x_fraction: float, y_fraction: float, _search_layout: str) -> None:
    """
    Spotify plays a track on **double-click** (Enter / media keys do not work reliably on search).
    Do NOT send Home — it can scroll the Artists strip and shift the click target down.
    """
    time.sleep(1.35)
    _win_try_activate_spotify_window()
    time.sleep(0.45)

    # Stop any resumed session so we hear the new track, not the old queue.
    _win_send_media_stop()
    time.sleep(0.35)
    _win_send_media_stop()
    time.sleep(0.35)

    hwnd = _win_find_spotify_hwnd()
    if hwnd:
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        time.sleep(0.15)
        xf = _env_click_frac("EXECUTOR_SPOTIFY_CLICK_X", x_fraction)
        yf = _env_click_frac("EXECUTOR_SPOTIFY_CLICK_Y", y_fraction)
        _win_double_click_first_search_result(hwnd, xf, yf)
    else:
        # Fallback: keyboard navigation
        _win_key_tap(VK_DOWN)
        time.sleep(0.15)
        _win_key_tap(VK_DOWN)
        time.sleep(0.18)
        _win_key_tap(VK_RETURN)
        time.sleep(0.12)
        _win_key_tap(VK_RETURN)


def _resume_spotify_search_darwin(x_fraction: float, y_fraction: float, _search_layout: str) -> None:
    time.sleep(1.0)
    script = f"""
    tell application "Spotify" to activate
    delay 0.55
    tell application "Spotify" to pause
    delay 0.4
    tell application "System Events" to tell process "Spotify"
        set frontmost to true
        set win to window 1
        set p to position of win
        set s to size of win
        set cx to (item 1 of p) + (item 1 of s) * {x_fraction}
        set cy to (item 2 of p) + (item 2 of s) * {y_fraction}
        click at {{cx, cy}}
        delay 0.08
        click at {{cx, cy}}
    end tell
    """
    subprocess.run(["osascript", "-e", script], capture_output=True, timeout=25, check=False)


def _resume_spotify_search_linux() -> None:
    time.sleep(1.0)
    subprocess.run(["playerctl", "-p", "spotify", "play"], capture_output=True, timeout=10, check=False)


def _resume_spotify_search(x_fraction: float, y_fraction: float, search_layout: str) -> None:
    if sys.platform == "win32":
        _resume_spotify_search_win(x_fraction, y_fraction, search_layout)
    elif sys.platform == "darwin":
        _resume_spotify_search_darwin(x_fraction, y_fraction, search_layout)
    else:
        _resume_spotify_search_linux()


def _resume_after_spotify_open(
    *,
    is_search: bool,
    click_x_fraction: float = _DEFAULT_CLICK_X,
    click_y_fraction: float = _CLICK_Y["generic"],
    search_layout: str = "generic",
) -> None:
    if is_search:
        _resume_spotify_search(click_x_fraction, click_y_fraction, search_layout)
    else:
        _resume_spotify_liked()


# ---------------------------------------------------------------------------
# URI + click-target builder
# ---------------------------------------------------------------------------

def _open_spotify_uri(uri: str) -> bool:
    if sys.platform == "win32":
        return _windows_shell_open_no_ui(uri)
    if sys.platform == "darwin":
        subprocess.Popen(["open", uri], close_fds=True)
        return True
    subprocess.Popen(["xdg-open", uri], close_fds=True)
    return True


def _spotify_uri_label_click_xy(
    target: str | None,
) -> tuple[str, str, bool, float, float, str]:
    """
    Map *target* → (uri, label, is_search, click_x, click_y, search_layout).

    search_layout: ``artist`` | ``track`` | ``album`` | ``generic``
    """
    raw = (target or "").strip()
    if not raw or raw.lower() in _NON_QUERY_APPS:
        return SPOTIFY_LIKED_URI, "Liked Songs", False, _DEFAULT_CLICK_X, _CLICK_Y["generic"], "generic"

    m = re.match(r"^(artist|track|album):\s*(.+)$", raw, re.I)
    if m:
        kind = m.group(1).lower()
        q    = re.sub(r"\s+", " ", m.group(2).strip())
        if not q:
            return SPOTIFY_LIKED_URI, "Liked Songs", False, _DEFAULT_CLICK_X, _CLICK_Y["generic"], "generic"
        uri   = f"spotify:search:{quote(q, safe='')}"
        label = f"Search ({kind}): {q}"
        x, y  = CLICK_SEARCH_FIRST
        return uri, label, True, x, y, kind

    # Generic free-text search — same click point
    q   = re.sub(r"\s+", " ", raw).strip()
    uri = f"spotify:search:{quote(q, safe='')}"
    sx, sy = CLICK_SEARCH_FIRST
    return uri, f"Search: {q}", True, sx, sy, "generic"


# ---------------------------------------------------------------------------
# Public handler
# ---------------------------------------------------------------------------

def handle_play_music(task: Task, ctx: HandlerContext) -> TaskResult:
    del ctx  # no allowlist needed for URI open
    uri, label, is_search, click_x, click_y, search_layout = _spotify_uri_label_click_xy(task.target)
    try:
        if not _open_spotify_uri(uri):
            return TaskResult(
                action=task.action,
                success=False,
                error_code="START_FAILED",
                message="Could not hand off to Spotify (shell open failed).",
            )
        _resume_after_spotify_open(
            is_search=is_search,
            click_x_fraction=click_x,
            click_y_fraction=click_y,
            search_layout=search_layout,
        )
        if is_search:
            msg = (
                f"Opened Spotify — {label}. "
                "Stopped playback, then double-clicked first search result (row 1)."
            )
        else:
            msg = f"Opened Spotify — {label}. Signaled play (media key / Spotify play)."
        return TaskResult(
            action=task.action,
            success=True,
            message=msg,
            artifacts={
                "spotify_uri":      uri,
                "label":            label,
                "is_search":        is_search,
                "search_layout":    search_layout,
                "click_x_fraction": click_x,
                "click_y_fraction": click_y,
            },
        )
    except OSError as e:
        return TaskResult(
            action=task.action,
            success=False,
            error_code="START_FAILED",
            message=str(e),
        )
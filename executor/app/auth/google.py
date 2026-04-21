"""Google OAuth2 (Desktop app) for Classroom API.

Uses GCR_CREDENTIALS_JSON from .env (the full JSON from Google Cloud Console).
Stores token in ~/.jarvis/google_classroom_token.json.
Opens the browser once; auto-refreshes thereafter.

Required scopes:
    https://www.googleapis.com/auth/classroom.courses.readonly
    https://www.googleapis.com/auth/classroom.coursework.me.readonly
    https://www.googleapis.com/auth/classroom.student-submissions.me.readonly
"""
from __future__ import annotations

# Load .env into os.environ so os.environ.get() can find our vars.
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(override=False)
except ImportError:
    pass

import json
import os
import time
from pathlib import Path
from typing import Optional

import httpx

from executor.app.auth.token_store import clear_token, load_token, save_token

_SERVICE = "google_classroom"
_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

CLASSROOM_SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
]


def _creds() -> dict:
    raw = os.environ.get("GCR_CREDENTIALS_JSON", "").strip()
    if not raw:
        raise RuntimeError("GCR_CREDENTIALS_JSON not set in .env")
    data = json.loads(raw)
    # Support both {"installed": {...}} and flat format
    return data.get("installed", data)


def _client_id() -> str:
    return _creds()["client_id"]


def _client_secret() -> str:
    return _creds()["client_secret"]


def _redirect_uri() -> str:
    """Always use 127.0.0.1:8889 for the local callback — avoids port-80 admin issues."""
    return os.environ.get("GCR_REDIRECT_URI", "http://127.0.0.1:8889/callback").strip()


# ---------------------------------------------------------------------------
# Auth code flow with local callback server
# ---------------------------------------------------------------------------

def _run_auth_flow(scopes: list[str]) -> dict:
    """Run OAuth2 authorization code flow with a local callback server."""
    import http.server
    import secrets
    import threading
    import urllib.parse
    import webbrowser

    redirect = _redirect_uri()
    parsed = urllib.parse.urlparse(redirect)
    port = parsed.port or 80

    state = secrets.token_urlsafe(16)

    params = {
        "client_id": _client_id(),
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state,
        "access_type": "offline",
        "prompt": "consent",  # ensures refresh_token is always returned
    }
    auth_url = f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"

    captured: dict[str, Optional[str]] = {"code": None, "error": None}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            captured["code"] = qs.get("code", [None])[0]
            captured["error"] = qs.get("error", [None])[0]
            body = b"<h2>JARVIS: Google authorization received. You can close this tab.</h2>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = http.server.HTTPServer(("127.0.0.1", port), _Handler)

    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    print(f"\n[JARVIS Google] Opening browser for Classroom authorization…\n{auth_url}\n")
    webbrowser.open(auth_url)

    deadline = time.time() + 120
    while time.time() < deadline:
        if captured["code"] or captured["error"]:
            break
        time.sleep(0.25)
    server.server_close()

    if captured["error"]:
        raise RuntimeError(f"Google auth denied: {captured['error']}")
    if not captured["code"]:
        raise RuntimeError("Google auth timed out.")

    token_data = {
        "code": captured["code"],
        "client_id": _client_id(),
        "client_secret": _client_secret(),
        "redirect_uri": redirect,
        "grant_type": "authorization_code",
    }
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(_TOKEN_URL, data=token_data)
        resp.raise_for_status()
        tokens: dict = resp.json()

    tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
    save_token(_SERVICE, tokens)
    return tokens


def _refresh(refresh_token: str) -> dict:
    data = {
        "client_id": _client_id(),
        "client_secret": _client_secret(),
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(_TOKEN_URL, data=data)
        resp.raise_for_status()
        tokens: dict = resp.json()

    if "refresh_token" not in tokens:
        tokens["refresh_token"] = refresh_token
    tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
    save_token(_SERVICE, tokens)
    return tokens


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_access_token(scopes: list[str] = CLASSROOM_SCOPES) -> str:
    """Return valid Google access token for Classroom API."""
    stored = load_token(_SERVICE)

    if stored.get("access_token"):
        if time.time() < stored.get("expires_at", 0) - 60:
            return stored["access_token"]
        rt = stored.get("refresh_token")
        if rt:
            try:
                return _refresh(rt)["access_token"]
            except Exception:
                clear_token(_SERVICE)

    return _run_auth_flow(scopes)["access_token"]


def revoke() -> None:
    clear_token(_SERVICE)

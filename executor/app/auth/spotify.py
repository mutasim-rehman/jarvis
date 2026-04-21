"""Spotify PKCE OAuth with a local callback server.

First call to ``get_access_token()`` opens the browser once for the user to
grant permission.  The callback is caught by a tiny localhost HTTP server.
All subsequent calls silently refresh via the stored refresh_token.

Env vars (from .env):
    Spotify_Client_ID
    Spotify_Client_Secret   (used only for token refresh — NOT sent in PKCE auth request)
    Spotify_Redirect_URI    (optional override, default: http://127.0.0.1:8888/callback)
"""
from __future__ import annotations

# Load .env into os.environ so os.environ.get() can find our vars.
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(override=False)  # override=False keeps any already-set shell vars
except ImportError:
    pass  # python-dotenv not installed; rely on vars being set in the shell

import base64
import hashlib
import http.server
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser
from typing import Optional

import httpx

from executor.app.auth.token_store import clear_token, load_token, save_token

_SERVICE = "spotify"
_AUTH_URL = "https://accounts.spotify.com/authorize"
_TOKEN_URL = "https://accounts.spotify.com/api/token"

_DEFAULT_SCOPES = " ".join([
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "app-remote-control",
    "streaming",
    "playlist-read-private",
    "user-library-read",
])


def _client_id() -> str:
    v = os.environ.get("Spotify_Client_ID", "").strip()
    if not v:
        raise RuntimeError("Spotify_Client_ID not set in .env")
    return v


def _client_secret() -> str:
    return os.environ.get("Spotify_Client_Secret", "").strip()


def _redirect_uri() -> str:
    return os.environ.get("Spotify_Redirect_URI", "http://127.0.0.1:8888/callback").strip()


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------

def _pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


# ---------------------------------------------------------------------------
# One-shot local HTTP server to capture the authorization code
# ---------------------------------------------------------------------------

class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    code: Optional[str] = None
    error: Optional[str] = None

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        _CallbackHandler.code = qs.get("code", [None])[0]
        _CallbackHandler.error = qs.get("error", [None])[0]
        body = b"<h2>JARVIS: Authorization received. You can close this tab.</h2>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):  # suppress request logs
        pass


def _run_pkce_flow(scopes: str) -> dict:
    """Open browser, wait for callback, exchange code for tokens. Returns token dict."""
    redirect = _redirect_uri()
    parsed = urllib.parse.urlparse(redirect)
    port = parsed.port or 8888

    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(16)

    params = {
        "client_id": _client_id(),
        "response_type": "code",
        "redirect_uri": redirect,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "state": state,
        "scope": scopes,
    }
    auth_url = f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"

    # Reset captured values
    _CallbackHandler.code = None
    _CallbackHandler.error = None

    # Start local server in background thread
    server = http.server.HTTPServer(("127.0.0.1", port), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    print(f"\n[JARVIS Spotify] Opening browser for authorization…\n{auth_url}\n")
    webbrowser.open(auth_url)

    # Wait up to 120 s for the callback
    deadline = time.time() + 120
    while time.time() < deadline:
        if _CallbackHandler.code or _CallbackHandler.error:
            break
        time.sleep(0.25)

    server.server_close()

    if _CallbackHandler.error:
        raise RuntimeError(f"Spotify auth denied: {_CallbackHandler.error}")
    if not _CallbackHandler.code:
        raise RuntimeError("Spotify auth timed out — no code received within 120 s.")

    # Exchange code for tokens
    token_data = {
        "grant_type": "authorization_code",
        "code": _CallbackHandler.code,
        "redirect_uri": redirect,
        "client_id": _client_id(),
        "code_verifier": verifier,
    }
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(_TOKEN_URL, data=token_data)
        resp.raise_for_status()
        tokens: dict = resp.json()

    tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
    save_token(_SERVICE, tokens)
    return tokens


def _refresh_tokens(refresh_token: str) -> dict:
    """Use the refresh_token to get a new access_token."""
    data: dict = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": _client_id(),
    }
    # If client_secret is available, use Basic auth (more compatible)
    secret = _client_secret()
    headers = {}
    if secret:
        creds = base64.b64encode(f"{_client_id()}:{secret}".encode()).decode()
        headers["Authorization"] = f"Basic {creds}"

    with httpx.Client(timeout=15.0) as client:
        resp = client.post(_TOKEN_URL, data=data, headers=headers)
        resp.raise_for_status()
        tokens: dict = resp.json()

    if "refresh_token" not in tokens:
        tokens["refresh_token"] = refresh_token  # preserve old one
    tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
    save_token(_SERVICE, tokens)
    return tokens


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_access_token(scopes: str = _DEFAULT_SCOPES) -> str:
    """Return a valid Spotify access token, refreshing or re-authorizing as needed."""
    stored = load_token(_SERVICE)

    if stored.get("access_token"):
        expires_at = stored.get("expires_at", 0)
        if time.time() < expires_at - 60:  # 60 s buffer
            return stored["access_token"]

        # Try refresh
        refresh_token = stored.get("refresh_token")
        if refresh_token:
            try:
                tokens = _refresh_tokens(refresh_token)
                return tokens["access_token"]
            except Exception:
                clear_token(_SERVICE)

    # Full PKCE flow
    tokens = _run_pkce_flow(scopes)
    return tokens["access_token"]


def revoke() -> None:
    """Clear stored tokens — next call will re-authorize."""
    clear_token(_SERVICE)

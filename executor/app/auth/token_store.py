"""Token persistence — read/write ~/.jarvis/<service>_token.json."""
from __future__ import annotations

import json
from pathlib import Path


def _token_dir() -> Path:
    d = Path.home() / ".jarvis"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_token(service: str) -> dict:
    p = _token_dir() / f"{service}_token.json"
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_token(service: str, data: dict) -> None:
    p = _token_dir() / f"{service}_token.json"
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def clear_token(service: str) -> None:
    p = _token_dir() / f"{service}_token.json"
    if p.is_file():
        p.unlink()

"""Verify Supabase-issued JWT access tokens."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import jwt

from backend.app.config import settings


@dataclass(frozen=True)
class SupabaseTokenClaims:
    sub: uuid.UUID
    email: str | None = None
    role: str | None = None


def verify_supabase_access_token(token: str) -> SupabaseTokenClaims:
    secret = settings.resolved_supabase_jwt_secret()
    if not secret:
        raise ValueError("SUPABASE_JWT_SECRET is not configured")
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"require": ["sub", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc
    sub_raw = payload.get("sub")
    if not sub_raw:
        raise ValueError("Token missing sub claim")
    try:
        sub = uuid.UUID(str(sub_raw))
    except ValueError as exc:
        raise ValueError("Invalid sub in token") from exc
    email = payload.get("email")
    if email is not None:
        email = str(email)
    role = payload.get("role")
    if role is not None:
        role = str(role)
    return SupabaseTokenClaims(sub=sub, email=email, role=role)

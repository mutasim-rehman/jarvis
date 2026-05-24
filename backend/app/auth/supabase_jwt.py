"""Verify Supabase-issued JWT access tokens."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

import httpx
import jwt

from backend.app.config import settings

logger = logging.getLogger(__name__)


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


def user_from_supabase_auth_api(token: str) -> SupabaseTokenClaims | None:
    """Validate access token via Supabase Auth API (works when local JWT secret mismatches)."""
    base = settings.resolved_supabase_url()
    anon = (settings.supabase_anon_key or "").strip()
    if not base or not anon:
        return None
    url = f"{base}/auth/v1/user"
    try:
        response = httpx.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": anon,
            },
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("Supabase auth user lookup failed: %s", exc)
        return None
    if response.status_code != 200:
        logger.warning("Supabase auth user lookup status=%s", response.status_code)
        return None
    data = response.json()
    user = data.get("user") if isinstance(data, dict) else None
    if not isinstance(user, dict):
        user = data if isinstance(data, dict) else None
    if not user:
        return None
    try:
        sub = uuid.UUID(str(user.get("id")))
    except (ValueError, TypeError):
        return None
    email = user.get("email")
    return SupabaseTokenClaims(
        sub=sub,
        email=str(email) if email else None,
        role="authenticated",
    )


def delete_supabase_auth_user(user_id: uuid.UUID) -> bool:
    """Remove auth.users row via Admin API (requires SUPABASE_SERVICE_ROLE_KEY)."""
    base = settings.resolved_supabase_url()
    key = (settings.supabase_service_role_key or "").strip()
    if not base or not key:
        return False
    url = f"{base}/auth/v1/admin/users/{user_id}"
    try:
        response = httpx.delete(
            url,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
            },
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("Supabase admin user delete failed: %s", exc)
        return False
    if response.status_code not in (200, 204):
        logger.warning("Supabase admin user delete status=%s", response.status_code)
        return False
    return True

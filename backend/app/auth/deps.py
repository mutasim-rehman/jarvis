"""FastAPI auth dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from backend.app.config import settings
from backend.app.auth.supabase_jwt import (
    SupabaseTokenClaims,
    user_from_supabase_auth_api,
    verify_supabase_access_token,
)


@dataclass(frozen=True)
class AuthUser:
    user_id: uuid.UUID
    email: str | None = None


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def _user_from_bearer(authorization: str | None) -> AuthUser | None:
    token = _extract_bearer(authorization)
    if not token:
        return None

    if settings.resolved_supabase_jwt_secret():
        try:
            claims: SupabaseTokenClaims = verify_supabase_access_token(token)
            return AuthUser(user_id=claims.sub, email=claims.email)
        except ValueError:
            pass

    claims = user_from_supabase_auth_api(token)
    if claims is not None:
        return AuthUser(user_id=claims.sub, email=claims.email)
    return None


async def get_current_user_optional(
    authorization: str | None = Header(default=None),
) -> AuthUser | None:
    return _user_from_bearer(authorization)


async def get_current_user_required(
    user: AuthUser | None = Depends(get_current_user_optional),
) -> AuthUser:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def verify_api_auth(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias=settings.api_key_header),
) -> AuthUser | None:
    """
    Dual auth for legacy dev key + Supabase JWT.
    Returns AuthUser when JWT valid; None when auth disabled or no credentials.
  """
    user = _user_from_bearer(authorization)
    if user is not None:
        return user
    if settings.api_require_auth:
        if settings.api_dev_token and x_api_key == settings.api_dev_token:
            return None
        if settings.api_auth_mode == "required":
            raise HTTPException(status_code=401, detail="Unauthorized")
        raise HTTPException(status_code=401, detail="Unauthorized")
    return None

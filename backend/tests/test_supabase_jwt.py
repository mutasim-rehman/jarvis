"""JWT verification tests."""

import time
import uuid

import jwt
import pytest

from backend.app.auth.supabase_jwt import verify_supabase_access_token
from backend.app.config import settings


def test_verify_valid_token(monkeypatch):
    secret = "test-jwt-secret-for-unit-tests"
    monkeypatch.setattr(settings, "supabase_jwt_secret", secret)
    user_id = uuid.uuid4()
    token = jwt.encode(
        {
            "sub": str(user_id),
            "email": "user@example.com",
            "role": "authenticated",
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        },
        secret,
        algorithm="HS256",
    )
    claims = verify_supabase_access_token(token)
    assert claims.sub == user_id
    assert claims.email == "user@example.com"


def test_verify_expired_token(monkeypatch):
    secret = "test-jwt-secret-for-unit-tests"
    monkeypatch.setattr(settings, "supabase_jwt_secret", secret)
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "aud": "authenticated",
            "exp": int(time.time()) - 10,
        },
        secret,
        algorithm="HS256",
    )
    with pytest.raises(ValueError, match="Invalid token"):
        verify_supabase_access_token(token)

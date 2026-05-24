"""Auth dependency tests."""

from unittest.mock import MagicMock, patch
import uuid

from backend.app.auth.deps import _user_from_bearer
from backend.app.auth.supabase_jwt import SupabaseTokenClaims


def test_user_from_bearer_falls_back_to_supabase_api_when_jwt_invalid(monkeypatch):
    user_id = uuid.uuid4()
    monkeypatch.setattr("backend.app.auth.deps.settings.supabase_jwt_secret", "wrong-secret")
    monkeypatch.setattr(
        "backend.app.auth.deps.verify_supabase_access_token",
        MagicMock(side_effect=ValueError("bad jwt")),
    )
    monkeypatch.setattr(
        "backend.app.auth.deps.user_from_supabase_auth_api",
        lambda _token: SupabaseTokenClaims(sub=user_id, email="u@example.com", role="authenticated"),
    )

    user = _user_from_bearer("Bearer fake-token")
    assert user is not None
    assert user.user_id == user_id

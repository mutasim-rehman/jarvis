"""Build LLM preference context for authenticated users."""

from __future__ import annotations

import uuid
from shared.preferences import PreferenceSettingsV1, build_preference_context_text

from backend.app.db.repositories import get_preference_settings
from backend.app.db.session import database_configured, session_scope


def load_preference_context_for_user(user_id: uuid.UUID | None) -> str | None:
    if user_id is None or not database_configured():
        return None
    try:
        with session_scope() as session:
            settings = get_preference_settings(session, user_id)
        if not settings.onboarding_completed and settings.personality_profile_v1 is None:
            if settings.sliders == PreferenceSettingsV1().sliders:
                return None
        return build_preference_context_text(settings)
    except Exception:
        return None

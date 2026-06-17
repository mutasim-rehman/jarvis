"""Account data access with Postgres primary and Supabase REST fallback."""

from __future__ import annotations

import logging
import uuid

import httpx
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from shared.preferences import PreferenceSettingsV1

from . import supabase_rest
from .repositories import (
    ensure_profile_and_preferences,
    get_preference_settings,
    patch_preference_settings,
    register_device,
    set_personality_profile,
    update_profile,
)
from .models import Preference, Profile
from .session import session_scope

logger = logging.getLogger(__name__)


def _use_rest_fallback(exc: SQLAlchemyError) -> bool:
    if not supabase_rest.rest_api_available():
        return False
    logger.warning("Postgres account query failed; using Supabase REST fallback: %s", exc)
    return True


def _raise_account_store_error(exc: Exception) -> None:
    if isinstance(exc, httpx.HTTPStatusError):
        detail = exc.response.text[:300] if exc.response is not None else str(exc)
        raise HTTPException(
            status_code=503,
            detail=f"Account storage unavailable via Supabase REST: {detail}",
        ) from exc
    raise exc


def ensure_profile_and_preferences_for_user(user_id: uuid.UUID) -> tuple[Profile, Preference]:
    try:
        with session_scope() as session:
            return ensure_profile_and_preferences(session, user_id)
    except SQLAlchemyError as exc:
        if not _use_rest_fallback(exc):
            raise
        try:
            return supabase_rest.ensure_profile_and_preferences_rest(user_id)
        except Exception as rest_exc:
            _raise_account_store_error(rest_exc)


def _call_rest(call):
    try:
        return call()
    except Exception as rest_exc:
        _raise_account_store_error(rest_exc)


def patch_preference_settings_for_user(user_id: uuid.UUID, patch: dict) -> PreferenceSettingsV1:
    try:
        with session_scope() as session:
            return patch_preference_settings(session, user_id, patch)
    except SQLAlchemyError as exc:
        if not _use_rest_fallback(exc):
            raise
        return _call_rest(lambda: supabase_rest.patch_preference_settings_rest(user_id, patch))


def set_personality_profile_for_user(user_id: uuid.UUID, profile_dict: dict) -> PreferenceSettingsV1:
    try:
        with session_scope() as session:
            return set_personality_profile(session, user_id, profile_dict)
    except SQLAlchemyError as exc:
        if not _use_rest_fallback(exc):
            raise
        return _call_rest(lambda: supabase_rest.set_personality_profile_rest(user_id, profile_dict))


def register_device_for_user(
    user_id: uuid.UUID,
    device_id: uuid.UUID,
    device_type: str,
    label: str = "",
) -> PreferenceSettingsV1:
    try:
        with session_scope() as session:
            return register_device(session, user_id, device_id, device_type, label)
    except SQLAlchemyError as exc:
        if not _use_rest_fallback(exc):
            raise
        return _call_rest(
            lambda: supabase_rest.register_device_rest(user_id, device_id, device_type, label)
        )


def update_profile_for_user(
    user_id: uuid.UUID,
    *,
    display_name: str | None = None,
    avatar_url: str | None = None,
) -> Profile:
    try:
        with session_scope() as session:
            return update_profile(
                session,
                user_id,
                display_name=display_name,
                avatar_url=avatar_url,
            )
    except SQLAlchemyError as exc:
        if not _use_rest_fallback(exc):
            raise
        return _call_rest(
            lambda: supabase_rest.update_profile_rest(
                user_id,
                display_name=display_name,
                avatar_url=avatar_url,
            )
        )


def get_preference_settings_for_user(user_id: uuid.UUID) -> PreferenceSettingsV1:
    try:
        with session_scope() as session:
            return get_preference_settings(session, user_id)
    except SQLAlchemyError as exc:
        if not _use_rest_fallback(exc):
            raise
        return _call_rest(lambda: supabase_rest.get_preference_settings_rest(user_id))


def ensure_profile_and_preferences_session(
    session: Session,
    user_id: uuid.UUID,
) -> tuple[Profile, Preference]:
    """Use inside an existing SQLAlchemy session; no REST fallback."""
    return ensure_profile_and_preferences(session, user_id)

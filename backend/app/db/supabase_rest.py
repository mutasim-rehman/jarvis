"""Supabase PostgREST fallback when direct Postgres is unreachable (e.g. IPv4-only networks)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from backend.app.config import settings
from shared.preferences import PreferenceSettingsV1, RegisteredDeviceV1, merge_preference_settings

from .models import Preference, Profile

logger = logging.getLogger(__name__)


def rest_api_available() -> bool:
    return bool(
        settings.resolved_supabase_url().strip()
        and (settings.supabase_service_role_key or "").strip()
    )


def _headers() -> dict[str, str]:
    key = (settings.supabase_service_role_key or "").strip()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _base_url() -> str:
    return f"{settings.resolved_supabase_url().rstrip('/')}/rest/v1"


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _request(
    method: str,
    table: str,
    *,
    params: dict[str, str] | None = None,
    json_body: Any = None,
) -> httpx.Response:
    url = f"{_base_url()}/{table}"
    response = httpx.request(
        method,
        url,
        headers=_headers(),
        params=params,
        json=json_body,
        timeout=20.0,
    )
    if response.status_code >= 400:
        logger.warning(
            "Supabase REST %s %s failed status=%s body=%s",
            method,
            table,
            response.status_code,
            response.text[:300],
        )
    return response


def _create_profile_row(user_id: uuid.UUID) -> Profile:
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": str(user_id),
        "display_name": None,
        "avatar_url": None,
        "created_at": now,
    }
    response = _request("POST", "profiles", json_body=row)
    if response.status_code == 409:
        existing = _fetch_profile(user_id)
        if existing is not None:
            return existing
    if response.status_code >= 400:
        response.raise_for_status()
    created = response.json()
    return _profile_from_row(created[0] if isinstance(created, list) else created)


def _create_preference_row(user_id: uuid.UUID) -> Preference:
    now = datetime.now(timezone.utc).isoformat()
    settings_doc = PreferenceSettingsV1().model_dump()
    row = {
        "user_id": str(user_id),
        "settings": settings_doc,
        "updated_at": now,
    }
    response = _request("POST", "preferences", json_body=row)
    if response.status_code == 409:
        existing = _fetch_preference(user_id)
        if existing is not None:
            return existing
    if response.status_code >= 400:
        response.raise_for_status()
    created = response.json()
    return _preference_from_row(created[0] if isinstance(created, list) else created)


def _profile_from_row(row: dict) -> Profile:
    return Profile(
        id=uuid.UUID(str(row["id"])),
        display_name=row.get("display_name"),
        avatar_url=row.get("avatar_url"),
        created_at=_parse_ts(row.get("created_at")),
    )


def _preference_from_row(row: dict) -> Preference:
    return Preference(
        user_id=uuid.UUID(str(row["user_id"])),
        settings=row.get("settings") or {},
        updated_at=_parse_ts(row.get("updated_at")),
    )


def _fetch_profile(user_id: uuid.UUID) -> Profile | None:
    response = _request(
        "GET",
        "profiles",
        params={"id": f"eq.{user_id}", "select": "*", "limit": "1"},
    )
    rows = response.json()
    if not rows:
        return None
    return _profile_from_row(rows[0])


def _fetch_preference(user_id: uuid.UUID) -> Preference | None:
    response = _request(
        "GET",
        "preferences",
        params={"user_id": f"eq.{user_id}", "select": "*", "limit": "1"},
    )
    rows = response.json()
    if not rows:
        return None
    return _preference_from_row(rows[0])


def ensure_profile_and_preferences_rest(user_id: uuid.UUID) -> tuple[Profile, Preference]:
    profile = _fetch_profile(user_id)
    pref = _fetch_preference(user_id)

    if profile is None:
        profile = _create_profile_row(user_id)

    if pref is None:
        pref = _create_preference_row(user_id)

    return profile, pref


def patch_preference_settings_rest(user_id: uuid.UUID, patch: dict) -> PreferenceSettingsV1:
    _, pref = ensure_profile_and_preferences_rest(user_id)
    merged = merge_preference_settings(pref.settings, patch)
    now = datetime.now(timezone.utc).isoformat()
    response = _request(
        "PATCH",
        "preferences",
        params={"user_id": f"eq.{user_id}"},
        json_body={"settings": merged.model_dump(), "updated_at": now},
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return merged


def set_personality_profile_rest(user_id: uuid.UUID, profile_dict: dict) -> PreferenceSettingsV1:
    settings = get_preference_settings_rest(user_id)
    data = settings.model_dump()
    data["personality_profile_v1"] = profile_dict
    return patch_preference_settings_rest(user_id, data)


def get_preference_settings_rest(user_id: uuid.UUID) -> PreferenceSettingsV1:
    _, pref = ensure_profile_and_preferences_rest(user_id)
    return PreferenceSettingsV1.model_validate(pref.settings or {})


def register_device_rest(
    user_id: uuid.UUID,
    device_id: uuid.UUID,
    device_type: str,
    label: str = "",
) -> PreferenceSettingsV1:
    settings = get_preference_settings_rest(user_id)
    devices = list(settings.devices)
    device_id_str = str(device_id)
    found = False
    for i, device in enumerate(devices):
        if device.device_id == device_id_str:
            devices[i] = RegisteredDeviceV1(
                device_id=device_id_str,
                device_type=device_type,  # type: ignore[arg-type]
                label=label or device.label,
            )
            found = True
            break
    if not found:
        devices.append(
            RegisteredDeviceV1(
                device_id=device_id_str,
                device_type=device_type,  # type: ignore[arg-type]
                label=label,
            )
        )
    return patch_preference_settings_rest(
        user_id,
        {"devices": [device.model_dump() for device in devices]},
    )


def update_profile_rest(
    user_id: uuid.UUID,
    *,
    display_name: str | None = None,
    avatar_url: str | None = None,
) -> Profile:
    ensure_profile_and_preferences_rest(user_id)
    payload: dict[str, Any] = {}
    if display_name is not None:
        payload["display_name"] = display_name
    if avatar_url is not None:
        payload["avatar_url"] = avatar_url
    if payload:
        response = _request("PATCH", "profiles", params={"id": f"eq.{user_id}"}, json_body=payload)
        if response.status_code >= 400:
            response.raise_for_status()
    profile = _fetch_profile(user_id)
    if profile is None:
        raise RuntimeError("Profile missing after update")
    return profile

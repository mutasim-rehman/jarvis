"""Data access for Phase 4.5 tables."""

from __future__ import annotations

import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from shared.preferences import (
    PreferenceSettingsV1,
    RegisteredDeviceV1,
    merge_preference_settings,
)

from .models import DeviceLink, PairingSession, Preference, Profile, Task


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_profile(session: Session, user_id: uuid.UUID) -> Profile | None:
    return session.get(Profile, user_id)


def ensure_profile_and_preferences(session: Session, user_id: uuid.UUID) -> tuple[Profile, Preference]:
    profile = session.get(Profile, user_id)
    if profile is None:
        profile = Profile(id=user_id, created_at=_utcnow())
        session.add(profile)
    pref = session.get(Preference, user_id)
    if pref is None:
        pref = Preference(
            user_id=user_id,
            settings=PreferenceSettingsV1().model_dump(),
            updated_at=_utcnow(),
        )
        session.add(pref)
    session.flush()
    return profile, pref


def update_profile(
    session: Session,
    user_id: uuid.UUID,
    *,
    display_name: str | None = None,
    avatar_url: str | None = None,
) -> Profile:
    profile, _ = ensure_profile_and_preferences(session, user_id)
    if display_name is not None:
        profile.display_name = display_name
    if avatar_url is not None:
        profile.avatar_url = avatar_url
    session.flush()
    return profile


def get_preference_settings(session: Session, user_id: uuid.UUID) -> PreferenceSettingsV1:
    _, pref = ensure_profile_and_preferences(session, user_id)
    return PreferenceSettingsV1.model_validate(pref.settings or {})


def patch_preference_settings(
    session: Session,
    user_id: uuid.UUID,
    patch: dict,
) -> PreferenceSettingsV1:
    _, pref = ensure_profile_and_preferences(session, user_id)
    merged = merge_preference_settings(pref.settings, patch)
    pref.settings = merged.model_dump()
    pref.updated_at = _utcnow()
    session.flush()
    return merged


def set_personality_profile(
    session: Session,
    user_id: uuid.UUID,
    profile_dict: dict,
) -> PreferenceSettingsV1:
    settings = get_preference_settings(session, user_id)
    data = settings.model_dump()
    data["personality_profile_v1"] = profile_dict
    return patch_preference_settings(session, user_id, data)


def register_device(
    session: Session,
    user_id: uuid.UUID,
    device_id: uuid.UUID,
    device_type: str,
    label: str = "",
) -> PreferenceSettingsV1:
    settings = get_preference_settings(session, user_id)
    devices = list(settings.devices)
    device_id_str = str(device_id)
    found = False
    for i, d in enumerate(devices):
        if d.device_id == device_id_str:
            devices[i] = RegisteredDeviceV1(
                device_id=device_id_str,
                device_type=device_type,  # type: ignore[arg-type]
                label=label or d.label,
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
    return patch_preference_settings(session, user_id, {"devices": [d.model_dump() for d in devices]})


def _generate_pair_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_pairing_session(
    session: Session,
    user_id: uuid.UUID,
    laptop_device_id: uuid.UUID,
    *,
    ttl_minutes: int = 5,
) -> PairingSession:
    for _ in range(10):
        code = _generate_pair_code()
        existing = session.execute(
            select(PairingSession).where(
                PairingSession.pair_code == code,
                PairingSession.used.is_(False),
            )
        ).scalar_one_or_none()
        if existing is None:
            break
    else:
        code = _generate_pair_code(8)
    row = PairingSession(
        user_id=user_id,
        laptop_device_id=laptop_device_id,
        pair_code=code,
        expires_at=_utcnow() + timedelta(minutes=ttl_minutes),
        used=False,
    )
    session.add(row)
    session.flush()
    return row


def claim_pairing_session(
    session: Session,
    user_id: uuid.UUID,
    pair_code: str,
    phone_device_id: uuid.UUID,
) -> DeviceLink:
    code = pair_code.strip().upper()
    row = session.execute(
        select(PairingSession).where(
            PairingSession.pair_code == code,
            PairingSession.used.is_(False),
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("Invalid or expired pairing code")
    if row.user_id and row.user_id != user_id:
        raise ValueError("Pairing code belongs to another user")
    if row.expires_at and row.expires_at < _utcnow():
        raise ValueError("Pairing code has expired")
    row.used = True
    link = DeviceLink(
        user_id=user_id,
        laptop_device_id=row.laptop_device_id,
        phone_device_id=phone_device_id,
        status="active",
        created_at=_utcnow(),
    )
    session.add(link)
    session.flush()
    return link


def list_device_links(session: Session, user_id: uuid.UUID) -> list[DeviceLink]:
    return list(
        session.execute(
            select(DeviceLink).where(
                DeviceLink.user_id == user_id,
                DeviceLink.status == "active",
            )
        ).scalars()
    )


def create_task(
    session: Session,
    user_id: uuid.UUID,
    target_device_id: uuid.UUID,
    payload: dict,
) -> Task:
    row = Task(
        user_id=user_id,
        target_device_id=target_device_id,
        payload=payload,
        status="pending",
        created_at=_utcnow(),
    )
    session.add(row)
    session.flush()
    return row


def delete_user_account(session: Session, user_id: uuid.UUID) -> None:
    """Delete all Phase 4.5 rows for this user."""
    session.execute(delete(Task).where(Task.user_id == user_id))
    session.execute(delete(DeviceLink).where(DeviceLink.user_id == user_id))
    session.execute(delete(PairingSession).where(PairingSession.user_id == user_id))
    session.execute(delete(Preference).where(Preference.user_id == user_id))
    session.execute(delete(Profile).where(Profile.id == user_id))
    session.flush()


def list_tasks_for_device(
    session: Session,
    user_id: uuid.UUID,
    target_device_id: uuid.UUID,
    *,
    status: str = "pending",
) -> list[Task]:
    return list(
        session.execute(
            select(Task).where(
                Task.user_id == user_id,
                Task.target_device_id == target_device_id,
                Task.status == status,
            )
        ).scalars()
    )

"""Phase 4.5 — auth, profile, preferences, pairing, tasks."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from shared.preferences import (
    AccountDeleteResponse,
    AuthMeResponse,
    DeviceLinkResponse,
    DeviceRegisterRequest,
    empty_personality_template,
    PairingClaimRequest,
    PairingClaimResponse,
    PairingSessionCreate,
    PairingSessionResponse,
    PersonalityProfileV1,
    PreferencesPatch,
    PreferencesResponse,
    PreferenceSettingsV1,
    ProfileResponse,
    ProfileUpdate,
    TaskCreateRequest,
    TaskResponse,
)

from backend.app.auth.deps import AuthUser, get_current_user_required
from backend.app.auth.supabase_jwt import delete_supabase_auth_user
from backend.app.db.repositories import (
    claim_pairing_session,
    create_pairing_session,
    create_task,
    delete_user_account,
    ensure_profile_and_preferences,
    get_preference_settings,
    list_device_links,
    list_tasks_for_device,
    patch_preference_settings,
    register_device,
    set_personality_profile,
    update_profile,
)
from backend.app.db.session import get_db
from backend.app.email.welcome import maybe_send_welcome_email

router = APIRouter(tags=["accounts"])
logger = logging.getLogger(__name__)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


@router.get("/auth/me", response_model=AuthMeResponse)
def auth_me(
    user: AuthUser = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    profile, pref = ensure_profile_and_preferences(db, user.user_id)
    settings = PreferenceSettingsV1.model_validate(pref.settings or {})
    return AuthMeResponse(
        user_id=user.user_id,
        email=user.email,
        profile=ProfileResponse(
            id=profile.id,
            display_name=profile.display_name,
            avatar_url=profile.avatar_url,
            created_at=_iso(profile.created_at),
        ),
        settings=settings,
        onboarding_completed=settings.onboarding_completed,
    )


@router.delete("/auth/account", response_model=AccountDeleteResponse)
def delete_account(
    user: AuthUser = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    delete_user_account(db, user.user_id)
    auth_removed = delete_supabase_auth_user(user.user_id)
    return AccountDeleteResponse(deleted=True, auth_user_removed=auth_removed)


@router.get("/users/profile", response_model=ProfileResponse)
def get_profile(
    user: AuthUser = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    profile, _ = ensure_profile_and_preferences(db, user.user_id)
    return ProfileResponse(
        id=profile.id,
        display_name=profile.display_name,
        avatar_url=profile.avatar_url,
        created_at=_iso(profile.created_at),
    )


@router.patch("/users/profile", response_model=ProfileResponse)
def patch_profile(
    body: ProfileUpdate,
    user: AuthUser = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    profile = update_profile(
        db,
        user.user_id,
        display_name=body.display_name,
        avatar_url=body.avatar_url,
    )
    return ProfileResponse(
        id=profile.id,
        display_name=profile.display_name,
        avatar_url=profile.avatar_url,
        created_at=_iso(profile.created_at),
    )


@router.get("/preferences", response_model=PreferencesResponse)
def get_preferences(
    user: AuthUser = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    _, pref = ensure_profile_and_preferences(db, user.user_id)
    settings = PreferenceSettingsV1.model_validate(pref.settings or {})
    return PreferencesResponse(
        user_id=user.user_id,
        settings=settings,
        updated_at=_iso(pref.updated_at),
    )


@router.patch("/preferences", response_model=PreferencesResponse)
def patch_preferences(
    body: PreferencesPatch,
    user: AuthUser = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    profile, pref = ensure_profile_and_preferences(db, user.user_id)
    old_settings = PreferenceSettingsV1.model_validate(pref.settings or {})
    patch = body.to_settings_patch()
    settings = patch_preference_settings(db, user.user_id, patch)

    completing_onboarding = (
        body.onboarding_completed is True
        and not old_settings.onboarding_completed
        and not old_settings.welcome_email_sent
    )
    if completing_onboarding and user.email:
        try:
            if maybe_send_welcome_email(to_email=user.email, display_name=profile.display_name):
                settings = patch_preference_settings(
                    db,
                    user.user_id,
                    {"welcome_email_sent": True},
                )
        except Exception:
            logger.exception("Welcome email failed for user_id=%s", user.user_id)

    _, pref = ensure_profile_and_preferences(db, user.user_id)
    return PreferencesResponse(
        user_id=user.user_id,
        settings=settings,
        updated_at=_iso(pref.updated_at),
    )


@router.get("/preferences/personality/template")
def personality_template():
    return empty_personality_template()


@router.post("/preferences/personality", response_model=PreferencesResponse)
def import_personality(
    body: PersonalityProfileV1,
    user: AuthUser = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    settings = set_personality_profile(db, user.user_id, body.model_dump())
    _, pref = ensure_profile_and_preferences(db, user.user_id)
    return PreferencesResponse(
        user_id=user.user_id,
        settings=settings,
        updated_at=_iso(pref.updated_at),
    )


@router.post("/devices/register", response_model=PreferencesResponse)
def devices_register(
    body: DeviceRegisterRequest,
    user: AuthUser = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    settings = register_device(
        db,
        user.user_id,
        body.device_id,
        body.device_type,
        body.label,
    )
    _, pref = ensure_profile_and_preferences(db, user.user_id)
    return PreferencesResponse(
        user_id=user.user_id,
        settings=settings,
        updated_at=_iso(pref.updated_at),
    )


@router.post("/pairing/sessions", response_model=PairingSessionResponse)
def pairing_create_session(
    body: PairingSessionCreate,
    user: AuthUser = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    row = create_pairing_session(db, user.user_id, body.laptop_device_id)
    if row.pair_code is None or row.expires_at is None:
        raise HTTPException(status_code=500, detail="Failed to create pairing session")
    return PairingSessionResponse(
        id=row.id,
        pair_code=row.pair_code,
        laptop_device_id=body.laptop_device_id,
        expires_at=_iso(row.expires_at) or "",
    )


@router.post("/pairing/claim", response_model=PairingClaimResponse)
def pairing_claim(
    body: PairingClaimRequest,
    user: AuthUser = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    try:
        link = claim_pairing_session(db, user.user_id, body.pair_code, body.phone_device_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if link.laptop_device_id is None or link.phone_device_id is None:
        raise HTTPException(status_code=500, detail="Incomplete device link")
    return PairingClaimResponse(
        device_link_id=link.id,
        laptop_device_id=link.laptop_device_id,
        phone_device_id=link.phone_device_id,
        status=link.status or "active",
    )


@router.get("/pairing/links", response_model=list[DeviceLinkResponse])
def pairing_list_links(
    user: AuthUser = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    links = list_device_links(db, user.user_id)
    return [
        DeviceLinkResponse(
            id=link.id,
            laptop_device_id=link.laptop_device_id,
            phone_device_id=link.phone_device_id,
            status=link.status,
            created_at=_iso(link.created_at),
        )
        for link in links
    ]


@router.post("/tasks", response_model=TaskResponse)
def tasks_create(
    body: TaskCreateRequest,
    user: AuthUser = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    row = create_task(db, user.user_id, body.target_device_id, body.payload)
    return TaskResponse(
        id=row.id,
        user_id=row.user_id,
        target_device_id=row.target_device_id,
        status=row.status,
        payload=row.payload,
        created_at=_iso(row.created_at),
    )


@router.get("/tasks", response_model=list[TaskResponse])
def tasks_list(
    target_device_id: uuid.UUID,
    user: AuthUser = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    rows = list_tasks_for_device(db, user.user_id, target_device_id)
    return [
        TaskResponse(
            id=row.id,
            user_id=row.user_id,
            target_device_id=row.target_device_id,
            status=row.status,
            payload=row.payload,
            created_at=_iso(row.created_at),
        )
        for row in rows
    ]

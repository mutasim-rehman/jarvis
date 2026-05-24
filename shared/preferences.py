"""Phase 4.5 — user preference and personality profile models."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PersonalityPhilosophyV1(BaseModel):
    worldview: str = ""
    view_on_meaning: str = ""
    view_on_success: str = ""
    view_on_failure: str = ""
    view_on_relationships: str = ""
    view_on_self: str = ""
    view_on_growth: str = ""
    contradictory_beliefs: list[str] = Field(default_factory=list)


class PersonalityCommunicationV1(BaseModel):
    tone: str = ""
    style: str = ""
    verbosity: str = ""
    formality: str = ""
    emotional_expression: str = ""
    humor: str = ""
    quirks: list[str] = Field(default_factory=list)
    speech_patterns: list[str] = Field(default_factory=list)
    conversation_habits: list[str] = Field(default_factory=list)


class PersonalityThinkingV1(BaseModel):
    decision_style: str = ""
    openness: str = ""
    reactivity: str = ""
    conflict_handling: str = ""
    persuasion_style: str = ""
    overthinking: str = ""
    risk_tolerance: str = ""


class PersonalitySocialBehaviorV1(BaseModel):
    towards_strangers: str = ""
    towards_friends: str = ""
    towards_authority: str = ""
    towards_conflict: str = ""
    trust_building: str = ""
    attachment_style: str = ""


class PersonalityProfileV1(BaseModel):
    name: str = ""
    profile: str = ""
    personality: str = ""
    archetype: str = ""
    philosophy: PersonalityPhilosophyV1 = Field(default_factory=PersonalityPhilosophyV1)
    beliefs: list[str] = Field(default_factory=list)
    values: list[str] = Field(default_factory=list)
    fears: list[str] = Field(default_factory=list)
    desires: list[str] = Field(default_factory=list)
    emotional_baseline: str = ""
    emotional_tendencies: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    communication: PersonalityCommunicationV1 = Field(default_factory=PersonalityCommunicationV1)
    thinking: PersonalityThinkingV1 = Field(default_factory=PersonalityThinkingV1)
    social_behavior: PersonalitySocialBehaviorV1 = Field(default_factory=PersonalitySocialBehaviorV1)
    behavioral_patterns: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    biases: list[str] = Field(default_factory=list)
    hidden_traits: list[str] = Field(default_factory=list)


class PreferenceSlidersV1(BaseModel):
    honesty: float = Field(default=0.7, ge=0.0, le=1.0)
    humor: float = Field(default=0.4, ge=0.0, le=1.0)
    formality: float = Field(default=0.6, ge=0.0, le=1.0)
    verbosity: float = Field(default=0.5, ge=0.0, le=1.0)
    proactivity: float = Field(default=0.5, ge=0.0, le=1.0)


class AssistantDefaultsV1(BaseModel):
    tone: str = "calm"
    verbosity: str = "moderate"
    suggest_actions: bool = True


class ContentHintsV1(BaseModel):
    genres: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    do_not_suggest: list[str] = Field(default_factory=list)


class IntegrationConsentsV1(BaseModel):
    spotify: bool = False
    youtube: bool = False


class RegisteredDeviceV1(BaseModel):
    device_id: str
    device_type: Literal["laptop", "phone", "pi"] = "laptop"
    label: str = ""


class PreferenceSettingsV1(BaseModel):
    version: int = 1
    onboarding_completed: bool = False
    sliders: PreferenceSlidersV1 = Field(default_factory=PreferenceSlidersV1)
    assistant_defaults: AssistantDefaultsV1 = Field(default_factory=AssistantDefaultsV1)
    content_hints: ContentHintsV1 = Field(default_factory=ContentHintsV1)
    integrations: IntegrationConsentsV1 = Field(default_factory=IntegrationConsentsV1)
    personality_profile_v1: PersonalityProfileV1 | None = None
    devices: list[RegisteredDeviceV1] = Field(default_factory=list)

    @field_validator("version")
    @classmethod
    def _version_must_be_one(cls, v: int) -> int:
        if v != 1:
            raise ValueError("Only PreferenceSettingsV1 (version=1) is supported")
        return v


def empty_personality_template() -> dict[str, Any]:
    return PersonalityProfileV1().model_dump()


def merge_preference_settings(
    current: dict[str, Any] | None,
    patch: dict[str, Any],
) -> PreferenceSettingsV1:
    base = PreferenceSettingsV1.model_validate(current or {})
    merged = {**base.model_dump(), **{k: v for k, v in patch.items() if v is not None}}
    if "sliders" in patch and isinstance(patch["sliders"], dict):
        merged["sliders"] = {**base.sliders.model_dump(), **patch["sliders"]}
    if "assistant_defaults" in patch and isinstance(patch["assistant_defaults"], dict):
        merged["assistant_defaults"] = {
            **base.assistant_defaults.model_dump(),
            **patch["assistant_defaults"],
        }
    if "content_hints" in patch and isinstance(patch["content_hints"], dict):
        merged["content_hints"] = {**base.content_hints.model_dump(), **patch["content_hints"]}
    if "integrations" in patch and isinstance(patch["integrations"], dict):
        merged["integrations"] = {**base.integrations.model_dump(), **patch["integrations"]}
    return PreferenceSettingsV1.model_validate(merged)


def personality_profile_summary(profile: PersonalityProfileV1, max_chars: int = 800) -> str:
    parts: list[str] = []
    if profile.name or profile.archetype:
        parts.append(f"User: {profile.name or 'unknown'}; archetype: {profile.archetype or 'n/a'}.")
    if profile.personality or profile.profile:
        parts.append(f"Personality: {(profile.personality or profile.profile)[:200]}.")
    comm = profile.communication
    comm_bits = [comm.tone, comm.style, comm.formality, comm.humor]
    comm_text = ", ".join(b for b in comm_bits if b)
    if comm_text:
        parts.append(f"Communication: {comm_text}.")
    if profile.values:
        parts.append(f"Values: {', '.join(profile.values[:6])}.")
    if profile.beliefs:
        parts.append(f"Beliefs: {', '.join(profile.beliefs[:4])}.")
    if profile.contradictions:
        parts.append(f"Contradictions: {', '.join(profile.contradictions[:3])}.")
    if profile.emotional_baseline:
        parts.append(f"Emotional baseline: {profile.emotional_baseline}.")
    if profile.thinking.decision_style:
        parts.append(f"Decision style: {profile.thinking.decision_style}.")
    text = " ".join(parts).strip()
    if len(text) > max_chars:
        return text[: max_chars - 3] + "..."
    return text


def build_preference_context_text(settings: PreferenceSettingsV1) -> str:
    lines: list[str] = ["USER PREFERENCES (honor these in tone and suggestions):"]
    s = settings.sliders
    lines.append(
        f"- Sliders: honesty={s.honesty:.2f}, humor={s.humor:.2f}, "
        f"formality={s.formality:.2f}, verbosity={s.verbosity:.2f}, proactivity={s.proactivity:.2f}."
    )
    ad = settings.assistant_defaults
    lines.append(
        f"- Assistant: tone={ad.tone}, verbosity={ad.verbosity}, "
        f"suggest_actions={ad.suggest_actions}."
    )
    if settings.content_hints.interests or settings.content_hints.do_not_suggest:
        interests = ", ".join(settings.content_hints.interests[:8]) or "none"
        avoid = ", ".join(settings.content_hints.do_not_suggest[:8]) or "none"
        lines.append(f"- Interests: {interests}. Avoid suggesting: {avoid}.")
    if settings.personality_profile_v1:
        summary = personality_profile_summary(settings.personality_profile_v1)
        if summary:
            lines.append(f"- Imported personality: {summary}")
    return "\n".join(lines)


# --- API DTOs ---


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None


class ProfileResponse(BaseModel):
    id: UUID
    display_name: str | None = None
    avatar_url: str | None = None
    created_at: str | None = None


class PreferencesResponse(BaseModel):
    user_id: UUID
    settings: PreferenceSettingsV1
    updated_at: str | None = None


class PreferencesPatch(BaseModel):
    onboarding_completed: bool | None = None
    sliders: PreferenceSlidersV1 | dict[str, float] | None = None
    assistant_defaults: AssistantDefaultsV1 | dict[str, Any] | None = None
    content_hints: ContentHintsV1 | dict[str, Any] | None = None
    integrations: IntegrationConsentsV1 | dict[str, bool] | None = None

    def to_settings_patch(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if self.onboarding_completed is not None:
            data["onboarding_completed"] = self.onboarding_completed
        if self.sliders is not None:
            data["sliders"] = (
                self.sliders.model_dump()
                if isinstance(self.sliders, PreferenceSlidersV1)
                else self.sliders
            )
        if self.assistant_defaults is not None:
            data["assistant_defaults"] = (
                self.assistant_defaults.model_dump()
                if isinstance(self.assistant_defaults, AssistantDefaultsV1)
                else self.assistant_defaults
            )
        if self.content_hints is not None:
            data["content_hints"] = (
                self.content_hints.model_dump()
                if isinstance(self.content_hints, ContentHintsV1)
                else self.content_hints
            )
        if self.integrations is not None:
            data["integrations"] = (
                self.integrations.model_dump()
                if isinstance(self.integrations, IntegrationConsentsV1)
                else self.integrations
            )
        return data


class DeviceRegisterRequest(BaseModel):
    device_id: UUID
    device_type: Literal["laptop", "phone", "pi"] = "laptop"
    label: str = ""


class PairingSessionCreate(BaseModel):
    laptop_device_id: UUID


class PairingSessionResponse(BaseModel):
    id: UUID
    pair_code: str
    laptop_device_id: UUID
    expires_at: str


class PairingClaimRequest(BaseModel):
    pair_code: str
    phone_device_id: UUID


class PairingClaimResponse(BaseModel):
    device_link_id: UUID
    laptop_device_id: UUID
    phone_device_id: UUID
    status: str


class DeviceLinkResponse(BaseModel):
    id: UUID
    laptop_device_id: UUID | None
    phone_device_id: UUID | None
    status: str | None
    created_at: str | None = None


class TaskCreateRequest(BaseModel):
    target_device_id: UUID
    payload: dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    id: UUID
    user_id: UUID | None
    target_device_id: UUID | None
    status: str | None
    payload: dict[str, Any] | None = None
    created_at: str | None = None


class AuthMeResponse(BaseModel):
    user_id: UUID
    email: str | None = None
    profile: ProfileResponse | None = None
    settings: PreferenceSettingsV1
    onboarding_completed: bool


class AccountDeleteResponse(BaseModel):
    deleted: bool
    auth_user_removed: bool = False

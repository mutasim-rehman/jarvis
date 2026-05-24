"""Tests for shared preference models (no DB)."""

from shared.preferences import (
    PersonalityProfileV1,
    PreferenceSettingsV1,
    build_preference_context_text,
    merge_preference_settings,
    personality_profile_summary,
)


def test_merge_preference_settings_sliders():
    current = PreferenceSettingsV1().model_dump()
    merged = merge_preference_settings(current, {"sliders": {"formality": 0.95}})
    assert merged.sliders.formality == 0.95
    assert merged.sliders.humor == 0.4


def test_personality_profile_summary_includes_tone():
    profile = PersonalityProfileV1(
        name="Alex",
        communication={"tone": "dry", "formality": "casual", "style": "", "verbosity": "", "emotional_expression": "", "humor": "witty", "quirks": [], "speech_patterns": [], "conversation_habits": []},
    )
    summary = personality_profile_summary(profile)
    assert "Alex" in summary
    assert "dry" in summary or "witty" in summary


def test_build_preference_context_includes_sliders():
    settings = PreferenceSettingsV1()
    settings.sliders.formality = 0.9
    text = build_preference_context_text(settings)
    assert "formality=0.90" in text
    assert "USER PREFERENCES" in text

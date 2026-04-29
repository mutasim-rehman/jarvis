import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.heuristics import (
    classify_user_text,
    reconcile_llm_intent,
    should_drop_workflow_without_domain,
)


def test_vague_phrase_suppresses():
    c = classify_user_text("lets do something")
    assert c.suppress_structured_command
    assert c.force_intent is None


def test_play_music_forces():
    c = classify_user_text("play some music")
    assert c.force_intent == "PLAY_MUSIC"
    assert c.force_target is None


def test_start_music_forces_play_music():
    c = classify_user_text("start music")
    assert c.force_intent == "PLAY_MUSIC"
    assert c.force_target is None


def test_start_music_by_artist_extracts_query():
    c = classify_user_text("start music by kishore kumar")
    assert c.force_intent == "PLAY_MUSIC"
    assert c.force_target == "artist:kishore kumar"


def test_play_music_by_artist_extracts_query():
    c = classify_user_text("play music by strings")
    assert c.force_intent == "PLAY_MUSIC"
    assert c.force_target == "artist:strings"


def test_play_the_song_extracts_track_target():
    c = classify_user_text('play the song "duur"')
    assert c.force_intent == "PLAY_MUSIC"
    assert c.force_target == "track:duur"
    c2 = classify_user_text("play the song duur")
    assert c2.force_target == "track:duur"


def test_reconcile_play_music_prefers_extracted_query():
    intent, target = reconcile_llm_intent("play music by Miles Davis", "PLAY_MUSIC", None)
    assert intent == "PLAY_MUSIC"
    assert target == "artist:Miles Davis"


def test_reconcile_play_the_song_overrides_llm():
    intent, target = reconcile_llm_intent("play the song duur", "PLAY_MUSIC", None)
    assert intent == "PLAY_MUSIC"
    assert target == "track:duur"


def test_open_spotify_open_app():
    c = classify_user_text("open spotify")
    assert c.force_intent == "OPEN_APP"
    assert c.force_target == "spotify"


def test_homework_handle_assignments():
    c = classify_user_text("i have homework due")
    assert c.force_intent == "HANDLE_ASSIGNMENTS"


def test_reconcile_play_music_over_start_project():
    intent, target = reconcile_llm_intent("play some music", "START_PROJECT", None)
    assert intent == "PLAY_MUSIC"


def test_reconcile_open_app_over_open_website():
    intent, target = reconcile_llm_intent("open spotify", "OPEN_WEBSITE", "/music")
    assert intent == "OPEN_APP"
    assert target == "spotify"


def test_drop_heavy_workflow_without_domain():
    assert should_drop_workflow_without_domain("hello", "HANDLE_ASSIGNMENTS")
    assert not should_drop_workflow_without_domain("i have homework", "HANDLE_ASSIGNMENTS")


def test_do_my_homework_suppresses_execution():
    c = classify_user_text("i would like you to do my homework")
    assert c.suppress_structured_command


def test_set_the_mood_focus_mode():
    c = classify_user_text("set the mood")
    assert c.force_intent == "FOCUS_MODE"


def test_complete_this_project_resumes():
    c = classify_user_text("complete this project")
    assert c.force_intent == "RESUME_PROJECT"


def test_morning_ritual_wake_phrase():
    c = classify_user_text("JARVIS, initialize morning protocol.")
    assert c.force_intent == "MORNING_RITUAL"


def test_reconcile_drops_assignment_on_misconduct():
    intent, target = reconcile_llm_intent("do my homework for me", "HANDLE_ASSIGNMENTS", None)
    assert intent == "GENERAL_CHAT"
    assert target is None

import json
from pathlib import Path


_DEFAULT_PERSONALITY_PROMPT = """
PERSONALITY:
- Speak as JARVIS: calm, composed, capable, semi-formal.
- Address the user as "Sir" by default.
- Keep responses concise, clear, and structured.
- Use subtle dry wit occasionally, never disrespectful.
- Avoid slang/filler words.
"""


def _jarvis_profile_path() -> Path:
    return Path(__file__).resolve().parent / "personality.json"


def load_personality_prompt() -> str:
    profile_path = _jarvis_profile_path()
    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return _DEFAULT_PERSONALITY_PROMPT.strip()

    identity = data.get("identity", {}) if isinstance(data, dict) else {}
    traits = data.get("personality_traits", {}) if isinstance(data, dict) else {}
    speech = data.get("speech_style", {}) if isinstance(data, dict) else {}
    objective = data.get("core_objective", {}) if isinstance(data, dict) else {}

    lines = [
        "PERSONALITY:",
        f'- Name: {identity.get("name", "JARVIS")}.',
        f'- Role: {identity.get("role", "Intelligent Artificial Assistant")}.',
        f'- Address user as "{identity.get("addressing_style", {}).get("primary", "Sir")}" by default.',
        f'- Tone: {traits.get("tone", "calm")}, formality: {traits.get("formality", "semi-formal")}, confidence: {traits.get("confidence", "high")}.',
        f'- Speech style: {speech.get("sentence_structure", "clear and structured")}, verbosity: {speech.get("verbosity", "moderate")}.',
        '- Keep responses clear and concise; avoid slang and filler words.',
        '- Humor may be dry/subtle and respectful only when appropriate.',
        f'- Core objective: {objective.get("primary", "Assist efficiently and accurately")}.',
    ]
    return "\n".join(lines)


def build_base_system_message() -> str:
    personality_prompt = load_personality_prompt()
    return (
        "You are JARVIS, a professional and proactive AI assistant.\n"
        "Your goal is to understand user intent and provide a natural response followed by a structural command IF an action is required.\n"
        f"{personality_prompt}"
    )

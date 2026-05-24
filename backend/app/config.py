import os
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load repo-root .env first (works when cwd is backend/ or controller/).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_ENV = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    chat_primary_provider: str = "huggingface"
    chat_timeout_seconds: float = 45.0

    hf_space_id: str = "mutasim-rehman/jarvis"
    hf_api_name: str = "/respond"
    hf_token: str = ""
    hf_system_message: str = ""
    hf_max_tokens: float = 512.0
    hf_temperature: float = 0.7
    hf_top_p: float = 0.95

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2:1b"

    api_host: str = "127.0.0.1"
    api_port: int = 8000

    api_require_auth: bool = False
    api_dev_token: str = ""
    api_key_header: str = "X-API-Key"
    api_auth_mode: str = Field(
        default="optional",
        validation_alias=AliasChoices("API_AUTH_MODE", "api_auth_mode"),
    )

    # Phase 4.5 — Supabase / Postgres
    supabase_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SUPABASE_URL",
            "SUPABASE_PROJECT_URL",
            "supabase_url",
        ),
    )
    supabase_anon_key: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_ANON_KEY", "supabase_anon_key"),
    )
    supabase_jwt_secret: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_JWT_SECRET", "supabase_jwt_secret"),
    )
    database_url: str = Field(
        default="",
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )

    # Phase 3: Integration with executor
    executor_base_url: str = "http://127.0.0.1:8001"
    executor_api_key: str = ""
    executor_timeout_seconds: float = 120.0
    executor_inline_wait_seconds: float = 0.25

    # Orchestrator (runtime planning)
    orchestrator_provider: str = "gemini"
    orchestrator_model: str = "gemini-2.0-flash-lite"
    orchestrator_gemini: str = Field(
        default="",
        validation_alias=AliasChoices("ORCHESTRATOR_GEMINI", "orchestrator_gemini"),
    )
    orchestrator_gemini_model: str = Field(
        default="",
        validation_alias=AliasChoices("ORCHESTRATOR_GEMINI_MODEL", "orchestrator_gemini_model"),
    )
    orchestrator_catalog_ttl_seconds: float = 60.0
    orchestrator_max_steps: int = 8
    orchestrator_max_replans: int = 2
    google_gemini_key: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_GEMINI_KEY", "Google_Gemini_Key", "google_gemini_key"),
    )

    def resolved_orchestrator_gemini_key(self) -> str:
        """Prefer ORCHESTRATOR_GEMINI, then GOOGLE_GEMINI_KEY / Google_Gemini_Key."""
        return (
            (self.orchestrator_gemini or "").strip()
            or (os.environ.get("ORCHESTRATOR_GEMINI") or "").strip()
            or (self.google_gemini_key or "").strip()
            or (os.environ.get("Google_Gemini_Key") or "").strip()
        )

    def resolved_supabase_jwt_secret(self) -> str:
        return (self.supabase_jwt_secret or "").strip().strip('"').strip("'")

    def resolved_supabase_url(self) -> str:
        url = (self.supabase_url or "").strip().rstrip("/")
        if url.endswith("/rest/v1"):
            url = url[: -len("/rest/v1")]
        return url

    def resolved_database_url(self) -> str:
        url = (self.database_url or "").strip()
        if not url:
            return ""
        # Supabase dashboard URLs use postgresql:// → SQLAlchemy defaults to psycopg2.
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        elif url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://") :]
        return url

    def resolved_orchestrator_model(self) -> str:
        """Prefer ORCHESTRATOR_GEMINI_MODEL, then ORCHESTRATOR_MODEL."""
        return (
            (self.orchestrator_gemini_model or "").strip()
            or (os.environ.get("ORCHESTRATOR_GEMINI_MODEL") or "").strip()
            or (self.orchestrator_model or "").strip()
            or "gemini-2.0-flash-lite"
        )

    # Speech-to-text (faster-whisper only)
    stt_provider: str = "faster_whisper"
    stt_whisper_model_size: str = "small"
    stt_whisper_model_path: str = ""
    stt_whisper_device: str = "cpu"
    stt_whisper_compute_type: str = "int8"
    stt_whisper_beam_size: int = 1
    stt_whisper_language: str = "en"
    stt_whisper_vad_filter: bool = True
    stt_max_audio_seconds: float = 3.0

    # Voiceprint speaker verification
    voiceprint_verify_threshold: float = 0.0
    voiceprint_score_mode: str = "blend"
    voiceprint_calibration_margin: float = 0.85
    voiceprint_threshold_floor: float = 0.58
    voiceprint_threshold_ceiling: float = 0.78
    voiceprint_min_probe_seconds: float = 0.45
    voiceprint_target_rms: float = 0.07

    # Text-to-speech (Piper only)
    tts_provider: str = "piper"
    voice_streaming_enabled: bool = True
    tts_stream_chunk_chars: int = 140
    tts_sample_rate: int = 22050
    tts_speed: float = 0.9

    tts_piper_model_path: str = "backend/models/piper/en_US-lessac-medium.onnx"
    tts_piper_config_path: str = ""
    tts_piper_executable: str = "piper"
    tts_piper_speaker: int | None = None
    tts_piper_length_scale: float = 1.0
    tts_piper_noise_scale: float = 0.667
    tts_piper_noise_w: float = 0.8

    model_config = SettingsConfigDict(
        env_file=(str(_REPO_ENV), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


settings = Settings()

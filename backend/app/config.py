from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Phase 3: Integration with executor
    executor_base_url: str = "http://127.0.0.1:8001"
    executor_api_key: str = ""
    executor_timeout_seconds: float = 120.0

    # Local offline speech-to-text (Vosk)
    stt_model_path: str = "backend/models/vosk-model-small-en-us-0.15"

    # Local text-to-speech (Kokoro)
    tts_kokoro_model_path: str = "backend/models/Kokoro-82M"
    tts_kokoro_voice: str = "bm_george"
    tts_kokoro_lang_code: str = "b"
    tts_sample_rate: int = 24000
    tts_speed: float = 0.9

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

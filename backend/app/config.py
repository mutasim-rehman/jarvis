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
    executor_inline_wait_seconds: float = 0.25

    # Speech-to-text provider selection
    stt_provider: str = "vosk"

    # Local offline speech-to-text (Vosk)
    stt_model_path: str = "backend/models/vosk-model-small-en-us-0.15"

    # Local speech-to-text (faster-whisper)
    stt_whisper_model_size: str = "small"
    stt_whisper_model_path: str = ""
    stt_whisper_device: str = "auto"
    stt_whisper_compute_type: str = "int8"
    stt_whisper_beam_size: int = 1
    stt_whisper_language: str = "en"
    stt_whisper_vad_filter: bool = True

    # Text-to-speech provider selection
    tts_provider: str = "kokoro"
    voice_streaming_enabled: bool = True
    tts_stream_chunk_chars: int = 140

    # Local text-to-speech (Kokoro)
    tts_kokoro_model_path: str = "backend/models/Kokoro-82M"
    tts_kokoro_voice: str = "bm_george"
    tts_kokoro_lang_code: str = "b"
    tts_sample_rate: int = 24000
    tts_speed: float = 0.9

    # Local text-to-speech (Piper)
    tts_piper_model_path: str = "backend/models/piper/en_US-lessac-medium.onnx"
    tts_piper_config_path: str = ""
    tts_piper_executable: str = "piper"
    tts_piper_speaker: int | None = None
    tts_piper_length_scale: float = 1.0
    tts_piper_noise_scale: float = 0.667
    tts_piper_noise_w: float = 0.8

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

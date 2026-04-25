import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ChatbotSettings:
    primary_provider: str = os.getenv("CHAT_PRIMARY_PROVIDER", "huggingface").strip().lower() or "huggingface"
    timeout_seconds: float = float(os.getenv("CHAT_TIMEOUT_SECONDS", "45"))

    hf_space_id: str = os.getenv("HF_SPACE_ID", "mutasim-rehman/jarvis").strip() or "mutasim-rehman/jarvis"
    hf_api_name: str = os.getenv("HF_API_NAME", "/respond").strip() or "/respond"
    hf_token: str = os.getenv("HF_TOKEN", "").strip()
    hf_system_message: str = os.getenv("HF_SYSTEM_MESSAGE", "").strip()
    hf_max_tokens: float = float(os.getenv("HF_MAX_TOKENS", "512"))
    hf_temperature: float = float(os.getenv("HF_TEMPERATURE", "0.7"))
    hf_top_p: float = float(os.getenv("HF_TOP_P", "0.95"))

    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip()
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2:1b").strip()


settings = ChatbotSettings()

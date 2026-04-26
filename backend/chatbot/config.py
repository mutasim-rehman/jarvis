import os

from pydantic_settings import BaseSettings, SettingsConfigDict


def _space_id_from_link(link: str) -> str:
    raw = (link or "").strip()
    if not raw:
        return ""

    normalized = raw.replace("https://", "").replace("http://", "").strip("/")
    marker = "huggingface.co/spaces/"
    if marker in normalized:
        return normalized.split(marker, 1)[1].strip("/")

    # If user already passed "owner/space" in the link variable, preserve it.
    if "/" in normalized and " " not in normalized:
        return normalized
    return ""


class ChatbotSettings(BaseSettings):
    primary_provider: str = (os.getenv("CHAT_PRIMARY_PROVIDER", "huggingface").strip().lower() or "huggingface")
    timeout_seconds: float = float(os.getenv("CHAT_TIMEOUT_SECONDS", "45"))

    hf_space_link: str = os.getenv("HF_SPACE_LINK", "").strip()
    hf_space_id: str = os.getenv("HF_SPACE_ID", "").strip()
    hf_api_name: str = os.getenv("HF_API_NAME", "/respond").strip() or "/respond"
    hf_token: str = os.getenv("HF_TOKEN", "").strip()
    hf_system_message: str = os.getenv("HF_SYSTEM_MESSAGE", "").strip()
    hf_max_tokens: float = float(os.getenv("HF_MAX_TOKENS", "512"))
    hf_temperature: float = float(os.getenv("HF_TEMPERATURE", "0.7"))
    hf_top_p: float = float(os.getenv("HF_TOP_P", "0.95"))

    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip()
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2:1b").strip()

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def resolved_hf_space_id(self) -> str:
        return (self.hf_space_id or "").strip() or _space_id_from_link(self.hf_space_link)


settings = ChatbotSettings()

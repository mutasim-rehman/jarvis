from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_host: str = "127.0.0.1"
    api_port: int = 8001

    api_require_auth: bool = False
    api_dev_token: str = ""
    api_key_header: str = "X-API-Key"

    allowlist_path: str = ""

    model_config = SettingsConfigDict(
        env_prefix="EXECUTOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

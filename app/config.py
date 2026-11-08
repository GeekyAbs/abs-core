from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    chat_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    embed_model: str = "openai/text-embedding-3-small"
    app_url: str = "https://abesh.site"
    app_title: str = "Abesh's Portfolio"

    db_path: str = "./data/portfolio.db"
    cors_origins: str = "http://localhost:5173"
    rate_limit: str = "20/minute"

    min_similarity: float = 0.35
    top_k: int = 5
    max_message_chars: int = 2000
    max_tokens: int = 400
    llm_timeout: float = 30.0
    embed_timeout: float = 20.0

    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_llm_configured(self) -> bool:
        return bool(self.openrouter_api_key.get_secret_value().strip())


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    chat_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    embed_model: str = "openai/text-embedding-3-small"  # override if unavailable on free tier

    db_path: str = "./data/portfolio.db"
    checkpoint_db_path: str = "./data/checkpoints.db"

    cors_origins: str = "http://localhost:5173"
    rate_limit: str = "20/minute"

    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()

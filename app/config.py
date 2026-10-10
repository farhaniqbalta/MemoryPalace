from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    anthropic_api_key: str
    openai_api_key: str
    telegram_bot_token: str

    claude_model: str = "claude-opus-5"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    api_base_url: str = "http://localhost:8000"


settings = Settings()

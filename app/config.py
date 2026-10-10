from typing import Literal, Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    openai_api_key: str = ""
    telegram_bot_token: str = ""
    telegram_owner_id: Optional[int] = Field(default=None, gt=0)

    claude_model: str = "claude-haiku-5-5"
    embedding_provider: Literal["gemini", "openai"] = "gemini"
    gemini_embedding_model: str = "gemini-embedding-001"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_model: Optional[str] = None
    embedding_dimensions: int = Field(default=1536, ge=1536, le=1536)

    api_base_url: str = "http://localhost:8000"

    @model_validator(mode="after")
    def select_embedding_model(self):
        if not self.embedding_model:
            self.embedding_model = (
                self.gemini_embedding_model
                if self.embedding_provider == "gemini"
                else self.openai_embedding_model
            )
        return self


settings = Settings()

from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "ContractLens"
    environment: str = "development"
    debug: bool = False

    # CORS
    cors_origins: str = "http://localhost:3200"

    # OpenAI
    openai_api_key: str

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str
    database_url: str

    # Redis (optional)
    redis_url: str = "redis://localhost:6379"

    # Sentry (optional - for error tracking)
    sentry_dsn: Optional[str] = None

    # Langfuse (optional - for AI observability)
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: str = "https://us.cloud.langfuse.com"

    # Processing
    worker_poll_interval: int = 15
    max_file_size_mb: int = 10

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

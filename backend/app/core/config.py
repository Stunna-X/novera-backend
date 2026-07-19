"""
Application configuration.

Loads environment variables and exposes them through
a strongly typed Settings object.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------

    APP_NAME: str = "Novera"

    APP_VERSION: str = "1.0.0"

    API_V1_PREFIX: str = "/api/v1"

    DEBUG: bool = True

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------

    DATABASE_URL: str = Field(...)

    # -------------------------------------------------------------------------
    # JWT
    # -------------------------------------------------------------------------

    SECRET_KEY: str = Field(...)

    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    JWT_ISSUER: str = "novera"

    JWT_AUDIENCE: str = "novera-api"

    # -------------------------------------------------------------------------
    # Email
    # -------------------------------------------------------------------------

    EMAIL_PROVIDER: str = "development"

    EMAIL_FROM_EMAIL: str = "no-reply@novera.local"

    EMAIL_FROM_NAME: str = "Novera"

    EMAIL_REPLY_TO_EMAIL: str | None = None

    EMAIL_OUTBOX_MAX_ATTEMPTS: int = 3

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------

    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.
    """
    return Settings()


settings = get_settings()
"""
Application configuration.

Loads environment variables and exposes them through
a strongly typed Settings object.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


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
    # Email identity
    # -------------------------------------------------------------------------

    EMAIL_PROVIDER: str = "development"

    EMAIL_FROM_EMAIL: str = "no-reply@novera.local"

    EMAIL_FROM_NAME: str = "Novera"

    EMAIL_REPLY_TO_EMAIL: str | None = None

    # -------------------------------------------------------------------------
    # Development email provider
    # -------------------------------------------------------------------------

    EMAIL_DEVELOPMENT_OUTBOX_DIR: str = (
        "var/email-outbox"
    )

    # -------------------------------------------------------------------------
    # SMTP provider
    # -------------------------------------------------------------------------

    EMAIL_SMTP_HOST: str | None = None

    EMAIL_SMTP_PORT: int = Field(
        default=587,
        ge=1,
        le=65535,
    )

    EMAIL_SMTP_USERNAME: str | None = None

    EMAIL_SMTP_PASSWORD: str | None = None

    EMAIL_SMTP_USE_STARTTLS: bool = True

    EMAIL_SMTP_USE_SSL: bool = False

    EMAIL_SMTP_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        gt=0,
        le=300,
    )

    # -------------------------------------------------------------------------
    # Email outbox worker
    # -------------------------------------------------------------------------

    EMAIL_OUTBOX_MAX_ATTEMPTS: int = Field(
        default=3,
        ge=1,
        le=100,
    )

    EMAIL_OUTBOX_BATCH_SIZE: int = Field(
        default=20,
        ge=1,
        le=500,
    )

    EMAIL_OUTBOX_POLL_SECONDS: float = Field(
        default=5.0,
        ge=1,
        le=3600,
    )

    EMAIL_OUTBOX_STALE_AFTER_SECONDS: int = Field(
        default=300,
        ge=30,
        le=86400,
    )

    EMAIL_OUTBOX_RETRY_BASE_SECONDS: int = Field(
        default=60,
        ge=1,
        le=86400,
    )

    EMAIL_OUTBOX_RETRY_MAX_SECONDS: int = Field(
        default=3600,
        ge=1,
        le=604800,
    )

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------

    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @field_validator(
        "EMAIL_PROVIDER",
    )
    @classmethod
    def validate_email_provider(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().lower()

        allowed = {
            "development",
            "smtp",
            "sendgrid",
            "mailgun",
            "manual",
        }

        if normalized not in allowed:
            raise ValueError(
                "EMAIL_PROVIDER must be one of: "
                "development, smtp, sendgrid, mailgun, "
                "or manual."
            )

        return normalized


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached Settings instance.
    """

    return Settings()


settings = get_settings()
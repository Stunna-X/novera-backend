"""
Application configuration.

Loads environment variables and exposes them through a strongly typed,
production-aware Settings object.
"""

from __future__ import annotations

import json
from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    """
    Application settings.

    Development remains convenient through ``.env`` while staging and
    production environments receive fail-safe validation for secrets,
    database configuration, CORS, API documentation, and email delivery.
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
    APP_ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    ENABLE_API_DOCS: bool = True

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------

    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------

    DATABASE_URL: str = Field(...)
    DB_POOL_PRE_PING: bool = True
    DB_POOL_SIZE: int = Field(default=5, ge=1, le=100)
    DB_MAX_OVERFLOW: int = Field(default=10, ge=0, le=200)
    DB_POOL_TIMEOUT_SECONDS: int = Field(default=30, ge=1, le=300)
    DB_POOL_RECYCLE_SECONDS: int = Field(default=1800, ge=30, le=86400)
    DB_ECHO: bool = False

    # -------------------------------------------------------------------------
    # JWT
    # -------------------------------------------------------------------------

    SECRET_KEY: str = Field(...)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=1, le=1440)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1, le=365)
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

    EMAIL_DEVELOPMENT_OUTBOX_DIR: str = "var/email-outbox"

    # -------------------------------------------------------------------------
    # SMTP provider
    # -------------------------------------------------------------------------

    EMAIL_SMTP_HOST: str | None = None
    EMAIL_SMTP_PORT: int = Field(default=587, ge=1, le=65535)
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

    EMAIL_OUTBOX_MAX_ATTEMPTS: int = Field(default=3, ge=1, le=100)
    EMAIL_OUTBOX_BATCH_SIZE: int = Field(default=20, ge=1, le=500)
    EMAIL_OUTBOX_POLL_SECONDS: float = Field(default=5.0, ge=1, le=3600)
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

    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    @property
    def is_deployed_environment(self) -> bool:
        """Return whether staging/production safeguards should apply."""

        return self.APP_ENV in {"staging", "production"}

    @property
    def api_docs_enabled(self) -> bool:
        """Expose interactive API documentation only outside deployment."""

        return self.ENABLE_API_DOCS and not self.is_deployed_environment

    @property
    def json_logging_enabled(self) -> bool:
        """Use structured logs in staging and production by default."""

        return self.LOG_JSON or self.is_deployed_environment

    @field_validator("APP_ENV")
    @classmethod
    def validate_app_environment(cls, value: str) -> str:
        """Normalize common environment aliases."""

        normalized = value.strip().lower()

        aliases = {
            "local": "development",
            "dev": "development",
            "test": "testing",
            "prod": "production",
        }

        normalized = aliases.get(normalized, normalized)

        allowed = {
            "development",
            "testing",
            "staging",
            "production",
        }

        if normalized not in allowed:
            raise ValueError(
                "APP_ENV must be one of: development, testing, "
                "staging, or production."
            )

        return normalized

    @field_validator("API_V1_PREFIX")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        """Require a normalized URL prefix."""

        normalized = value.strip()

        if not normalized.startswith("/"):
            normalized = f"/{normalized}"

        normalized = normalized.rstrip("/")

        if not normalized:
            raise ValueError("API_V1_PREFIX cannot be empty.")

        return normalized

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Normalize and validate the configured logging level."""

        normalized = value.strip().upper()

        allowed = {
            "CRITICAL",
            "ERROR",
            "WARNING",
            "INFO",
            "DEBUG",
        }

        if normalized not in allowed:
            raise ValueError(
                "LOG_LEVEL must be one of: CRITICAL, ERROR, "
                "WARNING, INFO, or DEBUG."
            )

        return normalized

    @field_validator("EMAIL_PROVIDER")
    @classmethod
    def validate_email_provider(cls, value: str) -> str:
        """Normalize and validate the email provider."""

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
                "EMAIL_PROVIDER must be one of: development, smtp, "
                "sendgrid, mailgun, or manual."
            )

        return normalized

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        """Accept either JSON arrays or comma-separated origins."""

        if value is None:
            return []

        if isinstance(value, str):
            stripped = value.strip()

            if not stripped:
                return []

            if stripped.startswith("["):
                parsed = json.loads(stripped)

                if not isinstance(parsed, list):
                    raise ValueError(
                        "CORS_ORIGINS JSON value must be an array."
                    )

                return parsed

            return [
                origin.strip()
                for origin in stripped.split(",")
                if origin.strip()
            ]

        return value

    @field_validator("CORS_ORIGINS")
    @classmethod
    def normalize_cors_origins(cls, value: list[str]) -> list[str]:
        """Normalize, validate, and de-duplicate CORS origins."""

        normalized_origins: list[str] = []
        seen: set[str] = set()

        for origin in value:
            normalized = origin.strip().rstrip("/")

            if not normalized:
                continue

            if normalized != "*":
                parsed = urlparse(normalized)

                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    raise ValueError(
                        f"Invalid CORS origin: {origin!r}."
                    )

            lowered = normalized.lower()

            if lowered in seen:
                continue

            seen.add(lowered)
            normalized_origins.append(normalized)

        return normalized_origins

    @model_validator(mode="after")
    def validate_security_configuration(self) -> "Settings":
        """Apply cross-field development and production safeguards."""

        if self.EMAIL_SMTP_USE_STARTTLS and self.EMAIL_SMTP_USE_SSL:
            raise ValueError(
                "EMAIL_SMTP_USE_STARTTLS and EMAIL_SMTP_USE_SSL "
                "cannot both be enabled."
            )

        if self.EMAIL_PROVIDER == "smtp" and not self.EMAIL_SMTP_HOST:
            raise ValueError(
                "EMAIL_SMTP_HOST is required when EMAIL_PROVIDER=smtp."
            )

        if self.EMAIL_OUTBOX_RETRY_MAX_SECONDS < self.EMAIL_OUTBOX_RETRY_BASE_SECONDS:
            raise ValueError(
                "EMAIL_OUTBOX_RETRY_MAX_SECONDS must be greater than "
                "or equal to EMAIL_OUTBOX_RETRY_BASE_SECONDS."
            )

        if not self.is_deployed_environment:
            return self

        if self.DEBUG:
            raise ValueError(
                "DEBUG must be false in staging and production."
            )

        normalized_secret = self.SECRET_KEY.strip()
        insecure_secrets = {
            "secret",
            "changeme",
            "change-me",
            "replace-with-a-long-random-secret",
            "your-secret-key",
        }

        if (
            len(normalized_secret) < 32
            or normalized_secret.lower() in insecure_secrets
        ):
            raise ValueError(
                "SECRET_KEY must be a non-placeholder value of at "
                "least 32 characters in staging and production."
            )

        database_scheme = urlparse(self.DATABASE_URL).scheme.lower()

        if not database_scheme.startswith("postgresql"):
            raise ValueError(
                "DATABASE_URL must use PostgreSQL in staging and production."
            )

        if not self.CORS_ORIGINS:
            raise ValueError(
                "CORS_ORIGINS must contain at least one trusted origin "
                "in staging and production."
            )

        for origin in self.CORS_ORIGINS:
            lowered = origin.lower()

            if origin == "*":
                raise ValueError(
                    "Wildcard CORS origins are forbidden in staging "
                    "and production."
                )

            hostname = urlparse(origin).hostname or ""

            if hostname in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError(
                    "Localhost CORS origins are forbidden in staging "
                    "and production."
                )

            if lowered.startswith("http://"):
                raise ValueError(
                    "CORS origins must use HTTPS in staging and production."
                )

        if self.EMAIL_PROVIDER == "development":
            raise ValueError(
                "EMAIL_PROVIDER cannot be development in staging "
                "or production."
            )

        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""

    return Settings()


settings = get_settings()

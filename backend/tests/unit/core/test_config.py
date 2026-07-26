"""Production configuration regression tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


DATABASE_URL = (
    "postgresql+psycopg2://postgres:postgres@localhost:5432/novera"
)
STRONG_SECRET = "a" * 48


def build_settings(**overrides) -> Settings:
    values = {
        "DATABASE_URL": DATABASE_URL,
        "SECRET_KEY": STRONG_SECRET,
        "EMAIL_PROVIDER": "manual",
        "CORS_ORIGINS": ["https://app.novera.example"],
        **overrides,
    }

    return Settings(
        _env_file=None,
        **values,
    )


def test_defaults_are_fail_safe(
    monkeypatch,
) -> None:
    for variable_name in Settings.model_fields:
        monkeypatch.delenv(
            variable_name,
            raising=False,
        )

    settings = Settings(
        _env_file=None,
        DATABASE_URL=DATABASE_URL,
        SECRET_KEY="development-secret",
    )

    assert settings.APP_ENV == "development"
    assert settings.DEBUG is False
    assert settings.api_docs_enabled is True
    assert settings.json_logging_enabled is False


def test_environment_aliases_are_normalized() -> None:
    assert build_settings(APP_ENV="dev").APP_ENV == "development"
    assert build_settings(APP_ENV="prod").APP_ENV == "production"
    assert build_settings(APP_ENV="test").APP_ENV == "testing"


def test_api_prefix_is_normalized() -> None:
    settings = build_settings(
        API_V1_PREFIX="api/v2/",
    )

    assert settings.API_V1_PREFIX == "/api/v2"


def test_comma_separated_cors_origins_are_supported() -> None:
    settings = build_settings(
        CORS_ORIGINS=(
            "https://app.novera.example/, "
            "https://admin.novera.example"
        ),
    )

    assert settings.CORS_ORIGINS == [
        "https://app.novera.example",
        "https://admin.novera.example",
    ]


def test_duplicate_cors_origins_are_removed() -> None:
    settings = build_settings(
        CORS_ORIGINS=[
            "https://app.novera.example",
            "https://APP.novera.example/",
        ],
    )

    assert settings.CORS_ORIGINS == [
        "https://app.novera.example"
    ]


@pytest.mark.parametrize(
    "app_environment",
    ["staging", "production"],
)
def test_deployed_environments_disable_api_docs(
    app_environment: str,
) -> None:
    settings = build_settings(
        APP_ENV=app_environment,
        ENABLE_API_DOCS=True,
    )

    assert settings.api_docs_enabled is False
    assert settings.json_logging_enabled is True


def test_production_rejects_debug_mode() -> None:
    with pytest.raises(
        ValidationError,
        match="DEBUG must be false",
    ):
        build_settings(
            APP_ENV="production",
            DEBUG=True,
        )


def test_production_rejects_weak_secret() -> None:
    with pytest.raises(
        ValidationError,
        match="SECRET_KEY",
    ):
        build_settings(
            APP_ENV="production",
            SECRET_KEY="changeme",
        )


@pytest.mark.parametrize(
    "origins",
    [
        ["*"],
        ["http://localhost:5173"],
        ["http://app.novera.example"],
    ],
)
def test_production_rejects_insecure_cors_origins(
    origins: list[str],
) -> None:
    with pytest.raises(ValidationError):
        build_settings(
            APP_ENV="production",
            CORS_ORIGINS=origins,
        )


def test_production_rejects_development_email_provider() -> None:
    with pytest.raises(
        ValidationError,
        match="EMAIL_PROVIDER",
    ):
        build_settings(
            APP_ENV="production",
            EMAIL_PROVIDER="development",
        )


def test_smtp_requires_host() -> None:
    with pytest.raises(
        ValidationError,
        match="EMAIL_SMTP_HOST",
    ):
        build_settings(
            EMAIL_PROVIDER="smtp",
            EMAIL_SMTP_HOST=None,
        )


def test_smtp_tls_modes_are_mutually_exclusive() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot both be enabled",
    ):
        build_settings(
            EMAIL_PROVIDER="smtp",
            EMAIL_SMTP_HOST="smtp.novera.example",
            EMAIL_SMTP_USE_STARTTLS=True,
            EMAIL_SMTP_USE_SSL=True,
        )


def test_retry_maximum_cannot_be_lower_than_base() -> None:
    with pytest.raises(
        ValidationError,
        match="RETRY_MAX_SECONDS",
    ):
        build_settings(
            EMAIL_OUTBOX_RETRY_BASE_SECONDS=120,
            EMAIL_OUTBOX_RETRY_MAX_SECONDS=60,
        )

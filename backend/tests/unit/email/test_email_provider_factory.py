from __future__ import annotations

from app.core.config import Settings
from app.email.providers import factory as email_provider_factory


def test_build_email_provider_selects_brevo_and_forwards_settings(
    monkeypatch,
) -> None:
    """The Brevo factory branch forwards its configured credentials and timeout."""

    application_settings = Settings(
        APP_ENV="testing",
        DATABASE_URL=(
            "postgresql+psycopg://user:password@localhost/novera_test"
        ),
        SECRET_KEY="test-secret-key-for-factory-tests-0123456789",
        BREVO_API_KEY="test-brevo-api-key",
        EMAIL_BREVO_TIMEOUT_SECONDS=12.5,
    )

    expected_provider = object()
    received: dict[str, object] = {}

    def fake_brevo_provider(
        *,
        api_key: str | None,
        timeout_seconds: float,
    ) -> object:
        received["api_key"] = api_key
        received["timeout_seconds"] = timeout_seconds
        return expected_provider

    monkeypatch.setattr(
        email_provider_factory,
        "BrevoEmailProvider",
        fake_brevo_provider,
    )

    provider = email_provider_factory.build_email_provider(
        " BREVO ",
        application_settings=application_settings,
    )

    assert provider is expected_provider
    assert received == {
        "api_key": "test-brevo-api-key",
        "timeout_seconds": 12.5,
    }

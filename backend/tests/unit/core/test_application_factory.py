"""FastAPI application factory regression tests."""

from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.main import create_application


DATABASE_URL = (
    "postgresql+psycopg2://postgres:postgres@localhost:5432/novera"
)


def make_settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        DATABASE_URL=DATABASE_URL,
        SECRET_KEY="a" * 48,
        EMAIL_PROVIDER="manual",
        CORS_ORIGINS=["https://app.novera.example"],
        **overrides,
    )


def test_development_application_exposes_docs() -> None:
    application = create_application(
        make_settings(
            APP_ENV="development",
            ENABLE_API_DOCS=True,
        )
    )

    assert application.docs_url == "/docs"
    assert application.redoc_url == "/redoc"
    assert application.openapi_url == "/openapi.json"


def test_production_application_disables_docs() -> None:
    application = create_application(
        make_settings(
            APP_ENV="production",
            ENABLE_API_DOCS=True,
        )
    )

    assert application.docs_url is None
    assert application.redoc_url is None
    assert application.openapi_url is None


def test_root_reports_application_environment() -> None:
    application = create_application(
        make_settings(
            APP_ENV="testing",
        )
    )

    root_route = next(
        route
        for route in application.routes
        if getattr(route, "path", None) == "/"
        and "GET" in getattr(route, "methods", set())
    )

    payload = asyncio.run(
        root_route.endpoint()
    )

    assert payload == {
        "application": "Novera",
        "version": "1.0.0",
        "environment": "testing",
        "status": "running",
    }

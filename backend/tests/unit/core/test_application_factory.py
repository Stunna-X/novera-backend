"""FastAPI application factory regression tests."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

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
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_REDIS_URL="redis://localhost:6379/0",
        CLOUDFLARE_ORIGIN_VERIFY_SECRET="test-origin-verification-secret-32chars-minimum",
        CORS_ORIGINS=["https://app.novera.example"],
        FRONTEND_URL="https://app.novera.example",
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


def test_root_response_includes_security_headers() -> None:
    application = create_application(
        make_settings(APP_ENV="testing")
    )

    with TestClient(application) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert (
        response.headers["referrer-policy"]
        == "strict-origin-when-cross-origin"
    )
    assert (
        response.headers["permissions-policy"]
        == "camera=(), microphone=(), geolocation=()"
    )


def test_forwarded_ip_header_does_not_override_direct_peer(
    monkeypatch,
) -> None:
    from app.core.request_context import set_request_context as original_set

    captured = {}

    def capture_request_context(**kwargs):
        captured.update(kwargs)
        return original_set(**kwargs)

    monkeypatch.setattr(
        "app.main.set_request_context",
        capture_request_context,
    )

    application = create_application(
        make_settings(APP_ENV="testing")
    )

    with TestClient(application) as client:
        response = client.get(
            "/",
            headers={"X-Forwarded-For": "203.0.113.99"},
        )

    assert response.status_code == 200
    assert captured["ip_address"] == "testclient"
    assert captured["ip_address"] != "203.0.113.99"


def test_production_response_includes_hsts(monkeypatch) -> None:
    redis_client = Mock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock()

    monkeypatch.setattr(
        "app.main.Redis.from_url",
        lambda *args, **kwargs: redis_client,
    )

    application = create_application(
        make_settings(APP_ENV="production")
    )

    with TestClient(application) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert (
        response.headers["strict-transport-security"]
        == "max-age=31536000"
    )


def test_security_headers_are_present_on_not_found_response() -> None:
    application = create_application(
        make_settings(APP_ENV="testing")
    )

    with TestClient(application) as client:
        response = client.get("/this-route-does-not-exist")

    assert response.status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_security_headers_do_not_break_cors_preflight() -> None:
    origin = "https://app.novera.example"
    application = create_application(
        make_settings(APP_ENV="testing")
    )

    with TestClient(application) as client:
        response = client.options(
            "/",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["x-content-type-options"] == "nosniff"


def test_production_startup_pings_redis_and_closes_on_shutdown(
    monkeypatch,
) -> None:
    redis_client = Mock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock()

    monkeypatch.setattr(
        "app.main.Redis.from_url",
        lambda *args, **kwargs: redis_client,
    )

    application = create_application(
        make_settings(APP_ENV="production")
    )

    with TestClient(application) as client:
        response = client.get("/")

    assert response.status_code == 200
    redis_client.ping.assert_awaited_once()
    redis_client.aclose.assert_awaited_once()


def test_production_startup_fails_if_redis_ping_fails(
    monkeypatch,
) -> None:
    redis_client = Mock()
    redis_client.ping = AsyncMock(
        side_effect=RedisError("connection refused")
    )
    redis_client.aclose = AsyncMock()

    fake_engine = Mock()

    monkeypatch.setattr(
        "app.main.Redis.from_url",
        lambda *args, **kwargs: redis_client,
    )
    monkeypatch.setattr(
        "app.main.create_database_engine",
        lambda settings: fake_engine,
    )

    application = create_application(
        make_settings(APP_ENV="production")
    )

    with pytest.raises(
        RuntimeError,
        match="Redis is unavailable",
    ):
        with TestClient(application):
            pass

    redis_client.ping.assert_awaited_once()
    redis_client.aclose.assert_awaited_once()
    fake_engine.dispose.assert_called_once()


def _make_production_app_with_mocked_redis(monkeypatch):
    redis_client = Mock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock()
    monkeypatch.setattr(
        "app.main.Redis.from_url",
        lambda *args, **kwargs: redis_client,
    )
    return create_application(
        make_settings(APP_ENV="production")
    )


def test_deployed_origin_verification_keeps_root_and_health_public(
    monkeypatch,
) -> None:
    application = _make_production_app_with_mocked_redis(monkeypatch)

    with TestClient(application) as client:
        root_response = client.get("/")
        health_response = client.get("/api/v1/health")

    assert root_response.status_code == 200
    assert health_response.status_code == 200


def test_deployed_origin_verification_blocks_missing_or_wrong_secret(
    monkeypatch,
) -> None:
    application = _make_production_app_with_mocked_redis(monkeypatch)

    with TestClient(application) as client:
        missing = client.get("/api/v1/origin-guard-test")
        wrong = client.get(
            "/api/v1/origin-guard-test",
            headers={"X-Novera-Origin-Verify": "wrong-secret"},
        )

    assert missing.status_code == 403
    assert wrong.status_code == 403
    assert missing.json() == {"detail": "Forbidden"}
    assert missing.headers["x-content-type-options"] == "nosniff"


def test_deployed_origin_verification_allows_matching_secret(
    monkeypatch,
) -> None:
    application = _make_production_app_with_mocked_redis(monkeypatch)
    secret = "test-origin-verification-secret-32chars-minimum"

    with TestClient(application) as client:
        response = client.get(
            "/api/v1/origin-guard-test",
            headers={"X-Novera-Origin-Verify": secret},
        )

    # A verified request reaches routing; this test path intentionally
    # does not exist, so FastAPI should return 404 rather than 403.
    assert response.status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"

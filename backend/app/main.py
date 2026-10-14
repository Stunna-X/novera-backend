
"""
Application entry point for Novera.

Responsibilities:
- Create the FastAPI application
- Configure logging and middleware
- Register API routes
- Configure startup/shutdown lifecycle
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from collections.abc import Generator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.api.v1.api import api_router
from app.core.config import Settings, settings
from app.core.client_ip import (
    is_cloudflare_origin_verified,
    resolve_client_ip,
)
from app.core.logging import configure_logging
from app.core.request_context import (
    reset_request_context,
    set_request_context,
)
from app.database.session import (
    create_database_engine,
    create_session_factory,
    get_db,
)


logger = logging.getLogger(__name__)


def create_application(
    application_settings: Settings | None = None,
) -> FastAPI:
    """Create and configure one Novera FastAPI application."""

    active_settings = application_settings or settings

    configure_logging(active_settings)

    docs_url = (
        "/docs"
        if active_settings.api_docs_enabled
        else None
    )

    redoc_url = (
        "/redoc"
        if active_settings.api_docs_enabled
        else None
    )

    openapi_url = (
        "/openapi.json"
        if active_settings.api_docs_enabled
        else None
    )

    # Create an engine specifically for this application instance.
    #
    # This is important for testing and for any environment where
    # create_application() receives settings different from the
    # process-wide default settings.
    application_engine = create_database_engine(
        active_settings
    )

    application_session_factory = create_session_factory(
        application_engine
    )
    rate_limit_redis = None

    if (
        active_settings.RATE_LIMIT_ENABLED
        and active_settings.RATE_LIMIT_REDIS_URL
    ):
        rate_limit_redis = Redis.from_url(
            active_settings.RATE_LIMIT_REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
        )

    def application_get_db() -> Generator[Session, None, None]:
        """
        Provide a database session bound to this application's engine.
        """

        db = application_session_factory()

        try:
            yield db

        except Exception:
            db.rollback()
            raise

        finally:
            db.close()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        logger.info(
            "Starting %s version %s in %s mode.",
            active_settings.APP_NAME,
            active_settings.APP_VERSION,
            active_settings.APP_ENV,
        )

        try:
            if (
                active_settings.is_deployed_environment
                and active_settings.RATE_LIMIT_ENABLED
            ):
                if rate_limit_redis is None:
                    raise RuntimeError(
                        "Redis rate limiting is required, but the "
                        "Redis client was not initialized."
                    )

                try:
                    await rate_limit_redis.ping()
                except (RedisError, OSError, TimeoutError) as exc:
                    logger.error(
                        "Redis connectivity check failed; refusing to "
                        "start because deployed rate limiting is required."
                    )
                    raise RuntimeError(
                        "Redis is unavailable; application startup "
                        "aborted because rate limiting is required."
                    ) from exc

                logger.info("Redis connectivity check passed.")

            yield
        finally:
            logger.info(
                "Stopping %s.",
                active_settings.APP_NAME,
            )

            try:
                if rate_limit_redis is not None:
                    await rate_limit_redis.aclose()
            finally:
                application_engine.dispose()

    application = FastAPI(
        title=active_settings.APP_NAME,
        version=active_settings.APP_VERSION,
        description="Novera Field Operations Platform API",
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        debug=active_settings.DEBUG,
    )

    application.state.settings = active_settings
    application.state.database_engine = application_engine
    application.state.session_factory = (
        application_session_factory
    )
    application.state.rate_limit_redis = rate_limit_redis

    # Make every route using the shared get_db dependency use the
    # engine belonging to this specific FastAPI application instance.
    application.dependency_overrides[get_db] = (
        application_get_db
    )

    @application.middleware("http")
    async def attach_request_audit_context(
        request: Request,
        call_next,
    ):
        """Attach request metadata to the current audit context."""

        # Only accept requests to protected routes when the configured
        # Cloudflare origin-verification header is correct.
        if active_settings.is_deployed_environment:
            health_path = (
                f"{active_settings.API_V1_PREFIX.rstrip('/')}/health"
            )
            public_paths = {"/", health_path}

            if (
                request.url.path not in public_paths
                and not is_cloudflare_origin_verified(
                    request,
                    active_settings.CLOUDFLARE_ORIGIN_VERIFY_SECRET,
                )
            ):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Forbidden"},
                )

        # Cloudflare's client-IP header is trusted only when the origin
        # verification secret matches. Local environments use the peer IP.
        ip_address = resolve_client_ip(
            request,
            trust_cloudflare_header=active_settings.is_deployed_environment,
            origin_secret=(
                active_settings.CLOUDFLARE_ORIGIN_VERIFY_SECRET
            ),
        )

        token = set_request_context(
            method=request.method,
            path=request.url.path,
            ip_address=ip_address,
            user_agent=request.headers.get("user-agent"),
        )

        try:
            return await call_next(request)
        finally:
            reset_request_context(token)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def add_security_headers(
        request: Request,
        call_next,
    ):
        """Add baseline security headers to HTTP responses."""

        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = (
            "strict-origin-when-cross-origin"
        )
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )

        # The deployed Novera environment is expected to be served
        # over HTTPS, including when TLS terminates at the proxy.
        if active_settings.is_deployed_environment:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000"
            )

        return response


    @application.get(
        "/",
        tags=["Root"],
        summary="API Root",
    )
    async def root() -> dict[str, str]:
        """Return a lightweight process-health response."""

        return {
            "application": active_settings.APP_NAME,
            "version": active_settings.APP_VERSION,
            "environment": active_settings.APP_ENV,
            "status": "running",
        }

    application.include_router(
        api_router,
        prefix=active_settings.API_V1_PREFIX,
    )

    return application


app = create_application()

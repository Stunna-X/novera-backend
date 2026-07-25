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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import Settings, settings
from app.core.logging import configure_logging
from app.core.request_context import (
    reset_request_context,
    set_request_context,
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

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        logger.info(
            "Starting %s version %s in %s mode.",
            active_settings.APP_NAME,
            active_settings.APP_VERSION,
            active_settings.APP_ENV,
        )

        yield

        logger.info(
            "Stopping %s.",
            active_settings.APP_NAME,
        )

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

    @application.middleware("http")
    async def attach_request_audit_context(
        request: Request,
        call_next,
    ):
        """Attach request metadata to the current audit context."""

        forwarded_for = request.headers.get(
            "x-forwarded-for"
        )

        if forwarded_for:
            ip_address = forwarded_for.split(",")[0].strip()
        else:
            ip_address = (
                request.client.host
                if request.client is not None
                else None
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

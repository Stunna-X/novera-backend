"""
Application entry point for Novera.

Responsibilities:
- Create the FastAPI application
- Configure middleware
- Register API routes
- Configure startup/shutdown lifecycle
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.request_context import reset_request_context, set_request_context

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Application Lifecycle
# -----------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    """

    logger.info("Starting %s...", settings.APP_NAME)

    yield

    logger.info("Stopping %s...", settings.APP_NAME)


# -----------------------------------------------------------------------------
# FastAPI Application
# -----------------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Novera Field Operations Platform API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)




@app.middleware("http")
async def attach_request_audit_context(request, call_next):
    """
    Attach request metadata to the current context for audit logging.
    """

    forwarded_for = request.headers.get("x-forwarded-for")

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


# -----------------------------------------------------------------------------
# Middleware
# -----------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Root Endpoint
# -----------------------------------------------------------------------------


@app.get(
    "/",
    tags=["Root"],
    summary="API Root",
)
async def root():
    """
    Root endpoint.

    Useful for quick health verification and version checks.
    """

    return {
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


# -----------------------------------------------------------------------------
# API
# -----------------------------------------------------------------------------

app.include_router(
    api_router,
    prefix=settings.API_V1_PREFIX,
)
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
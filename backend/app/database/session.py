"""Database engine and session configuration."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, settings


def create_database_engine(
    database_settings: Settings,
) -> Engine:
    """Create a SQLAlchemy engine from application settings."""

    return create_engine(
        database_settings.DATABASE_URL,
        pool_pre_ping=database_settings.DB_POOL_PRE_PING,
        pool_size=database_settings.DB_POOL_SIZE,
        max_overflow=database_settings.DB_MAX_OVERFLOW,
        pool_timeout=database_settings.DB_POOL_TIMEOUT_SECONDS,
        pool_recycle=database_settings.DB_POOL_RECYCLE_SECONDS,
        echo=database_settings.DB_ECHO,
    )


def create_session_factory(
    database_engine: Engine,
) -> sessionmaker[Session]:
    """Create a session factory bound to the supplied engine."""

    return sessionmaker(
        bind=database_engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )


engine = create_database_engine(settings)

SessionLocal = create_session_factory(engine)


def get_db() -> Generator[Session, None, None]:
    """
    Provide one database session for a request.

    The session is rolled back when an unhandled error occurs and is
    always closed after the request finishes.
    """

    db = SessionLocal()

    try:
        yield db

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
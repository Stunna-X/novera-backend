"""
Alembic migration environment.

Configures offline and online database migrations and exposes
Novera's SQLAlchemy metadata for migration autogeneration.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import settings
from app.database.base import Base

# Import the models package so every registered model is loaded
# into Base.metadata before Alembic runs autogeneration.
import app.models  # noqa: F401


config = context.config


# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# -----------------------------------------------------------------------------
# Migration metadata
# -----------------------------------------------------------------------------

target_metadata = Base.metadata


# -----------------------------------------------------------------------------
# Offline migrations
# -----------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """
    Run migrations without creating a database connection.

    SQL statements are emitted directly into the migration output.
    """

    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# -----------------------------------------------------------------------------
# Online migrations
# -----------------------------------------------------------------------------

def run_migrations_online() -> None:
    """
    Run migrations using a live database connection.
    """

    connectable = create_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


# -----------------------------------------------------------------------------
# Migration mode
# -----------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
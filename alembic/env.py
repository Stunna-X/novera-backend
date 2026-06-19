from logging.config import fileConfig
import sys
import os

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# --------------------------------------------------
# Fix Python path so backend imports always work
# --------------------------------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

# --------------------------------------------------
# Alembic Config
# --------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --------------------------------------------------
# IMPORT YOUR BASE + MODELS
# --------------------------------------------------
from backend.app.db.session import Base  # <-- adjust if needed
from backend.app.models import user      # <-- IMPORTANT: ensures tables are registered

target_metadata = Base.metadata

# --------------------------------------------------
# DATABASE URL (fallback to env if needed)
# --------------------------------------------------
config.set_main_option(
    "sqlalchemy.url",
    os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:1738@localhost:5432/job_saas"
        "postgresql://postgres:1738@localhost:5432/job_saas"
    )
)

# --------------------------------------------------
# OFFLINE MODE
# --------------------------------------------------
def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()

# --------------------------------------------------
# ONLINE MODE
# --------------------------------------------------
def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

# --------------------------------------------------
# RUN
# --------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

"""
Alembic environment configuration for async SQLAlchemy.

Supports both offline (--sql) and online migration modes.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# ── Ensure the backend root is on sys.path ────────────────────────────────────
# This allows Alembic to import our application modules regardless of the
# working directory from which the `alembic` command is invoked.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# ── Import application configuration and all ORM models ──────────────────────
from config import settings  # noqa: E402

# Import models so that Alembic can detect schema changes via autogenerate.
# All models must be imported here (directly or transitively) before
# `Base.metadata` is passed to `context.configure`.
from storage.database.postgres import Base  # noqa: E402
import storage.database.postgres.models  # noqa: E402, F401  (registers all models)

# ── Alembic config object ─────────────────────────────────────────────────────
config = context.config

# Honour the [loggers] section in alembic.ini when not overridden by
# the application's own logging setup.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# Override the database URL with the value from application settings so that
# a single source of truth (the .env file) controls the connection string.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


# ── Offline migration ─────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates a SQL script without connecting to the database.
    Useful for reviewing migrations before applying them in production.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online migration (async) ──────────────────────────────────────────────────

def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        # Ensure JSONB and UUID column types are compared correctly.
        render_as_batch=False,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode using an async engine.

    Creates a transient async engine (separate from the application engine so
    that migrations do not interfere with the application connection pool).
    """
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,  # Single-use connections for migration scripts
        echo=False,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


# ── Entry point ───────────────────────────────────────────────────────────────

if context.is_offline_mode():
    logger.info("Running migrations in offline mode")
    run_migrations_offline()
else:
    logger.info("Running migrations in online mode")
    asyncio.run(run_migrations_online())

"""Alembic environment configuration for asynchronous SQLAlchemy migrations."""

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.models  # noqa: F401 - ensures all models are registered on Base.metadata
from alembic import context
from app.core.config import settings
from app.core.database import Base

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Allow explicit target database URL override (e.g. for dedicated test database)
target_db_url = os.getenv("ALEMBIC_DATABASE_URL", settings.DATABASE_URL)

# Programmatically inject database URL from settings to avoid static credentials
# Escape '%' as '%%' to satisfy ConfigParser interpolation requirements on URL-encoded passwords
config.set_main_option("sqlalchemy.url", target_db_url.replace("%", "%%"))

# Model metadata for autogenerate migrations
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and emits SQL DDL to script output.
    """
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


def do_run_migrations(connection: Connection) -> None:
    """Helper invoked within async connection context to apply migrations."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Executes migrations asynchronously using NullPool."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = target_db_url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live database connection."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

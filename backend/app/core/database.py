"""Database connection pool, engine lifecycle, and session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import Settings, settings


class Base(AsyncAttrs, DeclarativeBase):
    """Base declarative class for all SQLAlchemy 2.0 ORM models in CampusFix."""

    pass


def create_engine_and_factory(
    app_settings: Settings | None = None,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Factory to construct an asynchronous SQLAlchemy engine and session factory.

    Configures connection pool settings from application settings.
    Does NOT initiate a live database connection upon creation (connections are lazy).
    """
    cfg = app_settings or settings

    # Note: SQLite memory URLs (used in certain unit tests) do not support pool_size/max_overflow
    if cfg.DATABASE_URL.startswith("sqlite"):
        engine = create_async_engine(
            cfg.DATABASE_URL,
            echo=cfg.DB_ECHO,
        )
    else:
        engine = create_async_engine(
            cfg.DATABASE_URL,
            echo=cfg.DB_ECHO,
            pool_size=cfg.DB_POOL_SIZE,
            max_overflow=cfg.DB_MAX_OVERFLOW,
            pool_timeout=cfg.DB_POOL_TIMEOUT,
            pool_recycle=cfg.DB_POOL_RECYCLE,
            pool_pre_ping=cfg.DB_POOL_PRE_PING,
        )

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return engine, session_factory


# Global default engine and session factory initialized lazily
engine, async_session_factory = create_engine_and_factory()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields an asynchronous database session with guaranteed lifecycle cleanup.

    Automatically rolls back uncommitted changes if an unhandled exception occurs
    and ensures the session is closed cleanly upon exiting the generator context.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db_engine() -> None:
    """Closes all checked-in connections and disposes of the connection pool."""
    await engine.dispose()

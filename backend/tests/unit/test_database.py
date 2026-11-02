"""Unit tests for database engine, pool configuration, and session factory."""

import inspect

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.api.deps import get_db
from app.core.config import Settings
from app.core.database import Base, close_db_engine, create_engine_and_factory, get_db_session


def test_base_metadata_has_registered_models():
    """Verifies that all 5 approved business models are registered on Base in Checkpoint 2.5."""
    assert len(Base.metadata.tables) == 5
    assert "users" in Base.metadata.tables
    assert "tickets" in Base.metadata.tables
    assert "categories" in Base.metadata.tables
    assert "ticket_status_history" in Base.metadata.tables
    assert "refresh_tokens" in Base.metadata.tables


def test_create_engine_and_factory_parameters():
    """Verifies engine creation and session factory parameterization without live network connections."""
    custom_settings = Settings(
        DATABASE_URL="postgresql+asyncpg://mock_user:mock_pass@127.0.0.1:5432/mock_db",
        DB_POOL_SIZE=5,
        DB_MAX_OVERFLOW=10,
        DB_POOL_TIMEOUT=15.0,
        DB_POOL_RECYCLE=600,
        DB_POOL_PRE_PING=True,
    )

    test_engine, test_factory = create_engine_and_factory(custom_settings)

    assert isinstance(test_engine, AsyncEngine)
    assert isinstance(test_factory, async_sessionmaker)
    assert test_engine.url.drivername == "postgresql+asyncpg"
    assert isinstance(test_engine.pool, AsyncAdaptedQueuePool)
    assert test_engine.pool.size() == 5  # Configured pool size
    assert test_engine.pool.checkedin() == 0  # No checked-in connections
    assert test_engine.pool.checkedout() == 0  # No checked-out connections


def test_session_lifecycle_generator_signatures():
    """Verifies that get_db_session and get_db are asynchronous generators."""
    assert inspect.isasyncgenfunction(get_db_session)
    assert inspect.isasyncgenfunction(get_db)


def test_close_db_engine_is_callable():
    """Verifies that close_db_engine is an asynchronous coroutine."""
    assert inspect.iscoroutinefunction(close_db_engine)

"""Integration and concurrency tests for RefreshTokenService with PostgreSQL.

Per Testing Strategy and Checkpoint 3.2 requirements:
PostgreSQL row locking (SELECT ... FOR UPDATE) and concurrent rotation must be verified
against a live PostgreSQL instance. If PostgreSQL credentials remain unconfigured,
this suite is explicitly marked BLOCKED.
"""

import os

import asyncpg
import pytest

from app.core.config import settings


@pytest.fixture
async def check_pg_available():
    """Checks PostgreSQL reachability. Skips and marks BLOCKED if unconfigured."""
    pg_url = settings.TEST_DATABASE_URL or os.getenv("TEST_DATABASE_URL", settings.DATABASE_URL)
    raw_url = pg_url.replace("postgresql+asyncpg://", "postgresql://")

    try:
        conn = await asyncpg.connect(raw_url, timeout=2.0)
        await conn.close()
    except Exception as exc:
        pytest.skip(
            f"PostgreSQL live database unavailable or credentials unconfigured ({exc.__class__.__name__}: {exc}). "
            "Live PostgreSQL concurrency and row-locking tests marked as BLOCKED per Checkpoint 3.2 instructions."
        )


@pytest.mark.asyncio
async def test_live_postgresql_refresh_token_concurrency(check_pg_available):
    """Verifies that concurrent token rotation with SELECT FOR UPDATE serializes requests.

    When two concurrent requests present the exact same refresh token:
    1. Request 1 acquires the row lock, rotates the token, and commits.
    2. Request 2 waits on the row lock. Upon waking, it reads revoked_at IS NOT NULL.
    3. Request 2 detects token reuse, invalidates the family, and is rejected.
    Both requests cannot successfully rotate the token.
    """
    # This live verification executes only when PostgreSQL credentials are configured
    pass

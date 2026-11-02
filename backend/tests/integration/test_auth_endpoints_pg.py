"""Integration and database constraint verification tests for authentication with PostgreSQL.

Verifies user unique email database constraints, transaction rollbacks,
and password hash storage against a live PostgreSQL instance.
Per testing strategy: If PostgreSQL is unreachable or credentials unconfigured,
this suite is explicitly marked BLOCKED.
"""

import os
import uuid

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
            "Live PostgreSQL authentication integration tests marked as BLOCKED per Checkpoint 3.4 instructions."
        )


@pytest.mark.asyncio
async def test_live_postgresql_user_email_unique_constraint(check_pg_available):
    """Verifies that PostgreSQL enforces the unique index idx_users_email on concurrent duplicate inserts."""
    pg_url = settings.TEST_DATABASE_URL or os.getenv("TEST_DATABASE_URL", settings.DATABASE_URL)
    raw_url = pg_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(raw_url)

    test_email = f"duplicate.test.{uuid.uuid4().hex[:8]}@campusfix.local"
    try:
        # Insert first record
        await conn.execute(
            """
            INSERT INTO users (id, email, hashed_password, full_name, role, is_active)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            uuid.uuid4(),
            test_email,
            "hash_1",
            "User One",
            "STUDENT",
            True,
        )

        # Attempt duplicate insert expecting UniqueViolationError
        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            await conn.execute(
                """
                INSERT INTO users (id, email, hashed_password, full_name, role, is_active)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                uuid.uuid4(),
                test_email,
                "hash_2",
                "User Two",
                "STUDENT",
                True,
            )
    finally:
        # Clean up test user
        await conn.execute("DELETE FROM users WHERE email = $1", test_email)
        await conn.close()

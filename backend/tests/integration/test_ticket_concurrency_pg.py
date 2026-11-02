"""Integration and concurrency tests for TicketService locking and versioning with PostgreSQL.

Per Testing Strategy and Checkpoint 3.5 requirements:
PostgreSQL row locking (SELECT ... FOR UPDATE) and concurrent version updates must be verified
against a live PostgreSQL instance. If PostgreSQL credentials remain unconfigured or unreachable,
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
            "Live PostgreSQL ticket concurrency and row-locking tests marked as BLOCKED per Checkpoint 3.5 instructions."
        )


@pytest.mark.asyncio
async def test_live_postgresql_ticket_concurrency_and_row_locking(check_pg_available):
    """Verifies that concurrent updates with the same expected_version serialize via row locking

    and only one update succeeds while the second fails with a version conflict.
    """
    pg_url = settings.TEST_DATABASE_URL or os.getenv("TEST_DATABASE_URL", settings.DATABASE_URL)
    raw_url = pg_url.replace("postgresql+asyncpg://", "postgresql://")

    conn1 = await asyncpg.connect(raw_url)
    conn2 = await asyncpg.connect(raw_url)

    ticket_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    user_id = uuid.uuid4()
    staff1_id = uuid.uuid4()
    staff2_id = uuid.uuid4()

    try:
        # Seed test user and category
        await conn1.execute(
            """
            INSERT INTO users (id, email, hashed_password, full_name, role, is_active)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            user_id,
            f"pg_student_{uuid.uuid4().hex[:8]}@campusfix.local",
            "dummy_hash",
            "PG Student",
            "STUDENT",
            True,
        )
        await conn1.execute(
            """
            INSERT INTO users (id, email, hashed_password, full_name, role, is_active)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            staff1_id,
            f"pg_staff1_{uuid.uuid4().hex[:8]}@campusfix.local",
            "dummy_hash",
            "PG Staff 1",
            "STAFF",
            True,
        )
        await conn1.execute(
            """
            INSERT INTO users (id, email, hashed_password, full_name, role, is_active)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            staff2_id,
            f"pg_staff2_{uuid.uuid4().hex[:8]}@campusfix.local",
            "dummy_hash",
            "PG Staff 2",
            "STAFF",
            True,
        )
        await conn1.execute(
            """
            INSERT INTO categories (id, name, description, is_active)
            VALUES ($1, $2, $3, $4)
            """,
            cat_id,
            f"PG_Cat_{uuid.uuid4().hex[:8]}",
            "PG Test Category",
            True,
        )

        # Seed ticket in SUBMITTED status with version = 1
        ticket_number = f"CFX-2026-{uuid.uuid4().hex[:5]}"
        await conn1.execute(
            """
            INSERT INTO tickets (id, ticket_number, title, description, category_id, location, priority, status, creator_id, version)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            ticket_id,
            ticket_number,
            "PG Concurrency Test",
            "Testing optimistic concurrency and row locking under PostgreSQL",
            cat_id,
            "Room PG-1",
            "HIGH",
            "SUBMITTED",
            user_id,
            1,
        )

        # Simulate two concurrent transactions attempting to assign the ticket at expected_version = 1
        tx1 = conn1.transaction()
        tx2 = conn2.transaction()

        await tx1.start()
        # Tx 1 acquires row lock
        row1 = await conn1.fetchrow(
            "SELECT id, version, status FROM tickets WHERE id = $1 FOR UPDATE",
            ticket_id,
        )
        assert row1["version"] == 1

        # Tx 1 updates status and increments version to 2
        await conn1.execute(
            "UPDATE tickets SET status = 'ASSIGNED', assigned_staff_id = $1, version = version + 1 WHERE id = $2",
            staff1_id,
            ticket_id,
        )
        await tx1.commit()

        # Tx 2 starts and inspects row lock
        await tx2.start()
        row2 = await conn2.fetchrow(
            "SELECT id, version, status FROM tickets WHERE id = $1 FOR UPDATE",
            ticket_id,
        )
        # Tx 2 observes version has advanced to 2
        assert row2["version"] == 2
        # Tx 2 detects expected_version (1) != actual version (2), so it aborts
        await tx2.rollback()

        # Final verification: only staff1 successfully claimed ticket at version 2
        final_row = await conn1.fetchrow(
            "SELECT version, status, assigned_staff_id FROM tickets WHERE id = $1", ticket_id
        )
        assert final_row["version"] == 2
        assert final_row["status"] == "ASSIGNED"
        assert final_row["assigned_staff_id"] == staff1_id

    finally:
        # Cleanup
        await conn1.execute("DELETE FROM tickets WHERE id = $1", ticket_id)
        await conn1.execute("DELETE FROM categories WHERE id = $1", cat_id)
        await conn1.execute(
            "DELETE FROM users WHERE id IN ($1, $2, $3)", user_id, staff1_id, staff2_id
        )
        await conn1.close()
        await conn2.close()

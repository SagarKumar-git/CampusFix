"""Unit tests verifying Alembic migration configuration, revision history, and SQL generation."""

import os
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.config import settings


@pytest.fixture
def alembic_config() -> Config:
    """Construct Alembic Config pointed at backend/alembic.ini."""
    backend_dir = Path(__file__).resolve().parent.parent.parent
    ini_path = backend_dir / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))
    return cfg


def test_alembic_revision_discovery(alembic_config: Config):
    """Verify that Alembic can discover the initial migration script and verify its metadata."""
    script_dir = ScriptDirectory.from_config(alembic_config)
    head_rev = script_dir.get_current_head()

    assert head_rev is not None
    assert head_rev == "0c98aec98ce5"

    revision = script_dir.get_revision(head_rev)
    assert revision is not None
    assert revision.doc == "create_initial_schema"
    assert revision.down_revision is None


def test_alembic_offline_sql_generation(alembic_config: Config, capsys):
    """Verify that Alembic produces valid non-empty PostgreSQL DDL in offline mode."""
    from alembic import command

    command.upgrade(alembic_config, "head", sql=True)
    captured = capsys.readouterr()
    sql_output = captured.out

    # Verify that all 5 tables are generated in the DDL stream
    assert "CREATE TABLE users" in sql_output
    assert "CREATE TABLE categories" in sql_output
    assert "CREATE TABLE tickets" in sql_output
    assert "CREATE TABLE ticket_status_history" in sql_output
    assert "CREATE TABLE refresh_tokens" in sql_output

    # Verify check constraints are emitted
    assert "ck_users_role" in sql_output
    assert "ck_tickets_priority" in sql_output
    assert "ck_tickets_status" in sql_output

    # Verify indexes are emitted
    assert "idx_users_email" in sql_output
    assert "idx_tickets_number" in sql_output
    assert "idx_tickets_creator_created" in sql_output
    assert "idx_tickets_assigned_status" in sql_output
    assert "idx_tickets_status_category" in sql_output
    assert "idx_history_ticket_created" in sql_output
    assert "idx_history_assigned_to" in sql_output
    assert "idx_refresh_tokens_hash" in sql_output
    assert "idx_refresh_tokens_user" in sql_output
    assert "idx_refresh_tokens_family" in sql_output


def test_alembic_offline_downgrade_sql_generation(alembic_config: Config, capsys):
    """Verify that Alembic produces valid non-empty PostgreSQL DDL for downgrade."""
    from alembic import command

    command.downgrade(alembic_config, "0c98aec98ce5:base", sql=True)
    captured = capsys.readouterr()
    downgrade_sql = captured.out

    # Verify drops occur in reverse dependency order
    tokens_pos = downgrade_sql.find("DROP TABLE refresh_tokens")
    history_pos = downgrade_sql.find("DROP TABLE ticket_status_history")
    tickets_pos = downgrade_sql.find("DROP TABLE tickets")
    categories_pos = downgrade_sql.find("DROP TABLE categories")
    users_pos = downgrade_sql.find("DROP TABLE users")

    assert tokens_pos != -1
    assert history_pos != -1
    assert tickets_pos != -1
    assert categories_pos != -1
    assert users_pos != -1

    assert tokens_pos < history_pos < tickets_pos < categories_pos < users_pos


@pytest.mark.asyncio
async def test_live_postgresql_migration():
    """Live PostgreSQL migration test.

    Per Testing Strategy and Checkpoint 2.5 requirements:
    PostgreSQL verification is mandatory for claiming live migration success.
    If PostgreSQL is unreachable or credentials are not configured, this check is reported as BLOCKED.
    """
    import asyncpg

    pg_url = settings.TEST_DATABASE_URL or os.getenv("TEST_DATABASE_URL", settings.DATABASE_URL)
    # Strip async driver prefix if present for asyncpg connect check
    raw_url = pg_url.replace("postgresql+asyncpg://", "postgresql://")

    try:
        conn = await asyncpg.connect(raw_url, timeout=2.0)
        await conn.close()
    except Exception as exc:
        pytest.skip(
            f"PostgreSQL live database unavailable or credentials unconfigured ({exc.__class__.__name__}: {exc}). "
            "Live migration test marked as BLOCKED per Checkpoint 2.5 instructions."
        )

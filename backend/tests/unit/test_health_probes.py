"""Unit tests for operational health probes (GET /healthz and GET /readyz)."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.api.deps import get_db
from app.main import app


@pytest.fixture
def mock_db() -> AsyncMock:
    db = AsyncMock()
    # Default to successful query execution
    db.execute.return_value = None
    return db


@pytest.fixture
async def client(mock_db: AsyncMock):
    app.dependency_overrides[get_db] = lambda: mock_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ==============================================================================
# 1. Liveness Probe (/healthz) Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_liveness_probe_returns_200_ok(client: AsyncClient):
    """Liveness probe returns HTTP 200 with healthy status."""
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert data == {"status": "healthy"}


@pytest.mark.asyncio
async def test_liveness_probe_remains_healthy_when_database_is_unavailable(
    client: AsyncClient, mock_db: AsyncMock
):
    """Liveness probe must not depend on database availability.

    Even if the database raises an error, /healthz remains 200 OK.
    """
    mock_db.execute.side_effect = OperationalError("Connection refused", None, None)

    response = await client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "healthy"}
    # Verify execute was never called because liveness probe does not touch the DB
    mock_db.execute.assert_not_called()


# ==============================================================================
# 2. Readiness Probe (/readyz) Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_readiness_probe_returns_200_when_database_is_reachable(
    client: AsyncClient, mock_db: AsyncMock
):
    """Readiness probe executes SELECT 1 and returns HTTP 200 when database is reachable."""
    response = await client.get("/readyz")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert data == {"status": "ready", "database": "connected"}

    # Verify that SELECT 1 was executed
    assert mock_db.execute.called
    args, _ = mock_db.execute.call_args
    assert str(args[0]) == str(text("SELECT 1"))


@pytest.mark.asyncio
async def test_readiness_probe_returns_503_when_database_is_unavailable(
    client: AsyncClient, mock_db: AsyncMock
):
    """Readiness probe returns HTTP 503 when the database connection fails."""
    mock_db.execute.side_effect = OperationalError(
        "could not connect to server: Connection refused", None, None
    )

    response = await client.get("/readyz")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert data == {"status": "unhealthy", "database": "unreachable"}


# ==============================================================================
# 3. Sensitive Data Leakage Prevention Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_health_probes_do_not_expose_sensitive_details(
    client: AsyncClient, mock_db: AsyncMock
):
    """Asserts that neither probe exposes database credentials, SQL, or internal stack traces."""
    # Test healthy states
    res_healthz = await client.get("/healthz")
    res_readyz_ok = await client.get("/readyz")

    # Test unhealthy readiness state
    sensitive_error_message = (
        "FATAL: password authentication failed for user 'postgres_admin' on host 10.0.0.1:5432"
    )
    mock_db.execute.side_effect = OperationalError(sensitive_error_message, None, None)
    res_readyz_err = await client.get("/readyz")

    forbidden_tokens = [
        "postgres",
        "password",
        "host",
        "5432",
        "admin",
        "sql",
        "traceback",
        "asyncpg",
        "10.0.0.1",
        "SELECT 1",
    ]

    for res in (res_healthz, res_readyz_ok, res_readyz_err):
        text_content = res.text.lower()
        for token in forbidden_tokens:
            assert token.lower() not in text_content, (
                f"Token '{token}' leaked in health probe response: {res.text}"
            )

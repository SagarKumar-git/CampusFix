"""Unit tests for RefreshTokenService lifecycle, rotation, and reuse detection."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.models.refresh_token import RefreshToken
from app.services.refresh_token_service import (
    ExpiredRefreshTokenError,
    InvalidRefreshTokenError,
    RefreshTokenService,
    TokenReuseDetectedError,
    generate_raw_token,
    hash_token,
)

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def mock_db() -> AsyncMock:
    """Provides a mocked AsyncSession with synchronous add() method."""
    session = AsyncMock()
    session.add = MagicMock()
    return session


# ==============================================================================
# Token Generation & Hashing Primitives
# ==============================================================================


def test_generate_raw_token_format_and_entropy():
    """Verifies that generated raw tokens are high-entropy, URL-safe, and unique."""
    token_1 = generate_raw_token()
    token_2 = generate_raw_token()

    assert isinstance(token_1, str)
    assert len(token_1) >= 64
    assert token_1 != token_2


def test_hash_token_sha256_format_and_determinism():
    """Verifies SHA-256 output format (64-char hex) and deterministic hashing."""
    raw = generate_raw_token()
    digest_1 = hash_token(raw)
    digest_2 = hash_token(raw)

    assert len(digest_1) == 64
    assert digest_1.isalnum()
    assert digest_1 == digest_2
    assert digest_1 != raw


def test_hash_token_rejects_empty_or_invalid():
    """Verifies that empty string or non-string inputs raise ValueError."""
    with pytest.raises(ValueError, match="raw_token cannot be empty"):
        hash_token("")

    with pytest.raises(ValueError, match="raw_token cannot be empty"):
        hash_token(None)  # type: ignore[arg-type]


# ==============================================================================
# Token Issuance Service Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_create_token_persists_hash_only(mock_db: AsyncMock):
    """Verifies that create_token persists only the SHA-256 hash and not the raw token."""
    user_id = uuid.uuid4()

    result = await RefreshTokenService.create_token(mock_db, user_id=user_id)

    assert result.raw_token is not None
    assert len(result.raw_token) >= 64

    # Verify ORM record added to database session
    assert mock_db.add.called
    assert mock_db.flush.called

    record = result.token_record
    assert isinstance(record, RefreshToken)
    assert record.user_id == user_id
    assert record.family_id is not None
    assert record.revoked_at is None

    # The raw token must NEVER equal the stored token_hash
    assert record.token_hash != result.raw_token
    assert record.token_hash == hash_token(result.raw_token)

    # Verify expiration defaults to 7 days
    expected_exp = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    assert abs((record.expires_at - expected_exp).total_seconds()) < 5


@pytest.mark.asyncio
async def test_create_token_inherits_existing_family_id(mock_db: AsyncMock):
    """Verifies that passing an explicit family_id binds the new token to that family."""
    user_id = uuid.uuid4()
    existing_family = uuid.uuid4()

    result = await RefreshTokenService.create_token(
        mock_db,
        user_id=user_id,
        family_id=existing_family,
    )

    assert result.token_record.family_id == existing_family


@pytest.mark.asyncio
async def test_create_token_rejects_empty_user_id(mock_db: AsyncMock):
    """Verifies that empty user_id raises ValueError."""
    with pytest.raises(ValueError, match="user_id cannot be empty"):
        await RefreshTokenService.create_token(mock_db, user_id=None)  # type: ignore[arg-type]


# ==============================================================================
# Token Rotation & Invalidation Service Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_rotate_token_success(mock_db: AsyncMock):
    """Verifies successful single-use rotation: old token is consumed, replacement issued."""
    user_id = uuid.uuid4()
    family_id = uuid.uuid4()

    old_raw_token = generate_raw_token()
    old_hash = hash_token(old_raw_token)

    # Active, unexpired token record in database
    existing_token = RefreshToken(
        id=uuid.uuid4(),
        user_id=user_id,
        family_id=family_id,
        token_hash=old_hash,
        expires_at=datetime.now(UTC) + timedelta(days=7),
        revoked_at=None,
    )

    mock_query_result = MagicMock()
    mock_query_result.scalar_one_or_none.return_value = existing_token
    mock_db.execute.return_value = mock_query_result

    result = await RefreshTokenService.rotate_token(mock_db, raw_token=old_raw_token)

    # 1. Old token must now be marked revoked
    assert existing_token.revoked_at is not None

    # 2. Replacement token must be returned with new raw value
    assert result.raw_token != old_raw_token

    # 3. Replacement token record must inherit same family_id and user_id
    new_record = result.token_record
    assert new_record.user_id == user_id
    assert new_record.family_id == family_id
    assert new_record.revoked_at is None
    assert new_record.token_hash == hash_token(result.raw_token)

    # 4. Replacement must be staged in session
    mock_db.add.assert_called_with(new_record)
    assert mock_db.flush.called


@pytest.mark.asyncio
async def test_rotate_token_rejects_unknown_token():
    """Verifies that an unrecognised refresh token raises InvalidRefreshTokenError."""
    mock_db = AsyncMock()
    mock_query_result = MagicMock()
    mock_query_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_query_result

    with pytest.raises(InvalidRefreshTokenError, match="Invalid or unknown refresh token"):
        await RefreshTokenService.rotate_token(mock_db, raw_token="nonexistent_token_string")


@pytest.mark.asyncio
async def test_rotate_token_rejects_empty_token():
    """Verifies that empty or invalid raw token strings raise InvalidRefreshTokenError."""
    mock_db = AsyncMock()

    with pytest.raises(InvalidRefreshTokenError, match="Refresh token must be a non-empty string"):
        await RefreshTokenService.rotate_token(mock_db, raw_token="")

    with pytest.raises(InvalidRefreshTokenError, match="Refresh token must be a non-empty string"):
        await RefreshTokenService.rotate_token(mock_db, raw_token=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_rotate_token_rejects_expired_token():
    """Verifies that expired refresh tokens are rejected and marked revoked."""
    mock_db = AsyncMock()
    raw_token = generate_raw_token()

    expired_token = RefreshToken(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        family_id=uuid.uuid4(),
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(UTC) - timedelta(minutes=5),  # Expired
        revoked_at=None,
    )

    mock_query_result = MagicMock()
    mock_query_result.scalar_one_or_none.return_value = expired_token
    mock_db.execute.return_value = mock_query_result

    with pytest.raises(ExpiredRefreshTokenError, match="Refresh token has expired"):
        await RefreshTokenService.rotate_token(mock_db, raw_token=raw_token)

    assert expired_token.revoked_at is not None
    assert mock_db.flush.called


@pytest.mark.asyncio
async def test_rotate_token_reuse_detection_triggers_family_revocation():
    """Verifies that presenting a previously consumed token triggers token reuse detection.

    When reuse is detected:
    - Entire family is invalidated
    - Invalidation is committed to DB
    - TokenReuseDetectedError is raised with family_id
    """
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    family_id = uuid.uuid4()
    reused_raw_token = generate_raw_token()

    # Already-consumed token (revoked_at is already set)
    consumed_token = RefreshToken(
        id=uuid.uuid4(),
        user_id=user_id,
        family_id=family_id,
        token_hash=hash_token(reused_raw_token),
        expires_at=datetime.now(UTC) + timedelta(days=6),
        revoked_at=datetime.now(UTC) - timedelta(minutes=10),
    )

    mock_query_result = MagicMock()
    mock_query_result.scalar_one_or_none.return_value = consumed_token
    mock_db.execute.return_value = mock_query_result

    with pytest.raises(TokenReuseDetectedError) as exc_info:
        await RefreshTokenService.rotate_token(mock_db, raw_token=reused_raw_token)

    assert exc_info.value.family_id == family_id
    assert "Token reuse detected" in str(exc_info.value)

    # Invalidation must be committed so revocation persists across sessions
    assert mock_db.commit.called


@pytest.mark.asyncio
async def test_rotate_token_rolls_back_on_unexpected_failure():
    """Verifies that unexpected database errors trigger session rollback."""
    mock_db = AsyncMock()
    mock_db.execute.side_effect = RuntimeError("Database connection severed")

    with pytest.raises(RuntimeError, match="Database connection severed"):
        await RefreshTokenService.rotate_token(mock_db, raw_token="any_token")

    assert mock_db.rollback.called


# ==============================================================================
# Revocation & Logout Operations
# ==============================================================================


@pytest.mark.asyncio
async def test_revoke_token_single():
    """Verifies revoking a single token marks revoked_at and returns True."""
    mock_db = AsyncMock()
    raw_token = generate_raw_token()

    active_token = RefreshToken(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        family_id=uuid.uuid4(),
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(days=5),
        revoked_at=None,
    )

    mock_query_result = MagicMock()
    mock_query_result.scalar_one_or_none.return_value = active_token
    mock_db.execute.return_value = mock_query_result

    success = await RefreshTokenService.revoke_token(mock_db, raw_token=raw_token)

    assert success is True
    assert active_token.revoked_at is not None
    assert mock_db.flush.called


@pytest.mark.asyncio
async def test_revoke_token_nonexistent_returns_false():
    """Verifies revoking a nonexistent token returns False safely."""
    mock_db = AsyncMock()
    mock_query_result = MagicMock()
    mock_query_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_query_result

    success = await RefreshTokenService.revoke_token(mock_db, raw_token="nonexistent_token")
    assert success is False


@pytest.mark.asyncio
async def test_revoke_family_updates_active_rows():
    """Verifies that revoke_family executes an update on active rows in that family."""
    mock_db = AsyncMock()
    family_id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.rowcount = 3
    mock_db.execute.return_value = mock_result

    count = await RefreshTokenService.revoke_family(mock_db, family_id=family_id)

    assert count == 3
    assert mock_db.execute.called
    assert mock_db.flush.called


@pytest.mark.asyncio
async def test_revoke_all_user_tokens():
    """Verifies that revoke_all_user_tokens executes an update across all user families."""
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.rowcount = 5
    mock_db.execute.return_value = mock_result

    count = await RefreshTokenService.revoke_all_user_tokens(mock_db, user_id=user_id)

    assert count == 5
    assert mock_db.execute.called
    assert mock_db.flush.called

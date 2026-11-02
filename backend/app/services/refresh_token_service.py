"""Refresh token lifecycle service for session management, atomic rotation, and reuse detection.

Implements token generation, SHA-256 hash persistence, atomic single-use rotation
with row-level locking (SELECT FOR UPDATE), family-wide reuse invalidation,
and session revocation as approved in ADR-002 and docs/SECURITY.md.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.refresh_token import RefreshToken

# ==============================================================================
# Security Exceptions
# ==============================================================================


class RefreshTokenError(Exception):
    """Base exception for refresh token service failures."""


class InvalidRefreshTokenError(RefreshTokenError):
    """Raised when a presented refresh token is missing, malformed, or not found."""


class ExpiredRefreshTokenError(RefreshTokenError):
    """Raised when a presented refresh token has exceeded its expiration timestamp."""


class TokenReuseDetectedError(RefreshTokenError):
    """Raised when a previously revoked/consumed token is reused (replay attack)."""

    def __init__(
        self,
        message: str = "Refresh token reuse detected. All active sessions in this chain have been revoked.",
        family_id: uuid.UUID | None = None,
    ) -> None:
        super().__init__(message)
        self.family_id = family_id


# ==============================================================================
# Data Structures
# ==============================================================================


class TokenIssueResult(NamedTuple):
    """Encapsulates the raw refresh token and the persisted RefreshToken ORM record."""

    raw_token: str
    token_record: RefreshToken


# ==============================================================================
# Hashing & Token Helpers
# ==============================================================================


def generate_raw_token() -> str:
    """Generates a cryptographically secure random token string.

    Returns:
        A high-entropy URL-safe base64 string (64 characters, 384 bits of entropy).
    """
    return secrets.token_urlsafe(48)


def hash_token(raw_token: str) -> str:
    """Computes the SHA-256 hex digest of a raw refresh token string.

    Args:
        raw_token: The plaintext token string to hash.

    Returns:
        Hex-encoded SHA-256 digest (64 characters).

    Raises:
        ValueError: If raw_token is empty or not a string.
    """
    if not raw_token or not isinstance(raw_token, str):
        raise ValueError("raw_token cannot be empty")
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


# ==============================================================================
# Refresh Token Service
# ==============================================================================


class RefreshTokenService:
    """Service layer managing the lifecycle of refresh tokens and session chains."""

    @staticmethod
    async def create_token(
        db: AsyncSession,
        user_id: uuid.UUID,
        family_id: uuid.UUID | None = None,
        expires_days: int | None = None,
    ) -> TokenIssueResult:
        """Issues a new refresh token, persisting only its SHA-256 hash.

        Args:
            db: Active asynchronous database session.
            user_id: UUID of the authenticated user.
            family_id: Optional UUID of an existing session family chain.
                If None, a new family UUID is generated (initial login).
            expires_days: Optional custom expiration lifespan in days.
                Defaults to settings.REFRESH_TOKEN_EXPIRE_DAYS.

        Returns:
            TokenIssueResult with the raw token (to return in cookie) and the ORM record.

        Raises:
            ValueError: If user_id is invalid.
        """
        if not user_id:
            raise ValueError("user_id cannot be empty")

        token_family = family_id or uuid.uuid4()
        raw_token = generate_raw_token()
        token_hash = hash_token(raw_token)

        days = expires_days or settings.REFRESH_TOKEN_EXPIRE_DAYS
        expires_at = datetime.now(UTC) + timedelta(days=days)

        token_record = RefreshToken(
            id=uuid.uuid4(),
            user_id=user_id,
            family_id=token_family,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked_at=None,
        )

        db.add(token_record)
        await db.flush()

        return TokenIssueResult(raw_token=raw_token, token_record=token_record)

    @staticmethod
    async def rotate_token(
        db: AsyncSession,
        raw_token: str,
    ) -> TokenIssueResult:
        """Atomically rotates a valid refresh token and issues a single-use replacement.

        Locks the database row using `SELECT ... FOR UPDATE` to serialize concurrent requests.
        If the token has already been revoked or consumed, detects token reuse, invalidates
        all active tokens in the entire family chain, commits the revocation, and raises
        TokenReuseDetectedError.

        Args:
            db: Active asynchronous database session.
            raw_token: Raw refresh token presented by the client.

        Returns:
            TokenIssueResult with the replacement raw token and its persisted ORM record.

        Raises:
            InvalidRefreshTokenError: If the token is empty, malformed, or does not exist.
            ExpiredRefreshTokenError: If the token expiration timestamp has passed.
            TokenReuseDetectedError: If the token was already consumed (reuse attack).
        """
        if not raw_token or not isinstance(raw_token, str):
            raise InvalidRefreshTokenError("Refresh token must be a non-empty string")

        token_hash = hash_token(raw_token)

        try:
            # Row-level lock: serializes concurrent refresh requests presenting the same token
            stmt = (
                select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
            )
            result = await db.execute(stmt)
            token_record = result.scalar_one_or_none()

            if token_record is None:
                raise InvalidRefreshTokenError("Invalid or unknown refresh token")

            now = datetime.now(UTC)

            # Check for reuse of an already-revoked or consumed token
            if token_record.revoked_at is not None:
                # Replay attack detected: revoke entire family to neutralize stolen token chain
                await RefreshTokenService.revoke_family(db, token_record.family_id)
                await db.commit()
                raise TokenReuseDetectedError(
                    message="Token reuse detected. All active sessions in this chain have been revoked.",
                    family_id=token_record.family_id,
                )

            # Check expiration
            if token_record.expires_at <= now:
                # Mark this token as revoked
                token_record.revoked_at = now
                await db.flush()
                raise ExpiredRefreshTokenError("Refresh token has expired")

            # Consume the current token (single-use rotation)
            token_record.revoked_at = now

            # Issue replacement token inheriting the exact same family_id
            new_raw_token = generate_raw_token()
            new_token_hash = hash_token(new_raw_token)
            new_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

            new_record = RefreshToken(
                id=uuid.uuid4(),
                user_id=token_record.user_id,
                family_id=token_record.family_id,
                token_hash=new_token_hash,
                expires_at=new_expires_at,
                revoked_at=None,
            )

            db.add(new_record)
            await db.flush()

            return TokenIssueResult(raw_token=new_raw_token, token_record=new_record)

        except (InvalidRefreshTokenError, ExpiredRefreshTokenError, TokenReuseDetectedError):
            raise
        except Exception:
            await db.rollback()
            raise

    @staticmethod
    async def revoke_token(
        db: AsyncSession,
        raw_token: str,
    ) -> bool:
        """Revokes a single refresh token by marking revoked_at.

        Args:
            db: Active asynchronous database session.
            raw_token: Raw refresh token to revoke.

        Returns:
            True if the token was found and marked revoked, False otherwise.
        """
        if not raw_token or not isinstance(raw_token, str):
            return False

        token_hash = hash_token(raw_token)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
        result = await db.execute(stmt)
        token_record = result.scalar_one_or_none()

        if token_record is None:
            return False

        if token_record.revoked_at is None:
            token_record.revoked_at = datetime.now(UTC)
            await db.flush()

        return True

    @staticmethod
    async def revoke_family(
        db: AsyncSession,
        family_id: uuid.UUID,
    ) -> int:
        """Revokes all active refresh tokens belonging to a specific session family.

        Does not affect other session families belonging to the same user.

        Args:
            db: Active asynchronous database session.
            family_id: UUID of the session family chain to invalidate.

        Returns:
            Number of rows updated.
        """
        now = datetime.now(UTC)
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.family_id == family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        result = await db.execute(stmt)
        await db.flush()
        return result.rowcount  # type: ignore[no-any-return]

    @staticmethod
    async def revoke_all_user_tokens(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> int:
        """Revokes all active refresh tokens for a user across all session families.

        Used for administrative security actions or password changes.

        Args:
            db: Active asynchronous database session.
            user_id: UUID of the user account.

        Returns:
            Number of rows updated.
        """
        now = datetime.now(UTC)
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        result = await db.execute(stmt)
        await db.flush()
        return result.rowcount  # type: ignore[no-any-return]

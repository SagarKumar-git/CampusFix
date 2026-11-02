"""Authentication service layer orchestrating registration, login, rotation, and logout.

Integrates Argon2id password hashing, PyJWT access token generation,
and RefreshTokenService session management.
"""

from __future__ import annotations

import uuid
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.auth import TokenResponse
from app.schemas.user import UserCreate, UserLogin
from app.services.refresh_token_service import RefreshTokenService

# ==============================================================================
# Domain Exceptions
# ==============================================================================


class AuthError(Exception):
    """Base exception for authentication service errors."""


class DuplicateEmailError(AuthError):
    """Raised when registration is attempted with an already existing email."""


class AuthenticationFailedError(AuthError):
    """Raised when credentials (email or password) are incorrect."""


class UserInactiveError(AuthError):
    """Raised when an inactive user account attempts authentication or token refresh."""


class UserNotFoundError(AuthError):
    """Raised when a user record is not found."""


# ==============================================================================
# Result Structures
# ==============================================================================


class LoginResult(NamedTuple):
    """Result of successful authentication."""

    access_token: str
    raw_refresh_token: str
    user: User


class RefreshResult(NamedTuple):
    """Result of successful refresh token rotation."""

    token_response: TokenResponse
    new_raw_refresh_token: str


# ==============================================================================
# Authentication Service
# ==============================================================================


class AuthService:
    """Service providing core user authentication and lifecycle operations."""

    @staticmethod
    async def register_student(
        db: AsyncSession,
        user_create: UserCreate,
    ) -> User:
        """Registers a new student account with Argon2id password hashing.

        Public self-registration strictly assigns the STUDENT role.

        Args:
            db: Asynchronous SQLAlchemy session.
            user_create: Validated student registration payload.

        Returns:
            Newly created User record.

        Raises:
            DuplicateEmailError: If an account with this email already exists.
        """
        email = user_create.email.strip().lower()

        # Check existing account
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise DuplicateEmailError(f"An account with email '{email}' already exists.")

        # Hash password using Argon2id
        hashed_pwd = hash_password(user_create.password)

        new_user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=hashed_pwd,
            full_name=user_create.full_name.strip(),
            role=UserRole.STUDENT.value,
            is_active=True,
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        return new_user

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        email: str,
        password: str,
    ) -> User:
        """Verifies user credentials safely without revealing specific field mismatches.

        Args:
            db: Asynchronous SQLAlchemy session.
            email: Candidate institutional email address.
            password: Candidate plaintext password.

        Returns:
            The authenticated User record.

        Raises:
            AuthenticationFailedError: If credentials do not match or user is not found.
            UserInactiveError: If the account is deactivated.
        """
        clean_email = email.strip().lower()
        stmt = select(User).where(User.email == clean_email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        # Constant-time safety: verify dummy hash if user not found to thwart timing attacks
        if user is None:
            verify_password(
                password,
                "$argon2id$v=19$m=65536,t=3,p=4$dummy_salt_for_timing_safety$dummy_hash_000000000",
            )
            raise AuthenticationFailedError("Invalid email or password.")

        if not verify_password(password, user.hashed_password):
            raise AuthenticationFailedError("Invalid email or password.")

        if not user.is_active:
            raise UserInactiveError("Account is inactive. Please contact the administrator.")

        return user

    @staticmethod
    async def login(
        db: AsyncSession,
        login_data: UserLogin,
    ) -> LoginResult:
        """Authenticates user and issues access token plus refresh token.

        Args:
            db: Asynchronous SQLAlchemy session.
            login_data: Validated login credentials payload.

        Returns:
            LoginResult containing access_token, raw_refresh_token, and user entity.
        """
        user = await AuthService.authenticate_user(
            db=db,
            email=login_data.email,
            password=login_data.password,
        )

        # Generate short-lived JWT access token
        access_token = create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role,
        )

        # Issue initial refresh token for a new session family
        token_issue = await RefreshTokenService.create_token(
            db=db,
            user_id=user.id,
        )
        await db.commit()

        return LoginResult(
            access_token=access_token,
            raw_refresh_token=token_issue.raw_token,
            user=user,
        )

    @staticmethod
    async def refresh_session(
        db: AsyncSession,
        raw_refresh_token: str,
    ) -> RefreshResult:
        """Rotates a refresh token and issues a replacement access token.

        Args:
            db: Asynchronous SQLAlchemy session.
            raw_refresh_token: Presented raw refresh token string.

        Returns:
            RefreshResult containing TokenResponse and new raw refresh token.

        Raises:
            InvalidRefreshTokenError: If token is missing, malformed, or not found.
            ExpiredRefreshTokenError: If token has expired.
            TokenReuseDetectedError: If token reuse is detected.
            UserInactiveError: If user account is deactivated.
        """
        # Rotate token atomically using row-level locking
        token_issue = await RefreshTokenService.rotate_token(
            db=db,
            raw_token=raw_refresh_token,
        )

        # Retrieve user to ensure active account status and current role
        stmt = select(User).where(User.id == token_issue.token_record.user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None or not user.is_active:
            # Revoke the session family if user is missing or inactive
            await RefreshTokenService.revoke_family(
                db=db,
                family_id=token_issue.token_record.family_id,
            )
            await db.commit()
            raise UserInactiveError("User account is inactive or not found.")

        # Issue replacement access token
        access_token = create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role,
        )
        await db.commit()

        token_response = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

        return RefreshResult(
            token_response=token_response,
            new_raw_refresh_token=token_issue.raw_token,
        )

    @staticmethod
    async def logout(
        db: AsyncSession,
        raw_refresh_token: str | None,
    ) -> bool:
        """Terminates session by revoking the refresh token.

        Args:
            db: Asynchronous SQLAlchemy session.
            raw_refresh_token: Active raw refresh token from cookie, if present.

        Returns:
            True if token was revoked, False otherwise.
        """
        if not raw_refresh_token:
            return False

        revoked = await RefreshTokenService.revoke_token(
            db=db,
            raw_token=raw_refresh_token,
        )
        await db.commit()
        return revoked

    @staticmethod
    async def get_user_by_id(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> User | None:
        """Retrieves a user by primary key UUID."""
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

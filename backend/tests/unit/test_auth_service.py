"""Unit tests for AuthService registration, authentication, login, refresh, and logout."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.security import hash_password
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserLogin
from app.services.auth_service import (
    AuthenticationFailedError,
    AuthService,
    DuplicateEmailError,
    UserInactiveError,
)
from app.services.refresh_token_service import TokenIssueResult


@pytest.fixture
def mock_db() -> AsyncMock:
    """Provides an AsyncSession mock with synchronous add method."""
    session = AsyncMock()
    session.add = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result
    return session


@pytest.mark.asyncio
async def test_register_student_success(mock_db: AsyncMock):
    """Student registration hashes password with Argon2id and sets STUDENT role."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    user_create = UserCreate(
        full_name="Jane Doe",
        email="jane.doe@university.edu",
        password="SecurePassword123!",
    )

    user = await AuthService.register_student(mock_db, user_create)

    assert user.full_name == "Jane Doe"
    assert user.email == "jane.doe@university.edu"
    assert user.role == UserRole.STUDENT.value
    assert user.is_active is True
    assert user.hashed_password.startswith("$argon2id$")
    assert user.hashed_password != "SecurePassword123!"

    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_student_duplicate_email_raises_duplicate_email_error(mock_db: AsyncMock):
    """Attempting to register with an existing email raises DuplicateEmailError."""
    existing_user = User(
        id=uuid.uuid4(),
        email="jane.doe@university.edu",
        hashed_password="hash",
        full_name="Existing User",
        role=UserRole.STUDENT.value,
        is_active=True,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_user
    mock_db.execute.return_value = mock_result

    user_create = UserCreate(
        full_name="Jane Doe",
        email="jane.doe@university.edu",
        password="SecurePassword123!",
    )

    with pytest.raises(DuplicateEmailError, match="already exists"):
        await AuthService.register_student(mock_db, user_create)

    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_user_success(mock_db: AsyncMock):
    """authenticate_user returns User on matching credentials."""
    raw_pwd = "SecurePassword123!"
    hashed_pwd = hash_password(raw_pwd)

    user = User(
        id=uuid.uuid4(),
        email="jane.doe@university.edu",
        hashed_password=hashed_pwd,
        full_name="Jane Doe",
        role=UserRole.STUDENT.value,
        is_active=True,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = mock_result

    authenticated = await AuthService.authenticate_user(
        mock_db,
        "jane.doe@university.edu",
        raw_pwd,
    )

    assert authenticated.id == user.id


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password_raises_auth_failed(mock_db: AsyncMock):
    """authenticate_user raises AuthenticationFailedError when password does not match."""
    hashed_pwd = hash_password("CorrectPassword123!")
    user = User(
        id=uuid.uuid4(),
        email="jane.doe@university.edu",
        hashed_password=hashed_pwd,
        full_name="Jane Doe",
        role=UserRole.STUDENT.value,
        is_active=True,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = mock_result

    with pytest.raises(AuthenticationFailedError, match="Invalid email or password"):
        await AuthService.authenticate_user(
            mock_db,
            "jane.doe@university.edu",
            "WrongPassword123!",
        )


@pytest.mark.asyncio
async def test_authenticate_user_nonexistent_user_raises_auth_failed(mock_db: AsyncMock):
    """authenticate_user raises generic AuthenticationFailedError when email does not exist."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with pytest.raises(AuthenticationFailedError, match="Invalid email or password"):
        await AuthService.authenticate_user(
            mock_db,
            "unknown@university.edu",
            "AnyPassword123!",
        )


@pytest.mark.asyncio
async def test_authenticate_user_inactive_raises_user_inactive_error(mock_db: AsyncMock):
    """authenticate_user raises UserInactiveError when account is deactivated."""
    raw_pwd = "SecurePassword123!"
    hashed_pwd = hash_password(raw_pwd)
    user = User(
        id=uuid.uuid4(),
        email="jane.doe@university.edu",
        hashed_password=hashed_pwd,
        full_name="Jane Doe",
        role=UserRole.STUDENT.value,
        is_active=False,  # Inactive account
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = mock_result

    with pytest.raises(UserInactiveError, match="Account is inactive"):
        await AuthService.authenticate_user(
            mock_db,
            "jane.doe@university.edu",
            raw_pwd,
        )


@pytest.mark.asyncio
async def test_login_success(mock_db: AsyncMock):
    """login returns access token, raw refresh token, and user record."""
    raw_pwd = "SecurePassword123!"
    user = User(
        id=uuid.uuid4(),
        email="jane.doe@university.edu",
        hashed_password=hash_password(raw_pwd),
        full_name="Jane Doe",
        role=UserRole.STUDENT.value,
        is_active=True,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = mock_result

    with patch(
        "app.services.auth_service.RefreshTokenService.create_token",
        new_callable=AsyncMock,
    ) as mock_create_token:
        mock_create_token.return_value = TokenIssueResult(
            raw_token="raw_refresh_token_123",
            token_record=RefreshToken(
                id=uuid.uuid4(),
                user_id=user.id,
                family_id=uuid.uuid4(),
                token_hash="hash",
                expires_at=datetime.now(UTC) + timedelta(days=7),
            ),
        )

        login_res = await AuthService.login(
            mock_db,
            UserLogin(email="jane.doe@university.edu", password=raw_pwd),
        )

        assert login_res.access_token is not None
        assert login_res.raw_refresh_token == "raw_refresh_token_123"
        assert login_res.user.id == user.id
        mock_db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_refresh_session_success(mock_db: AsyncMock):
    """refresh_session rotates token and returns new access token."""
    user = User(
        id=uuid.uuid4(),
        email="jane.doe@university.edu",
        hashed_password="hash",
        full_name="Jane Doe",
        role=UserRole.STUDENT.value,
        is_active=True,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = mock_result

    token_record = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        family_id=uuid.uuid4(),
        token_hash="hash",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    with patch(
        "app.services.auth_service.RefreshTokenService.rotate_token",
        new_callable=AsyncMock,
    ) as mock_rotate:
        mock_rotate.return_value = TokenIssueResult(
            raw_token="new_raw_token_xyz",
            token_record=token_record,
        )

        result = await AuthService.refresh_session(mock_db, "old_raw_token")

        assert result.new_raw_refresh_token == "new_raw_token_xyz"
        assert result.token_response.access_token is not None
        assert result.token_response.token_type == "bearer"
        mock_db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_logout_revokes_token(mock_db: AsyncMock):
    """logout marks token revoked and commits."""
    with patch(
        "app.services.auth_service.RefreshTokenService.revoke_token",
        new_callable=AsyncMock,
    ) as mock_revoke:
        mock_revoke.return_value = True

        revoked = await AuthService.logout(mock_db, "token_to_revoke")
        assert revoked is True
        mock_db.commit.assert_awaited_once()

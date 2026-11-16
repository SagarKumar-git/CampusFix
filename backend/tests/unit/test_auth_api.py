"""Unit and API contract tests for CampusFix authentication and profile REST endpoints.

Tests /api/v1/auth/register, /login, /refresh, /logout, /me, verifying HTTP response codes,
standard envelope formatting, cookie attributes, secret hash omission, and token security.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.user import User, UserRole
from app.services.auth_service import (
    AuthenticationFailedError,
    DuplicateEmailError,
    LoginResult,
    RefreshResult,
    UserInactiveError,
)
from app.services.refresh_token_service import (
    ExpiredRefreshTokenError,
    InvalidRefreshTokenError,
    TokenReuseDetectedError,
)

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Mock asynchronous SQLAlchemy session for endpoint tests."""
    session = AsyncMock()
    return session


@pytest.fixture
async def client(mock_db_session: AsyncMock):
    """Provides an AsyncClient connected to the FastAPI application with mocked DB dependency."""
    app.dependency_overrides[get_db] = lambda: mock_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def sample_student() -> User:
    """Provides a synthetic active Student user record."""
    return User(
        id=uuid.uuid4(),
        email="jane.doe@university.edu",
        hashed_password=hash_password("SecurePassword123!"),
        full_name="Jane Doe",
        role=UserRole.STUDENT.value,
        is_active=True,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_inactive_user() -> User:
    """Provides a synthetic inactive user record."""
    return User(
        id=uuid.uuid4(),
        email="inactive.user@university.edu",
        hashed_password=hash_password("SecurePassword123!"),
        full_name="Inactive User",
        role=UserRole.STUDENT.value,
        is_active=False,
        created_at=datetime.now(UTC),
    )


# ==============================================================================
# Registration Endpoint Tests (POST /api/v1/auth/register)
# ==============================================================================


@pytest.mark.asyncio
async def test_register_student_success(client: AsyncClient, sample_student: User):
    """POST /auth/register creates a student account and returns HTTP 201 with public profile."""
    with patch(
        "app.api.v1.auth.AuthService.register_student",
        new_callable=AsyncMock,
    ) as mock_register:
        mock_register.return_value = sample_student

        payload = {
            "full_name": "Jane Doe",
            "email": "jane.doe@university.edu",
            "password": "SecurePassword123!",
        }
        response = await client.post("/api/v1/auth/register", json=payload)

        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["data"]["email"] == "jane.doe@university.edu"
        assert body["data"]["full_name"] == "Jane Doe"
        assert body["data"]["role"] == "STUDENT"
        assert "hashed_password" not in body["data"]
        assert "password" not in body["data"]


@pytest.mark.asyncio
async def test_register_student_duplicate_email(client: AsyncClient):
    """POST /auth/register returns HTTP 409 Conflict when the email already exists."""
    with patch(
        "app.api.v1.auth.AuthService.register_student",
        new_callable=AsyncMock,
    ) as mock_register:
        mock_register.side_effect = DuplicateEmailError(
            "An account with this email address already exists."
        )

        payload = {
            "full_name": "Jane Doe",
            "email": "jane.doe@university.edu",
            "password": "SecurePassword123!",
        }
        response = await client.post("/api/v1/auth/register", json=payload)

        assert response.status_code == 409
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


@pytest.mark.asyncio
async def test_register_student_validation_errors(client: AsyncClient):
    """POST /auth/register returns HTTP 422 with validation details on invalid payload."""
    payload = {
        "full_name": "",  # Empty name
        "email": "not-an-email",
        "password": "weak",
    }
    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert isinstance(body["error"]["details"], list)


@pytest.mark.asyncio
async def test_register_student_prevents_role_elevation(client: AsyncClient):
    """POST /auth/register forbids extra fields like role='ADMINISTRATOR'."""
    payload = {
        "full_name": "Attacker",
        "email": "attacker@university.edu",
        "password": "SecurePassword123!",
        "role": "ADMINISTRATOR",
    }
    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


# ==============================================================================
# Login Endpoint Tests (POST /api/v1/auth/login)
# ==============================================================================


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, sample_student: User):
    """POST /auth/login returns access token, user profile, and sets HttpOnly refresh cookie."""
    with patch(
        "app.api.v1.auth.AuthService.login",
        new_callable=AsyncMock,
    ) as mock_login:
        mock_login.return_value = LoginResult(
            access_token="mock_access_jwt_string",
            raw_refresh_token="mock_refresh_token_string",
            user=sample_student,
        )

        payload = {
            "email": "jane.doe@university.edu",
            "password": "SecurePassword123!",
        }
        response = await client.post("/api/v1/auth/login", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["access_token"] == "mock_access_jwt_string"
        assert body["data"]["token_type"] == "bearer"
        assert body["data"]["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert body["data"]["user"]["email"] == "jane.doe@university.edu"
        assert "refresh_token" not in body["data"]

        # Check Set-Cookie header
        set_cookie = response.headers.get("set-cookie")
        assert set_cookie is not None
        assert "refresh_token=mock_refresh_token_string" in set_cookie
        assert "HttpOnly" in set_cookie
        assert "Path=/api/v1/auth" in set_cookie
        assert "SameSite=lax" in set_cookie or "samesite=lax" in set_cookie
        assert "secure" not in set_cookie.lower()


@pytest.mark.asyncio
async def test_login_cookie_secure_in_staging_and_production(
    client: AsyncClient, sample_student: User
):
    """POST /auth/login sets Secure=True on refresh cookie in staging and production environments."""
    mock_login_result = LoginResult(
        access_token="mock_access_jwt_string",
        raw_refresh_token="mock_refresh_token_string",
        user=sample_student,
    )

    with patch("app.api.v1.auth.AuthService.login", new_callable=AsyncMock) as mock_login:
        mock_login.return_value = mock_login_result

        payload = {
            "email": "jane.doe@university.edu",
            "password": "SecurePassword123!",
        }

        # Staging test: ENVIRONMENT=staging auto-enables Secure=True
        with (
            patch.object(settings, "ENVIRONMENT", "staging"),
            patch.object(settings, "COOKIE_SECURE", None),
        ):
            assert settings.is_cookie_secure is True
            response_staging = await client.post("/api/v1/auth/login", json=payload)
            assert response_staging.status_code == 200
            set_cookie_staging = response_staging.headers.get("set-cookie")
            assert set_cookie_staging is not None
            assert "secure" in set_cookie_staging.lower()
            assert "httponly" in set_cookie_staging.lower()
            assert "samesite=lax" in set_cookie_staging.lower()
            assert "path=/api/v1/auth" in set_cookie_staging.lower()

        # Production test: ENVIRONMENT=production auto-enables Secure=True
        with (
            patch.object(settings, "ENVIRONMENT", "production"),
            patch.object(settings, "COOKIE_SECURE", None),
        ):
            assert settings.is_cookie_secure is True
            response_prod = await client.post("/api/v1/auth/login", json=payload)
            assert response_prod.status_code == 200
            set_cookie_prod = response_prod.headers.get("set-cookie")
            assert set_cookie_prod is not None
            assert "secure" in set_cookie_prod.lower()

        # Explicit override test: COOKIE_SECURE=True in development
        with (
            patch.object(settings, "ENVIRONMENT", "development"),
            patch.object(settings, "COOKIE_SECURE", True),
        ):
            assert settings.is_cookie_secure is True
            response_override = await client.post("/api/v1/auth/login", json=payload)
            assert response_override.status_code == 200
            set_cookie_override = response_override.headers.get("set-cookie")
            assert "secure" in set_cookie_override.lower()


@pytest.mark.asyncio
async def test_logout_clears_cookie_with_secure_flag_in_staging(
    client: AsyncClient, sample_student: User
):
    """POST /auth/logout clears refresh cookie and preserves Secure=True in staging."""
    token = create_access_token(
        user_id=sample_student.id,
        email=sample_student.email,
        role=sample_student.role,
    )

    with (
        patch(
            "app.api.deps.AuthService.get_user_by_id",
            new_callable=AsyncMock,
        ) as mock_get_user,
        patch(
            "app.api.v1.auth.AuthService.logout",
            new_callable=AsyncMock,
        ) as mock_logout,
    ):
        mock_get_user.return_value = sample_student
        mock_logout.return_value = True

        with (
            patch.object(settings, "ENVIRONMENT", "staging"),
            patch.object(settings, "COOKIE_SECURE", None),
        ):
            client.cookies.set("refresh_token", "active_refresh_cookie")
            response = await client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            set_cookie = response.headers.get("set-cookie")
            assert set_cookie is not None
            assert "max-age=0" in set_cookie.lower()
            assert "secure" in set_cookie.lower()
            assert "httponly" in set_cookie.lower()
            assert "path=/api/v1/auth" in set_cookie.lower()


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    """POST /auth/login returns HTTP 401 on wrong credentials."""
    with patch(
        "app.api.v1.auth.AuthService.login",
        new_callable=AsyncMock,
    ) as mock_login:
        mock_login.side_effect = AuthenticationFailedError("Invalid email or password.")

        payload = {
            "email": "jane.doe@university.edu",
            "password": "WrongPassword123!",
        }
        response = await client.post("/api/v1/auth/login", json=payload)

        assert response.status_code == 401
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient):
    """POST /auth/login returns HTTP 403 on deactivated account."""
    with patch(
        "app.api.v1.auth.AuthService.login",
        new_callable=AsyncMock,
    ) as mock_login:
        mock_login.side_effect = UserInactiveError(
            "Account is inactive. Please contact the administrator."
        )

        payload = {
            "email": "inactive@university.edu",
            "password": "SecurePassword123!",
        }
        response = await client.post("/api/v1/auth/login", json=payload)

        assert response.status_code == 403
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "USER_INACTIVE"


# ==============================================================================
# Token Refresh Endpoint Tests (POST /api/v1/auth/refresh)
# ==============================================================================


@pytest.mark.asyncio
async def test_refresh_token_success_via_cookie(client: AsyncClient):
    """POST /auth/refresh rotates the single-use token and sets replacement cookie."""
    with patch(
        "app.api.v1.auth.AuthService.refresh_session",
        new_callable=AsyncMock,
    ) as mock_refresh:
        mock_refresh.return_value = RefreshResult(
            token_response={
                "access_token": "new_access_token_jwt",
                "token_type": "bearer",
                "expires_in": 900,
            },
            new_raw_refresh_token="new_raw_cookie_token",
        )

        client.cookies.set("refresh_token", "valid_current_token")
        response = await client.post("/api/v1/auth/refresh")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["access_token"] == "new_access_token_jwt"

        set_cookie = response.headers.get("set-cookie")
        assert set_cookie is not None
        assert "refresh_token=new_raw_cookie_token" in set_cookie


@pytest.mark.asyncio
async def test_refresh_token_missing_cookie_and_body(client: AsyncClient):
    """POST /auth/refresh returns HTTP 401 when refresh token is missing."""
    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_refresh_token_reuse_detected_clears_cookie(client: AsyncClient):
    """POST /auth/refresh detects replay attack, returns HTTP 401, and clears cookie."""
    with patch(
        "app.api.v1.auth.AuthService.refresh_session",
        new_callable=AsyncMock,
    ) as mock_refresh:
        mock_refresh.side_effect = TokenReuseDetectedError(
            message="Refresh token has already been consumed. Active session family revoked."
        )

        client.cookies.set("refresh_token", "replayed_token")
        response = await client.post("/api/v1/auth/refresh")

        assert response.status_code == 401
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "TOKEN_REUSE_DETECTED"

        set_cookie = response.headers.get("set-cookie")
        assert set_cookie is not None
        assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie


@pytest.mark.asyncio
async def test_refresh_token_expired_clears_cookie(client: AsyncClient):
    """POST /auth/refresh returns HTTP 401 on expired token and clears cookie."""
    with patch(
        "app.api.v1.auth.AuthService.refresh_session",
        new_callable=AsyncMock,
    ) as mock_refresh:
        mock_refresh.side_effect = ExpiredRefreshTokenError("Refresh token has expired.")

        client.cookies.set("refresh_token", "expired_token")
        response = await client.post("/api/v1/auth/refresh")

        assert response.status_code == 401
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "TOKEN_EXPIRED"

        set_cookie = response.headers.get("set-cookie")
        assert set_cookie is not None
        assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie


@pytest.mark.asyncio
async def test_refresh_token_invalid_clears_cookie(client: AsyncClient):
    """POST /auth/refresh returns HTTP 401 on invalid/unknown token and clears cookie."""
    with patch(
        "app.api.v1.auth.AuthService.refresh_session",
        new_callable=AsyncMock,
    ) as mock_refresh:
        mock_refresh.side_effect = InvalidRefreshTokenError("Invalid or unknown refresh token.")

        client.cookies.set("refresh_token", "invalid_token")
        response = await client.post("/api/v1/auth/refresh")

        assert response.status_code == 401
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "INVALID_TOKEN"

        set_cookie = response.headers.get("set-cookie")
        assert set_cookie is not None
        assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie


# ==============================================================================
# Logout Endpoint Tests (POST /api/v1/auth/logout)
# ==============================================================================


@pytest.mark.asyncio
async def test_logout_authenticated_success(client: AsyncClient, sample_student: User):
    """POST /auth/logout revokes session, clears cookie, and returns HTTP 200."""
    token = create_access_token(
        user_id=sample_student.id,
        email=sample_student.email,
        role=sample_student.role,
    )

    with (
        patch(
            "app.api.deps.AuthService.get_user_by_id",
            new_callable=AsyncMock,
        ) as mock_get_user,
        patch(
            "app.api.v1.auth.AuthService.logout",
            new_callable=AsyncMock,
        ) as mock_logout,
    ):
        mock_get_user.return_value = sample_student
        mock_logout.return_value = True

        client.cookies.set("refresh_token", "active_refresh_cookie")
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["message"] == "Successfully logged out."

        set_cookie = response.headers.get("set-cookie")
        assert set_cookie is not None
        assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie


@pytest.mark.asyncio
async def test_logout_unauthenticated_fails(client: AsyncClient):
    """POST /auth/logout requires valid Bearer access token."""
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 401


# ==============================================================================
# User Profile Endpoint Tests (GET /api/v1/auth/me)
# ==============================================================================


@pytest.mark.asyncio
async def test_get_me_authenticated_success(client: AsyncClient, sample_student: User):
    """GET /auth/me returns identity and profile of current user without sensitive fields."""
    token = create_access_token(
        user_id=sample_student.id,
        email=sample_student.email,
        role=sample_student.role,
    )

    with patch(
        "app.api.deps.AuthService.get_user_by_id",
        new_callable=AsyncMock,
    ) as mock_get_user:
        mock_get_user.return_value = sample_student

        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["id"] == str(sample_student.id)
        assert body["data"]["email"] == sample_student.email
        assert body["data"]["role"] == sample_student.role
        assert body["data"]["is_active"] is True
        assert "hashed_password" not in body["data"]


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient):
    """GET /auth/me returns HTTP 401 when Authorization header is missing."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_get_me_expired_token(client: AsyncClient, sample_student: User):
    """GET /auth/me returns HTTP 401 when access token has expired."""
    expired_token = create_access_token(
        user_id=sample_student.id,
        email=sample_student.email,
        role=sample_student.role,
        expires_delta=timedelta(seconds=-10),  # expired
    )

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_get_me_inactive_user_forbidden(client: AsyncClient, sample_inactive_user: User):
    """GET /auth/me returns HTTP 403 when user account is deactivated."""
    token = create_access_token(
        user_id=sample_inactive_user.id,
        email=sample_inactive_user.email,
        role=sample_inactive_user.role,
    )

    with patch(
        "app.api.deps.AuthService.get_user_by_id",
        new_callable=AsyncMock,
    ) as mock_get_user:
        mock_get_user.return_value = sample_inactive_user

        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "FORBIDDEN"

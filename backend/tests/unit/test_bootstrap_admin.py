"""Unit test suite for the initial administrator provisioning CLI (bootstrap_admin).

Verifies strict security, authorization, idempotency, interactive confirmation,
Argon2id hashing, database target safety, and engine disposal.
"""

from __future__ import annotations

import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.security import verify_password
from app.models.user import User, UserRole
from app.scripts.bootstrap_admin import (
    bootstrap_admin,
    check_database_target_safety,
    parse_args,
    prompt_password,
    run_cli,
    validate_admin_password,
)


@pytest.fixture
def mock_db() -> AsyncMock:
    """Provides a mocked asynchronous SQLAlchemy session."""
    session = AsyncMock()
    session.add = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result
    return session


# ==============================================================================
# Password Validation & Security Tests (Requirements C & E.10, E.14)
# ==============================================================================


def test_validate_admin_password_success():
    """Valid strong passwords passing all criteria are accepted."""
    pw = "Complex@Admin2026!"
    assert validate_admin_password(pw) == pw


@pytest.mark.parametrize(
    "invalid_pw,expected_error",
    [
        ("Short1!", "Administrator password must be at least 12 characters in length."),
        ("A" * 129, "Administrator password cannot exceed 128 characters in length."),
        ("password123!", "common default or weak password"),
        ("Admin123456!", "common default or weak password"),
        ("campusfix123!", "common default or weak password"),
        ("alllowercase123!", "contain at least one uppercase letter"),
        ("ALLUPPERCASE123!", "contain at least one lowercase letter"),
        ("NoNumbersHere!@", "contain at least one numerical digit"),
        ("NoSpecialChar123", "contain at least one special character"),
    ],
)
def test_validate_admin_password_rejections(invalid_pw: str, expected_error: str):
    """Rejects passwords violating length, complexity, or weak-password rules."""
    with pytest.raises(ValueError, match=expected_error):
        validate_admin_password(invalid_pw)


def test_bootstrap_admin_never_exposes_password_in_results():
    """Confirms candidate passwords are never echoed in error or result messages (Requirement E.10)."""
    secret = "TopSecretPassword2026!"
    with pytest.raises(ValueError) as excinfo:
        validate_admin_password(secret.lower())  # missing uppercase

    # Exception text does not print candidate password
    assert secret not in str(excinfo.value)
    assert secret.lower() not in str(excinfo.value)


def test_prompt_password_mismatch_raises_value_error():
    """When password confirmation does not match, raises ValueError."""
    with patch("getpass.getpass", side_effect=["SecretPassword123!", "MismatchPassword123!"]):
        with pytest.raises(ValueError, match="Passwords do not match"):
            prompt_password()


def test_prompt_password_does_not_use_environment_variable(monkeypatch):
    """Verifies ADMIN_INITIAL_PASSWORD is NOT read or used; interactive prompt required (Requirements A.3, E.9)."""
    monkeypatch.setenv("ADMIN_INITIAL_PASSWORD", "InjectedEnvSecret123!@")
    with patch("getpass.getpass", side_effect=["PromptedSecret123!", "PromptedSecret123!"]):
        pw = prompt_password()
        assert pw == "PromptedSecret123!"
        assert pw != "InjectedEnvSecret123!@"


# ==============================================================================
# CLI Argument Parsing & Unauthorized Flag Rejection (Requirements A & E.2)
# ==============================================================================


def test_parse_args_accepts_approved_arguments():
    """Verifies CLI argument parsing for approved arguments only."""
    args = parse_args(
        [
            "--email",
            "admin@test.edu",
            "--full-name",
            "Campus Admin",
            "--promote-existing",
        ]
    )
    assert args.email == "admin@test.edu"
    assert args.full_name == "Campus Admin"
    assert args.promote_existing is True


@pytest.mark.parametrize(
    "unauthorized_flag",
    [
        "--update-password",
        "-y",
        "--yes",
        "--force",
        "--skip-confirmation",
    ],
)
def test_parse_args_rejects_unauthorized_flags(unauthorized_flag: str):
    """CLI parser strictly rejects unauthorized flags like --update-password, -y, --yes (Requirements A.1, A.2, E.2)."""
    with pytest.raises(SystemExit):
        with patch("sys.stderr", new_callable=io.StringIO):
            parse_args(
                [
                    "--email",
                    "admin@test.edu",
                    "--full-name",
                    "Campus Admin",
                    unauthorized_flag,
                ]
            )


# ==============================================================================
# Administrator Creation & Idempotency Tests (Requirements A, E.1, E.14)
# ==============================================================================


@pytest.mark.asyncio
async def test_bootstrap_admin_creates_new_administrator(mock_db: AsyncMock):
    """Successfully provisions an active ADMINISTRATOR with Argon2id hash (Requirement E.14)."""
    result = await bootstrap_admin(
        db=mock_db,
        email="facilities.lead@university.edu",
        full_name="Dr. Alex Rivera",
        password="Valid@MasterAdmin2026!",
    )

    assert result.success is True
    assert result.action == "CREATED"
    assert result.user_id is not None
    assert "facilities.lead@university.edu" in result.message

    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()

    created_user = mock_db.add.call_args[0][0]
    assert isinstance(created_user, User)
    assert created_user.email == "facilities.lead@university.edu"
    assert created_user.full_name == "Dr. Alex Rivera"
    assert created_user.role == UserRole.ADMINISTRATOR.value
    assert created_user.is_active is True
    assert created_user.hashed_password.startswith("$argon2id$")
    assert verify_password("Valid@MasterAdmin2026!", created_user.hashed_password) is True


@pytest.mark.asyncio
async def test_bootstrap_admin_idempotent_for_existing_administrator_preserves_all_fields(
    mock_db: AsyncMock,
):
    """Existing active ADMINISTRATOR returns ALREADY_ADMIN and leaves every field unchanged (Requirements A.4, E.1)."""
    original_id = uuid.uuid4()
    original_hash = "$argon2id$v=19$m=65536,t=3,p=4$original_admin_hash"
    existing_admin = User(
        id=original_id,
        email="admin@university.edu",
        full_name="Original Facilities Admin",
        hashed_password=original_hash,
        role=UserRole.ADMINISTRATOR.value,
        is_active=True,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_admin
    mock_db.execute.return_value = mock_result

    result = await bootstrap_admin(
        db=mock_db,
        email="admin@university.edu",
        full_name="Attempted Altered Name",
        password="AttemptedNewPassword123!@",
    )

    assert result.success is True
    assert result.action == "ALREADY_ADMIN"
    assert result.user_id == original_id
    assert "already an active ADMINISTRATOR" in result.message

    # Verify that EVERY field remains strictly untouched
    assert existing_admin.id == original_id
    assert existing_admin.email == "admin@university.edu"
    assert existing_admin.full_name == "Original Facilities Admin"
    assert existing_admin.hashed_password == original_hash
    assert existing_admin.role == UserRole.ADMINISTRATOR.value
    assert existing_admin.is_active is True

    # Database commit must not be called
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_awaited()


# ==============================================================================
# Existing Account Promotion & Safety Tests (Requirements B & E.3-E.8)
# ==============================================================================


@pytest.mark.asyncio
async def test_bootstrap_admin_refuses_student_promotion_by_default(mock_db: AsyncMock):
    """Refuses promoting existing STUDENT account without --promote-existing (Requirements B, E.3)."""
    existing_student = User(
        id=uuid.uuid4(),
        email="student@university.edu",
        full_name="Student User",
        hashed_password="student_hash",
        role=UserRole.STUDENT.value,
        is_active=True,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_student
    mock_db.execute.return_value = mock_result

    result = await bootstrap_admin(
        db=mock_db,
        email="student@university.edu",
        full_name="Student User",
        password="ValidAdminPassword123!",
        promote_existing=False,
    )

    assert result.success is False
    assert result.action == "REFUSED"
    assert "Refusing automatic promotion" in result.message
    assert existing_student.role == UserRole.STUDENT.value
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_bootstrap_admin_promotes_existing_user_preserves_all_other_fields(
    mock_db: AsyncMock,
):
    """Promotes existing account to ADMINISTRATOR changing ONLY the role (Requirements B, E.8)."""
    user_id = uuid.uuid4()
    original_hash = "$argon2id$v=19$m=65536,t=3,p=4$original_staff_hash"
    existing_user = User(
        id=user_id,
        email="lead.tech@university.edu",
        full_name="Lead Tech Profile Name",
        hashed_password=original_hash,
        role=UserRole.STAFF.value,
        is_active=True,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_user
    mock_db.execute.return_value = mock_result

    result = await bootstrap_admin(
        db=mock_db,
        email="lead.tech@university.edu",
        full_name="Attempted Altered Full Name",
        password="ValidAdminPassword123!",
        promote_existing=True,
        confirm_promotion=True,
    )

    assert result.success is True
    assert result.action == "PROMOTED"
    # Role changed to ADMINISTRATOR
    assert existing_user.role == UserRole.ADMINISTRATOR.value
    # All other fields MUST be strictly preserved
    assert existing_user.id == user_id
    assert existing_user.email == "lead.tech@university.edu"
    assert existing_user.full_name == "Lead Tech Profile Name"
    assert existing_user.hashed_password == original_hash
    assert existing_user.is_active is True

    mock_db.commit.assert_awaited_once()


# ==============================================================================
# Interactive Promotion Confirmation Tests in CLI (Requirements B & E.4-E.7)
# ==============================================================================


@pytest.mark.asyncio
async def test_run_cli_refuses_promotion_when_response_is_y():
    """Promotion is cancelled if operator enters 'y' instead of exact 'yes' (Requirements B, E.4)."""
    stderr_buf = io.StringIO()
    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("builtins.input", return_value="y"),
        patch("sys.stderr", stderr_buf),
        patch(
            "app.scripts.bootstrap_admin.check_database_target_safety", return_value=(True, "Safe")
        ),
    ):
        code = await run_cli(
            ["--email", "student@university.edu", "--full-name", "Student", "--promote-existing"]
        )
        assert code == 1
        assert "Expected exact response 'yes'" in stderr_buf.getvalue()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_response", ["YES", "Yes", "Y", "no", "", "   "])
async def test_run_cli_refuses_promotion_for_any_non_exact_yes_response(invalid_response: str):
    """Promotion is cancelled for 'YES', 'Yes', empty, or any response other than 'yes' (Requirements B, E.5)."""
    stderr_buf = io.StringIO()
    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("builtins.input", return_value=invalid_response),
        patch("sys.stderr", stderr_buf),
        patch(
            "app.scripts.bootstrap_admin.check_database_target_safety", return_value=(True, "Safe")
        ),
    ):
        code = await run_cli(
            ["--email", "student@university.edu", "--full-name", "Student", "--promote-existing"]
        )
        assert code == 1
        assert "Expected exact response 'yes'" in stderr_buf.getvalue()


@pytest.mark.asyncio
async def test_run_cli_blocks_non_interactive_promotion():
    """Non-interactive execution (stdin not a tty) cannot promote an existing account (Requirements B, E.7)."""
    stderr_buf = io.StringIO()
    with (
        patch("sys.stdin.isatty", return_value=False),
        patch("sys.stderr", stderr_buf),
        patch(
            "app.scripts.bootstrap_admin.check_database_target_safety", return_value=(True, "Safe")
        ),
    ):
        code = await run_cli(
            ["--email", "student@university.edu", "--full-name", "Student", "--promote-existing"]
        )
        assert code == 1
        assert (
            "Non-interactive execution cannot promote an existing account" in stderr_buf.getvalue()
        )


@pytest.mark.asyncio
async def test_run_cli_succeeds_promotion_with_exact_yes(mock_db: AsyncMock):
    """Promotion succeeds when operator enters exact 'yes' (Requirements B, E.6)."""
    existing_staff = User(
        id=uuid.uuid4(),
        email="tech@university.edu",
        full_name="Tech Staff",
        hashed_password="staff_hash",
        role=UserRole.STAFF.value,
        is_active=True,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_staff
    mock_db.execute.return_value = mock_result

    async def fake_get_db_session():
        yield mock_db

    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("builtins.input", return_value="yes"),
        patch("app.scripts.bootstrap_admin.prompt_password", return_value="ValidAdminPass123!"),
        patch("app.scripts.bootstrap_admin.get_db_session", fake_get_db_session),
        patch("app.scripts.bootstrap_admin.close_db_engine", new_callable=AsyncMock),
        patch(
            "app.scripts.bootstrap_admin.check_database_target_safety", return_value=(True, "Safe")
        ),
    ):
        code = await run_cli(
            ["--email", "tech@university.edu", "--full-name", "Tech Staff", "--promote-existing"]
        )
        assert code == 0
        assert existing_staff.role == UserRole.ADMINISTRATOR.value
        mock_db.commit.assert_awaited_once()


# ==============================================================================
# Database Safety, Rollback & Disposal Tests (Requirements D & E.11, E.12, E.13)
# ==============================================================================


@pytest.mark.asyncio
async def test_bootstrap_admin_rolls_back_on_database_error(mock_db: AsyncMock):
    """Triggers db.rollback() without leaking raw SQL or credentials on commit error (Requirements D, E.11)."""
    mock_db.commit.side_effect = RuntimeError("Database disk full or constraint violation")

    result = await bootstrap_admin(
        db=mock_db,
        email="admin@university.edu",
        full_name="Admin Name",
        password="ValidAdminPassword123!",
    )

    assert result.success is False
    assert result.action == "ERROR"
    assert result.message == "Database transaction failed."
    mock_db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_cli_disposes_database_engine_in_finally_block():
    """Verifies that close_db_engine() is ALWAYS awaited in a finally block (Requirements D, E.12)."""
    close_mock = AsyncMock()

    async def fake_get_db_session():
        yield AsyncMock()

    with (
        patch("app.scripts.bootstrap_admin.prompt_password", return_value="ValidAdminPass123!"),
        patch("app.scripts.bootstrap_admin.get_db_session", fake_get_db_session),
        patch("app.scripts.bootstrap_admin.close_db_engine", close_mock),
        patch(
            "app.scripts.bootstrap_admin.check_database_target_safety", return_value=(True, "Safe")
        ),
        patch(
            "app.scripts.bootstrap_admin.bootstrap_admin",
            side_effect=RuntimeError("Simulated unhandled error"),
        ),
    ):
        with pytest.raises(RuntimeError, match="Simulated unhandled error"):
            await run_cli(["--email", "admin@u.edu", "--full-name", "Admin"])

        # Engine disposal MUST be invoked even upon unhandled exception
        close_mock.assert_awaited_once()


def test_check_database_target_safety_blocks_production(monkeypatch):
    """Rejects execution if settings.is_production is True (Requirements D, E.13)."""
    monkeypatch.setattr("app.core.config.settings.ENVIRONMENT", "production")
    is_safe, message = check_database_target_safety()
    assert is_safe is False
    assert "production" in message.lower()
    assert "separate explicit project-owner approval" in message


def test_check_database_target_safety_blocks_remote_host(monkeypatch):
    """Rejects execution if database host is remote or non-loopback (Requirements D, E.13)."""
    monkeypatch.setattr("app.core.config.settings.ENVIRONMENT", "development")
    monkeypatch.setattr(
        "app.core.config.settings.DATABASE_URL",
        "postgresql+asyncpg://user:pass@remote-postgres.render.com:5432/campusfix",
    )
    is_safe, message = check_database_target_safety()
    assert is_safe is False
    assert "remote or non-loopback" in message.lower()
    assert "separate explicit project-owner approval" in message


def test_check_database_target_safety_allows_local_loopback(monkeypatch):
    """Allows execution for local loopback hosts in non-production (Requirements D, E.13)."""
    monkeypatch.setattr("app.core.config.settings.ENVIRONMENT", "development")
    monkeypatch.setattr(
        "app.core.config.settings.DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/campusfix",
    )
    is_safe, message = check_database_target_safety()
    assert is_safe is True
    assert "local loopback host" in message.lower()

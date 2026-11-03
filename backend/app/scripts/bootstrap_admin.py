"""Operational CLI script to securely provision the initial CampusFix administrator.

Usage:
    python -m app.scripts.bootstrap_admin --email admin@university.edu --full-name "Campus Facilities Lead"

Security Rules:
    - Never accepts hardcoded, default, or environment-supplied passwords.
    - Prompts interactively with getpass.getpass() and confirms match.
    - Enforces >= 12 chars, uppercase, lowercase, digit, and special character.
    - Hashes password using Argon2id (RFC 9106 parameters).
    - Protects existing accounts: idempotent for existing ADMINISTRATOR (zero modifications).
    - Refuses promotion of STUDENT/STAFF unless --promote-existing is supplied AND operator
      interactively types exactly 'yes'. Non-interactive promotion is blocked.
    - Preserves all existing user profile fields (full name, password hash, active status)
      during promotion; mutates only the role.
    - Verifies database target safety: blocks execution against production environments
      or remote/non-loopback database hosts without separate explicit project-owner approval.
    - Disposes of database engine in a finally block.
    - Never prints or logs passwords or credential secrets.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import logging
import re
import sys
import uuid
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import close_db_engine, get_db_session
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.user import validate_email_format

logger = logging.getLogger("campusfix.bootstrap_admin")

LOCAL_DATABASE_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

# Common insecure or placeholder passwords strictly rejected
INSECURE_PASSWORDS = frozenset(
    {
        "admin",
        "admin123",
        "admin123!",
        "admin1234",
        "admin1234!",
        "admin12345",
        "admin12345!",
        "admin123456",
        "admin123456!",
        "administrator",
        "administrator123!",
        "password",
        "password123",
        "password123!",
        "campusfix",
        "campusfix123",
        "campusfix123!",
        "changeme",
        "changeme123",
        "letmein",
        "welcome",
        "welcome123",
        "root",
        "toor",
    }
)


class BootstrapResult(NamedTuple):
    """Result of an administrator bootstrap operation."""

    success: bool
    action: str  # "CREATED", "ALREADY_ADMIN", "PROMOTED", "REFUSED", "CANCELLED", "ERROR"
    user_id: uuid.UUID | None
    message: str


def check_database_target_safety() -> tuple[bool, str]:
    """Verifies that the target database and environment are safe for local bootstrap.

    Rejects execution if running in production or against a remote database host
    without separate explicit project-owner authorization (no bypass flag).
    """
    if settings.is_production:
        return (
            False,
            "Target environment is 'production'. Bootstrapping an administrator in "
            "production requires separate explicit project-owner approval.",
        )

    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite"):
        return True, "Local SQLite"

    try:
        parsed_url = make_url(db_url)
        host = parsed_url.host
    except Exception as err:
        return False, f"Failed to parse DATABASE_URL: {err}"

    if host is None or host.lower() not in LOCAL_DATABASE_HOSTS:
        return (
            False,
            f"Database host '{host}' is remote or non-loopback. Targeting remote "
            "databases requires separate explicit project-owner approval.",
        )

    return True, f"Local loopback host '{host}'"


def validate_admin_password(password: str) -> str:
    """Validates that candidate administrator password meets strict security criteria.

    Rules:
        - Minimum 12 characters.
        - Maximum 128 characters.
        - Not in common/default password blacklist.
        - At least one uppercase letter (A-Z).
        - At least one lowercase letter (a-z).
        - At least one numerical digit (0-9).
        - At least one special character.
    """
    if not isinstance(password, str):
        raise ValueError("Password must be a string")
    if len(password) < 12:
        raise ValueError("Administrator password must be at least 12 characters in length.")
    if len(password) > 128:
        raise ValueError("Administrator password cannot exceed 128 characters in length.")
    if password.lower() in INSECURE_PASSWORDS:
        raise ValueError(
            "The provided password is a common default or weak password. "
            "A strong, unique password is required."
        )
    if not re.search(r"[A-Z]", password):
        raise ValueError("Administrator password must contain at least one uppercase letter (A-Z).")
    if not re.search(r"[a-z]", password):
        raise ValueError("Administrator password must contain at least one lowercase letter (a-z).")
    if not re.search(r"\d", password):
        raise ValueError("Administrator password must contain at least one numerical digit (0-9).")
    if not re.search(r"[^a-zA-Z0-9]", password):
        raise ValueError(
            "Administrator password must contain at least one special character (e.g. !@#$%^&*)."
        )
    return password


async def bootstrap_admin(
    db: AsyncSession,
    email: str,
    full_name: str,
    password: str | None = None,
    promote_existing: bool = False,
    confirm_promotion: bool = False,
) -> BootstrapResult:
    """Provisions or verifies an initial CampusFix administrator account.

    Args:
        db: Asynchronous SQLAlchemy session.
        email: Administrator email address.
        full_name: Administrator display name.
        password: Raw plaintext password (validated and hashed with Argon2id).
        promote_existing: If True, allows promoting existing STUDENT or STAFF user.
        confirm_promotion: Explicit confirmation flag for existing user promotion.

    Returns:
        BootstrapResult with status, action, user_id, and descriptive message.
    """
    # 1. Normalize and validate inputs
    cleaned_email = validate_email_format(email)
    cleaned_name = full_name.strip()
    if not cleaned_name:
        return BootstrapResult(
            success=False,
            action="ERROR",
            user_id=None,
            message="Full name cannot be empty.",
        )

    try:
        # 2. Check for existing account
        stmt = select(User).where(User.email == cleaned_email)
        result = await db.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user is not None:
            # Case A: Existing user is already an ADMINISTRATOR (Idempotent safe return: zero changes)
            if existing_user.role == UserRole.ADMINISTRATOR.value:
                logger.info("Administrator account already exists: %s", cleaned_email)
                return BootstrapResult(
                    success=True,
                    action="ALREADY_ADMIN",
                    user_id=existing_user.id,
                    message=f"User '{cleaned_email}' is already an active ADMINISTRATOR (ID: {existing_user.id}). No changes made.",
                )

            # Case B: Existing user is STUDENT or STAFF
            if not promote_existing:
                logger.warning(
                    "Refusing promotion of existing user '%s' with role '%s' without explicit flag",
                    cleaned_email,
                    existing_user.role,
                )
                return BootstrapResult(
                    success=False,
                    action="REFUSED",
                    user_id=existing_user.id,
                    message=(
                        f"An account with email '{cleaned_email}' already exists with role '{existing_user.role}'. "
                        "Refusing automatic promotion. To promote this user to ADMINISTRATOR, rerun with --promote-existing."
                    ),
                )

            if not confirm_promotion:
                logger.info("Promotion not confirmed for user: %s", cleaned_email)
                return BootstrapResult(
                    success=False,
                    action="CANCELLED",
                    user_id=existing_user.id,
                    message="Promotion confirmation not provided. Operation cancelled.",
                )

            # Confirmed promotion: Mutate ONLY the role field.
            # Preserve existing full_name, hashed_password, is_active, and all other fields.
            previous_role = existing_user.role
            existing_user.role = UserRole.ADMINISTRATOR.value

            await db.commit()
            logger.info(
                "Promoted existing user '%s' from '%s' to ADMINISTRATOR (ID: %s)",
                cleaned_email,
                previous_role,
                existing_user.id,
            )
            return BootstrapResult(
                success=True,
                action="PROMOTED",
                user_id=existing_user.id,
                message=(
                    f"Successfully promoted existing user '{cleaned_email}' (ID: {existing_user.id}) "
                    f"from '{previous_role}' to 'ADMINISTRATOR'."
                ),
            )

        # Case C: New administrator creation
        if password is None:
            return BootstrapResult(
                success=False,
                action="ERROR",
                user_id=None,
                message="Password is required to create a new administrator account.",
            )

        validate_admin_password(password)
        hashed_pw = hash_password(password)

        new_user = User(
            id=uuid.uuid4(),
            email=cleaned_email,
            full_name=cleaned_name,
            hashed_password=hashed_pw,
            role=UserRole.ADMINISTRATOR.value,
            is_active=True,
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        logger.info("Successfully provisioned new administrator: %s", cleaned_email)
        return BootstrapResult(
            success=True,
            action="CREATED",
            user_id=new_user.id,
            message=f"Administrator '{cleaned_email}' successfully provisioned (ID: {new_user.id}).",
        )

    except Exception as exc:
        await db.rollback()
        logger.error("Database error during administrator bootstrap: %s", exc)
        return BootstrapResult(
            success=False,
            action="ERROR",
            user_id=None,
            message="Database transaction failed.",
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Configures and parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Securely provision or verify the initial CampusFix administrator account."
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Institutional email address for the administrator (e.g. admin@university.edu).",
    )
    parser.add_argument(
        "--full-name",
        required=True,
        help="Display name for the administrator (e.g. 'Campus Facilities Lead').",
    )
    parser.add_argument(
        "--promote-existing",
        action="store_true",
        default=False,
        help="Allow elevating an existing STUDENT or STAFF account to ADMINISTRATOR.",
    )
    return parser.parse_args(argv)


def prompt_password() -> str:
    """Interactively prompts for administrator password with masked input and confirmation."""
    pw1 = getpass.getpass("Enter administrator password: ")
    if not pw1:
        raise ValueError("Password cannot be empty.")

    pw2 = getpass.getpass("Confirm administrator password: ")
    if pw1 != pw2:
        raise ValueError("Passwords do not match.")

    return pw1


async def run_cli(argv: list[str] | None = None) -> int:
    """Async entrypoint for the CLI."""
    args = parse_args(argv)

    # 1. Validate email format upfront
    try:
        validate_email_format(args.email)
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    # 2. Check database target safety before any database interaction
    is_safe, safety_message = check_database_target_safety()
    if not is_safe:
        print(f"Security Error: {safety_message}", file=sys.stderr)
        return 1

    print(f"Target Environment: {settings.ENVIRONMENT}")
    print(f"Database Target: {settings.masked_database_url}")

    # 3. Interactive confirmation for promotion
    confirm_promotion = False
    if args.promote_existing:
        if not (hasattr(sys.stdin, "isatty") and sys.stdin.isatty()):
            print(
                "Error: Non-interactive execution cannot promote an existing account. "
                "An interactive TTY is required.",
                file=sys.stderr,
            )
            return 1
        try:
            response = input(
                f"Confirm promoting existing user '{args.email}' to ADMINISTRATOR? Type 'yes' to proceed: "
            ).strip()
            if response == "yes":
                confirm_promotion = True
            else:
                print(
                    f"Promotion cancelled: Expected exact response 'yes', received '{response}'.",
                    file=sys.stderr,
                )
                return 1
        except (EOFError, KeyboardInterrupt):
            print("\nPromotion cancelled: Input closed or interrupted.", file=sys.stderr)
            return 1

    # 4. Prompt for password with masked entry and double-entry confirmation
    password: str | None = None
    try:
        password = prompt_password()
        validate_admin_password(password)
    except ValueError as err:
        print(f"Password Error: {err}", file=sys.stderr)
        return 1

    # 5. Connect to database and execute within guaranteed engine disposal lifecycle
    try:
        async for db in get_db_session():
            result = await bootstrap_admin(
                db=db,
                email=args.email,
                full_name=args.full_name,
                password=password,
                promote_existing=args.promote_existing,
                confirm_promotion=confirm_promotion,
            )

            if result.success:
                print(f"SUCCESS: {result.message}")
                return 0
            else:
                print(f"FAILED: {result.message}", file=sys.stderr)
                return 1
    finally:
        await close_db_engine()

    return 1


def main() -> None:
    """Synchronous entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    exit_code = asyncio.run(run_cli())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

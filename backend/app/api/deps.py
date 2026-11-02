"""FastAPI dependency injection providers: database sessions and authentication."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.services.auth_service import AuthService

security_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection provider yielding an asynchronous database session per request."""
    async for session in get_db_session():
        yield session


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
) -> User:
    """Validates the Bearer access token from Authorization header and returns the User.

    Raises:
        HTTPException(401): If token is missing, expired, malformed, or user not found.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials.strip()

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err
    except jwt.PyJWTError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(str(user_id_str))
    except (ValueError, TypeError) as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err

    user = await AuthService.get_user_by_id(db, user_uuid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Verifies that the authenticated user account is active.

    Raises:
        HTTPException(403): If the user account is deactivated.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive. Please contact the administrator.",
        )
    return current_user


def require_roles(*allowed_roles: UserRole | str):
    """FastAPI dependency factory enforcing server-side Role-Based Access Control (RBAC).

    Validates that the authenticated user's role is within the permitted set of roles.

    Raises:
        HTTPException(403): If the user's role is unauthorized.
    """
    normalized = {UserRole(r) if isinstance(r, str) else r for r in allowed_roles}

    async def role_checker(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        user_role = (
            UserRole(current_user.role) if isinstance(current_user.role, str) else current_user.role
        )
        if user_role not in normalized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "INSUFFICIENT_PERMISSIONS",
                    "message": (
                        f"Action requires one of roles: {[r.value for r in normalized]}. "
                        f"User possesses role '{user_role.value}'."
                    ),
                },
            )
        return current_user

    return role_checker


# Reusable role-gated dependency aliases
require_admin = require_roles(UserRole.ADMINISTRATOR)
require_staff_or_admin = require_roles(UserRole.STAFF, UserRole.ADMINISTRATOR)
require_student_or_admin = require_roles(UserRole.STUDENT, UserRole.ADMINISTRATOR)

"""Authentication and user profile RESTful endpoints (/api/v1/auth)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.config import settings
from app.models.user import User
from app.schemas.auth import LoginResponseData, RefreshTokenRequest, TokenResponse
from app.schemas.common import MessageResponse, SuccessEnvelope
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.services.auth_service import (
    AuthenticationFailedError,
    AuthService,
    DuplicateEmailError,
    UserInactiveError,
)
from app.services.refresh_token_service import (
    ExpiredRefreshTokenError,
    InvalidRefreshTokenError,
    TokenReuseDetectedError,
)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"
REFRESH_COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400


def get_clear_cookie_headers() -> dict[str, str]:
    """Generates Set-Cookie header string to clear the refresh cookie on error responses."""
    secure_flag = "; Secure" if settings.is_production else ""
    return {
        "Set-Cookie": f"{REFRESH_COOKIE_NAME}=; Path={REFRESH_COOKIE_PATH}; Max-Age=0; HttpOnly; SameSite=lax{secure_flag}"
    }


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    """Sets the HttpOnly, SameSite=Lax refresh cookie with the configured lifetime."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.is_cookie_secure,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Clears the refresh cookie on normal response by setting an expired Max-Age=0."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value="",
        max_age=0,
        httponly=True,
        secure=settings.is_cookie_secure,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


@router.post(
    "/register",
    response_model=SuccessEnvelope[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register new student account",
)
async def register(
    user_create: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessEnvelope[UserResponse]:
    """Registers a new student account with Argon2id password hashing.

    Public registration strictly assigns the STUDENT role.
    """
    try:
        user = await AuthService.register_student(db=db, user_create=user_create)
    except DuplicateEmailError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EMAIL_ALREADY_REGISTERED",
                "message": "An account with this email address already exists.",
            },
        ) from err

    return SuccessEnvelope(data=UserResponse.model_validate(user))


@router.post(
    "/login",
    response_model=SuccessEnvelope[LoginResponseData],
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and issue tokens",
)
async def login(
    login_data: UserLogin,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessEnvelope[LoginResponseData]:
    """Authenticates user with email and password.

    Returns short-lived access JWT in response JSON and sets a 7-day HttpOnly refresh cookie.
    """
    try:
        login_result = await AuthService.login(db=db, login_data=login_data)
    except AuthenticationFailedError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Invalid email or password.",
            },
        ) from err
    except UserInactiveError as err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "USER_INACTIVE",
                "message": "Account is inactive. Please contact the administrator.",
            },
        ) from err

    # Set HttpOnly refresh cookie
    _set_refresh_cookie(response, login_result.raw_refresh_token)

    return SuccessEnvelope(
        data=LoginResponseData(
            access_token=login_result.access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(login_result.user),
        )
    )


@router.post(
    "/refresh",
    response_model=SuccessEnvelope[TokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and issue new access token",
)
async def refresh_token_endpoint(
    response: Response,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
    body: RefreshTokenRequest | None = None,
) -> SuccessEnvelope[TokenResponse]:
    """Atomically rotates the single-use refresh token using row-level locking.

    If token reuse is detected, revokes the entire session family and clears the client cookie.
    """
    clear_headers = get_clear_cookie_headers()
    candidate_token = refresh_token_cookie or (body.refresh_token if body else None)
    if not candidate_token:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_TOKEN",
                "message": "Refresh token is missing.",
            },
            headers=clear_headers,
        )

    try:
        refresh_result = await AuthService.refresh_session(
            db=db,
            raw_refresh_token=candidate_token,
        )
    except TokenReuseDetectedError as err:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "TOKEN_REUSE_DETECTED",
                "message": "Refresh token has already been consumed. Active session family revoked.",
            },
            headers=clear_headers,
        ) from err
    except ExpiredRefreshTokenError as err:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "TOKEN_EXPIRED",
                "message": "Refresh token has expired.",
            },
            headers=clear_headers,
        ) from err
    except InvalidRefreshTokenError as err:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_TOKEN",
                "message": "Invalid or unknown refresh token.",
            },
            headers=clear_headers,
        ) from err
    except UserInactiveError as err:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "USER_INACTIVE",
                "message": "User account is inactive. Please contact the administrator.",
            },
            headers=clear_headers,
        ) from err

    # Set new single-use refresh token in HttpOnly cookie
    _set_refresh_cookie(response, refresh_result.new_raw_refresh_token)

    return SuccessEnvelope(data=refresh_result.token_response)


@router.post(
    "/logout",
    response_model=SuccessEnvelope[MessageResponse],
    status_code=status.HTTP_200_OK,
    summary="Log out and terminate active session",
)
async def logout(
    response: Response,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> SuccessEnvelope[MessageResponse]:
    """Terminates session by marking the active refresh token as revoked and clearing the cookie."""
    if refresh_token_cookie:
        await AuthService.logout(db=db, raw_refresh_token=refresh_token_cookie)

    _clear_refresh_cookie(response)

    return SuccessEnvelope(data=MessageResponse(message="Successfully logged out."))


@router.get(
    "/me",
    response_model=SuccessEnvelope[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve authenticated user profile",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessEnvelope[UserResponse]:
    """Returns the authenticated identity and role profile of the current user."""
    return SuccessEnvelope(data=UserResponse.model_validate(current_user))

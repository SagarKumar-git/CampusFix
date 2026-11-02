"""Services package registering core domain logic and state machines."""

from __future__ import annotations

from app.services.auth_service import (
    AuthenticationFailedError,
    AuthError,
    AuthService,
    DuplicateEmailError,
    LoginResult,
    RefreshResult,
    UserInactiveError,
    UserNotFoundError,
)
from app.services.category_service import (
    CategoryError,
    CategoryService,
    DuplicateCategoryError,
)
from app.services.refresh_token_service import (
    ExpiredRefreshTokenError,
    InvalidRefreshTokenError,
    RefreshTokenError,
    RefreshTokenService,
    TokenIssueResult,
    TokenReuseDetectedError,
    generate_raw_token,
    hash_token,
)
from app.services.ticket_fsm import (
    InvalidAssigneeError,
    InvalidStateTransitionError,
    InvalidTargetStatusError,
    MissingTransitionCommentaryError,
    TerminalStateError,
    TicketDomainError,
    TicketFSM,
    TicketFSMError,
    UnauthorizedTransitionError,
)
from app.services.ticket_service import (
    CategoryInactiveError,
    CategoryNotFoundError,
    TicketConcurrencyError,
    TicketNotFoundError,
    TicketService,
)

__all__ = [
    # Auth Service
    "AuthService",
    "AuthError",
    "DuplicateEmailError",
    "AuthenticationFailedError",
    "UserInactiveError",
    "UserNotFoundError",
    "LoginResult",
    "RefreshResult",
    # Refresh Token Service
    "RefreshTokenService",
    "RefreshTokenError",
    "InvalidRefreshTokenError",
    "ExpiredRefreshTokenError",
    "TokenReuseDetectedError",
    "TokenIssueResult",
    "generate_raw_token",
    "hash_token",
    # Category Service
    "CategoryService",
    "CategoryError",
    "DuplicateCategoryError",
    # Ticket FSM
    "TicketFSM",
    "TicketDomainError",
    "TicketFSMError",
    "InvalidStateTransitionError",
    "TerminalStateError",
    "UnauthorizedTransitionError",
    "MissingTransitionCommentaryError",
    "InvalidTargetStatusError",
    "InvalidAssigneeError",
    # Ticket Domain Service
    "TicketService",
    "TicketNotFoundError",
    "TicketConcurrencyError",
    "CategoryNotFoundError",
    "CategoryInactiveError",
]

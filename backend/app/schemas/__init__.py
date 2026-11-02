"""Pydantic v2 schemas package for CampusFix API request and response contracts."""

from __future__ import annotations

from app.schemas.auth import (
    LoginResponseData,
    RefreshTokenRequest,
    TokenPayload,
    TokenResponse,
)
from app.schemas.category import (
    CategoryBase,
    CategoryCreate,
    CategoryResponse,
    CategorySummary,
    CategoryUpdate,
)
from app.schemas.common import (
    MessageResponse,
    PaginatedResponse,
    PaginationMeta,
    PaginationParams,
    SuccessEnvelope,
)
from app.schemas.error import (
    ErrorDetail,
    ErrorEnvelope,
    ProblemDetails,
    ValidationErrorItem,
)
from app.schemas.ticket import (
    AdminMetricsResponseData,
    TicketAssign,
    TicketAssignResponseData,
    TicketCreate,
    TicketFilterParams,
    TicketHistoryResponse,
    TicketResponse,
    TicketSummaryResponse,
    TicketTransition,
    TicketTransitionResponseData,
)
from app.schemas.user import (
    UserBase,
    UserCreate,
    UserLogin,
    UserQueryParams,
    UserResponse,
    UserRoleUpdate,
    UserSummary,
    validate_email_format,
    validate_password_complexity,
)

__all__ = [
    # Common & Envelopes
    "PaginationMeta",
    "PaginationParams",
    "SuccessEnvelope",
    "PaginatedResponse",
    "MessageResponse",
    # Error & Problem Details
    "ValidationErrorItem",
    "ErrorDetail",
    "ErrorEnvelope",
    "ProblemDetails",
    # User Schemas
    "UserBase",
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "UserSummary",
    "UserRoleUpdate",
    "UserQueryParams",
    "validate_email_format",
    "validate_password_complexity",
    # Auth Schemas
    "TokenResponse",
    "LoginResponseData",
    "RefreshTokenRequest",
    "TokenPayload",
    # Category Schemas
    "CategoryBase",
    "CategoryCreate",
    "CategoryUpdate",
    "CategoryResponse",
    "CategorySummary",
    # Ticket Schemas
    "TicketCreate",
    "TicketAssign",
    "TicketTransition",
    "TicketResponse",
    "TicketSummaryResponse",
    "TicketAssignResponseData",
    "TicketTransitionResponseData",
    "TicketHistoryResponse",
    "TicketFilterParams",
    "AdminMetricsResponseData",
]

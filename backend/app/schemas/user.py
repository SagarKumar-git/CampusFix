"""User account request and response Pydantic models."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import UserRole

# RFC 5322-compatible institutional email regex: username@domain.tld (requires valid TLD >= 2 chars)
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$")


def validate_email_format(v: str) -> str:
    """Validates institutional email format and normalizes to lowercase stripped string."""
    if not isinstance(v, str):
        raise ValueError("Email must be a string")
    cleaned = v.strip().lower()
    if not cleaned:
        raise ValueError("Email address cannot be empty")
    if len(cleaned) > 255:
        raise ValueError("Email address cannot exceed 255 characters")
    if not EMAIL_REGEX.match(cleaned):
        raise ValueError(
            "Email address must follow standard institutional format ('user@domain.tld')"
        )
    return cleaned


def validate_password_complexity(v: str) -> str:
    """Enforces FR-001 password complexity rules: min 8 chars, 1 digit, 1 upper, 1 lower."""
    if not isinstance(v, str):
        raise ValueError("Password must be a string")
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters in length")
    if len(v) > 128:
        raise ValueError("Password cannot exceed 128 characters in length")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one numerical digit (0-9)")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter (A-Z)")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter (a-z)")
    return v


class UserBase(BaseModel):
    """Base shared user attributes."""

    email: str = Field(description="Institutional email address")
    full_name: str = Field(
        min_length=1,
        max_length=150,
        description="Full legal or preferred name of the user",
    )

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        return validate_email_format(v)

    @field_validator("full_name")
    @classmethod
    def check_full_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Full name cannot be empty or pure whitespace")
        return stripped


class UserCreate(BaseModel):
    """Public self-registration request model. Strictly grants STUDENT role."""

    full_name: str = Field(
        min_length=1,
        max_length=150,
        description="Full legal or preferred name of the student",
    )
    email: str = Field(description="Institutional student email address")
    password: str = Field(
        description="Secure plaintext password (min 8 chars, >=1 upper, >=1 lower, >=1 number)"
    )

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        return validate_email_format(v)

    @field_validator("full_name")
    @classmethod
    def check_full_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Full name cannot be empty or pure whitespace")
        return stripped

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_complexity(v)


class UserLogin(BaseModel):
    """User authentication credentials request model."""

    email: str = Field(description="Registered institutional email address")
    password: str = Field(min_length=1, max_length=128, description="Account password")

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        return validate_email_format(v)

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Password cannot be empty")
        return v


class UserResponse(BaseModel):
    """Public user identity and profile response model. Never exposes password hashes or tokens."""

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool = True
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class UserSummary(BaseModel):
    """Lightweight user identity model for embedding in ticket and audit responses."""

    id: uuid.UUID
    full_name: str

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class UserRoleUpdate(BaseModel):
    """Administrative user role modification request model."""

    role: UserRole = Field(description="Target role to assign (STUDENT, STAFF, ADMINISTRATOR)")

    model_config = ConfigDict(extra="forbid")


class UserQueryParams(BaseModel):
    """Administrative query parameters for listing user accounts."""

    page: int = Field(default=1, ge=1, description="1-based page index")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page limit")
    search: str | None = Field(
        default=None,
        description="Case-insensitive search query matching full_name or email",
    )
    role: UserRole | None = Field(default=None, description="Filter by user role")
    is_active: bool | None = Field(default=None, description="Filter by account active status")

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("search")
    @classmethod
    def clean_search(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            return stripped if stripped else None
        return None

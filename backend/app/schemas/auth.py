"""Authentication request and response Pydantic models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserResponse


class TokenResponse(BaseModel):
    """Access token issuance response model (e.g. for /auth/refresh)."""

    access_token: str = Field(description="Signed short-lived JWT access token")
    token_type: str = Field(default="bearer", description="Token authorization type")
    expires_in: int = Field(
        default=900, description="Token validity duration in seconds (15 minutes)"
    )

    model_config = ConfigDict(extra="forbid")


class LoginResponseData(BaseModel):
    """Successful authentication response payload. Does not include refresh token (issued via HttpOnly cookie)."""

    access_token: str = Field(description="Signed short-lived JWT access token")
    token_type: str = Field(default="bearer", description="Token authorization type")
    expires_in: int = Field(
        default=900, description="Token validity duration in seconds (15 minutes)"
    )
    user: UserResponse = Field(description="Authenticated user identity and role profile")

    model_config = ConfigDict(extra="forbid")


class RefreshTokenRequest(BaseModel):
    """Optional payload for clients transmitting refresh token in request body rather than cookie."""

    refresh_token: str = Field(description="High-entropy refresh token string")

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TokenPayload(BaseModel):
    """Decoded access JWT claims payload schema."""

    sub: str = Field(description="Subject identifier (user UUID string)")
    email: str = Field(description="User institutional email address")
    role: str = Field(description="Authorization role claim")
    type: str = Field(default="access", description="Token type discriminator ('access')")
    iat: int = Field(description="Issued at epoch timestamp (seconds)")
    exp: int = Field(description="Expiration epoch timestamp (seconds)")

    model_config = ConfigDict(extra="ignore")

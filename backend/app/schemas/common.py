"""Common reusable schemas: envelopes, pagination, and basic messages."""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Pagination metadata included in paginated collection responses."""

    page: int = Field(ge=1, description="1-based current page index")
    page_size: int = Field(ge=1, le=100, description="Items per page limit")
    total: int = Field(ge=0, description="Total matching items across all pages")
    total_pages: int = Field(ge=0, description="Total number of available pages")

    model_config = ConfigDict(extra="forbid")


class PaginationParams(BaseModel):
    """Standard query parameters for paginated endpoints."""

    page: int = Field(default=1, ge=1, description="1-based page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page cap (max 100)")

    model_config = ConfigDict(extra="forbid")


class SuccessEnvelope(BaseModel, Generic[T]):
    """Standard API success envelope wrapping resource data."""

    success: Literal[True] = True
    data: T

    model_config = ConfigDict(extra="forbid")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard API envelope for paginated collection responses."""

    success: Literal[True] = True
    data: list[T]
    meta: PaginationMeta

    model_config = ConfigDict(extra="forbid")


class MessageResponse(BaseModel):
    """Generic informational message response (e.g. logout confirmation)."""

    message: str

    model_config = ConfigDict(extra="forbid")

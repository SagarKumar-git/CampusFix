"""Facility issue category request and response Pydantic models."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryBase(BaseModel):
    """Shared category attributes."""

    name: str = Field(min_length=2, max_length=100, description="Unique operational category title")
    description: str = Field(
        min_length=5, description="Explanatory scope and examples for the category"
    )
    is_active: bool = Field(
        default=True, description="Whether the category is available for filing tickets"
    )


class CategoryCreate(BaseModel):
    """Administrative category creation request model."""

    name: str = Field(min_length=2, max_length=100, description="Unique operational category title")
    description: str = Field(
        min_length=5, description="Explanatory scope and examples for the category"
    )
    is_active: bool = Field(default=True, description="Initial availability status")

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("name")
    @classmethod
    def check_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Category name cannot be empty or pure whitespace")
        return stripped

    @field_validator("description")
    @classmethod
    def check_description(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Category description cannot be empty or pure whitespace")
        return stripped


class CategoryUpdate(BaseModel):
    """Administrative category partial modification request model."""

    name: str | None = Field(
        default=None, min_length=2, max_length=100, description="Updated category title"
    )
    description: str | None = Field(
        default=None, min_length=5, description="Updated scope description"
    )
    is_active: bool | None = Field(default=None, description="Updated category active status")

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("name")
    @classmethod
    def check_name(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("Category name cannot be empty or pure whitespace")
            return stripped
        return None

    @field_validator("description")
    @classmethod
    def check_description(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("Category description cannot be empty or pure whitespace")
            return stripped
        return None


class CategoryResponse(BaseModel):
    """Detailed category representation."""

    id: uuid.UUID
    name: str
    description: str
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class CategorySummary(BaseModel):
    """Compact category reference embedded in ticket responses."""

    id: uuid.UUID
    name: str

    model_config = ConfigDict(from_attributes=True, extra="ignore")

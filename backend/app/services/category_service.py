"""Category domain service orchestrating category creation, updates, and listings."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate


class CategoryError(Exception):
    """Base exception for category service errors."""


class CategoryNotFoundError(CategoryError):
    """Raised when a facility category is not found."""


class DuplicateCategoryError(CategoryError):
    """Raised when attempting to create or rename a category to an existing name."""


class CategoryService:
    """Domain service managing facility issue categories."""

    @classmethod
    async def list_categories(
        cls,
        db: AsyncSession,
        *,
        include_inactive: bool = False,
    ) -> list[Category]:
        """Retrieves all facility issue categories.

        By default, returns only active categories.
        """
        stmt = select(Category).order_by(Category.name.asc())
        if not include_inactive:
            stmt = stmt.where(Category.is_active.is_(True))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def get_category_by_id(
        cls,
        db: AsyncSession,
        category_id: uuid.UUID,
    ) -> Category:
        """Retrieves a single category by primary key UUID."""
        stmt = select(Category).where(Category.id == category_id)
        result = await db.execute(stmt)
        category = result.scalar_one_or_none()
        if not category:
            raise CategoryNotFoundError(f"Category '{category_id}' was not found.")
        return category

    @classmethod
    async def create_category(
        cls,
        db: AsyncSession,
        *,
        data: CategoryCreate,
    ) -> Category:
        """Creates a new facility issue category."""
        # Check for duplicate name (case-insensitive)
        existing_stmt = select(Category).where(
            func.lower(Category.name) == data.name.strip().lower()
        )
        existing_res = await db.execute(existing_stmt)
        if existing_res.scalar_one_or_none() is not None:
            raise DuplicateCategoryError(f"A category named '{data.name.strip()}' already exists.")

        category = Category(
            id=uuid.uuid4(),
            name=data.name.strip(),
            description=data.description.strip(),
            is_active=data.is_active,
        )
        db.add(category)
        await db.commit()
        await db.refresh(category)
        return category

    @classmethod
    async def update_category(
        cls,
        db: AsyncSession,
        *,
        category_id: uuid.UUID,
        data: CategoryUpdate,
    ) -> Category:
        """Updates an existing category's name, description, or active status."""
        category = await cls.get_category_by_id(db, category_id)

        if data.name is not None and data.name.strip().lower() != category.name.lower():
            # Check if new name conflicts with an existing category
            existing_stmt = select(Category).where(
                func.lower(Category.name) == data.name.strip().lower(),
                Category.id != category_id,
            )
            existing_res = await db.execute(existing_stmt)
            if existing_res.scalar_one_or_none() is not None:
                raise DuplicateCategoryError(
                    f"A category named '{data.name.strip()}' already exists."
                )
            category.name = data.name.strip()

        if data.description is not None:
            category.description = data.description.strip()

        if data.is_active is not None:
            category.is_active = data.is_active

        category.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(category)
        return category

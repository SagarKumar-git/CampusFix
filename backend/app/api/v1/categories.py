"""Facility issue categories RESTful endpoints (/api/v1/categories)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db, require_admin
from app.models.user import User, UserRole
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.schemas.common import SuccessEnvelope
from app.services.category_service import (
    CategoryNotFoundError,
    CategoryService,
    DuplicateCategoryError,
)

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get(
    "",
    response_model=SuccessEnvelope[list[CategoryResponse]],
    status_code=status.HTTP_200_OK,
    summary="List facility issue categories",
)
async def list_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    include_inactive: bool = Query(
        default=False,
        description="Whether to include inactive categories (available for administrators only)",
    ),
) -> SuccessEnvelope[list[CategoryResponse]]:
    """Lists operational facility categories for issue filing and triage."""
    # Only administrators may view inactive categories
    allow_inactive = include_inactive and current_user.role == UserRole.ADMINISTRATOR.value

    categories = await CategoryService.list_categories(db, include_inactive=allow_inactive)
    items = [CategoryResponse.model_validate(c) for c in categories]
    return SuccessEnvelope(data=items)


@router.get(
    "/{id}",
    response_model=SuccessEnvelope[CategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve facility issue category by ID",
)
async def get_category(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_active_user)],
) -> SuccessEnvelope[CategoryResponse]:
    """Retrieves a single facility category by its UUID primary key."""
    try:
        category = await CategoryService.get_category_by_id(db, id)
    except CategoryNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND", "message": str(err)},
        ) from err

    return SuccessEnvelope(data=CategoryResponse.model_validate(category))


@router.post(
    "",
    response_model=SuccessEnvelope[CategoryResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new facility issue category",
)
async def create_category(
    data: CategoryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> SuccessEnvelope[CategoryResponse]:
    """Creates a new facility maintenance category. Restricted strictly to administrators."""
    try:
        category = await CategoryService.create_category(db, data=data)
    except DuplicateCategoryError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CATEGORY_ALREADY_EXISTS", "message": str(err)},
        ) from err

    return SuccessEnvelope(data=CategoryResponse.model_validate(category))


@router.patch(
    "/{id}",
    response_model=SuccessEnvelope[CategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Update or activate/deactivate a facility issue category",
)
async def update_category(
    id: uuid.UUID,
    data: CategoryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> SuccessEnvelope[CategoryResponse]:
    """Updates an existing category title, description, or active status. Restricted to administrators."""
    try:
        category = await CategoryService.update_category(db, category_id=id, data=data)
    except CategoryNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND", "message": str(err)},
        ) from err
    except DuplicateCategoryError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CATEGORY_ALREADY_EXISTS", "message": str(err)},
        ) from err

    return SuccessEnvelope(data=CategoryResponse.model_validate(category))

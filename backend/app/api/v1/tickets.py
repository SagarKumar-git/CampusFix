"""Maintenance tickets RESTful management endpoints (/api/v1/tickets)."""

from __future__ import annotations

import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_active_user,
    get_db,
    require_staff_or_admin,
)
from app.models.ticket import TicketPriority, TicketStatus
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationMeta, SuccessEnvelope
from app.schemas.ticket import (
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
from app.schemas.user import UserSummary
from app.services.ticket_fsm import (
    InvalidAssigneeError,
    InvalidStateTransitionError,
    InvalidTargetStatusError,
    MissingTransitionCommentaryError,
    TerminalStateError,
    UnauthorizedTransitionError,
)
from app.services.ticket_service import (
    CategoryInactiveError,
    CategoryNotFoundError,
    TicketConcurrencyError,
    TicketNotFoundError,
    TicketService,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post(
    "",
    response_model=SuccessEnvelope[TicketResponse],
    status_code=status.HTTP_201_CREATED,
    summary="File a new maintenance issue ticket",
)
async def create_ticket(
    data: TicketCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessEnvelope[TicketResponse]:
    """Submits a new campus facility issue report. Creator is unconditionally bound from the authenticated session."""
    try:
        ticket = await TicketService.create_ticket(
            db,
            creator=current_user,
            title=data.title,
            description=data.description,
            category_id=data.category_id,
            location=data.location,
            priority=data.priority,
        )
    except CategoryNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CATEGORY_NOT_FOUND", "message": str(err)},
        ) from err
    except CategoryInactiveError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "CATEGORY_INACTIVE", "message": str(err)},
        ) from err

    return SuccessEnvelope(data=TicketResponse.model_validate(ticket))


@router.get(
    "",
    response_model=PaginatedResponse[TicketSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="List tickets with filtering and pagination",
)
async def list_tickets(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page cap"),
    ticket_status: str | None = Query(
        default=None,
        alias="status",
        description="Filter by status (single or comma-separated tokens)",
    ),
    assigned_staff_id: str | None = Query(
        default=None,
        description="Technician UUID or 'me' for authenticated technician queue",
    ),
    category_id: uuid.UUID | None = Query(
        default=None,
        description="Filter by facility issue category UUID",
    ),
    priority: TicketPriority | None = Query(
        default=None,
        description="Filter by urgency tier (LOW, MEDIUM, HIGH, CRITICAL)",
    ),
) -> PaginatedResponse[TicketSummaryResponse]:
    """Lists tickets subject to role-based access control and IDOR isolation."""
    try:
        filters = TicketFilterParams(
            page=page,
            page_size=page_size,
            status=ticket_status,
            assigned_staff_id=assigned_staff_id,
            category_id=category_id,
            priority=priority,
        )
    except ValidationError as err:
        first_error = err.errors()[0] if err.errors() else {}
        details = [
            {
                "field": " -> ".join(str(p) for p in e.get("loc", [])),
                "message": e.get("msg", "Invalid parameter"),
                "type": e.get("type", "validation_error"),
            }
            for e in err.errors()
        ]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "VALIDATION_ERROR",
                "message": first_error.get("msg", "Invalid query parameters"),
                "details": details,
            },
        ) from err

    tickets, total = await TicketService.list_tickets(db, actor=current_user, filters=filters)

    items = [
        TicketSummaryResponse(
            id=t.id,
            ticket_number=t.ticket_number,
            title=t.title,
            category_name=t.category.name if t.category else "Uncategorized",
            location=t.location,
            priority=TicketPriority(t.priority),
            status=TicketStatus(t.status),
            creator_name=t.creator.full_name if t.creator else "Unknown",
            assigned_staff_name=t.assigned_staff.full_name if t.assigned_staff else None,
            created_at=t.created_at,
        )
        for t in tickets
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse(
        data=items,
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        ),
    )


@router.get(
    "/{id}",
    response_model=SuccessEnvelope[TicketResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve detailed ticket information by UUID",
)
async def get_ticket(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessEnvelope[TicketResponse]:
    """Retrieves full ticket details. Students may only view tickets they created (IDOR defense)."""
    try:
        ticket = await TicketService.get_ticket_by_id(db, ticket_id=id, actor=current_user)
    except TicketNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND", "message": str(err)},
        ) from err

    return SuccessEnvelope(data=TicketResponse.model_validate(ticket))


@router.post(
    "/{id}/assign",
    response_model=SuccessEnvelope[TicketAssignResponseData],
    status_code=status.HTTP_200_OK,
    summary="Assign or self-claim a ticket",
)
async def assign_ticket(
    id: uuid.UUID,
    data: TicketAssign,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_staff_or_admin)],
) -> SuccessEnvelope[TicketAssignResponseData]:
    """Assigns or claims a ticket. Restricted to staff and administrators."""
    try:
        ticket = await TicketService.assign_ticket(
            db,
            ticket_id=id,
            actor=current_user,
            staff_id=data.staff_id,
            expected_version=data.expected_version,
        )
    except TicketNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND", "message": str(err)},
        ) from err
    except TicketConcurrencyError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CONCURRENCY_CONFLICT",
                "message": str(err),
                "details": {
                    "expected_version": err.expected_version,
                    "actual_version": err.actual_version,
                },
            },
        ) from err
    except InvalidAssigneeError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "INVALID_ASSIGNEE", "message": str(err)},
        ) from err
    except UnauthorizedTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "INSUFFICIENT_PERMISSIONS", "message": str(err)},
        ) from err
    except InvalidStateTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "INVALID_STATE_TRANSITION", "message": str(err)},
        ) from err

    return SuccessEnvelope(
        data=TicketAssignResponseData(
            id=ticket.id,
            ticket_number=ticket.ticket_number,
            status=TicketStatus(ticket.status),
            assigned_staff_id=ticket.assigned_staff_id,
            version=ticket.version,
            updated_at=ticket.updated_at,
        )
    )


@router.post(
    "/{id}/transition",
    response_model=SuccessEnvelope[TicketTransitionResponseData],
    status_code=status.HTTP_200_OK,
    summary="Transition ticket lifecycle status or reopen ticket",
)
async def transition_ticket(
    id: uuid.UUID,
    data: TicketTransition,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessEnvelope[TicketTransitionResponseData]:
    """Executes a validated FSM state transition or administrative reopening."""
    try:
        ticket = await TicketService.transition_ticket(
            db,
            ticket_id=id,
            actor=current_user,
            target_status=data.target_status,
            expected_version=data.expected_version,
            notes=data.notes,
            assigned_staff_id=data.assigned_staff_id,
        )
    except TicketNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND", "message": str(err)},
        ) from err
    except TicketConcurrencyError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CONCURRENCY_CONFLICT",
                "message": str(err),
                "details": {
                    "expected_version": err.expected_version,
                    "actual_version": err.actual_version,
                },
            },
        ) from err
    except MissingTransitionCommentaryError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "MISSING_TRANSITION_COMMENTARY", "message": str(err)},
        ) from err
    except UnauthorizedTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "INSUFFICIENT_PERMISSIONS", "message": str(err)},
        ) from err
    except InvalidTargetStatusError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "INVALID_TARGET_STATUS", "message": str(err)},
        ) from err
    except InvalidStateTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "INVALID_STATE_TRANSITION", "message": str(err)},
        ) from err
    except TerminalStateError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "TERMINAL_STATE", "message": str(err)},
        ) from err
    except InvalidAssigneeError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "INVALID_ASSIGNEE", "message": str(err)},
        ) from err

    return SuccessEnvelope(
        data=TicketTransitionResponseData(
            id=ticket.id,
            ticket_number=ticket.ticket_number,
            status=TicketStatus(ticket.status),
            resolution_notes=ticket.resolution_notes,
            rejection_reason=ticket.rejection_reason,
            version=ticket.version,
            updated_at=ticket.updated_at,
        )
    )


@router.get(
    "/{id}/history",
    response_model=SuccessEnvelope[list[TicketHistoryResponse]],
    status_code=status.HTTP_200_OK,
    summary="Retrieve chronological audit trail for a ticket",
)
async def get_ticket_history(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessEnvelope[list[TicketHistoryResponse]]:
    """Retrieves immutable status transition history. Subject to student IDOR isolation."""
    try:
        history_records = await TicketService.get_ticket_history(
            db, ticket_id=id, actor=current_user
        )
    except TicketNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND", "message": str(err)},
        ) from err

    items = [
        TicketHistoryResponse(
            id=h.id,
            ticket_id=h.ticket_id,
            from_status=h.from_status,
            to_status=h.to_status,
            changed_by=(
                UserSummary.model_validate(h.changed_by_user)
                if h.changed_by_user
                else UserSummary(id=h.changed_by_user_id, full_name="Unknown")
            ),
            assigned_to=(
                UserSummary.model_validate(h.assigned_to_user) if h.assigned_to_user else None
            ),
            notes=h.notes,
            created_at=h.created_at,
        )
        for h in history_records
    ]

    return SuccessEnvelope(data=items)

"""Ticket management request, response, and filtering Pydantic models."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.ticket import TicketPriority, TicketStatus
from app.schemas.category import CategorySummary
from app.schemas.user import UserSummary


class TicketCreate(BaseModel):
    """Payload for submitting a new campus maintenance ticket."""

    title: str = Field(
        min_length=5,
        max_length=120,
        description="Concise, descriptive headline of the physical issue",
    )
    description: str = Field(
        min_length=10,
        max_length=2000,
        description="Detailed contextual breakdown of the facility problem",
    )
    category_id: uuid.UUID = Field(description="UUID of an active facility maintenance category")
    location: str = Field(
        min_length=3,
        max_length=100,
        description="Physical campus location (e.g. 'Science Block A, Room 402')",
    )
    priority: TicketPriority = Field(
        default=TicketPriority.MEDIUM,
        description="Urgency tier (LOW, MEDIUM, HIGH, CRITICAL). Defaults to MEDIUM.",
    )

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("title")
    @classmethod
    def check_title(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 5:
            raise ValueError("Title must be at least 5 characters after trimming")
        return stripped

    @field_validator("description")
    @classmethod
    def check_description(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 10:
            raise ValueError("Description must be at least 10 characters after trimming")
        return stripped

    @field_validator("location")
    @classmethod
    def check_location(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 3:
            raise ValueError("Location must be at least 3 characters after trimming")
        return stripped


class TicketAssign(BaseModel):
    """Payload for assigning or reassigning a ticket to a staff technician."""

    staff_id: uuid.UUID = Field(description="UUID of the staff technician to assign")
    expected_version: int = Field(
        ge=1,
        description="Current ticket version for optimistic concurrency verification",
    )

    model_config = ConfigDict(extra="forbid")


class TicketTransition(BaseModel):
    """Payload for requesting a status transition in the ticket lifecycle."""

    target_status: TicketStatus = Field(
        description="Target destination status in the Finite State Machine"
    )
    notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Explanatory notes or mandatory resolution/rejection justification",
    )
    assigned_staff_id: uuid.UUID | None = Field(
        default=None,
        description="Optional staff technician UUID when reopening a ticket to ASSIGNED",
    )
    expected_version: int = Field(
        ge=1,
        description="Current ticket version for optimistic concurrency verification",
    )

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            return stripped if stripped else None
        return None

    @model_validator(mode="after")
    def validate_transition_commentary(self) -> TicketTransition:
        """Enforces FR-015 mandatory commentary rules for RESOLVED and REJECTED statuses."""
        if self.target_status == TicketStatus.RESOLVED:
            if not self.notes or len(self.notes) < 10:
                raise ValueError(
                    "Resolving a ticket strictly requires 'notes' detailing resolution actions "
                    "(minimum 10 characters)."
                )
        elif self.target_status == TicketStatus.REJECTED:
            if not self.notes or len(self.notes) < 10:
                raise ValueError(
                    "Rejecting a ticket strictly requires 'notes' detailing the rejection reason "
                    "(minimum 10 characters)."
                )
        elif self.notes is not None and len(self.notes) < 10:
            raise ValueError("Transition notes must be at least 10 characters if provided.")
        return self


class TicketResponse(BaseModel):
    """Detailed ticket representation returned on GET /tickets/{id}."""

    id: uuid.UUID
    ticket_number: str
    title: str
    description: str
    category: CategorySummary
    location: str
    priority: TicketPriority
    status: TicketStatus
    creator: UserSummary
    assigned_staff: UserSummary | None = None
    resolution_notes: str | None = None
    rejection_reason: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class TicketSummaryResponse(BaseModel):
    """Flattened ticket summary representation returned in GET /tickets paginated lists."""

    id: uuid.UUID
    ticket_number: str
    title: str
    category_name: str
    location: str
    priority: TicketPriority
    status: TicketStatus
    creator_name: str
    assigned_staff_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class TicketAssignResponseData(BaseModel):
    """Data payload returned on successful ticket assignment."""

    id: uuid.UUID
    ticket_number: str
    status: TicketStatus
    assigned_staff_id: uuid.UUID | None
    version: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class TicketTransitionResponseData(BaseModel):
    """Data payload returned on successful ticket state transition."""

    id: uuid.UUID
    ticket_number: str
    status: TicketStatus
    resolution_notes: str | None = None
    rejection_reason: str | None = None
    version: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class TicketHistoryResponse(BaseModel):
    """Immutable status and assignment audit history record."""

    id: uuid.UUID
    ticket_id: uuid.UUID
    from_status: str | None = None
    to_status: str
    changed_by: UserSummary
    assigned_to: UserSummary | None = None
    notes: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class TicketFilterParams(BaseModel):
    """Query parameters for filtering and paginating tickets."""

    page: int = Field(default=1, ge=1, description="1-based page index")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page limit")
    status: str | None = Field(
        default=None,
        description="Filter by single status or comma-separated statuses (e.g. 'SUBMITTED,ASSIGNED')",
    )
    assigned_staff_id: str | None = Field(
        default=None,
        description="Filter by technician ID or literal 'me' for authenticated staff queue",
    )
    category_id: uuid.UUID | None = Field(
        default=None,
        description="Filter by facility issue category UUID",
    )
    priority: TicketPriority | None = Field(
        default=None,
        description="Filter by urgency tier (LOW, MEDIUM, HIGH, CRITICAL)",
    )

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("status")
    @classmethod
    def validate_status_tokens(cls, v: str | None) -> str | None:
        if v is None:
            return None
        tokens = [token.strip().upper() for token in v.split(",") if token.strip()]
        if not tokens:
            raise ValueError("Status filter cannot be empty if specified")
        valid_statuses = {s.value for s in TicketStatus}
        invalid_tokens = [t for t in tokens if t not in valid_statuses]
        if invalid_tokens:
            raise ValueError(
                f"Invalid status filter values: {invalid_tokens}. "
                f"Must be one or more of {sorted(valid_statuses)}."
            )
        return ",".join(tokens)

    @field_validator("assigned_staff_id")
    @classmethod
    def validate_assigned_staff_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip().lower()
        if cleaned == "me":
            return "me"
        try:
            parsed = uuid.UUID(v.strip())
            return str(parsed)
        except ValueError as err:
            raise ValueError("assigned_staff_id must be either 'me' or a valid UUID") from err


class AdminMetricsResponseData(BaseModel):
    """Aggregated operational metrics for the administrator dashboard."""

    total_tickets: int = Field(ge=0, description="Cumulative count of tickets filed")
    by_status: dict[str, int] = Field(description="Ticket count distribution across statuses")
    by_priority: dict[str, int] = Field(
        description="Ticket count distribution across priority tiers"
    )
    avg_resolution_hours: float = Field(
        ge=0.0, description="Mean elapsed hours from SUBMITTED to RESOLVED"
    )

    model_config = ConfigDict(extra="forbid")

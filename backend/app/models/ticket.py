"""Ticket ORM model for maintenance complaints and triage."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    desc,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.ticket_history import TicketStatusHistory
    from app.models.user import User


class TicketPriority(enum.StrEnum):
    """Urgency level assigned to a ticket."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TicketStatus(enum.StrEnum):
    """Lifecycle states of the CampusFix Finite State Machine."""

    SUBMITTED = "SUBMITTED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class Ticket(Base):
    """Core transactional entity tracking facility maintenance issues."""

    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    ticket_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    location: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TicketPriority.MEDIUM.value,
        server_default=text("'MEDIUM'"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TicketStatus.SUBMITTED.value,
        server_default=text("'SUBMITTED'"),
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_staff_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolution_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_tickets_priority",
        ),
        CheckConstraint(
            "status IN ('SUBMITTED', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED', 'REJECTED', 'CANCELLED')",
            name="ck_tickets_status",
        ),
        Index("idx_tickets_number", "ticket_number", unique=True),
        Index("idx_tickets_creator_created", "creator_id", desc("created_at")),
        Index("idx_tickets_assigned_status", "assigned_staff_id", "status"),
        Index("idx_tickets_status_category", "status", "category_id"),
    )

    # Relationships
    category: Mapped[Category] = relationship(
        "Category",
        back_populates="tickets",
    )
    creator: Mapped[User] = relationship(
        "User",
        back_populates="created_tickets",
        foreign_keys=[creator_id],
    )
    assigned_staff: Mapped[User | None] = relationship(
        "User",
        back_populates="assigned_tickets",
        foreign_keys=[assigned_staff_id],
    )
    status_history: Mapped[list[TicketStatusHistory]] = relationship(
        "TicketStatusHistory",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketStatusHistory.created_at.asc()",
    )

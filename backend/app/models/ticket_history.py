"""Ticket status history append-only audit log ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    asc,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.ticket import Ticket
    from app.models.user import User


class TicketStatusHistory(Base):
    """Immutable audit trail entry for ticket state transitions and assignments."""

    __tablename__ = "ticket_status_history"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    to_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_history_ticket_created", "ticket_id", asc("created_at")),
        Index("idx_history_assigned_to", "assigned_to_user_id"),
    )

    # Relationships
    ticket: Mapped[Ticket] = relationship(
        "Ticket",
        back_populates="status_history",
    )
    changed_by_user: Mapped[User] = relationship(
        "User",
        back_populates="status_history_changes",
        foreign_keys=[changed_by_user_id],
    )
    assigned_to_user: Mapped[User | None] = relationship(
        "User",
        back_populates="assigned_history_records",
        foreign_keys=[assigned_to_user_id],
    )

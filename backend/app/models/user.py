"""User account and authentication ORM model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.refresh_token import RefreshToken
    from app.models.ticket import Ticket
    from app.models.ticket_history import TicketStatusHistory


class UserRole(enum.StrEnum):
    """Permitted authorization roles in CampusFix."""

    STUDENT = "STUDENT"
    STAFF = "STAFF"
    ADMINISTRATOR = "ADMINISTRATOR"


class User(Base):
    """User account entity storing credentials, role, and profile."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=UserRole.STUDENT.value,
        server_default=text("'STUDENT'"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
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
            "role IN ('STUDENT', 'STAFF', 'ADMINISTRATOR')",
            name="ck_users_role",
        ),
        Index("idx_users_email", "email", unique=True),
    )

    # Relationships
    created_tickets: Mapped[list[Ticket]] = relationship(
        "Ticket",
        back_populates="creator",
        foreign_keys="[Ticket.creator_id]",
    )
    assigned_tickets: Mapped[list[Ticket]] = relationship(
        "Ticket",
        back_populates="assigned_staff",
        foreign_keys="[Ticket.assigned_staff_id]",
    )
    status_history_changes: Mapped[list[TicketStatusHistory]] = relationship(
        "TicketStatusHistory",
        back_populates="changed_by_user",
        foreign_keys="[TicketStatusHistory.changed_by_user_id]",
    )
    assigned_history_records: Mapped[list[TicketStatusHistory]] = relationship(
        "TicketStatusHistory",
        back_populates="assigned_to_user",
        foreign_keys="[TicketStatusHistory.assigned_to_user_id]",
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

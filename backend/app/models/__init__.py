"""SQLAlchemy 2.0 ORM models package for CampusFix.

Exports all declarative models and ensures their metadata is registered on Base.metadata.
"""

from app.models.category import Category
from app.models.refresh_token import RefreshToken
from app.models.ticket import Ticket, TicketPriority, TicketStatus
from app.models.ticket_history import TicketStatusHistory
from app.models.user import User, UserRole

__all__ = [
    "Category",
    "RefreshToken",
    "Ticket",
    "TicketPriority",
    "TicketStatus",
    "TicketStatusHistory",
    "User",
    "UserRole",
]

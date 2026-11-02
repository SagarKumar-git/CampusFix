"""Ticket domain service orchestrating creation, assignment, FSM transitions, and audit logs.

Implements transactional business operations, optimistic version concurrency control,
PostgreSQL row-level locking (SELECT ... FOR UPDATE), and append-only status audit trails
as specified in docs/ARCHITECTURE.md and docs/REQUIREMENTS.md.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.category import Category
from app.models.ticket import Ticket, TicketPriority, TicketStatus
from app.models.ticket_history import TicketStatusHistory
from app.models.user import User, UserRole
from app.schemas.ticket import TicketFilterParams
from app.services.auth_service import UserInactiveError
from app.services.ticket_fsm import (
    InvalidAssigneeError,
    InvalidStateTransitionError,
    InvalidTargetStatusError,
    TicketDomainError,
    TicketFSM,
    UnauthorizedTransitionError,
)

# ==============================================================================
# Domain Exceptions
# ==============================================================================


class TicketNotFoundError(TicketDomainError):
    """Raised when a ticket is not found or inaccessible due to student IDOR isolation."""


class TicketConcurrencyError(TicketDomainError):
    """Raised when an optimistic concurrency check fails due to a version conflict."""

    def __init__(
        self,
        message: str = "Ticket has been modified by another concurrent transaction.",
        expected_version: int | None = None,
        actual_version: int | None = None,
    ) -> None:
        super().__init__(message)
        self.expected_version = expected_version
        self.actual_version = actual_version


class CategoryNotFoundError(TicketDomainError):
    """Raised when the specified category ID does not exist."""


class CategoryInactiveError(TicketDomainError):
    """Raised when attempting to create a ticket under an inactive category."""


# ==============================================================================
# Ticket Domain Service
# ==============================================================================


class TicketService:
    """Domain service managing the complete ticket lifecycle, concurrency, and audit logging."""

    @classmethod
    async def _generate_ticket_number(cls, db: AsyncSession) -> str:
        """Generates the next human-readable ticket tracking code (CFX-YYYY-XXXXX).

        Queries the current highest tracking sequence for the current UTC year
        and increments by 1.
        """
        current_year = datetime.now(UTC).year
        prefix = f"CFX-{current_year}-"

        stmt = (
            select(Ticket.ticket_number)
            .where(Ticket.ticket_number.like(f"{prefix}%"))
            .order_by(Ticket.ticket_number.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        latest_number = result.scalar_one_or_none()

        if latest_number:
            try:
                suffix = int(latest_number.split("-")[-1])
                seq = suffix + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1

        return f"{prefix}{seq:05d}"

    @classmethod
    async def create_ticket(
        cls,
        db: AsyncSession,
        *,
        creator: User,
        title: str,
        description: str,
        category_id: uuid.UUID,
        location: str,
        priority: TicketPriority | str = TicketPriority.MEDIUM,
    ) -> Ticket:
        """Creates a new maintenance ticket in SUBMITTED status and writes initial audit history.

        Args:
            db: Active async database session.
            creator: Authenticated user creating the ticket.
            title: Headline summary of the maintenance issue.
            description: Contextual breakdown of the malfunction.
            category_id: UUID of an active facility category.
            location: Campus location string.
            priority: Urgency tier (LOW, MEDIUM, HIGH, CRITICAL).

        Returns:
            The created and persisted Ticket ORM instance.

        Raises:
            UserInactiveError: If the creator user account is deactivated.
            CategoryNotFoundError: If category_id does not exist.
            CategoryInactiveError: If the specified category is marked inactive.
        """
        if not creator.is_active:
            raise UserInactiveError(f"User '{creator.id}' is inactive and cannot create tickets.")

        # 1. Category validation
        category_stmt = select(Category).where(Category.id == category_id)
        category_res = await db.execute(category_stmt)
        category = category_res.scalar_one_or_none()

        if not category:
            raise CategoryNotFoundError(f"Facility category '{category_id}' was not found.")
        if not category.is_active:
            raise CategoryInactiveError(
                f"Facility category '{category.name}' is inactive and cannot accept new tickets."
            )

        # 2. Priority normalization
        if isinstance(priority, str):
            p_val = TicketPriority(priority.strip().upper()).value
        else:
            p_val = priority.value

        try:
            # 3. Generate sequential ticket tracking code
            ticket_number = await cls._generate_ticket_number(db)

            # 4. Instantiate Ticket model (FR-008 to FR-011)
            ticket_id = uuid.uuid4()
            ticket = Ticket(
                id=ticket_id,
                ticket_number=ticket_number,
                title=title.strip(),
                description=description.strip(),
                category_id=category.id,
                location=location.strip(),
                priority=p_val,
                status=TicketStatus.SUBMITTED.value,
                creator_id=creator.id,
                assigned_staff_id=None,
                resolution_notes=None,
                rejection_reason=None,
                version=1,
            )

            # 5. Instantiate initial audit history log (FR-017)
            history = TicketStatusHistory(
                id=uuid.uuid4(),
                ticket_id=ticket_id,
                from_status=None,
                to_status=TicketStatus.SUBMITTED.value,
                changed_by_user_id=creator.id,
                assigned_to_user_id=None,
                notes="Ticket submitted.",
            )

            db.add(ticket)
            db.add(history)
            await db.commit()
            await db.refresh(ticket)
            # Attach already loaded relations for schema serialization
            ticket.category = category
            ticket.creator = creator
            return ticket

        except Exception:
            await db.rollback()
            raise

    @classmethod
    async def assign_ticket(
        cls,
        db: AsyncSession,
        *,
        ticket_id: uuid.UUID,
        actor: User,
        staff_id: uuid.UUID,
        expected_version: int,
        notes: str | None = None,
    ) -> Ticket:
        """Assigns or reassigns a ticket to a staff technician.

        Uses row-level locking (SELECT ... FOR UPDATE) and optimistic concurrency
        verification against expected_version.

        Args:
            db: Active async database session.
            ticket_id: UUID of the target ticket.
            actor: Authenticated user initiating assignment (ADMINISTRATOR or STAFF).
            staff_id: UUID of the staff technician to assign.
            expected_version: Current version expected by the client.
            notes: Optional assignment context or notes.

        Returns:
            The mutated and persisted Ticket ORM instance.

        Raises:
            UserInactiveError: If actor is deactivated.
            TicketNotFoundError: If ticket does not exist.
            TicketConcurrencyError: If expected_version does not match current ticket version.
            InvalidAssigneeError: If target staff user is not an active STAFF member.
            UnauthorizedTransitionError: If actor lacks permission for this assignment.
            InvalidStateTransitionError: If ticket status cannot transition to ASSIGNED.
        """
        if not actor.is_active:
            raise UserInactiveError(f"User '{actor.id}' is inactive.")

        try:
            # 1. Fetch ticket with row-level locking (ADR-005)
            stmt = select(Ticket).where(Ticket.id == ticket_id).with_for_update()
            result = await db.execute(stmt)
            ticket = result.scalar_one_or_none()

            if not ticket:
                raise TicketNotFoundError(f"Ticket '{ticket_id}' was not found.")

            # 2. Verify optimistic concurrency
            if ticket.version != expected_version:
                raise TicketConcurrencyError(
                    f"Concurrency conflict on ticket '{ticket.ticket_number}': "
                    f"expected version {expected_version}, but current version is {ticket.version}.",
                    expected_version=expected_version,
                    actual_version=ticket.version,
                )

            # 3. Validate target staff technician
            staff_stmt = select(User).where(User.id == staff_id)
            staff_res = await db.execute(staff_stmt)
            staff = staff_res.scalar_one_or_none()

            if not staff or not staff.is_active or staff.role != UserRole.STAFF.value:
                raise InvalidAssigneeError(f"User '{staff_id}' is not an active staff technician.")

            # 4. Check role assignment rules
            if ticket.status == TicketStatus.SUBMITTED.value:
                if actor.role == UserRole.STAFF.value:
                    if staff_id != actor.id:
                        raise UnauthorizedTransitionError(
                            "Staff members can only claim tickets for themselves."
                        )
                elif actor.role != UserRole.ADMINISTRATOR.value:
                    raise UnauthorizedTransitionError("Students cannot assign tickets.")
            elif ticket.status == TicketStatus.ASSIGNED.value:
                if actor.role != UserRole.ADMINISTRATOR.value:
                    raise UnauthorizedTransitionError(
                        "Only administrators can reassign tickets to a different staff technician."
                    )
            else:
                raise InvalidStateTransitionError(
                    f"Cannot assign ticket currently in '{ticket.status}' status."
                )

            # 5. Validate transition through FSM
            TicketFSM.validate_transition(
                ticket.status,
                TicketStatus.ASSIGNED,
                actor.role,
                is_creator=(ticket.creator_id == actor.id),
                is_assignee=(ticket.assigned_staff_id == actor.id),
                notes=notes,
            )

            # 6. Apply atomic update and increment version
            old_status = ticket.status
            ticket.assigned_staff_id = staff.id
            ticket.status = TicketStatus.ASSIGNED.value
            ticket.version += 1
            ticket.updated_at = datetime.now(UTC)

            # 7. Record immutable audit log
            assignment_notes = notes or (
                "Claimed by technician."
                if actor.id == staff.id
                else f"Assigned to staff technician {staff.full_name}."
            )
            history = TicketStatusHistory(
                id=uuid.uuid4(),
                ticket_id=ticket.id,
                from_status=old_status,
                to_status=TicketStatus.ASSIGNED.value,
                changed_by_user_id=actor.id,
                assigned_to_user_id=staff.id,
                notes=assignment_notes,
            )

            db.add(history)
            await db.commit()
            await db.refresh(ticket)
            return ticket

        except Exception:
            await db.rollback()
            raise

    @classmethod
    async def transition_ticket(
        cls,
        db: AsyncSession,
        *,
        ticket_id: uuid.UUID,
        actor: User,
        target_status: TicketStatus | str,
        expected_version: int,
        notes: str | None = None,
        assigned_staff_id: uuid.UUID | None = None,
    ) -> Ticket:
        """Transitions ticket status following strict FSM rules with atomic audit logging.

        Uses row-level locking (SELECT ... FOR UPDATE) and optimistic concurrency
        verification against expected_version.

        Args:
            db: Active async database session.
            ticket_id: UUID of the target ticket.
            actor: Authenticated user executing the transition.
            target_status: Desired destination status in TicketStatus enum.
            expected_version: Current version expected by the client.
            notes: Mandatory resolution/rejection/reopening rationale or optional notes.
            assigned_staff_id: Optional technician UUID required when reopening to ASSIGNED.

        Returns:
            The mutated and persisted Ticket ORM instance.

        Raises:
            UserInactiveError: If actor is deactivated.
            TicketNotFoundError: If ticket does not exist.
            TicketConcurrencyError: If expected_version does not match current ticket version.
            TicketFSMError: If transition or authorization is rejected by the state machine.
            InvalidAssigneeError: If reassignment/reopening target staff user is invalid.
        """
        if not actor.is_active:
            raise UserInactiveError(f"User '{actor.id}' is inactive.")

        try:
            # 1. Fetch ticket with row-level locking (ADR-005)
            stmt = select(Ticket).where(Ticket.id == ticket_id).with_for_update()
            result = await db.execute(stmt)
            ticket = result.scalar_one_or_none()

            if not ticket:
                raise TicketNotFoundError(f"Ticket '{ticket_id}' was not found.")

            # 2. Verify optimistic concurrency
            if ticket.version != expected_version:
                raise TicketConcurrencyError(
                    f"Concurrency conflict on ticket '{ticket.ticket_number}': "
                    f"expected version {expected_version}, but current version is {ticket.version}.",
                    expected_version=expected_version,
                    actual_version=ticket.version,
                )

            # 3. Ownership and assignment context
            is_creator = ticket.creator_id == actor.id
            is_assignee = (
                ticket.assigned_staff_id is not None and ticket.assigned_staff_id == actor.id
            )

            # 4. FSM validation
            from_s, to_s = TicketFSM.validate_transition(
                ticket.status,
                target_status,
                actor.role,
                is_creator=is_creator,
                is_assignee=is_assignee,
                notes=notes,
            )

            # 5. Apply state-specific side effects
            cleaned_notes = notes.strip() if notes else None

            if to_s == TicketStatus.RESOLVED:
                ticket.resolution_notes = cleaned_notes

            elif to_s == TicketStatus.REJECTED:
                ticket.rejection_reason = cleaned_notes

            elif to_s == TicketStatus.CANCELLED:
                pass

            elif to_s == TicketStatus.SUBMITTED:
                # Administrator reopening to unassigned triage pool
                ticket.assigned_staff_id = None
                ticket.resolution_notes = None
                ticket.rejection_reason = None

            elif to_s == TicketStatus.ASSIGNED:
                if from_s in (TicketStatus.RESOLVED, TicketStatus.REJECTED):
                    # Administrator reopening to ASSIGNED
                    if assigned_staff_id is not None:
                        staff_stmt = select(User).where(User.id == assigned_staff_id)
                        staff_res = await db.execute(staff_stmt)
                        staff = staff_res.scalar_one_or_none()
                        if not staff or not staff.is_active or staff.role != UserRole.STAFF.value:
                            raise InvalidAssigneeError(
                                f"User '{assigned_staff_id}' is not an active staff technician."
                            )
                        ticket.assigned_staff_id = staff.id
                    elif ticket.assigned_staff_id is None:
                        raise InvalidAssigneeError(
                            "Reopening a ticket to ASSIGNED requires an assigned staff technician."
                        )
                    ticket.resolution_notes = None
                    ticket.rejection_reason = None

            # 6. Mutate status, increment version, touch updated_at
            ticket.status = to_s.value
            ticket.version += 1
            ticket.updated_at = datetime.now(UTC)

            # 7. Write immutable audit history entry
            history = TicketStatusHistory(
                id=uuid.uuid4(),
                ticket_id=ticket.id,
                from_status=from_s.value,
                to_status=to_s.value,
                changed_by_user_id=actor.id,
                assigned_to_user_id=ticket.assigned_staff_id,
                notes=cleaned_notes,
            )

            db.add(history)
            await db.commit()
            await db.refresh(ticket)
            return ticket

        except Exception:
            await db.rollback()
            raise

    @classmethod
    async def reopen_ticket(
        cls,
        db: AsyncSession,
        *,
        ticket_id: uuid.UUID,
        actor: User,
        target_status: TicketStatus | str,
        expected_version: int,
        reason: str,
        assigned_staff_id: uuid.UUID | None = None,
    ) -> Ticket:
        """Domain helper for administrator reopening of RESOLVED or REJECTED tickets.

        Enforces that target status must be ASSIGNED or SUBMITTED, and mandates
        a reason of at least 10 characters.
        """
        target_s = TicketFSM.normalize_status(target_status)
        if target_s not in (TicketStatus.ASSIGNED, TicketStatus.SUBMITTED):
            raise InvalidTargetStatusError(
                f"Cannot reopen ticket to '{target_s.value}'. Target status must be "
                "ASSIGNED or SUBMITTED."
            )

        return await cls.transition_ticket(
            db,
            ticket_id=ticket_id,
            actor=actor,
            target_status=target_s,
            expected_version=expected_version,
            notes=reason,
            assigned_staff_id=assigned_staff_id,
        )

    @classmethod
    async def get_ticket_by_id(
        cls,
        db: AsyncSession,
        *,
        ticket_id: uuid.UUID,
        actor: User,
    ) -> Ticket:
        """Retrieves a ticket by UUID enforcing student IDOR isolation (FR-012).

        Args:
            db: Active async database session.
            ticket_id: UUID of ticket to query.
            actor: Authenticated user querying the ticket.

        Returns:
            The Ticket ORM instance.

        Raises:
            TicketNotFoundError: If ticket does not exist, or if a STUDENT attempts to
                access a ticket created by another user.
        """
        stmt = (
            select(Ticket)
            .options(
                selectinload(Ticket.category),
                selectinload(Ticket.creator),
                selectinload(Ticket.assigned_staff),
            )
            .where(Ticket.id == ticket_id)
        )
        result = await db.execute(stmt)
        ticket = result.scalar_one_or_none()

        if not ticket:
            raise TicketNotFoundError(f"Ticket '{ticket_id}' was not found.")

        # IDOR Isolation: Students can only view their own tickets
        if actor.role == UserRole.STUDENT.value and ticket.creator_id != actor.id:
            raise TicketNotFoundError(f"Ticket '{ticket_id}' was not found.")

        return ticket

    @classmethod
    async def get_ticket_history(
        cls,
        db: AsyncSession,
        *,
        ticket_id: uuid.UUID,
        actor: User,
    ) -> list[TicketStatusHistory]:
        """Retrieves chronological audit trail for a ticket with IDOR isolation.

        Args:
            db: Active async database session.
            ticket_id: UUID of ticket.
            actor: Authenticated user querying the history.

        Returns:
            Chronological list of TicketStatusHistory records.

        Raises:
            TicketNotFoundError: If ticket does not exist or access is forbidden by IDOR.
        """
        # Ensure access permission via get_ticket_by_id
        await cls.get_ticket_by_id(db, ticket_id=ticket_id, actor=actor)

        stmt = (
            select(TicketStatusHistory)
            .options(
                selectinload(TicketStatusHistory.changed_by_user),
                selectinload(TicketStatusHistory.assigned_to_user),
            )
            .where(TicketStatusHistory.ticket_id == ticket_id)
            .order_by(TicketStatusHistory.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def list_tickets(
        cls,
        db: AsyncSession,
        *,
        actor: User,
        filters: TicketFilterParams,
    ) -> tuple[list[Ticket], int]:
        """Lists tickets with multi-attribute filtering, pagination, and role-based isolation.

        Role Enforcement (FR-012, FR-019, FR-023):
        - STUDENT: Unconditionally restricted to creator_id == actor.id. Any supplied
          assigned_staff_id filter is ignored.
        - STAFF: If assigned_staff_id == 'me', scopes to assigned_staff_id == actor.id.
          Can also query unassigned tickets (status=SUBMITTED) or general category/priority queues.
        - ADMINISTRATOR: Full global visibility across all tickets with arbitrary filter combinations.
        """
        query = select(Ticket).options(
            selectinload(Ticket.category),
            selectinload(Ticket.creator),
            selectinload(Ticket.assigned_staff),
        )

        # 1. Role-based ownership filtering
        if actor.role == UserRole.STUDENT.value:
            query = query.where(Ticket.creator_id == actor.id)
        else:
            if filters.assigned_staff_id:
                if filters.assigned_staff_id.lower() == "me":
                    query = query.where(Ticket.assigned_staff_id == actor.id)
                else:
                    try:
                        tech_uuid = uuid.UUID(filters.assigned_staff_id)
                        query = query.where(Ticket.assigned_staff_id == tech_uuid)
                    except ValueError:
                        pass

        # 2. Status filter
        if filters.status:
            tokens = [t.strip().upper() for t in filters.status.split(",") if t.strip()]
            if tokens:
                query = query.where(Ticket.status.in_(tokens))

        # 3. Category filter
        if filters.category_id:
            query = query.where(Ticket.category_id == filters.category_id)

        # 4. Priority filter
        if filters.priority:
            p_val = (
                filters.priority.value
                if isinstance(filters.priority, TicketPriority)
                else str(filters.priority)
            )
            query = query.where(Ticket.priority == p_val)

        # Count total matching records
        count_query = select(func.count()).select_from(query.order_by(None).subquery())
        total_res = await db.execute(count_query)
        total = total_res.scalar_one()

        # Apply ordering and pagination
        paginated_query = (
            query.order_by(Ticket.created_at.desc())
            .offset((filters.page - 1) * filters.page_size)
            .limit(filters.page_size)
        )
        result = await db.execute(paginated_query)
        tickets = list(result.scalars().all())

        return tickets, total

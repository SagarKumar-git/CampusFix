"""Unit tests for TicketService domain operations, optimistic concurrency, and audit logs."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.category import Category
from app.models.ticket import Ticket, TicketPriority, TicketStatus
from app.models.ticket_history import TicketStatusHistory
from app.models.user import User, UserRole
from app.services.auth_service import UserInactiveError
from app.services.ticket_fsm import (
    InvalidAssigneeError,
    InvalidStateTransitionError,
    InvalidTargetStatusError,
    MissingTransitionCommentaryError,
    UnauthorizedTransitionError,
)
from app.services.ticket_service import (
    CategoryInactiveError,
    CategoryNotFoundError,
    TicketConcurrencyError,
    TicketNotFoundError,
    TicketService,
)

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def mock_db() -> AsyncMock:
    """AsyncSession mock with synchronous add method."""
    session = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def active_student() -> User:
    """Standard active student user."""
    return User(
        id=uuid.uuid4(),
        email="student@campusfix.local",
        full_name="Jane Student",
        hashed_password="dummy",
        role=UserRole.STUDENT.value,
        is_active=True,
    )


@pytest.fixture
def other_student() -> User:
    """Second student user for IDOR testing."""
    return User(
        id=uuid.uuid4(),
        email="other.student@campusfix.local",
        full_name="Other Student",
        hashed_password="dummy",
        role=UserRole.STUDENT.value,
        is_active=True,
    )


@pytest.fixture
def active_staff() -> User:
    """Standard active facilities technician."""
    return User(
        id=uuid.uuid4(),
        email="staff.tech@campusfix.local",
        full_name="Alex Rivera",
        hashed_password="dummy",
        role=UserRole.STAFF.value,
        is_active=True,
    )


@pytest.fixture
def other_staff() -> User:
    """Second staff technician for reassignment testing."""
    return User(
        id=uuid.uuid4(),
        email="other.tech@campusfix.local",
        full_name="Sam Morgan",
        hashed_password="dummy",
        role=UserRole.STAFF.value,
        is_active=True,
    )


@pytest.fixture
def active_admin() -> User:
    """Standard active administrator."""
    return User(
        id=uuid.uuid4(),
        email="admin@campusfix.local",
        full_name="Campus Admin",
        hashed_password="dummy",
        role=UserRole.ADMINISTRATOR.value,
        is_active=True,
    )


@pytest.fixture
def active_category() -> Category:
    """Active facilities issue category."""
    return Category(
        id=uuid.uuid4(),
        name="Electrical",
        description="Power outlets, lighting, and wiring",
        is_active=True,
    )


# ==============================================================================
# 1. Ticket Creation Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_create_ticket_success(
    mock_db: AsyncMock, active_student: User, active_category: Category
):
    """Verifies successful ticket creation with code generation, initial state, and audit history."""
    # Mock category lookup
    mock_cat_res = MagicMock()
    mock_cat_res.scalar_one_or_none.return_value = active_category

    # Mock sequence code lookup (no previous tickets)
    mock_seq_res = MagicMock()
    mock_seq_res.scalar_one_or_none.return_value = None

    mock_db.execute.side_effect = [mock_cat_res, mock_seq_res]

    current_year = datetime.now(UTC).year
    expected_code = f"CFX-{current_year}-00001"

    ticket = await TicketService.create_ticket(
        mock_db,
        creator=active_student,
        title="Projector bulb shattered",
        description="The projector bulb in Room 204 shattered during lecture.",
        category_id=active_category.id,
        location="Science Block A, Room 204",
        priority=TicketPriority.HIGH,
    )

    assert ticket.ticket_number == expected_code
    assert ticket.title == "Projector bulb shattered"
    assert ticket.status == TicketStatus.SUBMITTED.value
    assert ticket.creator_id == active_student.id
    assert ticket.assigned_staff_id is None
    assert ticket.version == 1

    # Verify add called for both Ticket and TicketStatusHistory
    assert mock_db.add.call_count == 2
    added_objects = [call[0][0] for call in mock_db.add.call_args_list]

    ticket_obj = next(obj for obj in added_objects if isinstance(obj, Ticket))
    history_obj = next(obj for obj in added_objects if isinstance(obj, TicketStatusHistory))

    assert ticket_obj == ticket
    assert history_obj.ticket_id == ticket.id
    assert history_obj.from_status is None
    assert history_obj.to_status == TicketStatus.SUBMITTED.value
    assert history_obj.changed_by_user_id == active_student.id
    assert history_obj.notes == "Ticket submitted."

    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_ticket_increments_sequence_code(
    mock_db: AsyncMock, active_student: User, active_category: Category
):
    """Verifies that tracking sequence code increments when previous tickets exist."""
    current_year = datetime.now(UTC).year
    previous_code = f"CFX-{current_year}-00041"

    mock_cat_res = MagicMock()
    mock_cat_res.scalar_one_or_none.return_value = active_category

    mock_seq_res = MagicMock()
    mock_seq_res.scalar_one_or_none.return_value = previous_code

    mock_db.execute.side_effect = [mock_cat_res, mock_seq_res]

    ticket = await TicketService.create_ticket(
        mock_db,
        creator=active_student,
        title="Broken window latch",
        description="Window latch is broken in dormitory 3.",
        category_id=active_category.id,
        location="Hostel 3, Room 102",
        priority=TicketPriority.MEDIUM,
    )

    assert ticket.ticket_number == f"CFX-{current_year}-00042"


@pytest.mark.asyncio
async def test_create_ticket_inactive_creator_raises_user_inactive_error(
    mock_db: AsyncMock, active_student: User, active_category: Category
):
    """Deactivated user accounts cannot submit tickets."""
    active_student.is_active = False

    with pytest.raises(UserInactiveError, match="is inactive and cannot create tickets"):
        await TicketService.create_ticket(
            mock_db,
            creator=active_student,
            title="Valid title here",
            description="Valid description here",
            category_id=active_category.id,
            location="Library 2nd Floor",
        )


@pytest.mark.asyncio
async def test_create_ticket_missing_category_raises_category_not_found_error(
    mock_db: AsyncMock, active_student: User
):
    """Non-existent category ID raises CategoryNotFoundError."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    missing_id = uuid.uuid4()
    with pytest.raises(CategoryNotFoundError, match="was not found"):
        await TicketService.create_ticket(
            mock_db,
            creator=active_student,
            title="Valid title here",
            description="Valid description here",
            category_id=missing_id,
            location="Library 2nd Floor",
        )


@pytest.mark.asyncio
async def test_create_ticket_inactive_category_raises_category_inactive_error(
    mock_db: AsyncMock, active_student: User, active_category: Category
):
    """Deactivated categories cannot accept new tickets."""
    active_category.is_active = False
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = active_category
    mock_db.execute.return_value = mock_res

    with pytest.raises(CategoryInactiveError, match="is inactive"):
        await TicketService.create_ticket(
            mock_db,
            creator=active_student,
            title="Valid title here",
            description="Valid description here",
            category_id=active_category.id,
            location="Library 2nd Floor",
        )


# ==============================================================================
# 2. Ticket Assignment Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_assign_ticket_by_admin_success(
    mock_db: AsyncMock, active_admin: User, active_staff: User, active_student: User
):
    """Administrator assigns unassigned SUBMITTED ticket to staff member."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="AC Leak",
        description="Air conditioner is leaking water.",
        category_id=uuid.uuid4(),
        location="Lab 101",
        priority=TicketPriority.HIGH.value,
        status=TicketStatus.SUBMITTED.value,
        creator_id=active_student.id,
        assigned_staff_id=None,
        version=1,
    )

    mock_ticket_res = MagicMock()
    mock_ticket_res.scalar_one_or_none.return_value = ticket

    mock_staff_res = MagicMock()
    mock_staff_res.scalar_one_or_none.return_value = active_staff

    mock_db.execute.side_effect = [mock_ticket_res, mock_staff_res]

    updated = await TicketService.assign_ticket(
        mock_db,
        ticket_id=ticket.id,
        actor=active_admin,
        staff_id=active_staff.id,
        expected_version=1,
        notes="Assigned for immediate repair.",
    )

    assert updated.status == TicketStatus.ASSIGNED.value
    assert updated.assigned_staff_id == active_staff.id
    assert updated.version == 2

    # Check history log created
    assert mock_db.add.call_count == 1
    history = mock_db.add.call_args[0][0]
    assert isinstance(history, TicketStatusHistory)
    assert history.from_status == TicketStatus.SUBMITTED.value
    assert history.to_status == TicketStatus.ASSIGNED.value
    assert history.changed_by_user_id == active_admin.id
    assert history.assigned_to_user_id == active_staff.id
    assert history.notes == "Assigned for immediate repair."

    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_assign_ticket_staff_self_claim_success(
    mock_db: AsyncMock, active_staff: User, active_student: User
):
    """Staff member self-claims unassigned SUBMITTED ticket."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="Broken chair",
        description="Desk chair broken in room 12.",
        category_id=uuid.uuid4(),
        location="Room 12",
        priority=TicketPriority.LOW.value,
        status=TicketStatus.SUBMITTED.value,
        creator_id=active_student.id,
        assigned_staff_id=None,
        version=1,
    )

    mock_ticket_res = MagicMock()
    mock_ticket_res.scalar_one_or_none.return_value = ticket

    mock_staff_res = MagicMock()
    mock_staff_res.scalar_one_or_none.return_value = active_staff

    mock_db.execute.side_effect = [mock_ticket_res, mock_staff_res]

    updated = await TicketService.assign_ticket(
        mock_db,
        ticket_id=ticket.id,
        actor=active_staff,
        staff_id=active_staff.id,
        expected_version=1,
    )

    assert updated.status == TicketStatus.ASSIGNED.value
    assert updated.assigned_staff_id == active_staff.id
    assert updated.version == 2


@pytest.mark.asyncio
async def test_assign_ticket_staff_cannot_assign_other_technician(
    mock_db: AsyncMock, active_staff: User, other_staff: User, active_student: User
):
    """Staff members cannot assign tickets to other technicians."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="Broken chair",
        description="Desk chair broken.",
        category_id=uuid.uuid4(),
        location="Room 12",
        priority=TicketPriority.LOW.value,
        status=TicketStatus.SUBMITTED.value,
        creator_id=active_student.id,
        assigned_staff_id=None,
        version=1,
    )

    mock_ticket_res = MagicMock()
    mock_ticket_res.scalar_one_or_none.return_value = ticket

    mock_staff_res = MagicMock()
    mock_staff_res.scalar_one_or_none.return_value = other_staff

    mock_db.execute.side_effect = [mock_ticket_res, mock_staff_res]

    with pytest.raises(
        UnauthorizedTransitionError, match="Staff members can only claim tickets for themselves"
    ):
        await TicketService.assign_ticket(
            mock_db,
            ticket_id=ticket.id,
            actor=active_staff,
            staff_id=other_staff.id,
            expected_version=1,
        )


@pytest.mark.asyncio
async def test_assign_ticket_reassignment_by_admin(
    mock_db: AsyncMock,
    active_admin: User,
    active_staff: User,
    other_staff: User,
    active_student: User,
):
    """Administrator can reassign an ASSIGNED ticket to a different technician."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="Broken chair",
        description="Desk chair broken.",
        category_id=uuid.uuid4(),
        location="Room 12",
        priority=TicketPriority.LOW.value,
        status=TicketStatus.ASSIGNED.value,
        creator_id=active_student.id,
        assigned_staff_id=active_staff.id,
        version=2,
    )

    mock_ticket_res = MagicMock()
    mock_ticket_res.scalar_one_or_none.return_value = ticket

    mock_staff_res = MagicMock()
    mock_staff_res.scalar_one_or_none.return_value = other_staff

    mock_db.execute.side_effect = [mock_ticket_res, mock_staff_res]

    updated = await TicketService.assign_ticket(
        mock_db,
        ticket_id=ticket.id,
        actor=active_admin,
        staff_id=other_staff.id,
        expected_version=2,
        notes="Reassigned to specialist technician.",
    )

    assert updated.assigned_staff_id == other_staff.id
    assert updated.version == 3


@pytest.mark.asyncio
async def test_assign_ticket_version_mismatch_raises_ticket_concurrency_error(
    mock_db: AsyncMock, active_admin: User, active_staff: User, active_student: User
):
    """Mismatched expected_version raises TicketConcurrencyError (HTTP 409 Conflict)."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="Broken chair",
        description="Desk chair broken.",
        category_id=uuid.uuid4(),
        location="Room 12",
        priority=TicketPriority.LOW.value,
        status=TicketStatus.SUBMITTED.value,
        creator_id=active_student.id,
        assigned_staff_id=None,
        version=5,  # Ticket has advanced to version 5
    )

    mock_ticket_res = MagicMock()
    mock_ticket_res.scalar_one_or_none.return_value = ticket
    mock_db.execute.return_value = mock_ticket_res

    with pytest.raises(TicketConcurrencyError) as exc_info:
        await TicketService.assign_ticket(
            mock_db,
            ticket_id=ticket.id,
            actor=active_admin,
            staff_id=active_staff.id,
            expected_version=3,  # Stale client version 3
        )

    assert exc_info.value.expected_version == 3
    assert exc_info.value.actual_version == 5


@pytest.mark.asyncio
async def test_assign_ticket_invalid_assignee_role_raises_invalid_assignee_error(
    mock_db: AsyncMock, active_admin: User, active_student: User
):
    """Assigning to a user who is not a STAFF member raises InvalidAssigneeError."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="Broken chair",
        description="Desk chair broken.",
        category_id=uuid.uuid4(),
        location="Room 12",
        priority=TicketPriority.LOW.value,
        status=TicketStatus.SUBMITTED.value,
        creator_id=active_student.id,
        assigned_staff_id=None,
        version=1,
    )

    mock_ticket_res = MagicMock()
    mock_ticket_res.scalar_one_or_none.return_value = ticket

    mock_staff_res = MagicMock()
    # active_student has STUDENT role, not STAFF
    mock_staff_res.scalar_one_or_none.return_value = active_student

    mock_db.execute.side_effect = [mock_ticket_res, mock_staff_res]

    with pytest.raises(InvalidAssigneeError, match="not an active staff technician"):
        await TicketService.assign_ticket(
            mock_db,
            ticket_id=ticket.id,
            actor=active_admin,
            staff_id=active_student.id,
            expected_version=1,
        )


# ==============================================================================
# 3. Status Transition Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_transition_to_in_progress_by_assigned_staff(
    mock_db: AsyncMock, active_staff: User, active_student: User
):
    """Assigned staff moves ticket from ASSIGNED to IN_PROGRESS."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="Water leak",
        description="Pipe burst.",
        category_id=uuid.uuid4(),
        location="Building 2",
        priority=TicketPriority.CRITICAL.value,
        status=TicketStatus.ASSIGNED.value,
        creator_id=active_student.id,
        assigned_staff_id=active_staff.id,
        version=2,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = ticket
    mock_db.execute.return_value = mock_res

    updated = await TicketService.transition_ticket(
        mock_db,
        ticket_id=ticket.id,
        actor=active_staff,
        target_status=TicketStatus.IN_PROGRESS,
        expected_version=2,
        notes="Starting pipe replacement now.",
    )

    assert updated.status == TicketStatus.IN_PROGRESS.value
    assert updated.version == 3

    assert mock_db.add.call_count == 1
    history = mock_db.add.call_args[0][0]
    assert history.from_status == TicketStatus.ASSIGNED.value
    assert history.to_status == TicketStatus.IN_PROGRESS.value
    assert history.changed_by_user_id == active_staff.id


@pytest.mark.asyncio
async def test_transition_to_in_progress_unassigned_staff_blocked(
    mock_db: AsyncMock, active_staff: User, other_staff: User, active_student: User
):
    """Unassigned staff technician cannot transition ticket to IN_PROGRESS."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="Water leak",
        description="Pipe burst.",
        category_id=uuid.uuid4(),
        location="Building 2",
        priority=TicketPriority.CRITICAL.value,
        status=TicketStatus.ASSIGNED.value,
        creator_id=active_student.id,
        assigned_staff_id=other_staff.id,  # Assigned to other_staff, not active_staff
        version=2,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = ticket
    mock_db.execute.return_value = mock_res

    with pytest.raises(UnauthorizedTransitionError, match="Only the assigned staff technician"):
        await TicketService.transition_ticket(
            mock_db,
            ticket_id=ticket.id,
            actor=active_staff,
            target_status=TicketStatus.IN_PROGRESS,
            expected_version=2,
        )


@pytest.mark.asyncio
async def test_transition_to_resolved_saves_resolution_notes(
    mock_db: AsyncMock, active_staff: User, active_student: User
):
    """Resolving an IN_PROGRESS ticket saves resolution_notes and writes audit entry."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="Water leak",
        description="Pipe burst.",
        category_id=uuid.uuid4(),
        location="Building 2",
        priority=TicketPriority.CRITICAL.value,
        status=TicketStatus.IN_PROGRESS.value,
        creator_id=active_student.id,
        assigned_staff_id=active_staff.id,
        version=3,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = ticket
    mock_db.execute.return_value = mock_res

    notes = "Replaced broken valve with brass fitting and pressure-tested."
    updated = await TicketService.transition_ticket(
        mock_db,
        ticket_id=ticket.id,
        actor=active_staff,
        target_status=TicketStatus.RESOLVED,
        expected_version=3,
        notes=notes,
    )

    assert updated.status == TicketStatus.RESOLVED.value
    assert updated.resolution_notes == notes
    assert updated.version == 4


@pytest.mark.asyncio
async def test_transition_to_resolved_without_notes_fails(
    mock_db: AsyncMock, active_staff: User, active_student: User
):
    """Attempting to resolve without notes fails validation."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="Water leak",
        description="Pipe burst.",
        category_id=uuid.uuid4(),
        location="Building 2",
        priority=TicketPriority.CRITICAL.value,
        status=TicketStatus.IN_PROGRESS.value,
        creator_id=active_student.id,
        assigned_staff_id=active_staff.id,
        version=3,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = ticket
    mock_db.execute.return_value = mock_res

    with pytest.raises(
        MissingTransitionCommentaryError, match="Resolving a ticket strictly requires 'notes'"
    ):
        await TicketService.transition_ticket(
            mock_db,
            ticket_id=ticket.id,
            actor=active_staff,
            target_status=TicketStatus.RESOLVED,
            expected_version=3,
            notes=None,
        )


@pytest.mark.asyncio
async def test_student_cancellation_of_own_ticket(mock_db: AsyncMock, active_student: User):
    """Student creator can cancel ticket while in SUBMITTED status."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="Light flicker",
        description="Desk lamp flickered.",
        category_id=uuid.uuid4(),
        location="Room 3",
        priority=TicketPriority.LOW.value,
        status=TicketStatus.SUBMITTED.value,
        creator_id=active_student.id,
        assigned_staff_id=None,
        version=1,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = ticket
    mock_db.execute.return_value = mock_res

    updated = await TicketService.transition_ticket(
        mock_db,
        ticket_id=ticket.id,
        actor=active_student,
        target_status=TicketStatus.CANCELLED,
        expected_version=1,
        notes="Plug was simply loose; resolved.",
    )

    assert updated.status == TicketStatus.CANCELLED.value
    assert updated.version == 2


@pytest.mark.asyncio
async def test_student_cannot_cancel_another_students_ticket(
    mock_db: AsyncMock, active_student: User, other_student: User
):
    """Student cannot cancel a ticket created by someone else."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="Light flicker",
        description="Desk lamp flickered.",
        category_id=uuid.uuid4(),
        location="Room 3",
        priority=TicketPriority.LOW.value,
        status=TicketStatus.SUBMITTED.value,
        creator_id=other_student.id,  # Created by other_student
        assigned_staff_id=None,
        version=1,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = ticket
    mock_db.execute.return_value = mock_res

    with pytest.raises(
        UnauthorizedTransitionError, match="Only the ticket creator can cancel this ticket"
    ):
        await TicketService.transition_ticket(
            mock_db,
            ticket_id=ticket.id,
            actor=active_student,
            target_status=TicketStatus.CANCELLED,
            expected_version=1,
        )


@pytest.mark.asyncio
async def test_student_cannot_cancel_in_progress_ticket(
    mock_db: AsyncMock, active_student: User, active_staff: User
):
    """Student cannot cancel a ticket once work is IN_PROGRESS."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="Light flicker",
        description="Desk lamp flickered.",
        category_id=uuid.uuid4(),
        location="Room 3",
        priority=TicketPriority.LOW.value,
        status=TicketStatus.IN_PROGRESS.value,
        creator_id=active_student.id,
        assigned_staff_id=active_staff.id,
        version=3,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = ticket
    mock_db.execute.return_value = mock_res

    with pytest.raises(InvalidStateTransitionError, match="not permitted"):
        await TicketService.transition_ticket(
            mock_db,
            ticket_id=ticket.id,
            actor=active_student,
            target_status=TicketStatus.CANCELLED,
            expected_version=3,
        )


# ==============================================================================
# 4. Administrator Reopening Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_admin_reopen_resolved_ticket_to_submitted(
    mock_db: AsyncMock, active_admin: User, active_student: User, active_staff: User
):
    """Administrator reopens RESOLVED ticket back to SUBMITTED triage pool."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="Projector broken",
        description="Doesn't turn on.",
        category_id=uuid.uuid4(),
        location="Room 201",
        priority=TicketPriority.HIGH.value,
        status=TicketStatus.RESOLVED.value,
        creator_id=active_student.id,
        assigned_staff_id=active_staff.id,
        resolution_notes="Power cord replaced.",
        version=4,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = ticket
    mock_db.execute.return_value = mock_res

    reopen_reason = "Lecturer reports device shut down unexpectedly again."
    updated = await TicketService.reopen_ticket(
        mock_db,
        ticket_id=ticket.id,
        actor=active_admin,
        target_status=TicketStatus.SUBMITTED,
        expected_version=4,
        reason=reopen_reason,
    )

    assert updated.status == TicketStatus.SUBMITTED.value
    assert updated.assigned_staff_id is None
    assert updated.resolution_notes is None
    assert updated.version == 5

    history = mock_db.add.call_args[0][0]
    assert history.from_status == TicketStatus.RESOLVED.value
    assert history.to_status == TicketStatus.SUBMITTED.value
    assert history.notes == reopen_reason


@pytest.mark.asyncio
async def test_admin_reopen_resolved_ticket_to_assigned(
    mock_db: AsyncMock,
    active_admin: User,
    active_student: User,
    active_staff: User,
    other_staff: User,
):
    """Administrator reopens RESOLVED ticket to ASSIGNED with explicit technician."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="Projector broken",
        description="Doesn't turn on.",
        category_id=uuid.uuid4(),
        location="Room 201",
        priority=TicketPriority.HIGH.value,
        status=TicketStatus.RESOLVED.value,
        creator_id=active_student.id,
        assigned_staff_id=active_staff.id,
        resolution_notes="Power cord replaced.",
        version=4,
    )

    mock_ticket_res = MagicMock()
    mock_ticket_res.scalar_one_or_none.return_value = ticket

    mock_staff_res = MagicMock()
    mock_staff_res.scalar_one_or_none.return_value = other_staff

    mock_db.execute.side_effect = [mock_ticket_res, mock_staff_res]

    reopen_reason = "Diagnostic indicated motherboard malfunction; reassigned to specialist."
    updated = await TicketService.reopen_ticket(
        mock_db,
        ticket_id=ticket.id,
        actor=active_admin,
        target_status=TicketStatus.ASSIGNED,
        expected_version=4,
        reason=reopen_reason,
        assigned_staff_id=other_staff.id,
    )

    assert updated.status == TicketStatus.ASSIGNED.value
    assert updated.assigned_staff_id == other_staff.id
    assert updated.version == 5


@pytest.mark.asyncio
async def test_reopen_ticket_by_staff_or_student_blocked(
    mock_db: AsyncMock, active_staff: User, active_student: User
):
    """Students and staff cannot reopen tickets."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="Projector broken",
        description="Doesn't turn on.",
        category_id=uuid.uuid4(),
        location="Room 201",
        priority=TicketPriority.HIGH.value,
        status=TicketStatus.RESOLVED.value,
        creator_id=active_student.id,
        version=4,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = ticket
    mock_db.execute.return_value = mock_res

    # Staff attempt
    with pytest.raises(
        UnauthorizedTransitionError, match="Only administrators are authorized to reopen"
    ):
        await TicketService.reopen_ticket(
            mock_db,
            ticket_id=ticket.id,
            actor=active_staff,
            target_status=TicketStatus.ASSIGNED,
            expected_version=4,
            reason="Want to work on this again.",
        )

    # Student attempt
    with pytest.raises(
        UnauthorizedTransitionError, match="Only administrators are authorized to reopen"
    ):
        await TicketService.reopen_ticket(
            mock_db,
            ticket_id=ticket.id,
            actor=active_student,
            target_status=TicketStatus.SUBMITTED,
            expected_version=4,
            reason="Still not working at all.",
        )


@pytest.mark.asyncio
async def test_reopen_ticket_invalid_target_status_raises_error(
    mock_db: AsyncMock, active_admin: User, active_student: User
):
    """Reopening to IN_PROGRESS or CANCELLED is rejected."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="Projector broken",
        description="Doesn't turn on.",
        category_id=uuid.uuid4(),
        location="Room 201",
        priority=TicketPriority.HIGH.value,
        status=TicketStatus.RESOLVED.value,
        creator_id=active_student.id,
        version=4,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = ticket
    mock_db.execute.return_value = mock_res

    with pytest.raises(
        InvalidTargetStatusError, match="Target status must be ASSIGNED or SUBMITTED"
    ):
        await TicketService.reopen_ticket(
            mock_db,
            ticket_id=ticket.id,
            actor=active_admin,
            target_status=TicketStatus.IN_PROGRESS,
            expected_version=4,
            reason="Invalid target status reopen attempt.",
        )


# ==============================================================================
# 5. IDOR Isolation & History Query Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_get_ticket_by_id_student_own_ticket_succeeds(
    mock_db: AsyncMock, active_student: User
):
    """Student can retrieve their own ticket."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="AC failure",
        description="Too warm.",
        category_id=uuid.uuid4(),
        location="Room 5",
        priority=TicketPriority.MEDIUM.value,
        status=TicketStatus.SUBMITTED.value,
        creator_id=active_student.id,
        version=1,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = ticket
    mock_db.execute.return_value = mock_res

    result = await TicketService.get_ticket_by_id(
        mock_db,
        ticket_id=ticket.id,
        actor=active_student,
    )
    assert result == ticket


@pytest.mark.asyncio
async def test_get_ticket_by_id_student_other_ticket_raises_not_found(
    mock_db: AsyncMock, active_student: User, other_student: User
):
    """Student attempting to retrieve another student's ticket raises TicketNotFoundError (IDOR defense)."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="AC failure",
        description="Too warm.",
        category_id=uuid.uuid4(),
        location="Room 5",
        priority=TicketPriority.MEDIUM.value,
        status=TicketStatus.SUBMITTED.value,
        creator_id=other_student.id,  # Owned by other student
        version=1,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = ticket
    mock_db.execute.return_value = mock_res

    with pytest.raises(TicketNotFoundError):
        await TicketService.get_ticket_by_id(
            mock_db,
            ticket_id=ticket.id,
            actor=active_student,  # Accessing user is not creator
        )


@pytest.mark.asyncio
async def test_get_ticket_by_id_staff_and_admin_can_access_any_ticket(
    mock_db: AsyncMock, active_staff: User, active_admin: User, active_student: User
):
    """Staff and Administrators have global visibility across all tickets."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="AC failure",
        description="Too warm.",
        category_id=uuid.uuid4(),
        location="Room 5",
        priority=TicketPriority.MEDIUM.value,
        status=TicketStatus.SUBMITTED.value,
        creator_id=active_student.id,
        version=1,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = ticket
    mock_db.execute.return_value = mock_res

    # Staff access
    staff_res = await TicketService.get_ticket_by_id(
        mock_db,
        ticket_id=ticket.id,
        actor=active_staff,
    )
    assert staff_res == ticket

    # Admin access
    admin_res = await TicketService.get_ticket_by_id(
        mock_db,
        ticket_id=ticket.id,
        actor=active_admin,
    )
    assert admin_res == ticket


# ==============================================================================
# 6. Ticket Listing & Query Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_list_tickets_student_query_scoping(mock_db: AsyncMock, active_student: User):
    """Students only receive tickets where creator_id == active_student.id."""
    from app.schemas.ticket import TicketFilterParams

    filters = TicketFilterParams(page=1, page_size=20)

    mock_count_res = MagicMock()
    mock_count_res.scalar_one.return_value = 1

    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00001",
        title="Door latch jammed",
        description="Door won't open without force.",
        category_id=uuid.uuid4(),
        location="Room 10",
        priority=TicketPriority.LOW.value,
        status=TicketStatus.SUBMITTED.value,
        creator_id=active_student.id,
        version=1,
    )
    mock_list_res = MagicMock()
    mock_list_res.scalars.return_value.all.return_value = [ticket]

    mock_db.execute.side_effect = [mock_count_res, mock_list_res]

    tickets, total = await TicketService.list_tickets(
        mock_db,
        actor=active_student,
        filters=filters,
    )

    assert total == 1
    assert len(tickets) == 1
    assert tickets[0].creator_id == active_student.id


@pytest.mark.asyncio
async def test_list_tickets_staff_assigned_me_filter(mock_db: AsyncMock, active_staff: User):
    """Staff query with assigned_staff_id='me' scopes to assigned technician."""
    from app.schemas.ticket import TicketFilterParams

    filters = TicketFilterParams(page=1, page_size=20, assigned_staff_id="me")

    mock_count_res = MagicMock()
    mock_count_res.scalar_one.return_value = 2

    mock_list_res = MagicMock()
    mock_list_res.scalars.return_value.all.return_value = []

    mock_db.execute.side_effect = [mock_count_res, mock_list_res]

    tickets, total = await TicketService.list_tickets(
        mock_db,
        actor=active_staff,
        filters=filters,
    )

    assert total == 2
    assert tickets == []

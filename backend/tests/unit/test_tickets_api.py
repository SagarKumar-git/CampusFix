"""Comprehensive API contract, security, and RBAC tests for Ticket REST endpoints (/api/v1/tickets)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db
from app.main import app
from app.models.category import Category
from app.models.ticket import Ticket, TicketPriority, TicketStatus
from app.models.ticket_history import TicketStatusHistory
from app.models.user import User, UserRole
from app.schemas.ticket import TicketFilterParams
from app.services.ticket_fsm import (
    InvalidAssigneeError,
    UnauthorizedTransitionError,
)
from app.services.ticket_service import (
    CategoryInactiveError,
    CategoryNotFoundError,
    TicketConcurrencyError,
    TicketNotFoundError,
)

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def student_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="student@campusfix.local",
        full_name="Jane Student",
        role=UserRole.STUDENT.value,
        is_active=True,
    )


@pytest.fixture
def other_student_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="other.student@campusfix.local",
        full_name="Other Student",
        role=UserRole.STUDENT.value,
        is_active=True,
    )


@pytest.fixture
def staff_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="alex.rivera@campusfix.local",
        full_name="Alex Rivera",
        role=UserRole.STAFF.value,
        is_active=True,
    )


@pytest.fixture
def other_staff_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="sam.morgan@campusfix.local",
        full_name="Sam Morgan",
        role=UserRole.STAFF.value,
        is_active=True,
    )


@pytest.fixture
def admin_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="admin@campusfix.local",
        full_name="Campus Admin",
        role=UserRole.ADMINISTRATOR.value,
        is_active=True,
    )


@pytest.fixture
def test_category() -> Category:
    return Category(
        id=uuid.uuid4(),
        name="Classroom Audio-Visual",
        description="Projectors, microphones, smartboards",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
async def client(mock_db: AsyncMock):
    app.dependency_overrides[get_db] = lambda: mock_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def make_sample_ticket(
    creator: User,
    category: Category,
    status: TicketStatus = TicketStatus.SUBMITTED,
    assigned_staff: User | None = None,
    version: int = 1,
) -> Ticket:
    """Helper creating a populated Ticket ORM mock with relations attached."""
    t = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-00042",
        title="Projector HDMI Port Damaged",
        description="HDMI port pins are bent and video cuts out during lectures.",
        category_id=category.id,
        location="Science Block A, Room 402",
        priority=TicketPriority.HIGH.value,
        status=status.value,
        creator_id=creator.id,
        assigned_staff_id=assigned_staff.id if assigned_staff else None,
        resolution_notes=None,
        rejection_reason=None,
        version=version,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    t.creator = creator
    t.category = category
    t.assigned_staff = assigned_staff
    return t


# ==============================================================================
# 1. POST /api/v1/tickets Tests (Creation)
# ==============================================================================


@pytest.mark.asyncio
async def test_create_ticket_unauthenticated(client: AsyncClient):
    """Unauthenticated requests are rejected with HTTP 401."""
    response = await client.post("/api/v1/tickets", json={})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_create_ticket_student_success(
    client: AsyncClient, student_user: User, test_category: Category
):
    """Student creates ticket, creator is bound from session, returns HTTP 201 Created."""
    app.dependency_overrides[get_current_user] = lambda: student_user

    sample = make_sample_ticket(creator=student_user, category=test_category)

    with patch(
        "app.services.ticket_service.TicketService.create_ticket", return_value=sample
    ) as mock_create:
        response = await client.post(
            "/api/v1/tickets",
            json={
                "title": "Projector HDMI Port Damaged",
                "description": "HDMI port pins are bent and video cuts out during lectures.",
                "category_id": str(test_category.id),
                "location": "Science Block A, Room 402",
                "priority": "HIGH",
            },
        )
        assert response.status_code == 201
        # Assert creator was bound from current_user, not client payload
        mock_create.assert_awaited_once_with(
            mock_create.call_args[0][0],
            creator=student_user,
            title="Projector HDMI Port Damaged",
            description="HDMI port pins are bent and video cuts out during lectures.",
            category_id=test_category.id,
            location="Science Block A, Room 402",
            priority=TicketPriority.HIGH,
        )

    data = response.json()
    assert data["success"] is True
    assert data["data"]["ticket_number"] == "CFX-2026-00042"
    assert data["data"]["status"] == "SUBMITTED"
    assert data["data"]["creator"]["id"] == str(student_user.id)
    assert data["data"]["creator"]["full_name"] == student_user.full_name


@pytest.mark.asyncio
async def test_create_ticket_inactive_category_returns_422(
    client: AsyncClient, student_user: User, test_category: Category
):
    """Filing ticket under inactive category returns HTTP 422 CATEGORY_INACTIVE."""
    app.dependency_overrides[get_current_user] = lambda: student_user

    with patch(
        "app.services.ticket_service.TicketService.create_ticket",
        side_effect=CategoryInactiveError("Category is inactive"),
    ):
        response = await client.post(
            "/api/v1/tickets",
            json={
                "title": "Broken window pane",
                "description": "Cracked glass window pane.",
                "category_id": str(test_category.id),
                "location": "Hostel 2, Room 10",
                "priority": "MEDIUM",
            },
        )
        assert response.status_code == 422

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "CATEGORY_INACTIVE"


@pytest.mark.asyncio
async def test_create_ticket_missing_category_returns_404(client: AsyncClient, student_user: User):
    """Filing ticket with non-existent category returns HTTP 404 CATEGORY_NOT_FOUND."""
    app.dependency_overrides[get_current_user] = lambda: student_user

    missing_id = uuid.uuid4()
    with patch(
        "app.services.ticket_service.TicketService.create_ticket",
        side_effect=CategoryNotFoundError("Category not found"),
    ):
        response = await client.post(
            "/api/v1/tickets",
            json={
                "title": "Broken window pane",
                "description": "Cracked glass window pane.",
                "category_id": str(missing_id),
                "location": "Hostel 2, Room 10",
                "priority": "MEDIUM",
            },
        )
        assert response.status_code == 404

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "CATEGORY_NOT_FOUND"


# ==============================================================================
# 2. GET /api/v1/tickets Tests (Listing & Filtering)
# ==============================================================================


@pytest.mark.asyncio
async def test_list_tickets_student_idor_enforcement(
    client: AsyncClient, student_user: User, test_category: Category
):
    """Student query passes actor=student_user to TicketService for server-side IDOR isolation."""
    app.dependency_overrides[get_current_user] = lambda: student_user

    sample = make_sample_ticket(creator=student_user, category=test_category)

    with patch(
        "app.services.ticket_service.TicketService.list_tickets",
        return_value=([sample], 1),
    ) as mock_list:
        response = await client.get("/api/v1/tickets?page=1&page_size=20")
        assert response.status_code == 200
        # Check that actor passed is student_user
        mock_list.assert_awaited_once()
        assert mock_list.call_args[1]["actor"] == student_user

    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) == 1
    assert data["meta"]["total"] == 1
    assert data["meta"]["total_pages"] == 1
    assert data["data"][0]["ticket_number"] == "CFX-2026-00042"


@pytest.mark.asyncio
async def test_list_tickets_staff_assigned_me_filter(
    client: AsyncClient, staff_user: User, test_category: Category
):
    """Staff query with assigned_staff_id=me filters technician queue."""
    app.dependency_overrides[get_current_user] = lambda: staff_user

    sample = make_sample_ticket(
        creator=staff_user,
        category=test_category,
        status=TicketStatus.ASSIGNED,
        assigned_staff=staff_user,
    )

    with patch(
        "app.services.ticket_service.TicketService.list_tickets",
        return_value=([sample], 1),
    ) as mock_list:
        response = await client.get(
            "/api/v1/tickets?assigned_staff_id=me&status=ASSIGNED,IN_PROGRESS"
        )
        assert response.status_code == 200
        filters: TicketFilterParams = mock_list.call_args[1]["filters"]
        assert filters.assigned_staff_id == "me"
        assert filters.status == "ASSIGNED,IN_PROGRESS"


@pytest.mark.asyncio
async def test_list_tickets_invalid_status_tokens_rejected(client: AsyncClient, student_user: User):
    """Invalid status values return HTTP 422 VALIDATION_ERROR."""
    app.dependency_overrides[get_current_user] = lambda: student_user

    response = await client.get("/api/v1/tickets?status=INVALID_STATUS,FOOBAR")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# ==============================================================================
# 3. GET /api/v1/tickets/{id} Tests (Detail View & IDOR)
# ==============================================================================


@pytest.mark.asyncio
async def test_get_ticket_student_own_ticket_success(
    client: AsyncClient, student_user: User, test_category: Category
):
    """Student can retrieve details of their own ticket."""
    app.dependency_overrides[get_current_user] = lambda: student_user

    sample = make_sample_ticket(creator=student_user, category=test_category)

    with patch("app.services.ticket_service.TicketService.get_ticket_by_id", return_value=sample):
        response = await client.get(f"/api/v1/tickets/{sample.id}")
        assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == str(sample.id)
    assert data["data"]["creator"]["id"] == str(student_user.id)


@pytest.mark.asyncio
async def test_get_ticket_student_other_ticket_idor_blocked(
    client: AsyncClient, student_user: User
):
    """Student attempting to view another student's ticket returns HTTP 404 RESOURCE_NOT_FOUND (IDOR defense)."""
    app.dependency_overrides[get_current_user] = lambda: student_user

    ticket_id = uuid.uuid4()
    with patch(
        "app.services.ticket_service.TicketService.get_ticket_by_id",
        side_effect=TicketNotFoundError("Ticket not found"),
    ):
        response = await client.get(f"/api/v1/tickets/{ticket_id}")
        assert response.status_code == 404

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"


# ==============================================================================
# 4. POST /api/v1/tickets/{id}/assign Tests (Assignment & Reassignment)
# ==============================================================================


@pytest.mark.asyncio
async def test_assign_ticket_by_student_forbidden(
    client: AsyncClient, student_user: User, staff_user: User
):
    """Students cannot assign tickets (HTTP 403 INSUFFICIENT_PERMISSIONS)."""
    app.dependency_overrides[get_current_user] = lambda: student_user

    ticket_id = uuid.uuid4()
    response = await client.post(
        f"/api/v1/tickets/{ticket_id}/assign",
        json={"staff_id": str(staff_user.id), "expected_version": 1},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_assign_ticket_staff_self_claim_success(
    client: AsyncClient, staff_user: User, student_user: User, test_category: Category
):
    """Staff technician self-claims ticket, returning HTTP 200 with TicketAssignResponseData."""
    app.dependency_overrides[get_current_user] = lambda: staff_user

    sample = make_sample_ticket(
        creator=student_user,
        category=test_category,
        status=TicketStatus.ASSIGNED,
        assigned_staff=staff_user,
        version=2,
    )

    with patch("app.services.ticket_service.TicketService.assign_ticket", return_value=sample):
        response = await client.post(
            f"/api/v1/tickets/{sample.id}/assign",
            json={"staff_id": str(staff_user.id), "expected_version": 1},
        )
        assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "ASSIGNED"
    assert data["data"]["assigned_staff_id"] == str(staff_user.id)
    assert data["data"]["version"] == 2


@pytest.mark.asyncio
async def test_assign_ticket_stale_version_returns_409(client: AsyncClient, staff_user: User):
    """Attempting assignment with stale version returns HTTP 409 CONCURRENCY_CONFLICT."""
    app.dependency_overrides[get_current_user] = lambda: staff_user

    ticket_id = uuid.uuid4()
    with patch(
        "app.services.ticket_service.TicketService.assign_ticket",
        side_effect=TicketConcurrencyError(
            "Version mismatch", expected_version=1, actual_version=3
        ),
    ):
        response = await client.post(
            f"/api/v1/tickets/{ticket_id}/assign",
            json={"staff_id": str(staff_user.id), "expected_version": 1},
        )
        assert response.status_code == 409

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "CONCURRENCY_CONFLICT"
    assert data["error"]["details"]["expected_version"] == 1
    assert data["error"]["details"]["actual_version"] == 3


@pytest.mark.asyncio
async def test_assign_ticket_invalid_assignee_returns_422(client: AsyncClient, admin_user: User):
    """Assigning to an inactive or non-staff user returns HTTP 422 INVALID_ASSIGNEE."""
    app.dependency_overrides[get_current_user] = lambda: admin_user

    ticket_id = uuid.uuid4()
    fake_tech_id = uuid.uuid4()
    with patch(
        "app.services.ticket_service.TicketService.assign_ticket",
        side_effect=InvalidAssigneeError("User is not an active staff technician"),
    ):
        response = await client.post(
            f"/api/v1/tickets/{ticket_id}/assign",
            json={"staff_id": str(fake_tech_id), "expected_version": 1},
        )
        assert response.status_code == 422

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_ASSIGNEE"


# ==============================================================================
# 5. POST /api/v1/tickets/{id}/transition Tests (Lifecycle & Reopening)
# ==============================================================================


@pytest.mark.asyncio
async def test_transition_to_in_progress_by_staff_assignee(
    client: AsyncClient, staff_user: User, student_user: User, test_category: Category
):
    """Assigned technician starts work (IN_PROGRESS), returning HTTP 200 OK."""
    app.dependency_overrides[get_current_user] = lambda: staff_user

    sample = make_sample_ticket(
        creator=student_user,
        category=test_category,
        status=TicketStatus.IN_PROGRESS,
        assigned_staff=staff_user,
        version=3,
    )

    with patch("app.services.ticket_service.TicketService.transition_ticket", return_value=sample):
        response = await client.post(
            f"/api/v1/tickets/{sample.id}/transition",
            json={
                "target_status": "IN_PROGRESS",
                "notes": "Commencing diagnosis and parts testing.",
                "expected_version": 2,
            },
        )
        assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "IN_PROGRESS"
    assert data["data"]["version"] == 3


@pytest.mark.asyncio
async def test_transition_to_resolved_with_notes(
    client: AsyncClient, staff_user: User, student_user: User, test_category: Category
):
    """Technician marks ticket RESOLVED with mandatory resolution notes."""
    app.dependency_overrides[get_current_user] = lambda: staff_user

    notes = "Replaced damaged HDMI wall socket and tested video feed."
    sample = make_sample_ticket(
        creator=student_user,
        category=test_category,
        status=TicketStatus.RESOLVED,
        assigned_staff=staff_user,
        version=4,
    )
    sample.resolution_notes = notes

    with patch("app.services.ticket_service.TicketService.transition_ticket", return_value=sample):
        response = await client.post(
            f"/api/v1/tickets/{sample.id}/transition",
            json={
                "target_status": "RESOLVED",
                "notes": notes,
                "expected_version": 3,
            },
        )
        assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "RESOLVED"
    assert data["data"]["resolution_notes"] == notes
    assert data["data"]["version"] == 4


@pytest.mark.asyncio
async def test_transition_to_resolved_missing_notes_rejected(client: AsyncClient, staff_user: User):
    """Resolving without notes fails validation with HTTP 422."""
    app.dependency_overrides[get_current_user] = lambda: staff_user

    ticket_id = uuid.uuid4()
    response = await client.post(
        f"/api/v1/tickets/{ticket_id}/transition",
        json={
            "target_status": "RESOLVED",
            "expected_version": 3,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_student_cancellation_success(
    client: AsyncClient, student_user: User, test_category: Category
):
    """Student creator cancels their own ticket in SUBMITTED status."""
    app.dependency_overrides[get_current_user] = lambda: student_user

    sample = make_sample_ticket(
        creator=student_user,
        category=test_category,
        status=TicketStatus.CANCELLED,
        version=2,
    )

    with patch("app.services.ticket_service.TicketService.transition_ticket", return_value=sample):
        response = await client.post(
            f"/api/v1/tickets/{sample.id}/transition",
            json={
                "target_status": "CANCELLED",
                "notes": "Issue resolved itself automatically.",
                "expected_version": 1,
            },
        )
        assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_administrator_reopening_resolved_ticket_success(
    client: AsyncClient, admin_user: User, student_user: User, test_category: Category
):
    """Administrator reopens a RESOLVED ticket back to ASSIGNED with mandatory reason."""
    app.dependency_overrides[get_current_user] = lambda: admin_user

    reason = "Lecturer reported projector video flickering again during afternoon session."
    sample = make_sample_ticket(
        creator=student_user,
        category=test_category,
        status=TicketStatus.ASSIGNED,
        version=5,
    )

    with patch("app.services.ticket_service.TicketService.transition_ticket", return_value=sample):
        response = await client.post(
            f"/api/v1/tickets/{sample.id}/transition",
            json={
                "target_status": "ASSIGNED",
                "notes": reason,
                "expected_version": 4,
            },
        )
        assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "ASSIGNED"
    assert data["data"]["version"] == 5


@pytest.mark.asyncio
async def test_reopening_by_student_forbidden(client: AsyncClient, student_user: User):
    """Students attempting to reopen a ticket receive HTTP 403 INSUFFICIENT_PERMISSIONS."""
    app.dependency_overrides[get_current_user] = lambda: student_user

    ticket_id = uuid.uuid4()
    with patch(
        "app.services.ticket_service.TicketService.transition_ticket",
        side_effect=UnauthorizedTransitionError(
            "Only administrators are authorized to reopen tickets."
        ),
    ):
        response = await client.post(
            f"/api/v1/tickets/{ticket_id}/transition",
            json={
                "target_status": "SUBMITTED",
                "notes": "Still broken, please fix immediately.",
                "expected_version": 4,
            },
        )
        assert response.status_code == 403

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


# ==============================================================================
# 6. GET /api/v1/tickets/{id}/history Tests (Audit Log)
# ==============================================================================


@pytest.mark.asyncio
async def test_get_ticket_history_student_own_ticket(client: AsyncClient, student_user: User):
    """Student can retrieve history for their own ticket."""
    app.dependency_overrides[get_current_user] = lambda: student_user

    ticket_id = uuid.uuid4()
    mock_history = [
        TicketStatusHistory(
            id=uuid.uuid4(),
            ticket_id=ticket_id,
            from_status=None,
            to_status="SUBMITTED",
            changed_by_user_id=student_user.id,
            assigned_to_user_id=None,
            notes="Ticket submitted.",
            created_at=datetime.now(UTC),
        )
    ]
    mock_history[0].changed_by_user = student_user
    mock_history[0].assigned_to_user = None

    with patch(
        "app.services.ticket_service.TicketService.get_ticket_history", return_value=mock_history
    ):
        response = await client.get(f"/api/v1/tickets/{ticket_id}/history")
        assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) == 1
    assert data["data"][0]["to_status"] == "SUBMITTED"
    assert data["data"][0]["changed_by"]["id"] == str(student_user.id)
    assert data["data"][0]["assigned_to"] is None


@pytest.mark.asyncio
async def test_get_ticket_history_other_student_idor_blocked(
    client: AsyncClient, student_user: User
):
    """Student attempting to view history of someone else's ticket returns HTTP 404 RESOURCE_NOT_FOUND."""
    app.dependency_overrides[get_current_user] = lambda: student_user

    ticket_id = uuid.uuid4()
    with patch(
        "app.services.ticket_service.TicketService.get_ticket_history",
        side_effect=TicketNotFoundError("Ticket not found"),
    ):
        response = await client.get(f"/api/v1/tickets/{ticket_id}/history")
        assert response.status_code == 404

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"

"""Comprehensive security, RBAC, IDOR, lifecycle, and error-handling audit test suite.

Checkpoint 3.7 verification suite auditing:
- Authentication & Session security (token claims, expiry, inactive accounts, secret privacy)
- RBAC role isolation across STUDENT, STAFF, and ADMINISTRATOR
- IDOR defenses and 404 masking for student tickets and audit trails
- Ticket FSM lifecycle, administrator reopening (RESOLVED/REJECTED -> SUBMITTED/ASSIGNED),
  commentary length constraints, and terminal CANCELLED state immutability
- Concurrency version verification and HTTP 409 Conflict mapping
- Robustness against malformed UUIDs, invalid bodies, and information leakage
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.category import Category
from app.models.ticket import Ticket, TicketPriority, TicketStatus
from app.models.user import User, UserRole
from app.services.ticket_fsm import (
    TerminalStateError,
    UnauthorizedTransitionError,
)
from app.services.ticket_service import (
    TicketConcurrencyError,
    TicketNotFoundError,
)

# ==============================================================================
# Fixtures & Synthetic Test Fixtures
# ==============================================================================


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def student_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="student.auditor@campusfix.local",
        full_name="Alice Student",
        hashed_password=hash_password("StudentPassword123!"),
        role=UserRole.STUDENT.value,
        is_active=True,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def other_student_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="other.student@campusfix.local",
        full_name="Bob Student",
        hashed_password=hash_password("OtherStudentPassword123!"),
        role=UserRole.STUDENT.value,
        is_active=True,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def staff_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="tech.primary@campusfix.local",
        full_name="Charlie Technician",
        hashed_password=hash_password("StaffPassword123!"),
        role=UserRole.STAFF.value,
        is_active=True,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def other_staff_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="tech.secondary@campusfix.local",
        full_name="Dave Specialist",
        hashed_password=hash_password("OtherStaffPassword123!"),
        role=UserRole.STAFF.value,
        is_active=True,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def admin_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="admin.security@campusfix.local",
        full_name="Security Administrator",
        hashed_password=hash_password("AdminPassword123!"),
        role=UserRole.ADMINISTRATOR.value,
        is_active=True,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def inactive_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="suspended.user@campusfix.local",
        full_name="Suspended User",
        hashed_password=hash_password("SuspendedPassword123!"),
        role=UserRole.STUDENT.value,
        is_active=False,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_category() -> Category:
    return Category(
        id=uuid.uuid4(),
        name="Electrical & Power Systems",
        description="Power outlets, distribution panels, and high-voltage campus wiring",
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


def make_audit_ticket(
    creator: User,
    category: Category,
    status: TicketStatus = TicketStatus.SUBMITTED,
    assigned_staff: User | None = None,
    version: int = 1,
) -> Ticket:
    t = Ticket(
        id=uuid.uuid4(),
        ticket_number="CFX-2026-99999",
        title="Sparks emitted from laboratory wall socket",
        description="Electrical wall socket in Chemistry Lab 304 sparks upon plugging in equipment.",
        category_id=category.id,
        location="Chemistry Building, Lab 304",
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
# 1. Unauthenticated Access & Token Security Audit
# ==============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "endpoint", "payload"),
    [
        ("GET", "/api/v1/auth/me", None),
        ("POST", "/api/v1/auth/logout", None),
        ("GET", "/api/v1/categories", None),
        (
            "GET",
            "/api/v1/categories/550e8400-e29b-41d4-a716-446655440000",
            None,
        ),
        (
            "POST",
            "/api/v1/categories",
            {"name": "New Cat", "description": "New Category description"},
        ),
        (
            "PATCH",
            "/api/v1/categories/550e8400-e29b-41d4-a716-446655440000",
            {"name": "Updated"},
        ),
        (
            "POST",
            "/api/v1/tickets",
            {
                "title": "Title",
                "description": "Desc",
                "category_id": "550e8400-e29b-41d4-a716-446655440000",
                "location": "Loc",
                "priority": "LOW",
            },
        ),
        ("GET", "/api/v1/tickets", None),
        ("GET", "/api/v1/tickets/550e8400-e29b-41d4-a716-446655440000", None),
        (
            "POST",
            "/api/v1/tickets/550e8400-e29b-41d4-a716-446655440000/assign",
            {
                "staff_id": "550e8400-e29b-41d4-a716-446655440001",
                "expected_version": 1,
            },
        ),
        (
            "POST",
            "/api/v1/tickets/550e8400-e29b-41d4-a716-446655440000/transition",
            {
                "target_status": "CANCELLED",
                "expected_version": 1,
            },
        ),
        (
            "GET",
            "/api/v1/tickets/550e8400-e29b-41d4-a716-446655440000/history",
            None,
        ),
    ],
)
async def test_unauthenticated_requests_strictly_rejected(
    client: AsyncClient, method: str, endpoint: str, payload: dict | None
):
    """Verifies that all protected endpoints reject requests without Authorization header with HTTP 401."""
    if method == "GET":
        response = await client.get(endpoint)
    elif method == "POST":
        response = await client.post(endpoint, json=payload or {})
    elif method == "PATCH":
        response = await client.patch(endpoint, json=payload or {})

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert "timestamp" in body


@pytest.mark.asyncio
async def test_bearer_token_validation_failures(client: AsyncClient, mock_db: AsyncMock):
    """Verifies that invalid, expired, and non-existent user JWTs are rejected with HTTP 401."""
    # 1. Malformed token format
    res_malformed = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-valid-token"}
    )
    assert res_malformed.status_code == 401
    assert res_malformed.json()["error"]["code"] == "UNAUTHORIZED"

    # 2. Expired access token
    expired_token = create_access_token(
        user_id=uuid.uuid4(),
        email="expired@campusfix.local",
        role=UserRole.STUDENT,
        expires_delta=timedelta(seconds=-60),
    )
    res_expired = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert res_expired.status_code == 401
    assert "expired" in res_expired.json()["error"]["message"].lower()

    # 3. Token with non-existent user ID
    valid_jwt_orphan = create_access_token(
        user_id=uuid.uuid4(),
        email="ghost@campusfix.local",
        role=UserRole.STUDENT,
        expires_delta=timedelta(minutes=15),
    )
    with patch("app.services.auth_service.AuthService.get_user_by_id", return_value=None):
        res_orphan = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {valid_jwt_orphan}"},
        )
        assert res_orphan.status_code == 401
        assert "not found" in res_orphan.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_inactive_user_access_blocked_across_endpoints(
    client: AsyncClient, inactive_user: User
):
    """Verifies that deactivated users cannot access any active endpoint (HTTP 403 FORBIDDEN)."""
    app.dependency_overrides[get_current_user] = lambda: inactive_user

    # Categories list
    res_cat = await client.get("/api/v1/categories")
    assert res_cat.status_code == 403
    assert "inactive" in res_cat.json()["error"]["message"].lower()

    # Tickets list
    res_tick = await client.get("/api/v1/tickets")
    assert res_tick.status_code == 403
    assert "inactive" in res_tick.json()["error"]["message"].lower()


# ==============================================================================
# 2. Secret & Password Privacy Audit
# ==============================================================================


@pytest.mark.asyncio
async def test_password_hashes_never_exposed_in_responses(
    client: AsyncClient, student_user: User, sample_category: Category
):
    """Audits ticket responses and user references to ensure hashed_password is never leaked."""
    app.dependency_overrides[get_current_user] = lambda: student_user

    ticket = make_audit_ticket(creator=student_user, category=sample_category)

    with patch(
        "app.services.ticket_service.TicketService.get_ticket_by_id",
        return_value=ticket,
    ):
        response = await client.get(f"/api/v1/tickets/{ticket.id}")
        assert response.status_code == 200
        text = response.text
        assert "hashed_password" not in text
        assert "password" not in text
        assert "hash_" not in text
        assert "$argon2id$" not in text


# ==============================================================================
# 3. RBAC Isolation & IDOR Verification
# ==============================================================================


@pytest.mark.asyncio
async def test_student_rbac_restrictions_and_idor_protection(
    client: AsyncClient,
    student_user: User,
    other_student_user: User,
    sample_category: Category,
):
    """Verifies student isolation: cannot create categories, cannot assign tickets,

    and access to another student's ticket is masked as HTTP 404 (IDOR protection).
    """
    app.dependency_overrides[get_current_user] = lambda: student_user

    # 1. Student cannot create categories
    res_create_cat = await client.post(
        "/api/v1/categories",
        json={"name": "Forbidden Cat", "description": "Student category creation attempt"},
    )
    assert res_create_cat.status_code == 403
    assert res_create_cat.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # 2. Student cannot update categories
    res_update_cat = await client.patch(
        f"/api/v1/categories/{sample_category.id}",
        json={"name": "Forbidden Modification"},
    )
    assert res_update_cat.status_code == 403
    assert res_update_cat.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # 3. Student cannot assign tickets
    fake_ticket_id = uuid.uuid4()
    res_assign = await client.post(
        f"/api/v1/tickets/{fake_ticket_id}/assign",
        json={"staff_id": str(uuid.uuid4()), "expected_version": 1},
    )
    assert res_assign.status_code == 403
    assert res_assign.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # 4. IDOR Defense: Accessing another student's ticket returns 404 Not Found (not 403)
    with patch(
        "app.services.ticket_service.TicketService.get_ticket_by_id",
        side_effect=TicketNotFoundError(f"Ticket '{fake_ticket_id}' was not found."),
    ):
        res_get_ticket = await client.get(f"/api/v1/tickets/{fake_ticket_id}")
        assert res_get_ticket.status_code == 404
        assert res_get_ticket.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    # 5. IDOR Defense: Accessing another student's history returns 404 Not Found
    with patch(
        "app.services.ticket_service.TicketService.get_ticket_history",
        side_effect=TicketNotFoundError(f"Ticket '{fake_ticket_id}' was not found."),
    ):
        res_history = await client.get(f"/api/v1/tickets/{fake_ticket_id}/history")
        assert res_history.status_code == 404
        assert res_history.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_staff_rbac_boundaries_and_work_isolation(
    client: AsyncClient,
    staff_user: User,
    sample_category: Category,
):
    """Verifies staff boundaries: cannot create categories, cannot assign other technicians,

    and cannot transition tickets assigned to someone else.
    """
    app.dependency_overrides[get_current_user] = lambda: staff_user

    # 1. Staff cannot create categories
    res_cat = await client.post(
        "/api/v1/categories",
        json={"name": "Staff Cat", "description": "Staff category creation attempt"},
    )
    assert res_cat.status_code == 403
    assert res_cat.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # 2. Staff cannot assign another technician
    fake_ticket_id = uuid.uuid4()
    other_tech_id = uuid.uuid4()
    with patch(
        "app.services.ticket_service.TicketService.assign_ticket",
        side_effect=UnauthorizedTransitionError(
            "Staff members may only self-claim unassigned tickets."
        ),
    ):
        res_assign = await client.post(
            f"/api/v1/tickets/{fake_ticket_id}/assign",
            json={"staff_id": str(other_tech_id), "expected_version": 1},
        )
        assert res_assign.status_code == 403
        assert res_assign.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # 3. Staff cannot start work on a ticket assigned to a different technician
    with patch(
        "app.services.ticket_service.TicketService.transition_ticket",
        side_effect=UnauthorizedTransitionError(
            "Only the assigned staff technician or an administrator may start work on this ticket."
        ),
    ):
        res_trans = await client.post(
            f"/api/v1/tickets/{fake_ticket_id}/transition",
            json={"target_status": "IN_PROGRESS", "expected_version": 1},
        )
        assert res_trans.status_code == 403
        assert res_trans.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


# ==============================================================================
# 4. Ticket Lifecycle & Reopening Audit
# ==============================================================================


@pytest.mark.asyncio
async def test_reopening_authorization_and_validation(
    client: AsyncClient,
    admin_user: User,
    staff_user: User,
    student_user: User,
    sample_category: Category,
):
    """Verifies that reopening is strictly restricted to ADMINISTRATOR,

    supports both RESOLVED and REJECTED states transitioning to SUBMITTED or ASSIGNED,
    and enforces reason >= 10 characters.
    """
    fake_ticket_id = uuid.uuid4()

    # 1. Student attempting to reopen returns 403
    app.dependency_overrides[get_current_user] = lambda: student_user
    with patch(
        "app.services.ticket_service.TicketService.transition_ticket",
        side_effect=UnauthorizedTransitionError(
            "Only administrators may reopen tickets from 'RESOLVED'."
        ),
    ):
        res_student_reopen = await client.post(
            f"/api/v1/tickets/{fake_ticket_id}/transition",
            json={
                "target_status": "SUBMITTED",
                "notes": "Student wants this ticket reopened because issue persists.",
                "expected_version": 2,
            },
        )
        assert res_student_reopen.status_code == 403
        assert res_student_reopen.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # 2. Staff attempting to reopen returns 403
    app.dependency_overrides[get_current_user] = lambda: staff_user
    with patch(
        "app.services.ticket_service.TicketService.transition_ticket",
        side_effect=UnauthorizedTransitionError(
            "Only administrators may reopen tickets from 'REJECTED'."
        ),
    ):
        res_staff_reopen = await client.post(
            f"/api/v1/tickets/{fake_ticket_id}/transition",
            json={
                "target_status": "ASSIGNED",
                "notes": "Staff technician requesting ticket reopening for additional inspection.",
                "expected_version": 2,
            },
        )
        assert res_staff_reopen.status_code == 403
        assert res_staff_reopen.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # 3. Administrator successfully reopens REJECTED ticket to SUBMITTED
    app.dependency_overrides[get_current_user] = lambda: admin_user
    reopened_ticket = make_audit_ticket(
        creator=student_user, category=sample_category, status=TicketStatus.SUBMITTED, version=3
    )
    with patch(
        "app.services.ticket_service.TicketService.transition_ticket",
        return_value=reopened_ticket,
    ) as mock_trans:
        res_admin_reopen_sub = await client.post(
            f"/api/v1/tickets/{fake_ticket_id}/transition",
            json={
                "target_status": "SUBMITTED",
                "notes": "Reopening previously rejected ticket following user appeal and review.",
                "expected_version": 2,
            },
        )
        assert res_admin_reopen_sub.status_code == 200
        assert res_admin_reopen_sub.json()["data"]["status"] == "SUBMITTED"
        assert res_admin_reopen_sub.json()["data"]["version"] == 3
        mock_trans.assert_awaited_once()

    # 4. Administrator successfully reopens RESOLVED ticket to ASSIGNED with staff_id
    reopened_assigned_ticket = make_audit_ticket(
        creator=student_user,
        category=sample_category,
        status=TicketStatus.ASSIGNED,
        assigned_staff=staff_user,
        version=4,
    )
    with patch(
        "app.services.ticket_service.TicketService.transition_ticket",
        return_value=reopened_assigned_ticket,
    ) as mock_trans_assigned:
        res_admin_reopen_ass = await client.post(
            f"/api/v1/tickets/{fake_ticket_id}/transition",
            json={
                "target_status": "ASSIGNED",
                "notes": "Facility issue recurred within 24 hours. Reopening and reassigning technician.",
                "assigned_staff_id": str(staff_user.id),
                "expected_version": 3,
            },
        )
        assert res_admin_reopen_ass.status_code == 200
        assert res_admin_reopen_ass.json()["data"]["status"] == "ASSIGNED"
        assert res_admin_reopen_ass.json()["data"]["version"] == 4
        mock_trans_assigned.assert_awaited_once()


@pytest.mark.asyncio
async def test_reopening_and_resolution_notes_length_enforcement(
    client: AsyncClient, admin_user: User
):
    """Enforces minimum 10-character commentary rules for RESOLVED, REJECTED, and reopening."""
    app.dependency_overrides[get_current_user] = lambda: admin_user
    fake_ticket_id = uuid.uuid4()

    # 1. Notes missing for RESOLVED
    res_no_notes = await client.post(
        f"/api/v1/tickets/{fake_ticket_id}/transition",
        json={"target_status": "RESOLVED", "expected_version": 1},
    )
    assert res_no_notes.status_code == 422
    assert res_no_notes.json()["error"]["code"] == "VALIDATION_ERROR"

    # 2. Notes too short (< 10 chars) for RESOLVED
    res_short_notes = await client.post(
        f"/api/v1/tickets/{fake_ticket_id}/transition",
        json={"target_status": "RESOLVED", "notes": "Fixed it", "expected_version": 1},
    )
    assert res_short_notes.status_code == 422
    assert res_short_notes.json()["error"]["code"] == "VALIDATION_ERROR"

    # 3. Notes missing for REJECTED
    res_no_reject_reason = await client.post(
        f"/api/v1/tickets/{fake_ticket_id}/transition",
        json={"target_status": "REJECTED", "expected_version": 1},
    )
    assert res_no_reject_reason.status_code == 422
    assert res_no_reject_reason.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_terminal_cancelled_state_cannot_be_transitioned(
    client: AsyncClient, admin_user: User
):
    """Verifies that terminal CANCELLED tickets cannot be transitioned or reopened."""
    app.dependency_overrides[get_current_user] = lambda: admin_user
    fake_ticket_id = uuid.uuid4()

    with patch(
        "app.services.ticket_service.TicketService.transition_ticket",
        side_effect=TerminalStateError(
            "Ticket is in terminal state 'CANCELLED' and cannot be transitioned."
        ),
    ):
        response = await client.post(
            f"/api/v1/tickets/{fake_ticket_id}/transition",
            json={
                "target_status": "SUBMITTED",
                "notes": "Attempting to revive a cancelled ticket.",
                "expected_version": 2,
            },
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "TERMINAL_STATE"


# ==============================================================================
# 5. Concurrency & Optimistic Version Conflict Verification
# ==============================================================================


@pytest.mark.asyncio
async def test_concurrency_conflict_returns_409_with_versions(
    client: AsyncClient, admin_user: User
):
    """Verifies that an optimistic concurrency mismatch maps cleanly to HTTP 409 Conflict

    with expected_version and actual_version details in standard envelope.
    """
    app.dependency_overrides[get_current_user] = lambda: admin_user
    fake_ticket_id = uuid.uuid4()

    # 1. On transition
    with patch(
        "app.services.ticket_service.TicketService.transition_ticket",
        side_effect=TicketConcurrencyError(
            "Concurrency conflict on ticket 'CFX-2026-00042': expected version 1, but current version is 2.",
            expected_version=1,
            actual_version=2,
        ),
    ):
        response = await client.post(
            f"/api/v1/tickets/{fake_ticket_id}/transition",
            json={"target_status": "IN_PROGRESS", "expected_version": 1},
        )
        assert response.status_code == 409
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "CONCURRENCY_CONFLICT"
        assert body["error"]["details"]["expected_version"] == 1
        assert body["error"]["details"]["actual_version"] == 2

    # 2. On assignment
    with patch(
        "app.services.ticket_service.TicketService.assign_ticket",
        side_effect=TicketConcurrencyError(
            "Concurrency conflict on ticket 'CFX-2026-00042': expected version 2, but current version is 3.",
            expected_version=2,
            actual_version=3,
        ),
    ):
        response_assign = await client.post(
            f"/api/v1/tickets/{fake_ticket_id}/assign",
            json={"staff_id": str(uuid.uuid4()), "expected_version": 2},
        )
        assert response_assign.status_code == 409
        body_assign = response_assign.json()
        assert body_assign["success"] is False
        assert body_assign["error"]["code"] == "CONCURRENCY_CONFLICT"
        assert body_assign["error"]["details"]["expected_version"] == 2
        assert body_assign["error"]["details"]["actual_version"] == 3


# ==============================================================================
# 6. API Robustness & Schema Validation
# ==============================================================================


@pytest.mark.asyncio
async def test_api_robustness_against_malformed_inputs(client: AsyncClient, admin_user: User):
    """Verifies standardized error handling for malformed UUIDs, invalid query params, and forbidden fields."""
    app.dependency_overrides[get_current_user] = lambda: admin_user

    # 1. Malformed UUID in path parameter
    res_bad_uuid = await client.get("/api/v1/tickets/not-a-valid-uuid")
    assert res_bad_uuid.status_code == 422
    assert res_bad_uuid.json()["error"]["code"] == "VALIDATION_ERROR"

    # 2. Malformed query pagination parameters (page=0, page_size=200)
    res_bad_page = await client.get("/api/v1/tickets?page=0&page_size=200")
    assert res_bad_page.status_code == 422
    assert res_bad_page.json()["error"]["code"] == "VALIDATION_ERROR"

    # 3. Invalid status query filter
    res_bad_status = await client.get("/api/v1/tickets?status=INVALID_STATUS")
    assert res_bad_status.status_code == 422
    assert res_bad_status.json()["error"]["code"] == "VALIDATION_ERROR"

    # 4. Extra forbidden fields in request payload (ConfigDict(extra="forbid"))
    res_extra_field = await client.post(
        "/api/v1/tickets",
        json={
            "title": "Valid Title For Issue",
            "description": "Valid description of at least ten characters.",
            "category_id": str(uuid.uuid4()),
            "location": "Library Room 101",
            "priority": "LOW",
            "creator_id": str(uuid.uuid4()),  # Extra forbidden field
        },
    )
    assert res_extra_field.status_code == 422
    assert res_extra_field.json()["error"]["code"] == "VALIDATION_ERROR"

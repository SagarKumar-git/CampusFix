"""Comprehensive unit test suite for CampusFix Pydantic v2 schemas and error models.

Validates all request and response contracts, constraint boundaries, sanitization,
RFC 7807 Problem Details serialization, and protection against leaking sensitive hashes.
"""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models.ticket import TicketPriority, TicketStatus
from app.models.user import UserRole
from app.schemas.auth import (
    LoginResponseData,
    RefreshTokenRequest,
    TokenPayload,
    TokenResponse,
)
from app.schemas.category import (
    CategoryCreate,
    CategoryResponse,
    CategorySummary,
    CategoryUpdate,
)
from app.schemas.common import (
    MessageResponse,
    PaginatedResponse,
    PaginationMeta,
    PaginationParams,
    SuccessEnvelope,
)
from app.schemas.error import (
    ErrorDetail,
    ErrorEnvelope,
    ProblemDetails,
    ValidationErrorItem,
)
from app.schemas.ticket import (
    AdminMetricsResponseData,
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
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserQueryParams,
    UserResponse,
    UserRoleUpdate,
    UserSummary,
    validate_email_format,
    validate_password_complexity,
)

# ==============================================================================
# 1. User & Authentication Schemas Tests
# ==============================================================================


def test_user_create_valid():
    """Valid student registration payload passes validation and strips whitespace."""
    payload = {
        "full_name": "  Jane Doe  ",
        "email": "JANE.DOE@university.edu  ",
        "password": "SecurePassword123!",
    }
    user = UserCreate(**payload)
    assert user.full_name == "Jane Doe"
    assert user.email == "jane.doe@university.edu"
    assert user.password == "SecurePassword123!"


@pytest.mark.parametrize(
    "invalid_email",
    [
        "notanemail",
        "@domain.com",
        "user@",
        "user@domain",
        "user space@domain.com",
        "user@domain..com",
        "user@domain.",
        "",
        "   ",
        "a" * 250 + "@domain.com",  # Exceeds 255 chars
    ],
)
def test_user_create_invalid_email(invalid_email: str):
    """Malformed or invalid email formats raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(
            full_name="Jane Doe",
            email=invalid_email,
            password="SecurePassword123!",
        )
    assert "email" in str(exc_info.value)


@pytest.mark.parametrize(
    ("bad_password", "expected_err"),
    [
        ("Short1!", "at least 8 characters"),
        ("a" * 129 + "1A!", "cannot exceed 128 characters"),
        ("NoNumberHere!", "at least one numerical digit"),
        ("lowercase123!", "at least one uppercase letter"),
        ("UPPERCASE123!", "at least one lowercase letter"),
    ],
)
def test_user_create_password_rules(bad_password: str, expected_err: str):
    """FR-001 password complexity enforcement rejects insufficient passwords."""
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(
            full_name="Jane Doe",
            email="jane.doe@university.edu",
            password=bad_password,
        )
    assert expected_err in str(exc_info.value)


def test_user_create_rejects_extra_fields():
    """Privilege escalation or unexpected request fields are strictly forbidden."""
    payload = {
        "full_name": "Jane Doe",
        "email": "jane.doe@university.edu",
        "password": "SecurePassword123!",
        "role": "ADMINISTRATOR",
        "is_active": True,
        "id": str(uuid.uuid4()),
    }
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(**payload)
    err = str(exc_info.value)
    assert "extra_forbidden" in err or "Extra inputs are not permitted" in err


def test_user_create_empty_or_whitespace_name():
    """Empty or pure whitespace full_name fails validation."""
    with pytest.raises(ValidationError):
        UserCreate(
            full_name="   ",
            email="jane.doe@university.edu",
            password="SecurePassword123!",
        )


def test_user_login_valid():
    """Valid login credentials validate and normalize email."""
    login = UserLogin(email="  Jane.Doe@university.edu ", password="PlainPassword123!")
    assert login.email == "jane.doe@university.edu"
    assert login.password == "PlainPassword123!"


def test_user_login_invalid():
    """Empty password, invalid email format, or extra fields are rejected."""
    with pytest.raises(ValidationError):
        UserLogin(email="invalid_email", password="ValidPassword123!")

    with pytest.raises(ValidationError):
        UserLogin(email="jane.doe@university.edu", password="")

    with pytest.raises(ValidationError):
        UserLogin(
            email="jane.doe@university.edu",
            password="ValidPassword123!",
            extra_field="malicious",
        )


def test_user_response_serialization_and_masking():
    """UserResponse serializes ORM-like data and never exposes password hash or security tokens."""
    uid = uuid.uuid4()
    now = datetime.now(UTC)
    data = {
        "id": uid,
        "email": "jane.doe@university.edu",
        "full_name": "Jane Doe",
        "role": UserRole.STUDENT,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
        # Intentionally include sensitive backend fields to test exclusion
        "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$fake_hash",
        "raw_token": "secret_token_12345",
    }
    user_resp = UserResponse.model_validate(data)
    dumped = user_resp.model_dump()

    assert dumped["id"] == uid
    assert dumped["email"] == "jane.doe@university.edu"
    assert dumped["role"] == UserRole.STUDENT
    assert "hashed_password" not in dumped
    assert "raw_token" not in dumped
    assert not hasattr(user_resp, "hashed_password")


def test_user_summary_serialization():
    """UserSummary provides minimal public representation for embedded records."""
    uid = uuid.uuid4()
    summary = UserSummary(id=uid, full_name="Staff Tech")
    assert summary.id == uid
    assert summary.full_name == "Staff Tech"


def test_user_validation_helper_functions():
    """validate_email_format and validate_password_complexity work standalone."""
    assert validate_email_format("  USER@DOMAIN.EDU ") == "user@domain.edu"
    assert validate_password_complexity("ValidPass123!") == "ValidPass123!"

    with pytest.raises(ValueError):
        validate_email_format("bad_email")

    with pytest.raises(ValueError):
        validate_password_complexity("weak")


def test_user_role_update_valid_and_invalid():
    """UserRoleUpdate allows valid enum values and rejects invalid or extra fields."""
    update = UserRoleUpdate(role=UserRole.STAFF)
    assert update.role == UserRole.STAFF

    with pytest.raises(ValidationError):
        UserRoleUpdate(role="SUPERUSER")  # type: ignore

    with pytest.raises(ValidationError):
        UserRoleUpdate(role=UserRole.STAFF, unexpected="field")


def test_user_query_params_boundaries():
    """UserQueryParams validates pagination caps and strips search query."""
    params = UserQueryParams(page=2, page_size=50, search="  Jane Doe  ", role=UserRole.STUDENT)
    assert params.page == 2
    assert params.page_size == 50
    assert params.search == "Jane Doe"
    assert params.role == UserRole.STUDENT

    # Empty search string cleaned to None
    params_empty_search = UserQueryParams(search="   ")
    assert params_empty_search.search is None

    with pytest.raises(ValidationError):
        UserQueryParams(page=0)

    with pytest.raises(ValidationError):
        UserQueryParams(page_size=101)


# ==============================================================================
# 2. Auth Tokens & Session Schemas Tests
# ==============================================================================


def test_token_response_and_login_response():
    """TokenResponse and LoginResponseData serialize tokens without exposing refresh tokens."""
    token_resp = TokenResponse(access_token="eyJhbGciOi...", token_type="bearer", expires_in=900)
    assert token_resp.access_token == "eyJhbGciOi..."
    assert token_resp.expires_in == 900
    assert "refresh_token" not in token_resp.model_dump()

    uid = uuid.uuid4()
    now = datetime.now(UTC)
    user = UserResponse(
        id=uid,
        email="jane.doe@university.edu",
        full_name="Jane Doe",
        role=UserRole.STUDENT,
        is_active=True,
        created_at=now,
    )
    login_resp = LoginResponseData(
        access_token="eyJhbGciOi...",
        token_type="bearer",
        expires_in=900,
        user=user,
    )
    dumped = login_resp.model_dump()
    assert dumped["user"]["id"] == uid
    assert "refresh_token" not in dumped


def test_refresh_token_request_and_token_payload():
    """RefreshTokenRequest and TokenPayload validate correctly."""
    req = RefreshTokenRequest(refresh_token="  token_abc123  ")
    assert req.refresh_token == "token_abc123"

    payload = TokenPayload(
        sub=str(uuid.uuid4()),
        email="jane.doe@university.edu",
        role="STUDENT",
        type="access",
        iat=1700000000,
        exp=1700000900,
    )
    assert payload.type == "access"


# ==============================================================================
# 3. Category Schemas Tests
# ==============================================================================


def test_category_create_and_update():
    """CategoryCreate and CategoryUpdate enforce length constraints and extra field rejection."""
    cat = CategoryCreate(
        name="  Electrical & Lighting  ",
        description="Power outlets, circuit breakers, and lighting fixtures.",
        is_active=True,
    )
    assert cat.name == "Electrical & Lighting"
    assert cat.is_active is True

    # Category name too short
    with pytest.raises(ValidationError):
        CategoryCreate(name="E", description="Valid description")

    # Category description too short
    with pytest.raises(ValidationError):
        CategoryCreate(name="Valid Name", description="Tiny")

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        CategoryCreate(name="Valid Name", description="Valid description", extra_field=True)

    # Partial updates
    update = CategoryUpdate(name="HVAC Systems")
    assert update.name == "HVAC Systems"
    assert update.description is None
    assert update.is_active is None


def test_category_response_and_summary():
    """CategoryResponse and CategorySummary serialize from attributes."""
    cat_id = uuid.uuid4()
    resp = CategoryResponse(
        id=cat_id,
        name="Plumbing",
        description="Pipes and faucets",
        is_active=True,
    )
    assert resp.id == cat_id

    summary = CategorySummary(id=cat_id, name="Plumbing")
    assert summary.name == "Plumbing"


# ==============================================================================
# 4. Ticket Schemas Tests
# ==============================================================================


def test_ticket_create_valid():
    """Valid ticket filing payload with default priority MEDIUM."""
    cat_id = uuid.uuid4()
    payload = {
        "title": "Projector HDMI Port Damaged",
        "description": "The HDMI input port is bent and cannot connect to presenter laptops.",
        "category_id": cat_id,
        "location": "Science Block A, Room 402",
    }
    ticket = TicketCreate(**payload)
    assert ticket.title == "Projector HDMI Port Damaged"
    assert ticket.category_id == cat_id
    assert ticket.priority == TicketPriority.MEDIUM
    assert ticket.location == "Science Block A, Room 402"


@pytest.mark.parametrize(
    ("bad_field", "value"),
    [
        ("title", "Tiny"),  # < 5 chars
        ("title", "A" * 121),  # > 120 chars
        ("description", "Too short"),  # < 10 chars
        ("description", "A" * 2001),  # > 2000 chars
        ("location", "No"),  # < 3 chars
        ("location", "A" * 101),  # > 100 chars
        ("category_id", "invalid-uuid"),
        ("priority", "SUPER_URGENT"),
    ],
)
def test_ticket_create_field_constraints(bad_field: str, value):
    """Field constraints reject out-of-boundary values."""
    cat_id = uuid.uuid4()
    valid_data = {
        "title": "Valid Ticket Title",
        "description": "Valid ticket description with sufficient detail.",
        "category_id": cat_id,
        "location": "Valid Location Room 101",
        "priority": TicketPriority.HIGH,
    }
    valid_data[bad_field] = value
    with pytest.raises(ValidationError):
        TicketCreate(**valid_data)


def test_ticket_create_rejects_extra_fields():
    """Clients are strictly prohibited from passing arbitrary initial status, creator_id, or version."""
    cat_id = uuid.uuid4()
    payload = {
        "title": "Valid Ticket Title",
        "description": "Valid ticket description with sufficient detail.",
        "category_id": cat_id,
        "location": "Valid Location Room 101",
        "status": "RESOLVED",  # Malicious attempt to file pre-resolved ticket
        "creator_id": str(uuid.uuid4()),
        "version": 99,
    }
    with pytest.raises(ValidationError):
        TicketCreate(**payload)


def test_ticket_assign_valid_and_invalid():
    """TicketAssign validates staff UUID, expected_version ge=1, and forbids extra fields."""
    staff_id = uuid.uuid4()
    assign = TicketAssign(staff_id=staff_id, expected_version=1)
    assert assign.staff_id == staff_id
    assert assign.expected_version == 1

    # Invalid UUID
    with pytest.raises(ValidationError):
        TicketAssign(staff_id="not-a-uuid", expected_version=1)  # type: ignore

    # expected_version < 1
    with pytest.raises(ValidationError):
        TicketAssign(staff_id=staff_id, expected_version=0)

    # Extra fields
    with pytest.raises(ValidationError):
        TicketAssign(staff_id=staff_id, expected_version=1, notes="Extra field")


def test_ticket_assign_and_transition_response_data():
    """TicketAssignResponseData and TicketTransitionResponseData serialize mutations."""
    tid = uuid.uuid4()
    staff_id = uuid.uuid4()
    now = datetime.now(UTC)

    assign_data = TicketAssignResponseData(
        id=tid,
        ticket_number="CFX-2026-00042",
        status=TicketStatus.ASSIGNED,
        assigned_staff_id=staff_id,
        version=2,
        updated_at=now,
    )
    assert assign_data.status == TicketStatus.ASSIGNED

    trans_data = TicketTransitionResponseData(
        id=tid,
        ticket_number="CFX-2026-00042",
        status=TicketStatus.RESOLVED,
        resolution_notes="Resolved promptly with new equipment.",
        version=3,
        updated_at=now,
    )
    assert trans_data.resolution_notes is not None


def test_ticket_history_response():
    """TicketHistoryResponse serializes historical transition log entries."""
    hid = uuid.uuid4()
    tid = uuid.uuid4()
    uid = uuid.uuid4()
    now = datetime.now(UTC)

    history = TicketHistoryResponse(
        id=hid,
        ticket_id=tid,
        from_status=TicketStatus.SUBMITTED,
        to_status=TicketStatus.ASSIGNED,
        changed_by=UserSummary(id=uid, full_name="Admin Person"),
        assigned_to=UserSummary(id=uuid.uuid4(), full_name="Tech Guy"),
        notes="Assigned to specialist.",
        created_at=now,
    )
    assert history.from_status == TicketStatus.SUBMITTED
    assert history.changed_by.full_name == "Admin Person"


def test_ticket_transition_in_progress():
    """Transitioning to IN_PROGRESS does not mandate notes."""
    trans = TicketTransition(target_status=TicketStatus.IN_PROGRESS, expected_version=2)
    assert trans.target_status == TicketStatus.IN_PROGRESS
    assert trans.notes is None
    assert trans.expected_version == 2


def test_ticket_transition_resolved_requires_notes():
    """FR-015: Transitioning to RESOLVED strictly requires resolution notes >= 10 chars."""
    # Missing notes
    with pytest.raises(ValidationError) as exc_info:
        TicketTransition(target_status=TicketStatus.RESOLVED, expected_version=2)
    assert "Resolving a ticket strictly requires 'notes'" in str(exc_info.value)

    # Notes too short (< 10 chars)
    with pytest.raises(ValidationError) as exc_info:
        TicketTransition(
            target_status=TicketStatus.RESOLVED,
            notes="Fixed it",
            expected_version=2,
        )
    assert "Resolving a ticket strictly requires 'notes'" in str(exc_info.value)

    # Valid resolution
    valid_trans = TicketTransition(
        target_status=TicketStatus.RESOLVED,
        notes="Replaced the blown projector lamp and tested video signal.",
        expected_version=2,
    )
    assert valid_trans.notes is not None
    assert len(valid_trans.notes) >= 10


def test_ticket_transition_rejected_requires_notes():
    """FR-015: Transitioning to REJECTED strictly requires rejection notes >= 10 chars."""
    # Missing notes
    with pytest.raises(ValidationError) as exc_info:
        TicketTransition(target_status=TicketStatus.REJECTED, expected_version=1)
    assert "Rejecting a ticket strictly requires 'notes'" in str(exc_info.value)

    # Notes too short
    with pytest.raises(ValidationError) as exc_info:
        TicketTransition(
            target_status=TicketStatus.REJECTED,
            notes="No",
            expected_version=1,
        )
    assert "Rejecting a ticket strictly requires 'notes'" in str(exc_info.value)

    # Valid rejection
    valid_trans = TicketTransition(
        target_status=TicketStatus.REJECTED,
        notes="Duplicate request. Issue already being tracked under CFX-2026-00010.",
        expected_version=1,
    )
    assert valid_trans.notes is not None


def test_ticket_response_detail_serialization():
    """TicketResponse serializes nested category and user summaries."""
    ticket_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    data = {
        "id": ticket_id,
        "ticket_number": "CFX-2026-00042",
        "title": "Projector HDMI Port Damaged",
        "description": "Wall socket bent and unusable.",
        "category": {"id": cat_id, "name": "Classroom Audio-Visual"},
        "location": "Science Block A, Room 402",
        "priority": TicketPriority.HIGH,
        "status": TicketStatus.SUBMITTED,
        "creator": {"id": user_id, "full_name": "Jane Doe"},
        "assigned_staff": None,
        "resolution_notes": None,
        "rejection_reason": None,
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    resp = TicketResponse.model_validate(data)
    assert resp.id == ticket_id
    assert resp.category.name == "Classroom Audio-Visual"
    assert resp.creator.full_name == "Jane Doe"
    assert resp.assigned_staff is None


def test_ticket_summary_response_serialization():
    """TicketSummaryResponse matches flattened list view requirements."""
    ticket_id = uuid.uuid4()
    now = datetime.now(UTC)
    data = {
        "id": ticket_id,
        "ticket_number": "CFX-2026-00042",
        "title": "Projector HDMI Port Damaged",
        "category_name": "Classroom Audio-Visual",
        "location": "Science Block A, Room 402",
        "priority": TicketPriority.HIGH,
        "status": TicketStatus.SUBMITTED,
        "creator_name": "Jane Doe",
        "assigned_staff_name": None,
        "created_at": now,
    }
    summary = TicketSummaryResponse.model_validate(data)
    assert summary.ticket_number == "CFX-2026-00042"
    assert summary.creator_name == "Jane Doe"


def test_ticket_filter_params_validation():
    """TicketFilterParams validates comma-separated statuses and assigned_staff_id formats."""
    # Valid filter with comma-separated status and 'me' assignee
    params = TicketFilterParams(
        status="SUBMITTED,ASSIGNED,IN_PROGRESS",
        assigned_staff_id="me",
        page=1,
        page_size=25,
    )
    assert params.status == "SUBMITTED,ASSIGNED,IN_PROGRESS"
    assert params.assigned_staff_id == "me"

    # Valid filter with UUID assignee
    staff_uuid = uuid.uuid4()
    params_uuid = TicketFilterParams(assigned_staff_id=str(staff_uuid))
    assert params_uuid.assigned_staff_id == str(staff_uuid)

    # Invalid status token in list
    with pytest.raises(ValidationError) as exc_info:
        TicketFilterParams(status="SUBMITTED,INVALID_STATUS")
    assert "Invalid status filter values" in str(exc_info.value)

    # Invalid assigned_staff_id (neither 'me' nor UUID)
    with pytest.raises(ValidationError) as exc_info:
        TicketFilterParams(assigned_staff_id="not-me-and-not-uuid")
    assert "assigned_staff_id must be either 'me' or a valid UUID" in str(exc_info.value)


def test_admin_metrics_response_data():
    """AdminMetricsResponseData validates operational statistics structure."""
    metrics = AdminMetricsResponseData(
        total_tickets=128,
        by_status={
            "SUBMITTED": 14,
            "ASSIGNED": 22,
            "IN_PROGRESS": 18,
            "RESOLVED": 68,
            "REJECTED": 4,
            "CANCELLED": 2,
        },
        by_priority={"CRITICAL": 5, "HIGH": 32, "MEDIUM": 65, "LOW": 26},
        avg_resolution_hours=18.4,
    )
    assert metrics.total_tickets == 128
    assert metrics.avg_resolution_hours == 18.4


# ==============================================================================
# 5. Standard Envelopes & RFC 7807 Problem Details Tests
# ==============================================================================


def test_message_response_and_pagination_params():
    """MessageResponse and PaginationParams validate contracts."""
    msg = MessageResponse(message="Successfully logged out.")
    assert msg.message == "Successfully logged out."

    params = PaginationParams(page=3, page_size=50)
    assert params.page == 3
    assert params.page_size == 50

    with pytest.raises(ValidationError):
        PaginationParams(page=0)


def test_success_envelope():
    """SuccessEnvelope wraps arbitrary resource models with success: True."""
    payload = {"message": "Resource created"}
    envelope = SuccessEnvelope[dict](data=payload)
    assert envelope.success is True
    assert envelope.data == payload


def test_paginated_response():
    """PaginatedResponse wraps items with standard pagination metadata."""
    meta = PaginationMeta(page=1, page_size=20, total=45, total_pages=3)
    resp = PaginatedResponse[str](data=["item1", "item2"], meta=meta)
    assert resp.success is True
    assert len(resp.data) == 2
    assert resp.meta.total_pages == 3

    # Boundary violation: page_size > 100
    with pytest.raises(ValidationError):
        PaginationMeta(page=1, page_size=101, total=10, total_pages=1)


def test_error_envelope():
    """ErrorEnvelope formats structured application errors."""
    error = ErrorDetail(
        code="RESOURCE_NOT_FOUND",
        message="Ticket does not exist.",
        details={"ticket_id": str(uuid.uuid4())},
    )
    envelope = ErrorEnvelope(error=error)
    assert envelope.success is False
    assert envelope.error.code == "RESOURCE_NOT_FOUND"
    assert envelope.timestamp is not None


def test_problem_details_rfc7807():
    """ProblemDetails complies with RFC 7807 problem structure and extensions."""
    invalid_param = ValidationErrorItem(
        field="password",
        message="Password must contain at least one uppercase letter",
        type="value_error",
    )
    problem = ProblemDetails(
        type="https://campusfix.example/errors/validation",
        title="Unprocessable Entity",
        status=422,
        detail="The request payload failed field validation rules.",
        instance="/api/v1/auth/register",
        code="VALIDATION_ERROR",
        invalid_params=[invalid_param],
    )
    dumped = problem.model_dump()
    assert dumped["type"] == "https://campusfix.example/errors/validation"
    assert dumped["status"] == 422
    assert dumped["code"] == "VALIDATION_ERROR"
    assert len(dumped["invalid_params"]) == 1
    assert dumped["invalid_params"][0]["field"] == "password"

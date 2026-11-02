"""API contract and authorization tests for Category REST endpoints (/api/v1/categories)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db
from app.main import app
from app.models.category import Category
from app.models.user import User, UserRole
from app.services.category_service import (
    CategoryNotFoundError,
    DuplicateCategoryError,
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
        full_name="Student User",
        role=UserRole.STUDENT.value,
        is_active=True,
    )


@pytest.fixture
def staff_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="staff@campusfix.local",
        full_name="Staff User",
        role=UserRole.STAFF.value,
        is_active=True,
    )


@pytest.fixture
def admin_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="admin@campusfix.local",
        full_name="Admin User",
        role=UserRole.ADMINISTRATOR.value,
        is_active=True,
    )


@pytest.fixture
async def client(mock_db: AsyncMock):
    app.dependency_overrides[get_db] = lambda: mock_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ==============================================================================
# 1. GET /api/v1/categories Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_list_categories_unauthenticated(client: AsyncClient):
    """Unauthenticated requests are rejected with HTTP 401."""
    response = await client.get("/api/v1/categories")
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_list_categories_authenticated_student(client: AsyncClient, student_user: User):
    """Authenticated student receives list of active categories wrapped in SuccessEnvelope."""
    app.dependency_overrides[get_current_user] = lambda: student_user

    mock_cats = [
        Category(
            id=uuid.uuid4(),
            name="Electrical",
            description="Power, lighting, outlets",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        Category(
            id=uuid.uuid4(),
            name="Plumbing",
            description="Pipes, sinks, drainage",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
    ]

    with patch(
        "app.services.category_service.CategoryService.list_categories", return_value=mock_cats
    ) as mock_list:
        response = await client.get("/api/v1/categories")
        assert response.status_code == 200
        mock_list.assert_awaited_once_with(mock_list.call_args[0][0], include_inactive=False)

    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) == 2
    assert data["data"][0]["name"] == "Electrical"
    assert data["data"][1]["name"] == "Plumbing"


@pytest.mark.asyncio
async def test_list_categories_admin_include_inactive(client: AsyncClient, admin_user: User):
    """Administrator passing include_inactive=true receives both active and inactive categories."""
    app.dependency_overrides[get_current_user] = lambda: admin_user

    with patch(
        "app.services.category_service.CategoryService.list_categories", return_value=[]
    ) as mock_list:
        response = await client.get("/api/v1/categories?include_inactive=true")
        assert response.status_code == 200
        mock_list.assert_awaited_once_with(mock_list.call_args[0][0], include_inactive=True)


# ==============================================================================
# 2. GET /api/v1/categories/{id} Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_get_category_by_id_success(client: AsyncClient, student_user: User):
    """Retrieves an existing category by UUID."""
    app.dependency_overrides[get_current_user] = lambda: student_user

    cat_id = uuid.uuid4()
    mock_cat = Category(
        id=cat_id,
        name="HVAC",
        description="Heating, Ventilation, AC",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with patch(
        "app.services.category_service.CategoryService.get_category_by_id", return_value=mock_cat
    ):
        response = await client.get(f"/api/v1/categories/{cat_id}")
        assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == str(cat_id)
    assert data["data"]["name"] == "HVAC"


@pytest.mark.asyncio
async def test_get_category_by_id_not_found(client: AsyncClient, student_user: User):
    """Non-existent category UUID returns HTTP 404 RESOURCE_NOT_FOUND."""
    app.dependency_overrides[get_current_user] = lambda: student_user

    cat_id = uuid.uuid4()
    with patch(
        "app.services.category_service.CategoryService.get_category_by_id",
        side_effect=CategoryNotFoundError("Category not found"),
    ):
        response = await client.get(f"/api/v1/categories/{cat_id}")
        assert response.status_code == 404

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"


# ==============================================================================
# 3. POST /api/v1/categories Tests (Creation)
# ==============================================================================


@pytest.mark.asyncio
async def test_create_category_by_student_forbidden(client: AsyncClient, student_user: User):
    """Students are rejected from creating categories with HTTP 403 INSUFFICIENT_PERMISSIONS."""
    app.dependency_overrides[get_current_user] = lambda: student_user

    response = await client.post(
        "/api/v1/categories",
        json={"name": "New Cat", "description": "Scope details"},
    )
    assert response.status_code == 403
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_create_category_by_staff_forbidden(client: AsyncClient, staff_user: User):
    """Staff technicians are rejected from creating categories with HTTP 403 INSUFFICIENT_PERMISSIONS."""
    app.dependency_overrides[get_current_user] = lambda: staff_user

    response = await client.post(
        "/api/v1/categories",
        json={"name": "New Cat", "description": "Scope details"},
    )
    assert response.status_code == 403
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_create_category_by_admin_success(client: AsyncClient, admin_user: User):
    """Administrator creates a new category, returning HTTP 201 Created."""
    app.dependency_overrides[get_current_user] = lambda: admin_user

    cat_id = uuid.uuid4()
    mock_cat = Category(
        id=cat_id,
        name="Laboratory Equipment",
        description="Fume hoods, autoclaves, and centrifuge units",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with patch(
        "app.services.category_service.CategoryService.create_category", return_value=mock_cat
    ):
        response = await client.post(
            "/api/v1/categories",
            json={
                "name": "Laboratory Equipment",
                "description": "Fume hoods, autoclaves, and centrifuge units",
                "is_active": True,
            },
        )
        assert response.status_code == 201

    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == str(cat_id)
    assert data["data"]["name"] == "Laboratory Equipment"


@pytest.mark.asyncio
async def test_create_category_duplicate_conflict(client: AsyncClient, admin_user: User):
    """Attempting to create a category with duplicate name returns HTTP 409 CATEGORY_ALREADY_EXISTS."""
    app.dependency_overrides[get_current_user] = lambda: admin_user

    with patch(
        "app.services.category_service.CategoryService.create_category",
        side_effect=DuplicateCategoryError("A category named 'Electrical' already exists."),
    ):
        response = await client.post(
            "/api/v1/categories",
            json={
                "name": "Electrical",
                "description": "Duplicate description here",
            },
        )
        assert response.status_code == 409

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "CATEGORY_ALREADY_EXISTS"


# ==============================================================================
# 4. PATCH /api/v1/categories/{id} Tests (Update)
# ==============================================================================


@pytest.mark.asyncio
async def test_update_category_by_admin_success(client: AsyncClient, admin_user: User):
    """Administrator updates category details, returning HTTP 200 OK."""
    app.dependency_overrides[get_current_user] = lambda: admin_user

    cat_id = uuid.uuid4()
    updated_cat = Category(
        id=cat_id,
        name="Updated Name",
        description="Updated Scope description",
        is_active=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with patch(
        "app.services.category_service.CategoryService.update_category", return_value=updated_cat
    ):
        response = await client.patch(
            f"/api/v1/categories/{cat_id}",
            json={
                "name": "Updated Name",
                "is_active": False,
            },
        )
        assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "Updated Name"
    assert data["data"]["is_active"] is False


@pytest.mark.asyncio
async def test_update_category_not_found(client: AsyncClient, admin_user: User):
    """Updating a non-existent category returns HTTP 404 RESOURCE_NOT_FOUND."""
    app.dependency_overrides[get_current_user] = lambda: admin_user

    cat_id = uuid.uuid4()
    with patch(
        "app.services.category_service.CategoryService.update_category",
        side_effect=CategoryNotFoundError("Category not found"),
    ):
        response = await client.patch(
            f"/api/v1/categories/{cat_id}",
            json={"name": "New Name"},
        )
        assert response.status_code == 404

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_update_category_by_student_forbidden(client: AsyncClient, student_user: User):
    """Students cannot update categories (HTTP 403)."""
    app.dependency_overrides[get_current_user] = lambda: student_user

    cat_id = uuid.uuid4()
    response = await client.patch(
        f"/api/v1/categories/{cat_id}",
        json={"name": "New Name"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

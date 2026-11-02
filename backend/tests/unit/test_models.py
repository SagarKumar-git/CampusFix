"""Unit tests asserting SQLAlchemy model definitions, schema metadata, constraints, and relationships."""

import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text, Uuid
from sqlalchemy.orm import class_mapper

from app.core.database import Base
from app.models import (
    Category,
    RefreshToken,
    Ticket,
    TicketPriority,
    TicketStatus,
    TicketStatusHistory,
    User,
    UserRole,
)


def test_metadata_contains_all_approved_tables():
    """Base.metadata must register exactly the 5 approved tables."""
    expected_tables = {
        "users",
        "categories",
        "tickets",
        "ticket_status_history",
        "refresh_tokens",
    }
    registered_tables = set(Base.metadata.tables.keys())
    assert registered_tables == expected_tables, (
        f"Mismatch in registered tables: {registered_tables ^ expected_tables}"
    )


def test_user_model_columns_and_constraints():
    """Verify users table structure, column types, nullability, defaults, and constraints."""
    table = Base.metadata.tables["users"]

    # Primary key
    assert table.c.id.primary_key is True
    assert isinstance(table.c.id.type, Uuid)

    # Columns and nullability
    assert isinstance(table.c.email.type, String)
    assert table.c.email.type.length == 255
    assert table.c.email.nullable is False

    assert isinstance(table.c.hashed_password.type, String)
    assert table.c.hashed_password.type.length == 255
    assert table.c.hashed_password.nullable is False

    assert isinstance(table.c.full_name.type, String)
    assert table.c.full_name.type.length == 150
    assert table.c.full_name.nullable is False

    assert isinstance(table.c.role.type, String)
    assert table.c.role.type.length == 20
    assert table.c.role.nullable is False

    assert isinstance(table.c.is_active.type, Boolean)
    assert table.c.is_active.nullable is False

    assert isinstance(table.c.created_at.type, DateTime)
    assert table.c.created_at.type.timezone is True
    assert table.c.created_at.nullable is False

    assert isinstance(table.c.updated_at.type, DateTime)
    assert table.c.updated_at.type.timezone is True
    assert table.c.updated_at.nullable is False

    # Check constraints
    check_constraints = [c for c in table.constraints if isinstance(c, CheckConstraint)]
    role_checks = [c for c in check_constraints if c.name == "ck_users_role"]
    assert len(role_checks) == 1
    assert "STUDENT" in str(role_checks[0].sqltext)
    assert "STAFF" in str(role_checks[0].sqltext)
    assert "ADMINISTRATOR" in str(role_checks[0].sqltext)

    # Indexes
    index_dict = {idx.name: idx for idx in table.indexes}
    assert "idx_users_email" in index_dict
    assert index_dict["idx_users_email"].unique is True


def test_category_model_columns():
    """Verify categories table structure, column types, nullability, and unique constraints."""
    table = Base.metadata.tables["categories"]

    assert table.c.id.primary_key is True
    assert isinstance(table.c.name.type, String)
    assert table.c.name.type.length == 100
    assert table.c.name.nullable is False
    assert table.c.name.unique is True

    assert isinstance(table.c.description.type, Text)
    assert table.c.description.nullable is False

    assert isinstance(table.c.is_active.type, Boolean)
    assert table.c.is_active.nullable is False

    assert isinstance(table.c.created_at.type, DateTime)
    assert table.c.created_at.type.timezone is True
    assert isinstance(table.c.updated_at.type, DateTime)
    assert table.c.updated_at.type.timezone is True


def test_ticket_model_columns_constraints_and_foreign_keys():
    """Verify tickets table structure, types, FSM check constraints, versioning, and FKs."""
    table = Base.metadata.tables["tickets"]

    assert table.c.id.primary_key is True
    assert isinstance(table.c.ticket_number.type, String)
    assert table.c.ticket_number.type.length == 30
    assert table.c.ticket_number.nullable is False

    assert isinstance(table.c.title.type, String)
    assert table.c.title.type.length == 120
    assert table.c.title.nullable is False

    assert isinstance(table.c.description.type, Text)
    assert table.c.description.nullable is False

    assert isinstance(table.c.location.type, String)
    assert table.c.location.type.length == 100
    assert table.c.location.nullable is False

    assert isinstance(table.c.priority.type, String)
    assert table.c.priority.type.length == 20
    assert table.c.priority.nullable is False

    assert isinstance(table.c.status.type, String)
    assert table.c.status.type.length == 20
    assert table.c.status.nullable is False

    assert isinstance(table.c.version.type, Integer)
    assert table.c.version.nullable is False

    assert table.c.resolution_notes.nullable is True
    assert table.c.rejection_reason.nullable is True
    assert table.c.assigned_staff_id.nullable is True

    # Foreign Keys & ondelete rules
    fk_targets = {fk.target_fullname: fk.ondelete for fk in table.foreign_keys}
    assert fk_targets["categories.id"] == "RESTRICT"
    assert fk_targets["users.id"] in ("RESTRICT", "SET NULL")

    # Verify both FKs to users.id
    fks_to_users = [fk for fk in table.foreign_keys if fk.column.table.name == "users"]
    assert len(fks_to_users) == 2
    creator_fk = next(fk for fk in fks_to_users if fk.parent.name == "creator_id")
    staff_fk = next(fk for fk in fks_to_users if fk.parent.name == "assigned_staff_id")
    assert creator_fk.ondelete == "RESTRICT"
    assert staff_fk.ondelete == "SET NULL"

    # Check constraints
    check_constraints = {
        c.name: str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)
    }
    assert "ck_tickets_priority" in check_constraints
    assert "ck_tickets_status" in check_constraints
    assert "SUBMITTED" in check_constraints["ck_tickets_status"]
    assert "CANCELLED" in check_constraints["ck_tickets_status"]

    # Indexes
    index_dict = {idx.name: idx for idx in table.indexes}
    assert "idx_tickets_number" in index_dict
    assert index_dict["idx_tickets_number"].unique is True
    assert "idx_tickets_creator_created" in index_dict
    assert "idx_tickets_assigned_status" in index_dict
    assert "idx_tickets_status_category" in index_dict


def test_ticket_status_history_columns_and_foreign_keys():
    """Verify ticket_status_history table columns, FKs, and cascade/restrict rules."""
    table = Base.metadata.tables["ticket_status_history"]

    assert table.c.id.primary_key is True
    assert isinstance(table.c.to_status.type, String)
    assert table.c.to_status.nullable is False
    assert table.c.from_status.nullable is True
    assert table.c.notes.nullable is True

    # FKs
    ticket_fk = next(fk for fk in table.foreign_keys if fk.parent.name == "ticket_id")
    assert ticket_fk.ondelete == "CASCADE"

    changed_by_fk = next(fk for fk in table.foreign_keys if fk.parent.name == "changed_by_user_id")
    assert changed_by_fk.ondelete == "RESTRICT"

    assigned_to_fk = next(
        fk for fk in table.foreign_keys if fk.parent.name == "assigned_to_user_id"
    )
    assert assigned_to_fk.ondelete == "RESTRICT"

    # Indexes
    index_names = {idx.name for idx in table.indexes}
    assert "idx_history_ticket_created" in index_names
    assert "idx_history_assigned_to" in index_names


def test_refresh_token_columns_and_family_tracking():
    """Verify refresh_tokens table columns, token_hash uniqueness, family_id, and indexes."""
    table = Base.metadata.tables["refresh_tokens"]

    assert table.c.id.primary_key is True
    assert isinstance(table.c.family_id.type, Uuid)
    assert table.c.family_id.nullable is False

    assert isinstance(table.c.token_hash.type, String)
    assert table.c.token_hash.type.length == 255
    assert table.c.token_hash.nullable is False

    assert table.c.expires_at.nullable is False
    assert table.c.revoked_at.nullable is True

    user_fk = next(fk for fk in table.foreign_keys if fk.parent.name == "user_id")
    assert user_fk.ondelete == "CASCADE"

    # Indexes
    index_dict = {idx.name: idx for idx in table.indexes}
    assert "idx_refresh_tokens_hash" in index_dict
    assert index_dict["idx_refresh_tokens_hash"].unique is True
    assert "idx_refresh_tokens_user" in index_dict
    assert "idx_refresh_tokens_family" in index_dict


def test_model_relationships_wiring():
    """Assert all ORM relationships are correctly wired and configured."""
    user_mapper = class_mapper(User)
    ticket_mapper = class_mapper(Ticket)
    category_mapper = class_mapper(Category)
    history_mapper = class_mapper(TicketStatusHistory)
    token_mapper = class_mapper(RefreshToken)

    # User relationships
    assert "created_tickets" in user_mapper.relationships
    assert "assigned_tickets" in user_mapper.relationships
    assert "status_history_changes" in user_mapper.relationships
    assert "assigned_history_records" in user_mapper.relationships
    assert "refresh_tokens" in user_mapper.relationships

    # Ticket relationships
    assert "creator" in ticket_mapper.relationships
    assert "assigned_staff" in ticket_mapper.relationships
    assert "category" in ticket_mapper.relationships
    assert "status_history" in ticket_mapper.relationships

    # Category relationships
    assert "tickets" in category_mapper.relationships

    # TicketStatusHistory relationships
    assert "ticket" in history_mapper.relationships
    assert "changed_by_user" in history_mapper.relationships
    assert "assigned_to_user" in history_mapper.relationships

    # RefreshToken relationships
    assert "user" in token_mapper.relationships


def test_model_enum_definitions():
    """Verify that domain enum classes match the approved requirements specification."""
    assert {r.value for r in UserRole} == {"STUDENT", "STAFF", "ADMINISTRATOR"}
    assert {p.value for p in TicketPriority} == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert {s.value for s in TicketStatus} == {
        "SUBMITTED",
        "ASSIGNED",
        "IN_PROGRESS",
        "RESOLVED",
        "REJECTED",
        "CANCELLED",
    }


def test_model_column_python_defaults():
    """Verify that column defaults have the expected Python-level default generators."""
    users_table = Base.metadata.tables["users"]
    tickets_table = Base.metadata.tables["tickets"]
    assert users_table.c.id.default.is_callable is True
    assert users_table.c.id.default.arg.__name__ == "uuid4"
    assert users_table.c.role.default.arg == UserRole.STUDENT.value
    assert users_table.c.is_active.default.arg is True
    assert tickets_table.c.id.default.is_callable is True
    assert tickets_table.c.id.default.arg.__name__ == "uuid4"
    assert tickets_table.c.version.default.arg == 1
    assert tickets_table.c.priority.default.arg == TicketPriority.MEDIUM.value
    assert tickets_table.c.status.default.arg == TicketStatus.SUBMITTED.value


def test_instantiate_model():
    """Verify model instantiation and attribute assignment."""
    user_id = uuid.uuid4()
    test_user = User(
        id=user_id,
        email="test@campusfix.local",
        hashed_password="fake_digest_value",
        full_name="Test User",
        role=UserRole.STUDENT.value,
        is_active=True,
    )
    assert test_user.id == user_id
    assert test_user.role == UserRole.STUDENT.value
    assert test_user.is_active is True

    ticket_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    test_ticket = Ticket(
        id=ticket_id,
        ticket_number="CFX-2026-00001",
        title="Flickering classroom projector",
        description="Room 101 projector light keeps dropping off.",
        category_id=cat_id,
        location="Engineering Block, Room 101",
        creator_id=user_id,
        priority=TicketPriority.MEDIUM.value,
        status=TicketStatus.SUBMITTED.value,
        version=1,
    )
    assert test_ticket.id == ticket_id
    assert test_ticket.priority == TicketPriority.MEDIUM.value
    assert test_ticket.status == TicketStatus.SUBMITTED.value
    assert test_ticket.version == 1

"""create_initial_schema

Revision ID: 0c98aec98ce5
Revises:
Create Date: 2026-10-29 23:54:36.701328

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0c98aec98ce5"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default=sa.text("'STUDENT'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "role IN ('STUDENT', 'STAFF', 'ADMINISTRATOR')",
            name="ck_users_role",
        ),
    )
    op.create_index("idx_users_email", "users", ["email"], unique=True)

    # 2. categories table
    op.create_table(
        "categories",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # 3. tickets table
    op.create_table(
        "tickets",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("ticket_number", sa.String(30), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "category_id",
            sa.Uuid(),
            sa.ForeignKey("categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("location", sa.String(100), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False, server_default=sa.text("'MEDIUM'")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'SUBMITTED'")),
        sa.Column(
            "creator_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "assigned_staff_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_tickets_priority",
        ),
        sa.CheckConstraint(
            "status IN ('SUBMITTED', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED', 'REJECTED', 'CANCELLED')",
            name="ck_tickets_status",
        ),
    )
    op.create_index("idx_tickets_number", "tickets", ["ticket_number"], unique=True)
    op.create_index(
        "idx_tickets_creator_created",
        "tickets",
        ["creator_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_tickets_assigned_status",
        "tickets",
        ["assigned_staff_id", "status"],
    )
    op.create_index(
        "idx_tickets_status_category",
        "tickets",
        ["status", "category_id"],
    )

    # 4. ticket_status_history table
    op.create_table(
        "ticket_status_history",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "ticket_id",
            sa.Uuid(),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column(
            "changed_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "assigned_to_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_history_ticket_created",
        "ticket_status_history",
        ["ticket_id", "created_at"],
    )
    op.create_index(
        "idx_history_assigned_to",
        "ticket_status_history",
        ["assigned_to_user_id"],
    )

    # 5. refresh_tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_refresh_tokens_hash", "refresh_tokens", ["token_hash"], unique=True)
    op.create_index("idx_refresh_tokens_user", "refresh_tokens", ["user_id"])
    op.create_index("idx_refresh_tokens_family", "refresh_tokens", ["family_id"])


def downgrade() -> None:
    # 5. refresh_tokens
    op.drop_index("idx_refresh_tokens_family", table_name="refresh_tokens")
    op.drop_index("idx_refresh_tokens_user", table_name="refresh_tokens")
    op.drop_index("idx_refresh_tokens_hash", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    # 4. ticket_status_history
    op.drop_index("idx_history_assigned_to", table_name="ticket_status_history")
    op.drop_index("idx_history_ticket_created", table_name="ticket_status_history")
    op.drop_table("ticket_status_history")

    # 3. tickets
    op.drop_index("idx_tickets_status_category", table_name="tickets")
    op.drop_index("idx_tickets_assigned_status", table_name="tickets")
    op.drop_index("idx_tickets_creator_created", table_name="tickets")
    op.drop_index("idx_tickets_number", table_name="tickets")
    op.drop_table("tickets")

    # 2. categories
    op.drop_table("categories")

    # 1. users
    op.drop_index("idx_users_email", table_name="users")
    op.drop_table("users")

"""Create identity and audit tables.

Revision ID: 20260816_0002
Revises: 20260813_0001
Create Date: 2026-08-16 00:00:00 UTC
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260816_0002"
down_revision: Union[str, None] = "20260813_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("failed_login_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(length=50), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("source_ip", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=True),
        sa.Column("resource_id", sa.String(length=80), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name="fk_audit_events_actor_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"], unique=False)
    op.create_index("ix_audit_events_actor_username", "audit_events", ["actor_username"], unique=False)
    op.create_index("ix_audit_events_correlation_id", "audit_events", ["correlation_id"], unique=False)
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"], unique=False)
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"], unique=False)
    op.create_index("ix_audit_events_outcome", "audit_events", ["outcome"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_events_outcome", table_name="audit_events")
    op.drop_index("ix_audit_events_occurred_at", table_name="audit_events")
    op.drop_index("ix_audit_events_event_type", table_name="audit_events")
    op.drop_index("ix_audit_events_correlation_id", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_username", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

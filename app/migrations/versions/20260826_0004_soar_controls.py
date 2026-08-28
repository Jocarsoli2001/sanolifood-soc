"""Create reversible SOAR controls for the business application.

Revision ID: 20260826_0004
Revises: 20260817_0003
Create Date: 2026-08-26 00:00:00 UTC
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260826_0004"
down_revision: Union[str, None] = "20260817_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "soar_controls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action_id", sa.String(length=36), nullable=False),
        sa.Column("incident_id", sa.String(length=36), nullable=False),
        sa.Column("control_type", sa.String(length=40), nullable=False),
        sa.Column("target", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.CheckConstraint(
            "control_type in ('app_ip_block','app_account_lock','quality_guard')",
            name="ck_soar_controls_type",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_soar_controls"),
        sa.UniqueConstraint("action_id", name="uq_soar_controls_action_id"),
    )
    op.create_index("ix_soar_controls_active", "soar_controls", ["active"], unique=False)
    op.create_index("ix_soar_controls_control_type", "soar_controls", ["control_type"], unique=False)
    op.create_index("ix_soar_controls_expires_at", "soar_controls", ["expires_at"], unique=False)
    op.create_index("ix_soar_controls_incident_id", "soar_controls", ["incident_id"], unique=False)
    op.create_index("ix_soar_controls_target", "soar_controls", ["target"], unique=False)


def downgrade() -> None:
    op.drop_table("soar_controls")

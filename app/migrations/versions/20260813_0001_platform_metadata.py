"""Create platform metadata table.

Revision ID: 20260813_0001
Revises:
Create Date: 2026-08-13 00:00:00 UTC
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260813_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_metadata",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_platform_metadata"),
    )
    op.bulk_insert(
        sa.table(
            "platform_metadata",
            sa.column("key", sa.String),
            sa.column("value", sa.String),
        ),
        [
            {"key": "schema_version", "value": "20260813_0001"},
            {"key": "organization", "value": "SanoliFood SA"},
        ],
    )


def downgrade() -> None:
    op.drop_table("platform_metadata")


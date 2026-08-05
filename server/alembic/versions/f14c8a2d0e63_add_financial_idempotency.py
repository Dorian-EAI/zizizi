"""add durable financial request idempotency

Revision ID: f14c8a2d0e63
Revises: e02b4d79f321
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f14c8a2d0e63"
down_revision: Union[str, None] = "e02b4d79f321"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "idempotency_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_type", sa.String(length=16), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("resource_type", sa.String(length=32), nullable=True),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_type",
            "owner_id",
            "idempotency_key",
            name="uq_idempotency_owner_key",
        ),
    )
    with op.batch_alter_table("idempotency_requests", schema=None) as batch_op:
        batch_op.create_index(
            "ix_idempotency_operation_created",
            ["operation", "created_at"],
            unique=False,
        )
        batch_op.create_index(
            "ix_idempotency_resource",
            ["resource_type", "resource_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("idempotency_requests", schema=None) as batch_op:
        batch_op.drop_index("ix_idempotency_resource")
        batch_op.drop_index("ix_idempotency_operation_created")
    op.drop_table("idempotency_requests")

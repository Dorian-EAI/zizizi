"""add order cancellation requests

Revision ID: a1c9e4f7b2d3
Revises: f14c8a2d0e63
Create Date: 2026-11-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1c9e4f7b2d3"
down_revision: Union[str, None] = "f14c8a2d0e63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "order_cancellation_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_no", sa.String(length=32), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=256), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("fee_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("reviewed_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_admin_id"], ["admins.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_order_cancellation_requests_request_no",
        "order_cancellation_requests",
        ["request_no"],
        unique=True,
    )
    op.create_index(
        "ix_order_cancellation_requests_order_id",
        "order_cancellation_requests",
        ["order_id"],
    )
    op.create_index(
        "ix_order_cancellation_requests_user_id",
        "order_cancellation_requests",
        ["user_id"],
    )
    op.create_index(
        "ix_order_cancellation_requests_worker_id",
        "order_cancellation_requests",
        ["worker_id"],
    )
    op.create_index(
        "ix_order_cancellation_requests_status",
        "order_cancellation_requests",
        ["status"],
    )
    op.create_index(
        "ix_order_cancellation_requests_created_at",
        "order_cancellation_requests",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_order_cancellation_requests_created_at",
        table_name="order_cancellation_requests",
    )
    op.drop_index(
        "ix_order_cancellation_requests_status",
        table_name="order_cancellation_requests",
    )
    op.drop_index(
        "ix_order_cancellation_requests_worker_id",
        table_name="order_cancellation_requests",
    )
    op.drop_index(
        "ix_order_cancellation_requests_user_id",
        table_name="order_cancellation_requests",
    )
    op.drop_index(
        "ix_order_cancellation_requests_order_id",
        table_name="order_cancellation_requests",
    )
    op.drop_index(
        "ix_order_cancellation_requests_request_no",
        table_name="order_cancellation_requests",
    )
    op.drop_table("order_cancellation_requests")

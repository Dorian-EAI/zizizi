"""add worker fund entries

Revision ID: c5e8b1f70a92
Revises: a1c9e4f7b2d3
Create Date: 2026-11-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5e8b1f70a92"
down_revision: Union[str, None] = "a1c9e4f7b2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "worker_fund_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entry_no", sa.String(length=32), nullable=False),
        sa.Column("worker_id", sa.Integer(), nullable=False),
        sa.Column("order_no", sa.String(length=32), nullable=True),
        sa.Column("bucket", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("balance_after", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("reference_type", sa.String(length=32), nullable=False),
        sa.Column("reference_id", sa.String(length=64), nullable=False),
        sa.Column("source_entry_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reference_type",
            "reference_id",
            "bucket",
            "direction",
            name="uq_worker_fund_entry_reference",
        ),
    )
    op.create_index(
        "ix_worker_fund_entries_entry_no",
        "worker_fund_entries",
        ["entry_no"],
        unique=True,
    )
    op.create_index(
        "ix_worker_fund_entries_worker_id",
        "worker_fund_entries",
        ["worker_id"],
    )
    op.create_index(
        "ix_worker_fund_entries_order_no",
        "worker_fund_entries",
        ["order_no"],
    )
    op.create_index(
        "ix_worker_fund_entries_source_entry_id",
        "worker_fund_entries",
        ["source_entry_id"],
    )
    op.create_index(
        "ix_worker_fund_entries_created_at",
        "worker_fund_entries",
        ["created_at"],
    )
    op.create_index(
        "ix_worker_fund_entries_worker_bucket",
        "worker_fund_entries",
        ["worker_id", "bucket"],
    )


def downgrade() -> None:
    op.drop_index("ix_worker_fund_entries_worker_bucket", table_name="worker_fund_entries")
    op.drop_index("ix_worker_fund_entries_created_at", table_name="worker_fund_entries")
    op.drop_index("ix_worker_fund_entries_source_entry_id", table_name="worker_fund_entries")
    op.drop_index("ix_worker_fund_entries_order_no", table_name="worker_fund_entries")
    op.drop_index("ix_worker_fund_entries_worker_id", table_name="worker_fund_entries")
    op.drop_index("ix_worker_fund_entries_entry_no", table_name="worker_fund_entries")
    op.drop_table("worker_fund_entries")

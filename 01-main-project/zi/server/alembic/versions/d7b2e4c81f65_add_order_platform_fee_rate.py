"""add order platform fee rate snapshot

Revision ID: d7b2e4c81f65
Revises: c5e8b1f70a92
Create Date: 2026-11-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7b2e4c81f65"
down_revision: Union[str, None] = "c5e8b1f70a92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "platform_fee_rate",
            sa.Numeric(precision=5, scale=4),
            nullable=True,
            comment="平台服务费率快照（0-1）",
        ),
    )


def downgrade() -> None:
    op.drop_column("orders", "platform_fee_rate")

"""add worker certification data

Revision ID: b842d1a7c903
Revises: 59fdc7715893
Create Date: 2026-08-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b842d1a7c903"
down_revision: Union[str, None] = "59fdc7715893"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("workers", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "certification_data",
                sa.JSON(),
                nullable=True,
                comment="认证申请非敏感快照（身份证号仅保存脱敏值）",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("workers", schema=None) as batch_op:
        batch_op.drop_column("certification_data")

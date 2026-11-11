"""add admin password lifecycle

Revision ID: d91e7c42a610
Revises: c73a1f4e9b20
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d91e7c42a610"
down_revision: Union[str, None] = "c73a1f4e9b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("admins", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "must_change_password",
                sa.Boolean(),
                server_default=sa.true(),
                nullable=False,
                comment="首次登录或重置后必须修改密码",
            )
        )
    with op.batch_alter_table("admins", schema=None) as batch_op:
        batch_op.alter_column(
            "must_change_password",
            existing_type=sa.Boolean(),
            existing_nullable=False,
            server_default=None,
        )


def downgrade() -> None:
    with op.batch_alter_table("admins", schema=None) as batch_op:
        batch_op.drop_column("must_change_password")

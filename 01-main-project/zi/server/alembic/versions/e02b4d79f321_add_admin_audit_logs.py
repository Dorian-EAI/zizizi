"""add persistent admin audit logs

Revision ID: e02b4d79f321
Revises: d91e7c42a610
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e02b4d79f321"
down_revision: Union[str, None] = "d91e7c42a610"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_admin_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["actor_admin_id"], ["admins.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("admin_audit_logs", schema=None) as batch_op:
        batch_op.create_index("ix_admin_audit_logs_action", ["action"], unique=False)
        batch_op.create_index("ix_admin_audit_logs_actor_admin_id", ["actor_admin_id"], unique=False)
        batch_op.create_index("ix_admin_audit_logs_created_at", ["created_at"], unique=False)
        batch_op.create_index("ix_admin_audit_target", ["target_type", "target_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("admin_audit_logs", schema=None) as batch_op:
        batch_op.drop_index("ix_admin_audit_target")
        batch_op.drop_index("ix_admin_audit_logs_created_at")
        batch_op.drop_index("ix_admin_audit_logs_actor_admin_id")
        batch_op.drop_index("ix_admin_audit_logs_action")
    op.drop_table("admin_audit_logs")

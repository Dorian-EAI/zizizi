"""add agent sessions

Revision ID: d7a4c9e21b60
Revises: d7b2e4c81f65
Create Date: 2026-11-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7a4c9e21b60"
down_revision: Union[str, None] = "d7b2e4c81f65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_no", sa.String(length=48), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("state_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_sessions_session_no",
        "agent_sessions",
        ["session_no"],
        unique=True,
    )
    op.create_index(
        "ix_agent_sessions_user_id",
        "agent_sessions",
        ["user_id"],
    )
    op.create_index(
        "ix_agent_sessions_updated_at",
        "agent_sessions",
        ["updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_sessions_updated_at", table_name="agent_sessions")
    op.drop_index("ix_agent_sessions_user_id", table_name="agent_sessions")
    op.drop_index("ix_agent_sessions_session_no", table_name="agent_sessions")
    op.drop_table("agent_sessions")

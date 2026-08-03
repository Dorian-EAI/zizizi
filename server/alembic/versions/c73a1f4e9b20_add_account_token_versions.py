"""add account token versions

Revision ID: c73a1f4e9b20
Revises: b842d1a7c903
Create Date: 2026-08-03

All existing sessions are intentionally invalidated by starting the persisted
version at 1; legacy JWTs have no ``ver`` claim and therefore resolve to 0.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c73a1f4e9b20"
down_revision: Union[str, None] = "b842d1a7c903"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table_name in ("users", "workers", "admins"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "token_version",
                    sa.Integer(),
                    server_default=sa.text("1"),
                    nullable=False,
                    comment="会话版本，递增后旧 JWT 全部失效",
                )
            )

        # The temporary server default backfills existing rows. Remove it in a
        # second batch so the migrated schema continues to match the models,
        # where new account versions are initialized by SQLAlchemy.
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.alter_column(
                "token_version",
                existing_type=sa.Integer(),
                existing_nullable=False,
                server_default=None,
            )


def downgrade() -> None:
    for table_name in ("admins", "workers", "users"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_column("token_version")

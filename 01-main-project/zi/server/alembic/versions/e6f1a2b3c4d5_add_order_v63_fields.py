"""add v6.3 order pricing and acceptance fields

Revision ID: e6f1a2b3c4d5
Revises: d7a4c9e21b60
Create Date: 2026-11-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6f1a2b3c4d5"
down_revision: Union[str, None] = "d7a4c9e21b60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "pricing_mode",
            sa.String(length=16),
            nullable=False,
            server_default="bidding",
            comment="定价模式 fixed_price/bidding/self_priced",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "acceptance_state",
            sa.String(length=16),
            nullable=False,
            server_default="not_required",
            comment="验收状态 not_required/pending/accepted/auto_accepted/disputed",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "empty_run_fee_state",
            sa.String(length=16),
            nullable=False,
            server_default="none",
            comment="空跑费状态 none/pending/paid/waived/disputed",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "empty_run_fee_amount",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default="0",
            comment="空跑费金额（元，定点小数）",
        ),
    )
    op.add_column(
        "orders",
        sa.Column("acceptance_deadline", sa.DateTime(), nullable=True, comment="验收截止时间"),
    )
    op.add_column(
        "orders",
        sa.Column(
            "risk_confirmation_version",
            sa.String(length=64),
            nullable=True,
            comment="风险确认书版本",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "dispatch_acceleration_fee",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default="0",
            comment="加速接单费（元，定点小数）",
        ),
    )
    op.create_index("ix_orders_pricing_mode", "orders", ["pricing_mode"])

    op.add_column(
        "service_types",
        sa.Column(
            "pricing_modes",
            sa.Text(),
            nullable=True,
            comment="允许的定价模式 JSON 数组",
        ),
    )
    op.add_column(
        "service_types",
        sa.Column(
            "pricing_schema",
            sa.Text(),
            nullable=True,
            comment="品类化下单字段/加价项 JSON",
        ),
    )
    op.add_column(
        "service_types",
        sa.Column("service_boundary", sa.Text(), nullable=True, comment="服务边界 JSON"),
    )
    op.add_column(
        "service_types",
        sa.Column(
            "risk_confirmation",
            sa.Text(),
            nullable=True,
            comment="风险确认书 JSON",
        ),
    )
    op.add_column(
        "service_types",
        sa.Column(
            "warranty_days",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="默认质保天数",
        ),
    )


def downgrade() -> None:
    op.drop_column("service_types", "warranty_days")
    op.drop_column("service_types", "risk_confirmation")
    op.drop_column("service_types", "service_boundary")
    op.drop_column("service_types", "pricing_schema")
    op.drop_column("service_types", "pricing_modes")

    op.drop_index("ix_orders_pricing_mode", table_name="orders")
    op.drop_column("orders", "dispatch_acceleration_fee")
    op.drop_column("orders", "risk_confirmation_version")
    op.drop_column("orders", "acceptance_deadline")
    op.drop_column("orders", "empty_run_fee_amount")
    op.drop_column("orders", "empty_run_fee_state")
    op.drop_column("orders", "acceptance_state")
    op.drop_column("orders", "pricing_mode")

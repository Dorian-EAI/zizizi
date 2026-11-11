"""师傅资金桶不可变分录账本

每条分录只允许追加，不允许修改或删除金额；同一业务动作通过
(reference_type, reference_id, bucket, direction) 唯一约束保证幂等。
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, Numeric, String, UniqueConstraint

from app.database import Base

# 师傅资金桶：待结算 / 可提现 / 冻结 / 提现中 / 已提现 / 冲正
FUND_BUCKETS = (
    "pending_settlement",
    "available",
    "frozen",
    "withdrawing",
    "withdrawn",
    "reversed",
)


class WorkerFundEntry(Base):
    """师傅资金桶分录"""

    __tablename__ = "worker_fund_entries"
    __table_args__ = (
        UniqueConstraint(
            "reference_type",
            "reference_id",
            "bucket",
            "direction",
            name="uq_worker_fund_entry_reference",
        ),
        Index("ix_worker_fund_entries_worker_bucket", "worker_id", "bucket"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_no = Column(String(32), unique=True, index=True, nullable=False, comment="分录编号")
    worker_id = Column(Integer, index=True, nullable=False, comment="师傅 ID")
    order_no = Column(String(32), index=True, nullable=True, comment="关联业务订单号")

    bucket = Column(
        String(32),
        nullable=False,
        comment="pending_settlement/available/frozen/withdrawing/withdrawn/reversed",
    )
    direction = Column(String(8), nullable=False, comment="credit 增加 / debit 减少")
    amount = Column(Numeric(12, 2), nullable=False, comment="分录金额（正数，元）")
    balance_after = Column(Numeric(12, 2), nullable=True, comment="该桶分录后余额（元）")

    reference_type = Column(String(32), nullable=False, comment="业务类型")
    reference_id = Column(String(64), nullable=False, comment="业务主键")
    source_entry_id = Column(
        Integer,
        index=True,
        nullable=True,
        comment="关联的待结算来源分录 ID",
    )
    description = Column(String(255), nullable=True, comment="分录说明")

    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)

"""师傅保证金体系"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric
from app.database import Base


class WorkerDeposit(Base):
    """师傅保证金账户"""
    __tablename__ = "worker_deposits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False, unique=True)

    deposit_level = Column(String(20), default="trainee", comment="trainee/formal/gold")
    total_deposited = Column(Integer, default=0, comment="累计缴纳，单位分")
    balance = Column(Integer, default=0, comment="当前余额，单位分")
    frozen_amount = Column(Integer, default=0, comment="冻结金额，单位分")

    platform_cut_rate = Column(Numeric(4, 3), default=0.150, comment="平台抽成比例")
    daily_order_limit = Column(Integer, default=3, comment="每日抢单上限")
    status = Column(String(20), default="normal", comment="normal/frozen/refunding")
    refund_requested_at = Column(DateTime, nullable=True, comment="保证金退款申请时间")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DepositTransaction(Base):
    """保证金流水"""
    __tablename__ = "deposit_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False, index=True)

    type = Column(String(20), nullable=False, comment="deposit/deduct/refund/freeze/unfreeze")
    amount = Column(Integer, nullable=False, comment="金额，单位分")
    balance_after = Column(Integer, nullable=False, comment="变动后余额")

    reason = Column(String(200), nullable=False, comment="变动原因")
    related_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    related_claim_id = Column(Integer, ForeignKey("insurance_claims.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

"""安心保 — 服务保险与理赔"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from app.database import Base


class InsurancePolicy(Base):
    """安心保保单"""
    __tablename__ = "insurance_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=True)

    level = Column(String(20), nullable=False, comment="基础版/标准版/尊享版")
    premium = Column(Integer, nullable=False, comment="保费，单位分")
    coverage = Column(Integer, nullable=False, comment="赔付额度，单位分")

    status = Column(String(20), default="active", comment="active/claimed/expired")
    claimed_amount = Column(Integer, default=0, comment="已赔付金额，单位分")
    created_at = Column(DateTime, default=datetime.utcnow)
    expired_at = Column(DateTime, nullable=False, comment="保单过期时间")


class InsuranceClaim(Base):
    """理赔申请"""
    __tablename__ = "insurance_claims"

    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_id = Column(Integer, ForeignKey("insurance_policies.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=True)

    reason = Column(Text, nullable=False, comment="理赔原因")
    evidence_images = Column(JSON, default=list, comment="损失照片URL列表")
    claim_amount = Column(Integer, nullable=False, comment="申请赔付金额，单位分")

    status = Column(String(20), default="pending", comment="pending/approved/rejected")
    audit_remark = Column(Text, comment="审核备注")
    audited_by = Column(Integer, ForeignKey("admins.id"), nullable=True)
    audited_at = Column(DateTime, nullable=True)
    settled_amount = Column(Integer, default=0, comment="实际赔付金额")

    created_at = Column(DateTime, default=datetime.utcnow)
    settled_at = Column(DateTime, nullable=True)

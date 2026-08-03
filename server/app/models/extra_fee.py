"""现场补差价"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from app.database import Base


class OrderExtraFee(Base):
    """订单补差价记录"""
    __tablename__ = "order_extra_fees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    items = Column(JSON, nullable=False, default=list, comment="[{name, price, unit}]")
    total_amount = Column(Integer, nullable=False, comment="补差价总额，单位分")
    reason = Column(Text, nullable=False, comment="补差价原因")
    photo_urls = Column(JSON, default=list, comment="现场照片")

    status = Column(String(20), default="pending", comment="pending/approved/rejected")
    user_remark = Column(Text, comment="用户备注/拒绝原因")
    retry_count = Column(Integer, default=0, comment="申请次数")

    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

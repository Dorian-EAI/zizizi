"""质检回访"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey
from app.database import Base


class QualityInspection(Base):
    """质检回访记录"""
    __tablename__ = "quality_inspections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)

    inspect_type = Column(String(20), default="auto", comment="auto/manual")
    rating = Column(Integer, nullable=True, comment="回访评分1-5")
    satisfaction = Column(String(20), nullable=True, comment="satisfied/neutral/dissatisfied")

    feedback = Column(Text, comment="用户反馈")
    is_complaint = Column(Boolean, default=False, comment="是否生成投诉")
    complaint_ticket_id = Column(Integer, nullable=True)

    status = Column(String(20), default="pending", comment="pending/done/need_follow")
    inspector_id = Column(Integer, ForeignKey("admins.id"), nullable=True)
    inspected_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    send_at = Column(DateTime, nullable=True, comment="发送回访时间")

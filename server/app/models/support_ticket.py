"""客服工单与仲裁"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from app.database import Base


class SupportTicket(Base):
    """客服工单"""
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_no = Column(String(32), unique=True, nullable=False)

    ticket_type = Column(String(30), nullable=False, comment="complaint/refund/claim/appeal")
    priority = Column(String(10), default="normal", comment="low/normal/high/urgent")
    status = Column(String(20), default="open", comment="open/processing/resolved/closed")

    creator_type = Column(String(20), nullable=False, comment="user/worker")
    creator_id = Column(Integer, nullable=False)
    creator_name = Column(String(50), nullable=False)
    creator_phone = Column(String(20), nullable=True)

    related_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    evidence_urls = Column(JSON, default=list)

    resolution = Column(Text, comment="处理方案")
    refund_amount = Column(Integer, default=0, comment="退款金额")
    deduct_deposit = Column(Integer, default=0, comment="扣除保证金")

    assigned_to = Column(Integer, ForeignKey("admins.id"), nullable=True)
    resolved_by = Column(Integer, ForeignKey("admins.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TicketReply(Base):
    """工单回复"""
    __tablename__ = "ticket_replies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("support_tickets.id"), nullable=False, index=True)

    reply_type = Column(String(20), nullable=False, comment="user/worker/admin/system")
    replier_id = Column(Integer, nullable=False)
    replier_name = Column(String(50), nullable=False)

    content = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False, comment="是否内部备注")

    created_at = Column(DateTime, default=datetime.utcnow)

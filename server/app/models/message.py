"""消息推送数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Index
from app.database import Base


class Message(Base):
    """站内消息表"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_type = Column(String(16), nullable=False, index=True, comment="消息接收方类型: user/worker/admin")
    owner_id = Column(Integer, nullable=False, index=True, comment="接收方 ID")
    type = Column(String(16), nullable=False, comment="消息类型: order/system/activity")
    title = Column(String(128), nullable=False, comment="消息标题")
    content = Column(String(1024), nullable=False, comment="消息内容")
    payload = Column(Text, nullable=True, comment="扩展字段 JSON，如 {order_id, coupon_id, amount}")
    is_read = Column(Boolean, default=False, comment="是否已读")
    created_at = Column(DateTime, default=datetime.utcnow, index=True, comment="创建时间")
    read_at = Column(DateTime, nullable=True, comment="阅读时间")

    __table_args__ = (
        Index("ix_owner_type_owner_id_is_read", "owner_type", "owner_id", "is_read"),
    )

"""通知设置等系统设置数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, UniqueConstraint
from app.database import Base


class NotificationSetting(Base):
    """消息通知设置表（支持 user 与 worker）"""
    __tablename__ = "notification_settings"
    __table_args__ = (
        UniqueConstraint("owner_type", "owner_id", name="uniq_owner_type_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_type = Column(String(16), nullable=False, comment="所属主体类型: user / worker")
    owner_id = Column(Integer, nullable=False, comment="所属主体 ID (user_id 或 worker_id)")

    push_order = Column(Boolean, default=True, comment="订单相关通知")
    push_system = Column(Boolean, default=True, comment="系统通知")
    push_activity = Column(Boolean, default=True, comment="活动营销通知")
    push_sms = Column(Boolean, default=False, comment="短信通知")

    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

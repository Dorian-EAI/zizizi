"""积分系统数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index
from app.database import Base


class PointLog(Base):
    """积分变动流水表"""
    __tablename__ = "point_logs"
    __table_args__ = (
        Index("idx_user_created", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, nullable=False, comment="用户 ID")
    change = Column(Integer, nullable=False, comment="积分变动：正数加/负数减")
    balance_after = Column(Integer, nullable=False, comment="变动后积分余额")
    reason = Column(String(64), nullable=False, comment="变动来源/原因")
    order_no = Column(String(32), nullable=True, comment="关联订单号")
    created_at = Column(DateTime, default=datetime.utcnow, index=True, comment="创建时间")


class PointRule(Base):
    """积分规则配置表"""
    __tablename__ = "point_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(32), unique=True, nullable=False, comment="规则 key：daily_signin / review_order / invite_user 等")
    name = Column(String(32), nullable=False, comment="规则名称")
    point_value = Column(Integer, nullable=False, comment="单次奖励/扣除积分数")
    daily_limit = Column(Integer, default=0, comment="每日上限次数，0 表示无限制")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

"""优惠券数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, Index
from app.database import Base


class CouponTemplate(Base):
    """优惠券模板"""
    __tablename__ = "coupon_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, comment="券名")
    type = Column(String(16), nullable=False, default="fixed", comment="fixed(满减)/percent(折扣)/free(免单)")
    value = Column(Numeric(12, 4), nullable=False, comment="减免金额或折扣比率(0-1)")
    min_spend = Column(Numeric(12, 2), default=0, comment="最低消费（元）")
    service_type = Column(String(32), nullable=True, comment="限定服务类型key，空=通用")
    total_quota = Column(Integer, default=1000, comment="总量(-1=不限)")
    per_user_limit = Column(Integer, default=1, comment="每人限领")
    valid_start = Column(DateTime, nullable=True)
    valid_end = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Coupon(Base):
    """用户优惠券实例"""
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    code = Column(String(32), unique=True, comment="券码")
    status = Column(String(16), nullable=False, default="available", comment="available/used/expired")
    used_order_no = Column(String(32), nullable=True, index=True)
    used_at = Column(DateTime, nullable=True)
    expire_at = Column(DateTime, nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow)

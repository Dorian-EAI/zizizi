"""家庭年卡 / 服务套餐"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Numeric
from app.database import Base


class AnnualCardTemplate(Base):
    """年卡模板"""
    __tablename__ = "annual_card_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, comment="年卡名称")
    price = Column(Integer, nullable=False, comment="售价，单位分")
    total_value = Column(Integer, nullable=False, comment="总价值，单位分")
    service_count = Column(Integer, nullable=False, comment="可用次数")
    urgent_discount = Column(Numeric(3, 2), default=1.00, comment="加急折扣")
    description = Column(Text, comment="权益说明")
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserAnnualCard(Base):
    """用户持有的年卡实例"""
    __tablename__ = "user_annual_cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(Integer, ForeignKey("annual_card_templates.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    order_no = Column(String(32), unique=True, nullable=False, comment="购买订单号")

    total_count = Column(Integer, nullable=False, comment="总次数")
    used_count = Column(Integer, default=0, comment="已使用次数")
    status = Column(String(20), default="active", comment="active/used/expired/refunded")

    valid_start = Column(DateTime, nullable=False)
    valid_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

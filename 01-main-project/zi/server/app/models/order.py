"""订单与竞价数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Numeric, Text, ForeignKey, JSON
from app.database import Base


class Order(Base):
    """订单表"""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_no = Column(String(32), unique=True, index=True, nullable=False, comment="订单编号")

    # 关联
    user_id = Column(Integer, index=True, nullable=False, comment="发布用户 ID")
    worker_id = Column(Integer, nullable=True, comment="接单师傅 ID（选中后填入）")

    # 服务信息
    service_type = Column(String(32), nullable=False, comment="服务类型 key")
    service_name = Column(String(32), nullable=False, comment="服务类型名称")
    description = Column(Text, nullable=True, comment="问题描述")
    images = Column(Text, nullable=True, comment="问题图片 JSON 数组")

    # 地址与时间
    address = Column(String(512), nullable=True, comment="服务地址（JSON）")
    appoint_time = Column(DateTime, nullable=True, comment="预约时间")

    # 价格
    budget = Column(Numeric(12, 2), default=0, comment="用户预算（元，定点小数）")
    final_price = Column(Numeric(12, 2), nullable=True, comment="最终成交价（元，定点小数）")
    urgent = Column(Boolean, default=False, comment="是否加急")
    urgent_amount = Column(Numeric(12, 2), default=0, comment="加急费用（元，定点小数）")

    # 状态: pending=待接单/竞价中, accepted=已接单, departing=师傅出发, arrived=已到达, serving=服务中, completed=已完成, paid=已支付, cancelled=已取消, reviewed=已评价
    status = Column(String(16), default="pending", nullable=False, index=True)

    # CAS 乐观锁版本号
    version = Column(Integer, default=0, nullable=False)

    # 服务阶段时间线
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    accepted_at = Column(DateTime, nullable=True, comment="接单时间")
    departed_at = Column(DateTime, nullable=True, comment="师傅出发时间")
    arrived_at = Column(DateTime, nullable=True, comment="师傅到达时间")
    started_at = Column(DateTime, nullable=True, comment="开始服务时间")
    completed_at = Column(DateTime, nullable=True, comment="完成服务时间")
    paid_at = Column(DateTime, nullable=True, comment="支付时间")
    cancelled_at = Column(DateTime, nullable=True, comment="取消时间")

    # 评价
    rating = Column(Integer, nullable=True, comment="评分 1-5")
    review_tags = Column(Text, nullable=True, comment="评价标签 JSON")
    review_content = Column(Text, nullable=True, comment="评价内容")
    review_images = Column(Text, nullable=True, comment="评价图片 JSON")
    is_anonymous = Column(Boolean, default=False, comment="匿名评价")
    reviewed_at = Column(DateTime, nullable=True, comment="评价时间")


class Bidding(Base):
    """师傅竞价/抢单记录表"""
    __tablename__ = "biddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, index=True, nullable=False, comment="订单 ID")
    worker_id = Column(Integer, index=True, nullable=False, comment="师傅 ID")
    price = Column(Numeric(12, 2), nullable=False, comment="报价金额（元，定点小数）")
    message = Column(String(256), nullable=True, comment="给用户的留言")
    eta = Column(String(64), nullable=True, comment="预计到达时间")

    is_selected = Column(Boolean, default=False, comment="是否被用户选中")

    created_at = Column(DateTime, default=datetime.utcnow)

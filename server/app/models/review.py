"""评论/评价独立数据模型

从 Order 表解耦评价数据，支持：
- 评价审核（运营后台审核后展示）
- 评价回复（师傅可回复）
- 评价点赞（其他用户可点赞）
- 评价标签聚合与精炼
- 师傅/服务维度聚合展示
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey, Index
from app.database import Base


class Review(Base):
    """用户评价表 — 独立存储，从订单评价自动同步"""
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 关联
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True, comment="订单 ID")
    user_id = Column(Integer, nullable=False, index=True, comment="评价用户 ID")
    worker_id = Column(Integer, nullable=True, index=True, comment="被评价师傅 ID")
    service_type = Column(String(32), nullable=True, index=True, comment="服务类型 key")

    # 评分
    rating = Column(Integer, nullable=False, comment="评分 1-5")
    review_tags = Column(Text, nullable=True, comment="评价标签 JSON ['技术好','准时','收费合理']")
    review_content = Column(Text, nullable=True, comment="评价文字内容")
    review_images = Column(Text, nullable=True, comment="评价图片 JSON 数组")
    is_anonymous = Column(Boolean, default=False, comment="是否匿名评价")

    # 审核状态
    status = Column(String(16), default="pending", nullable=False, comment="pending=待审核 approved=已通过 rejected=未通过")
    reject_reason = Column(Text, nullable=True, comment="审核不通过原因")
    reviewed_by = Column(Integer, nullable=True, comment="审核管理员 ID")
    reviewed_at = Column(DateTime, nullable=True, comment="审核时间")

    # 师傅回复
    worker_reply = Column(Text, nullable=True, comment="师傅回复内容")
    worker_reply_at = Column(DateTime, nullable=True, comment="师傅回复时间")

    # 互动
    like_count = Column(Integer, default=0, comment="点赞数")

    # 精炼摘要（AI/运营生成，用于师傅主页展示）
    highlight_summary = Column(Text, nullable=True, comment="精炼摘要：如'用户一致称赞技术专业、响应迅速'")

    created_at = Column(DateTime, default=datetime.utcnow, comment="评价创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_reviews_worker_status", "worker_id", "status"),
        Index("idx_reviews_service_status", "service_type", "status"),
        Index("idx_reviews_created", "created_at"),
    )


class ReviewLike(Base):
    """评价点赞表"""
    __tablename__ = "review_likes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_review_like_unique", "review_id", "user_id", unique=True),
    )

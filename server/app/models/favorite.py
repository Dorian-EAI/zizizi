"""收藏师傅数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, UniqueConstraint
from app.database import Base


class FavoriteWorker(Base):
    """师傅收藏表"""
    __tablename__ = "favorite_workers"
    __table_args__ = (
        UniqueConstraint("user_id", "worker_id", name="uniq_user_worker"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, nullable=False, comment="用户 ID")
    worker_id = Column(Integer, index=True, nullable=False, comment="师傅 ID")
    created_at = Column(DateTime, default=datetime.utcnow, comment="收藏时间")

"""意见反馈数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base


class Feedback(Base):
    """意见反馈表"""
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, nullable=True, comment="提交用户 ID（未登录时可空）")
    type = Column(String(16), nullable=False, comment="类型: suggestion/bug/complaint/other")
    content = Column(Text, nullable=False, comment="反馈内容")
    images = Column(Text, nullable=True, comment="图片 URL JSON 数组")
    contact = Column(String(64), nullable=True, comment="联系方式")
    status = Column(String(16), default="pending", nullable=False, comment="状态: pending/processing/resolved")
    reply = Column(Text, nullable=True, comment="后台回复内容")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

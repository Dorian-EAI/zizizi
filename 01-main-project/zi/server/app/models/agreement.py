"""协议页与关于我们等页面内容数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base


class PageContent(Base):
    """通用页面内容表（协议/隐私/关于我们/帮助等）"""
    __tablename__ = "page_contents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(32), unique=True, nullable=False, comment="页面 key: agreement/privacy/about/help")
    title = Column(String(128), nullable=False, comment="页面标题")
    content = Column(Text, nullable=False, comment="Markdown 内容")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

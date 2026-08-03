"""FAQ 数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey
from app.database import Base


class FAQCategory(Base):
    """FAQ 分类表"""
    __tablename__ = "faq_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(32), nullable=False, comment="分类名：账号/订单/支付/师傅/隐私")
    sort_order = Column(Integer, default=0, comment="排序权重")


class FAQ(Base):
    """FAQ 常见问题表"""
    __tablename__ = "faqs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("faq_categories.id"), index=True, nullable=False, comment="所属分类 ID")
    question = Column(String(255), nullable=False, comment="问题")
    answer = Column(Text, nullable=False, comment="答案")
    sort_order = Column(Integer, default=0, comment="分类内排序")
    is_active = Column(Boolean, default=True, comment="是否展示")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

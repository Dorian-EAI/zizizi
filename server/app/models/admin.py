"""运营后台管理员数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index
from app.database import Base


class Admin(Base):
    """管理员表"""
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(32), unique=True, nullable=False, index=True, comment="登录账号")
    password_hash = Column(String(128), nullable=False, comment="bcrypt哈希")
    real_name = Column(String(32), nullable=True, comment="真实姓名")
    role = Column(String(16), default="operator", nullable=False, comment="角色: super_admin / operator / customer_service")
    token_version = Column(Integer, default=1, nullable=False, comment="会话版本，递增后旧 JWT 全部失效")
    is_active = Column(Boolean, default=True, comment="是否启用")
    last_login_at = Column(DateTime, nullable=True, comment="最后登录时间")
    last_login_ip = Column(String(45), nullable=True, comment="最后登录IP")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    __table_args__ = (
        Index("ix_admins_username_role", "username", "role"),
    )

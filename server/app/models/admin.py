"""运营后台管理员数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index, Text, ForeignKey
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
    must_change_password = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="首次登录或重置后必须修改密码",
    )
    is_active = Column(Boolean, default=True, comment="是否启用")
    last_login_at = Column(DateTime, nullable=True, comment="最后登录时间")
    last_login_ip = Column(String(45), nullable=True, comment="最后登录IP")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    __table_args__ = (
        Index("ix_admins_username_role", "username", "role"),
    )


class AdminAuditLog(Base):
    """持久化后台写操作审计，禁止把密钥、密码或证件明文写入 detail。"""

    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_admin_id = Column(Integer, ForeignKey("admins.id"), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)
    target_type = Column(String(32), nullable=False)
    target_id = Column(String(64), nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("ix_admin_audit_target", "target_type", "target_id"),
    )

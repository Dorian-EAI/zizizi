"""用户与师傅数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Numeric, Text, JSON
from app.database import Base


class User(Base):
    """用户表 — C 端普通用户"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), unique=True, index=True, nullable=False, comment="微信 openid")
    unionid = Column(String(64), nullable=True, comment="微信 unionid")
    nickname = Column(String(64), nullable=True, comment="昵称")
    avatar = Column(String(512), nullable=True, comment="头像 URL")
    phone = Column(String(20), nullable=True, comment="手机号")
    role = Column(String(16), default="user", nullable=False, comment="当前角色: user/worker")
    token_version = Column(Integer, default=1, nullable=False, comment="会话版本，递增后旧 JWT 全部失效")

    # 会员
    member_level = Column(Integer, default=0, comment="会员等级 0=普通 1=银卡 2=金卡 3=钻石")
    growth_value = Column(Integer, default=0, comment="成长值")

    # 钱包
    balance = Column(Numeric(12, 2), default=0, comment="钱包余额（元，定点小数）")

    # 状态
    is_active = Column(Boolean, default=True, comment="是否启用")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Worker(Base):
    """师傅表 — B 端服务提供者"""
    __tablename__ = "workers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), unique=True, index=True, nullable=False)
    unionid = Column(String(64), nullable=True)
    nickname = Column(String(64), nullable=True)
    avatar = Column(String(512), nullable=True)
    phone = Column(String(20), nullable=True)
    token_version = Column(Integer, default=1, nullable=False, comment="会话版本，递增后旧 JWT 全部失效")

    # 认证
    real_name = Column(String(32), nullable=True, comment="真实姓名")
    # id_card 字段长度扩至 256 以容纳 AES 加密后的 base64 密文
    # 加密格式: base64(salt(16) || iv(16) || ciphertext)，明文 18 位身份证加密后约 88+ 字符
    # 256 留充足余量；存储层永远只存密文，读取时通过 aes.decrypt_field 解密
    id_card = Column(String(256), nullable=True, comment="身份证号（AES 加密存储）")
    certified = Column(Integer, default=0, comment="认证状态: 0=未认证 1=审核中 2=已认证 3=未通过")
    skills = Column(Text, nullable=True, comment="技能标签 JSON 数组")
    certificates = Column(Text, nullable=True, comment="证书图片 JSON 数组")
    certification_data = Column(
        JSON,
        nullable=True,
        comment="认证申请非敏感快照（身份证号仅保存脱敏值）",
    )

    # 评级
    rating = Column(Float, default=5.0, comment="综合评分")
    service_count = Column(Integer, default=0, comment="服务次数")
    total_orders = Column(Integer, default=0, comment="总接单数量")
    completed_orders = Column(Integer, default=0, comment="已完成订单数")
    level = Column(Integer, default=1, comment="师傅等级")

    # 钱包
    balance = Column(Numeric(12, 2), default=0, comment="可提现余额（元，定点小数）")

    # 接单设置
    is_online = Column(Boolean, default=True, comment="是否在线接单")
    service_area = Column(String(256), nullable=True, comment="服务区域")
    service_types = Column(Text, nullable=True, comment="可接服务类型 JSON 数组")

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Address(Base):
    """用户地址表"""
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, nullable=False, comment="所属用户")
    name = Column(String(32), nullable=False, comment="收件人姓名")
    phone = Column(String(20), nullable=False, comment="联系电话")
    province = Column(String(32), nullable=False)
    city = Column(String(32), nullable=False)
    district = Column(String(32), nullable=False)
    detail = Column(String(256), nullable=False, comment="详细地址")
    label = Column(String(16), default="家", comment="标签: 家/公司/其他")
    is_default = Column(Boolean, default=False, comment="是否默认")
    location_lat = Column(Float, nullable=True, comment="纬度")
    location_lng = Column(Float, nullable=True, comment="经度")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

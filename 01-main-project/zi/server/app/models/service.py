"""服务类型数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, Text
from app.database import Base


class ServiceType(Base):
    """服务类型表"""
    __tablename__ = "service_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(32), unique=True, index=True, nullable=False, comment="服务 key 如 electric")
    name = Column(String(32), nullable=False, comment="展示名")
    icon = Column(String(255), nullable=True, comment="图标 URL")
    banner = Column(String(255), nullable=True, comment="banner 图 URL")
    category = Column(String(32), nullable=True, comment="所属大类")
    price_min = Column(Numeric(12, 2), default=0, comment="起步价（元）")
    price_max = Column(Numeric(12, 2), default=0, comment="最高价（元）")
    price_unit = Column(String(8), default="次", comment="计价单位")
    description = Column(Text, nullable=True, comment="服务介绍 (Markdown)")
    process_steps = Column(Text, nullable=True, comment="服务流程 JSON 步骤列表 [{step, title, desc}]")
    faq = Column(Text, nullable=True, comment="FAQ JSON [{q, a}]")
    cases = Column(Text, nullable=True, comment="服务案例 JSON [{title, desc, images}]")

    # 服务图文详情（2026-07 扩展）
    intro_video = Column(String(512), nullable=True, comment="介绍视频 URL")
    service_images = Column(Text, nullable=True, comment="服务实景图 JSON [{url, caption, sort}]")
    detail_sections = Column(Text, nullable=True, comment="详情段落 JSON [{title, content, image}]")
    service_standards = Column(Text, nullable=True, comment="服务标准/保障 JSON [{icon, title, desc}]")
    price_details = Column(Text, nullable=True, comment="价格明细 JSON [{item, price, unit, note}]")

    # v6.3 品类化下单与风险确认
    pricing_modes = Column(Text, nullable=True, comment="允许的定价模式 JSON 数组")
    pricing_schema = Column(Text, nullable=True, comment="品类化下单字段/加价项 JSON")
    service_boundary = Column(Text, nullable=True, comment="服务边界 JSON")
    risk_confirmation = Column(Text, nullable=True, comment="风险确认书 JSON")
    warranty_days = Column(
        Integer, default=0, server_default="0", nullable=False, comment="默认质保天数"
    )

    sort_order = Column(Integer, default=0, comment="排序权重")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

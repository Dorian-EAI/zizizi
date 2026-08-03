"""动态定价 / 高峰加价"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Numeric, JSON
from app.database import Base


class PeakTimeConfig(Base):
    """高峰时段加价配置"""
    __tablename__ = "peak_time_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, comment="配置名称")

    time_ranges = Column(JSON, nullable=False, comment='''时段规则 JSON''')
    surcharge_rate = Column(Numeric(4, 3), default=0.100, comment="加价比例")
    surcharge_max = Column(Integer, default=5000, comment="加价上限，单位分")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

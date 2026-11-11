"""LBS 服务轨迹 + 实时位置"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text
from app.database import Base


class OrderLbsTrack(Base):
    """订单LBS轨迹节点（签到记录）"""
    __tablename__ = "order_lbs_tracks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)

    node_type = Column(String(20), nullable=False, comment="depart/arrive/start/finish/user_confirm")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(String(255), nullable=True)
    distance_meters = Column(Integer, nullable=True, comment="与订单地址距离（米）")
    is_abnormal = Column(Boolean, default=False, comment="是否位置异常")

    photo_url = Column(String(500), nullable=True, comment="签到照片")
    remark = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class WorkerLiveLocation(Base):
    """师傅实时位置（每个师傅一条，每次上报覆盖更新）"""
    __tablename__ = "worker_live_locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False, unique=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True, comment="当前关联订单ID")

    latitude = Column(Float, nullable=False, comment="纬度")
    longitude = Column(Float, nullable=False, comment="经度")
    heading = Column(Float, nullable=True, comment="行进方向角度 0-360")
    speed = Column(Float, nullable=True, comment="速度 m/s")

    # 状态: idle=空闲, to_pickup=前往服务地, arriving=即将到达, serving=服务中, leaving=离开
    track_status = Column(String(20), default="idle", comment="idle/to_pickup/arriving/serving/leaving")

    # 预估信息
    eta_seconds = Column(Integer, nullable=True, comment="预估到达剩余秒数")
    distance_meters = Column(Integer, nullable=True, comment="预估到达剩余距离米")

    last_reported_at = Column(DateTime, nullable=True, comment="最后上报时间")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LocationHistory(Base):
    """位置历史轨迹点（用于绘制师傅移动路线）"""
    __tablename__ = "location_histories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    heading = Column(Float, nullable=True)
    speed = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

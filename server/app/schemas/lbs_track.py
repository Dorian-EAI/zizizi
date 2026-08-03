"""LBS轨迹 Pydantic 模型"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CheckinRequest(BaseModel):
    node_type: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    photo_url: Optional[str] = None
    remark: Optional[str] = None


class LbsTrackResponse(BaseModel):
    id: int
    order_id: int
    worker_id: int
    node_type: str
    latitude: Optional[float]
    longitude: Optional[float]
    address: Optional[str]
    distance_meters: Optional[int]
    is_abnormal: bool
    photo_url: Optional[str]
    remark: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

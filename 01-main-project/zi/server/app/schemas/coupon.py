"""优惠券相关 Pydantic 模型"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CreateCouponTemplate(BaseModel):
    name: str
    type: str = "fixed"
    value: float
    min_spend: float = 0
    service_type: Optional[str] = None
    total_quota: int = 1000
    per_user_limit: int = 1
    valid_start: Optional[datetime] = None
    valid_end: Optional[datetime] = None
    is_active: bool = True


class CouponTemplateResponse(BaseModel):
    id: int
    name: str
    type: str
    value: float
    min_spend: float
    service_type: Optional[str]
    total_quota: int
    per_user_limit: int
    valid_start: Optional[datetime]
    valid_end: Optional[datetime]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CouponResponse(BaseModel):
    id: int
    template_id: int
    user_id: int
    code: str
    status: str
    used_order_no: Optional[str]
    used_at: Optional[datetime]
    expire_at: Optional[datetime]
    received_at: datetime
    template: Optional[dict] = None

    class Config:
        from_attributes = True

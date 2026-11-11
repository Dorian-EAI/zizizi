"""家庭年卡 Pydantic 模型"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class AnnualCardTemplateResponse(BaseModel):
    id: int
    name: str
    price: int
    total_value: int
    service_count: int
    urgent_discount: float
    description: Optional[str]
    is_active: bool
    sort_order: int
    created_at: datetime

    class Config:
        from_attributes = True


class PurchaseCardRequest(BaseModel):
    template_id: int
    payment_method: str = "wechat"


class UserAnnualCardResponse(BaseModel):
    id: int
    template_id: int
    user_id: int
    order_no: str
    total_count: int
    used_count: int
    status: str
    valid_start: datetime
    valid_end: datetime
    created_at: datetime
    template: Optional[AnnualCardTemplateResponse] = None

    class Config:
        from_attributes = True


class UseCardRequest(BaseModel):
    card_id: int

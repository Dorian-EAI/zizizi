"""积分相关 Pydantic 模型"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PointBalanceResponse(BaseModel):
    balance: int
    month_earn: int
    total_earn: int
    today_signin: bool


class PointLogResponse(BaseModel):
    id: int
    change: int
    balance_after: int
    reason: str
    order_no: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PointExchangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coupon_template_id: int = Field(..., gt=0)

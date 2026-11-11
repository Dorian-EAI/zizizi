"""保证金 Pydantic 模型"""

from datetime import datetime
from typing import Literal, Optional, List
from pydantic import BaseModel, ConfigDict
from pydantic import Field


class DepositPayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: int = Field(..., gt=0, le=100000000, description="保证金金额，单位分")
    payment_method: Literal["wechat"] = "wechat"


class DepositLevelConfig(BaseModel):
    level: str
    amount: int
    daily_order_limit: int
    platform_cut_rate: float


class DepositTransactionResponse(BaseModel):
    id: int
    worker_id: int
    type: str
    amount: int
    balance_after: int
    reason: str
    related_order_id: Optional[int]
    related_claim_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class DepositDetailResponse(BaseModel):
    worker_id: int
    deposit_level: str
    balance: int
    frozen_amount: int
    total_deposited: int
    platform_cut_rate: float
    daily_order_limit: int
    status: str
    recent_transactions: List[DepositTransactionResponse] = Field(default_factory=list)


class AdminDeductDepositRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: int = Field(..., gt=0, le=100000000, description="扣除金额，单位分")
    reason: str = Field(..., min_length=2, max_length=200)

"""钱包相关 Pydantic 模型"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


class RechargeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: float = Field(..., gt=0, le=1000000)
    method: Literal["wechat"] = "wechat"


class WithdrawRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: float = Field(..., ge=10, le=1000000)
    method: Literal["wechat"] = "wechat"
    bank_info: Optional[str] = Field(None, max_length=512)


class PayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_no: str = Field(..., min_length=1, max_length=64)
    method: Literal["wechat", "wallet", "combined", "offline"] = "wallet"
    coupon_id: Optional[int] = Field(None, gt=0)
    wallet_amount: Optional[float] = Field(None, ge=0, le=1000000)
    wechat_amount: Optional[float] = Field(None, ge=0, le=1000000)
    order_version: Optional[int] = Field(None, ge=0)


class RefundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_no: str = Field(..., min_length=1, max_length=64)
    reason: str = Field(..., min_length=2, max_length=512)
    amount: Optional[float] = Field(None, gt=0, le=1000000)


class OfflineConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_no: str = Field(..., min_length=1, max_length=64)


class TransactionResponse(BaseModel):
    id: int
    type: str = Field(..., max_length=32)
    amount: float
    balance_after: Optional[float]
    method: Optional[str] = Field(None, max_length=32)
    order_id: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = Field(None, max_length=512)
    status: str = Field(..., max_length=32)
    created_at: datetime

    class Config:
        from_attributes = True


class WalletResponse(BaseModel):
    balance: float
    month_income: float
    month_expense: float
    total_income: float

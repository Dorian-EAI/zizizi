"""补差价 Pydantic 模型"""

from datetime import datetime
from typing import Annotated, Optional, List
from pydantic import BaseModel, ConfigDict, Field, model_validator


PhotoUrl = Annotated[str, Field(max_length=512)]


class ExtraFeeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=50)
    price: int = Field(..., gt=0, le=100_000_000, description="单位：分")
    unit: str = Field("次", min_length=1, max_length=10)


class ApplyExtraFeeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[ExtraFeeItem] = Field(..., min_length=1, max_length=20)
    total_amount: int = Field(..., gt=0, le=100_000_000, description="单位：分")
    reason: str = Field(..., min_length=2, max_length=500)
    photo_urls: List[PhotoUrl] = Field(default_factory=list, max_length=9)

    @model_validator(mode="after")
    def validate_total(self):
        if sum(item.price for item in self.items) != self.total_amount:
            raise ValueError("total_amount 必须等于各补差价项目之和")
        return self


class ExtraFeeResponse(BaseModel):
    id: int
    order_id: int
    worker_id: int
    user_id: int
    items: List[dict]
    total_amount: int
    reason: str
    photo_urls: List[str]
    status: str
    user_remark: Optional[str]
    retry_count: int
    created_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


class RejectExtraFeeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=1, max_length=500)

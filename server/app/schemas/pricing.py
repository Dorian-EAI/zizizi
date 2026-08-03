"""动态定价 Pydantic 模型"""

from datetime import datetime
import re
from typing import Literal, Optional, List
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TimeRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str
    end: str
    weekdays: List[int] = Field(..., min_length=1, max_length=7)

    @field_validator("start", "end")
    @classmethod
    def validate_time(cls, value: str) -> str:
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("时间必须为 HH:MM")
        return value

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, value: List[int]) -> List[int]:
        if any(day < 1 or day > 7 for day in value):
            raise ValueError("weekdays 仅允许 1-7")
        if len(set(value)) != len(value):
            raise ValueError("weekdays 不能重复")
        return value


class SurchargeResponse(BaseModel):
    is_peak_time: bool
    surcharge_rate: float
    surcharge_max: int
    current_surcharge: int


class CalculateAmountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_amount: int = Field(..., gt=0, le=100_000_000, description="基础金额，单位分")
    service_type: Optional[str] = Field(None, max_length=64)
    is_urgent: bool = False
    coupon_id: Optional[int] = Field(None, gt=0)
    annual_card_id: Optional[int] = Field(None, gt=0)


class CalculateAmountResponse(BaseModel):
    base_amount: int
    peak_surcharge: int
    urgent_amount: int
    member_discount: int
    member_discount_status: Literal["unavailable"]
    member_discount_reason: str
    coupon_discount: int
    annual_card_discount: int
    final_amount: int


class PeakTimeConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=50)
    time_ranges: List[TimeRange] = Field(..., min_length=1, max_length=32)
    surcharge_rate: float = Field(..., ge=0, le=1)
    surcharge_max: int = Field(..., ge=0, le=10_000_000)


class PeakTimeConfigResponse(BaseModel):
    id: int
    name: str
    time_ranges: List[TimeRange]
    surcharge_rate: float
    surcharge_max: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

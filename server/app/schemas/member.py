"""会员相关 Pydantic 模型"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class LevelInfo(BaseModel):
    level: int
    level_name: str
    growth: int
    next_level_growth: int
    progress_percent: int


class GrowthLogResponse(BaseModel):
    id: int
    amount: int
    reason: str
    created_at: datetime


class MemberResponse(BaseModel):
    level_info: LevelInfo
    growth_value: int
    month_spend: float
    coupon_count: int
    benefits: List[Dict[str, Any]]


class TestAddGrowthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: int = Field(..., gt=0, le=1000)
    reason: str = Field(..., min_length=1, max_length=64)

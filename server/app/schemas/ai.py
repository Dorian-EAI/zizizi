"""AI 估价相关 Pydantic 模型"""

from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class AIAnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(..., min_length=1, max_length=2000)
    service_type: Optional[str] = Field(None, max_length=64)
    # 约 6 MiB 原图的 base64 上限，避免超大 JSON 请求拖垮进程。
    image_base64: Optional[str] = Field(None, max_length=8_388_608)


class AIAnalyzeResponse(BaseModel):
    service_type: str
    service_name: str
    confidence: float
    problem_type: str
    severity: str  # low/medium/high/critical
    severity_text: str
    estimated_price_min: float
    estimated_price_max: float
    estimated_time: str
    suggestion: str
    parts: List[str] = Field(default_factory=list)


class AIChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1, max_length=2000)
    context: Optional[str] = Field(None, max_length=8000)


class AIChatResponse(BaseModel):
    text: str
    actions: List[dict] = Field(default_factory=list)


# ===== 规则化估价（pricing_engine）相关模型 =====

class EstimateRequest(BaseModel):
    """规则化估价请求"""
    model_config = ConfigDict(extra="forbid")

    service_type: Optional[str] = Field(
        None,
        max_length=64,
        description="服务类型代码：water_electric/air_conditioner/appliance/pipeline/"
                    "door_window/circuit/furniture/wall",
    )
    description: str = Field("", max_length=2000, description="问题描述，用于命中复杂度关键词")
    images_count: int = Field(0, ge=0, le=9, description="图片数量（影响置信度）")
    urgency: str = Field(
        "normal",
        description="紧急程度：normal/urgent_10/urgent_20/urgent_50",
    )
    city: Optional[str] = Field(None, max_length=64, description="城市（保留参数）")
    area_size: Optional[float] = Field(
        None, ge=0, le=100000, description="面积（平方米），>100 触发大面积加价"
    )


class EstimateBreakdownItem(BaseModel):
    """价格明细项"""
    item: str
    amount: float


class EstimateResponse(BaseModel):
    """规则化估价响应"""
    service_type: Optional[str] = None
    service_name: Optional[str] = None
    min_price: float
    max_price: float
    suggested_price: float
    confidence: float
    estimated_minutes: int
    breakdown: List[EstimateBreakdownItem] = Field(default_factory=list)

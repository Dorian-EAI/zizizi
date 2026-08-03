"""订单相关 Pydantic 模型"""

import json
import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional, List, Annotated, Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


# 图片 URL 字符串约束（用于 List 元素）
_ImageUrlStr = Annotated[str, Field(max_length=512)]


def _load_address_payload(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("address 必须是结构化 JSON，不能是普通字符串") from exc
    if not isinstance(parsed, dict):
        raise ValueError("address 必须是结构化 JSON 对象")
    return parsed


class OrderAddressRequest(BaseModel):
    """Structured service location accepted by the create-order contract."""

    model_config = ConfigDict(extra="forbid")

    address: str = Field(..., min_length=2, max_length=400)
    latitude: float = Field(..., ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(..., ge=-180, le=180, allow_inf_nan=False)

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def require_numeric_coordinate(cls, value: Any) -> Any:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("latitude/longitude 必须是 JSON 数字")
        return value

    @field_validator("address")
    @classmethod
    def normalize_address_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("address.address 不能为空")
        return value

    @model_validator(mode="after")
    def reject_null_island(self):
        if not math.isfinite(self.latitude) or not math.isfinite(self.longitude):
            raise ValueError("address 坐标必须是有限数值")
        if self.latitude == 0 and self.longitude == 0:
            raise ValueError("address 坐标不能为 0,0")
        return self


def normalize_order_address(value: Any) -> str:
    """Validate and canonicalize the structured address stored on an order."""
    address = (
        value
        if isinstance(value, OrderAddressRequest)
        else OrderAddressRequest.model_validate(_load_address_payload(value))
    )
    return json.dumps(
        address.model_dump(),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def normalize_future_appointment(value: Optional[datetime]) -> Optional[datetime]:
    """Normalize appointment timestamps to naive UTC and reject the past."""
    if value is None:
        return None
    if value.tzinfo is not None and value.utcoffset() is not None:
        normalized = value.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        normalized = value
    if normalized < datetime.utcnow():
        raise ValueError("预约时间不能早于当前时间")
    return normalized


# ===== 请求 =====
class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_type: str = Field(..., min_length=1, max_length=32)
    # 仅为兼容旧客户端保留；创建时展示名始终取服务端 ServiceType.name。
    service_name: Optional[str] = Field(None, max_length=256)
    description: Optional[str] = Field(None, max_length=512)
    images: Optional[List[_ImageUrlStr]] = Field(default_factory=list, max_length=9)
    address: OrderAddressRequest
    appoint_time: Optional[datetime] = None
    budget: Optional[Decimal] = Field(
        Decimal("0"), ge=0, le=1_000_000, max_digits=9, decimal_places=2
    )
    urgent: bool = False
    urgent_amount: Optional[Decimal] = Field(
        Decimal("0"), ge=0, le=1_000_000, max_digits=9, decimal_places=2
    )

    @field_validator("address", mode="before")
    @classmethod
    def validate_address(cls, value: Any) -> Any:
        return _load_address_payload(value)

    @field_validator("appoint_time")
    @classmethod
    def validate_appointment(cls, value: Optional[datetime]) -> Optional[datetime]:
        return normalize_future_appointment(value)


class BiddingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price: Decimal = Field(
        ..., ge=0, le=1_000_000, max_digits=9, decimal_places=2
    )
    message: Optional[str] = Field(None, max_length=1024)
    eta: Optional[str] = Field(None, max_length=256)


class SelectWorkerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bidding_id: int


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int = Field(..., ge=1, le=5)
    tags: Optional[List[Annotated[str, Field(max_length=256)]]] = Field(default_factory=list, max_length=20)
    content: Optional[str] = Field(None, max_length=1024)
    images: Optional[List[_ImageUrlStr]] = Field(default_factory=list, max_length=9)
    is_anonymous: bool = False


class UpdateOrderStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "cancelled"]
    price: Optional[Decimal] = Field(
        None, ge=0, le=1_000_000, max_digits=9, decimal_places=2
    )
    # 前端 api.orders.cancel 会附带 cancel_reason，接受但当前不持久化
    # （订单表暂无该字段；如需记录可在 Order 模型加列后写入）
    cancel_reason: Optional[str] = Field(None, max_length=256)


# ===== 响应 =====
class OrderResponse(BaseModel):
    id: int
    order_no: str = Field(..., max_length=64)
    user_id: int
    worker_id: Optional[int]
    service_type: str = Field(..., max_length=256)
    service_name: str = Field(..., max_length=256)
    description: Optional[str] = Field(None, max_length=512)
    images: Optional[str] = Field(None, max_length=2048)
    address: Optional[str] = Field(None, max_length=512)
    appoint_time: Optional[datetime]
    budget: float
    final_price: Optional[float]
    urgent: bool
    urgent_amount: float
    status: str = Field(..., max_length=32)
    created_at: datetime
    accepted_at: Optional[datetime]
    departed_at: Optional[datetime]
    arrived_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    paid_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    reviewed_at: Optional[datetime]
    rating: Optional[int]
    review_content: Optional[str] = Field(None, max_length=1024)

    class Config:
        from_attributes = True


class AvailableOrderResponse(BaseModel):
    """Minimal order projection shown before a worker is selected.

    Deliberately excludes ownership, contact details, the exact address and
    coordinates.  Distance is calculated server-side and is the only location
    signal exposed in the dispatch hall.
    """

    id: int
    service_type: str = Field(..., max_length=256)
    service_name: str = Field(..., max_length=256)
    description: Optional[str] = Field(None, max_length=512)
    images: Optional[str] = Field(None, max_length=2048)
    appoint_time: Optional[datetime]
    budget: float
    urgent: bool
    urgent_amount: float
    status: str = Field(..., max_length=32)
    created_at: datetime
    distance_meters: Optional[int] = None
    distance_text: Optional[str] = Field(None, max_length=64)
    duration_seconds: Optional[int] = None
    route_mode: Optional[str] = Field(None, max_length=32)

    model_config = ConfigDict(from_attributes=True)


class BiddingResponse(BaseModel):
    id: int
    order_id: int
    worker_id: int
    worker_name: Optional[str] = Field(None, max_length=32)
    worker_avatar: Optional[str] = Field(None, max_length=512)
    worker_rating: Optional[float] = None
    worker_service_count: Optional[int] = None
    price: float
    message: Optional[str] = Field(None, max_length=1024)
    eta: Optional[str] = Field(None, max_length=256)
    is_selected: bool
    created_at: datetime

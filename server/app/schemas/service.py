"""服务类型相关 Pydantic 模型"""

from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToggleServiceActiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool


class ServiceTypeListResponse(BaseModel):
    id: int
    key: str
    name: str
    icon: Optional[str] = None
    category: Optional[str] = None
    price_min: float
    price_max: float
    price_unit: str
    is_active: bool

    class Config:
        from_attributes = True


class ServiceTypeDetailResponse(BaseModel):
    id: int
    key: str
    name: str
    icon: Optional[str] = None
    banner: Optional[str] = None
    category: Optional[str] = None
    price_min: float
    price_max: float
    price_unit: str
    description: Optional[str] = None
    process_steps: Optional[List[Any]] = None
    faq: Optional[List[Any]] = None
    cases: Optional[List[Any]] = None
    # 扩展图文
    intro_video: Optional[str] = None
    service_images: Optional[List[Any]] = None
    detail_sections: Optional[List[Any]] = None
    service_standards: Optional[List[Any]] = None
    price_details: Optional[List[Any]] = None

    class Config:
        from_attributes = True


class ServiceTypeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., min_length=1, max_length=32, pattern="^[a-z][a-z0-9_]*$")
    name: str = Field(..., min_length=1, max_length=32)
    icon: Optional[str] = Field(None, max_length=255)
    banner: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=32)
    price_min: float = Field(0, ge=0, le=1_000_000)
    price_max: float = Field(0, ge=0, le=1_000_000)
    price_unit: str = Field("次", min_length=1, max_length=8)
    description: Optional[str] = Field(None, max_length=50_000)
    process_steps: Optional[List[Any]] = Field(None, max_length=50)
    faq: Optional[List[Any]] = Field(None, max_length=100)
    cases: Optional[List[Any]] = Field(None, max_length=100)
    # 扩展图文
    intro_video: Optional[str] = Field(None, max_length=512)
    service_images: Optional[List[Any]] = Field(None, max_length=100)
    detail_sections: Optional[List[Any]] = Field(None, max_length=100)
    service_standards: Optional[List[Any]] = Field(None, max_length=100)
    price_details: Optional[List[Any]] = Field(None, max_length=200)
    sort_order: int = Field(0, ge=-10_000, le=10_000)

    @model_validator(mode="after")
    def validate_price_range(self):
        if self.price_max < self.price_min:
            raise ValueError("price_max 不能小于 price_min")
        return self


class ServiceCaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=100)
    desc: Optional[str] = Field(None, max_length=2000)
    images: Optional[List[str]] = Field(None, max_length=20)

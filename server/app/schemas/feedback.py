"""意见反馈相关 Pydantic 模型"""

from datetime import datetime
from typing import Optional, List, Annotated, Literal
from pydantic import BaseModel, Field, ConfigDict


# 图片 URL 字符串约束（用于 List 元素）
_ImageUrlStr = Annotated[str, Field(max_length=512)]


class FeedbackCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["suggestion", "bug", "complaint", "other"]
    content: str = Field(..., max_length=1024)
    images: Optional[List[_ImageUrlStr]] = Field(default_factory=list, max_length=9)
    contact: Optional[str] = Field(None, max_length=256)


class FeedbackResponse(BaseModel):
    id: int
    type: str = Field(..., max_length=32)
    content: str = Field(..., max_length=1024)
    images: Optional[List[str]] = Field(None, max_length=9)
    contact: Optional[str] = Field(None, max_length=256)
    status: str = Field(..., max_length=32)
    reply: Optional[str] = Field(None, max_length=1024)
    created_at: datetime

    class Config:
        from_attributes = True


class FeedbackUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["pending", "processing", "resolved"]
    reply: Optional[str] = Field(None, max_length=1024)

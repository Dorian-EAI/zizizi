"""评论/评价 Pydantic 模型"""

from datetime import datetime
from typing import Annotated, Literal, Optional, List
from pydantic import BaseModel, ConfigDict, Field


ShortTag = Annotated[str, Field(min_length=1, max_length=20)]
ImageUrl = Annotated[str, Field(max_length=512)]


class ReviewCreateRequest(BaseModel):
    """前端提交评价（同 Order ReviewRequest，用于兼容）"""
    model_config = ConfigDict(extra="forbid")

    rating: int = Field(..., ge=1, le=5)
    tags: List[ShortTag] = Field(default_factory=list, max_length=10)
    content: Optional[str] = Field(None, max_length=2000)
    images: List[ImageUrl] = Field(default_factory=list, max_length=9)
    is_anonymous: bool = False


class WorkerReplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str = Field(..., min_length=1, max_length=1000)


class ReviewResponse(BaseModel):
    id: int
    order_id: int
    user_id: int
    worker_id: Optional[int]
    service_type: Optional[str]
    rating: int
    review_tags: List[str] = Field(default_factory=list)
    review_content: Optional[str]
    review_images: List[str] = Field(default_factory=list)
    is_anonymous: bool
    status: str
    worker_reply: Optional[str]
    worker_reply_at: Optional[datetime]
    like_count: int
    highlight_summary: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewListParams(BaseModel):
    worker_id: Optional[int] = Field(None, gt=0)
    service_type: Optional[str] = Field(None, max_length=32)
    rating: Optional[int] = Field(None, ge=1, le=5)
    status: Literal["pending", "approved", "rejected"] = "approved"
    page: int = Field(1, ge=1)
    size: int = Field(10, ge=1, le=100)


class ReviewStatsResponse(BaseModel):
    """评价统计数据"""
    total_count: int
    avg_rating: float
    rating_5_count: int
    rating_4_count: int
    rating_3_count: int
    rating_2_count: int
    rating_1_count: int
    tag_counts: List[dict] = Field(default_factory=list)  # [{tag, count}]
    highlight_summary: Optional[str]


class ReviewAuditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["approved", "rejected"]
    reject_reason: Optional[str] = Field(None, max_length=1000)

"""FAQ、协议页、关于我们等内容页 Pydantic 模型"""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field


class PageUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=100_000)


class FAQResponse(BaseModel):
    id: int
    category_id: int
    question: str
    answer: str


class FAQCategoryResponse(BaseModel):
    id: int
    name: str
    faqs: List[FAQResponse] = []


class PageResponse(BaseModel):
    key: str
    title: str
    content: str
    updated_at: Optional[datetime] = None

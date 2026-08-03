"""消息相关 Pydantic 模型"""

from datetime import datetime
from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class MessageResponse(BaseModel):
    id: int
    owner_type: str
    owner_id: int
    type: str
    title: str
    content: str
    payload: Optional[Dict[str, Any]] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    list: List[MessageResponse]
    total: int
    unread_count: int
    page: int
    has_more: bool


class TestSendMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_type: Literal["user", "worker"]
    owner_id: int = Field(..., gt=0)
    type: str = Field(..., min_length=1, max_length=32)
    title: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=2000)

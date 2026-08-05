"""消息相关 Pydantic 模型"""

import json
from datetime import datetime
from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    @field_validator("payload", mode="before")
    @classmethod
    def parse_payload_json(cls, value):
        if value is None or value == "":
            return None
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
            return parsed if isinstance(parsed, dict) else None
        return value

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

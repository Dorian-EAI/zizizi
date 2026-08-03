"""质检回访 Pydantic 模型"""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class InspectionFeedbackRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    feedback: Optional[str] = Field(None, max_length=1000)

    model_config = {"extra": "forbid"}


class QualityInspectionResponse(BaseModel):
    id: int
    order_id: int
    user_id: int
    worker_id: int
    inspect_type: str
    rating: Optional[int]
    satisfaction: Optional[str]
    feedback: Optional[str]
    is_complaint: bool
    complaint_ticket_id: Optional[int]
    status: str
    inspector_id: Optional[int]
    inspected_at: Optional[datetime]
    created_at: datetime
    send_at: Optional[datetime]

    class Config:
        from_attributes = True


class AdminAuditInspectionRequest(BaseModel):
    status: Literal["done", "need_follow"]
    remark: Optional[str] = Field(None, max_length=1000)

    model_config = {"extra": "forbid"}

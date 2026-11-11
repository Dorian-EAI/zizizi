"""客服工单 Pydantic 模型"""

from datetime import datetime
from typing import Annotated, Optional, List
from pydantic import BaseModel, ConfigDict, Field


EvidenceUrl = Annotated[str, Field(max_length=512)]


class CreateTicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_type: str = Field(..., min_length=1, max_length=30)
    title: str = Field(..., min_length=2, max_length=200)
    description: str = Field(..., min_length=5, max_length=5000)
    related_order_id: Optional[int] = Field(None, gt=0)
    evidence_urls: List[EvidenceUrl] = Field(default_factory=list, max_length=9)


class TicketReplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., min_length=1, max_length=2000)


class AdminTicketReplyRequest(TicketReplyRequest):
    is_internal: bool = False


class TicketReplyResponse(BaseModel):
    id: int
    ticket_id: int
    reply_type: str
    replier_id: int
    replier_name: str
    content: str
    is_internal: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SupportTicketResponse(BaseModel):
    id: int
    ticket_no: str
    ticket_type: str
    priority: str
    status: str
    creator_type: str
    creator_id: int
    creator_name: str
    creator_phone: Optional[str]
    related_order_id: Optional[int]
    title: str
    description: str
    evidence_urls: List[str]
    resolution: Optional[str]
    refund_amount: int
    deduct_deposit: int
    assigned_to: Optional[int]
    resolved_by: Optional[int]
    resolved_at: Optional[datetime]
    closed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    replies: List[TicketReplyResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class AdminAssignTicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    admin_id: int = Field(..., gt=0)


class AdminResolveTicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution: str = Field(..., min_length=2, max_length=5000)
    refund_amount: int = Field(0, ge=0, le=100_000_000)
    deduct_deposit: int = Field(0, ge=0, le=100_000_000)

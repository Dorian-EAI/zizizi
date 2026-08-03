"""安心保 Pydantic 模型"""

from datetime import datetime
from typing import Annotated, Literal, Optional, List
from pydantic import BaseModel, ConfigDict, Field


EvidenceUrl = Annotated[str, Field(max_length=512)]


class InsuranceLevelConfig(BaseModel):
    level: str
    premium: int
    coverage: int


class BuyInsuranceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: Literal["basic", "standard", "premium"]


class InsurancePolicyResponse(BaseModel):
    id: int
    order_id: int
    user_id: int
    worker_id: Optional[int]
    level: str
    premium: int
    coverage: int
    status: str
    claimed_amount: int
    created_at: datetime
    expired_at: datetime

    class Config:
        from_attributes = True


class SubmitClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: int = Field(..., gt=0)
    reason: str = Field(..., min_length=5, max_length=5000)
    evidence_images: List[EvidenceUrl] = Field(..., min_length=1, max_length=9)
    claim_amount: int = Field(..., gt=0, le=100_000_000)


class InsuranceClaimResponse(BaseModel):
    id: int
    policy_id: int
    order_id: int
    user_id: int
    worker_id: Optional[int]
    reason: str
    evidence_images: List[str]
    claim_amount: int
    status: str
    audit_remark: Optional[str]
    audited_by: Optional[int]
    audited_at: Optional[datetime]
    settled_amount: int
    created_at: datetime
    settled_at: Optional[datetime]

    class Config:
        from_attributes = True


class AuditClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["approved", "rejected"]
    settled_amount: int = Field(0, ge=0, le=100_000_000)
    remark: str = Field("", max_length=2000)

"""安心保 API"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_current_account, get_current_admin
from app.models.user import User
from app.schemas.insurance import (
    BuyInsuranceRequest,
    InsurancePolicyResponse,
    SubmitClaimRequest,
    InsuranceClaimResponse,
    AuditClaimRequest,
)
from app.services import insurance_service
from app.utils.response import success

router = APIRouter(prefix="/api/insurance", tags=["安心保"])


@router.post("/orders/{order_id}/buy")
async def buy_insurance(
    order_id: int,
    req: BuyInsuranceRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """为订单购买安心保"""
    policy = insurance_service.create_policy(db, order_id, user.id, req.level)
    return success(data=InsurancePolicyResponse.model_validate(policy).model_dump(mode="json"))


@router.get("/orders/{order_id}/policy")
async def get_order_policy(
    order_id: int,
    current=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """查询订单保单"""
    policy = insurance_service.get_policy_by_order(db, order_id)
    if not policy:
        return success(data=None)
    account, account_type = current
    allowed = policy.user_id == account.id if account_type == "user" else policy.worker_id == account.id
    if not allowed:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="无权查看该保单")
    return success(data=InsurancePolicyResponse.model_validate(policy).model_dump(mode="json"))


@router.post("/claims")
async def submit_claim(
    req: SubmitClaimRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提交理赔申请"""
    claim = insurance_service.submit_claim(
        db, user.id, req.policy_id, req.reason, req.evidence_images, req.claim_amount
    )
    return success(data=InsuranceClaimResponse.model_validate(claim).model_dump(mode="json"))


@router.get("/claims")
async def my_claims(
    status: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的理赔列表"""
    result = insurance_service.list_claims(db, user_id=user.id, status=status)
    return success(data=result)


# ===== 管理员接口 =====

@router.get("/admin/claims")
async def admin_claims(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """理赔审核列表（后台）"""
    result = insurance_service.list_claims(db, status=status, page=page, size=size)
    return success(data=result)


@router.put("/admin/claims/{claim_id}/audit")
async def audit_claim(
    claim_id: int,
    req: AuditClaimRequest,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """审核理赔"""
    claim = insurance_service.audit_claim(db, admin.id, claim_id, req.status, req.settled_amount, req.remark)
    return success(data=InsuranceClaimResponse.model_validate(claim).model_dump(mode="json"))

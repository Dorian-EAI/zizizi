"""补差价 API"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_worker, get_current_user, get_current_account
from app.models.user import Worker, User
from app.models.order import Order
from app.schemas.extra_fee import ApplyExtraFeeRequest, RejectExtraFeeRequest, ExtraFeeResponse
from app.services import extra_fee_service
from app.utils.response import success

router = APIRouter(tags=["补差价"])


@router.post("/api/worker/orders/{order_id}/extra-fee")
async def apply_extra_fee(
    order_id: int,
    req: ApplyExtraFeeRequest,
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """师傅申请补差价"""
    extra = extra_fee_service.apply_extra_fee(
        db, worker.id, order_id, [i.model_dump() for i in req.items],
        req.total_amount, req.reason, req.photo_urls
    )
    return success(data=ExtraFeeResponse.model_validate(extra).model_dump(mode="json"))


@router.get("/api/orders/{order_id}/extra-fees")
async def get_extra_fees(
    order_id: int,
    current=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """查询订单补差价记录"""
    account, account_type = current
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="订单不存在")
    allowed = order.user_id == account.id if account_type == "user" else order.worker_id == account.id
    if not allowed:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="无权查看该订单")
    extras = extra_fee_service.get_extra_fee_list(db, order_id)
    return success(data=[ExtraFeeResponse.model_validate(e).model_dump(mode="json") for e in extras])


@router.put("/api/orders/{order_id}/extra-fees/{extra_fee_id}/approve")
async def approve_extra_fee(
    order_id: int,
    extra_fee_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用户同意补差价"""
    extra = extra_fee_service.approve_extra_fee(db, user.id, order_id, extra_fee_id)
    return success(data=ExtraFeeResponse.model_validate(extra).model_dump(mode="json"))


@router.put("/api/orders/{order_id}/extra-fees/{extra_fee_id}/reject")
async def reject_extra_fee(
    order_id: int,
    extra_fee_id: int,
    req: RejectExtraFeeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用户拒绝补差价"""
    extra = extra_fee_service.reject_extra_fee(db, user.id, order_id, extra_fee_id, req.reason)
    return success(data=ExtraFeeResponse.model_validate(extra).model_dump(mode="json"))

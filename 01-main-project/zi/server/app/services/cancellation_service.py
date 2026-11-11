"""订单取消申请业务逻辑。

规则：
- pending 订单仍走原有直接取消；
- accepted/departing/arrived 订单只能提交取消申请，由运营确认；
- serving 及之后进入售后/争议，不允许取消申请；
- 未配置取消费用规则时费用固定为 0，不得自动扣款。
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.order import Order, OrderCancellationRequest
from app.models.user import User
from app.services import message_service
from app.services.order_service import _cas_update_status
from app.utils.snowflake import generate_business_no

CANCELLABLE_STATUSES = {"accepted", "departing", "arrived"}
_DIRECT_CANCEL_HINT = "待接单订单可直接取消，无需提交取消申请"


def get_latest_request(db: Session, order_id: int) -> Optional[OrderCancellationRequest]:
    return (
        db.query(OrderCancellationRequest)
        .filter(OrderCancellationRequest.order_id == order_id)
        .order_by(OrderCancellationRequest.id.desc())
        .first()
    )


def serialize_request(request: Optional[OrderCancellationRequest]) -> Optional[dict]:
    if not request:
        return None
    return {
        "id": request.id,
        "request_no": request.request_no,
        "order_id": request.order_id,
        "user_id": request.user_id,
        "worker_id": request.worker_id,
        "reason": request.reason,
        "note": request.note,
        "status": request.status,
        "fee_amount": float(request.fee_amount or 0),
        "review_remark": request.review_remark,
        "created_at": request.created_at,
        "reviewed_at": request.reviewed_at,
    }


def create_request(
    db: Session,
    user: User,
    order_id: int,
    reason: str,
    note: Optional[str] = None,
) -> OrderCancellationRequest:
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权操作该订单")

    status = str(order.status or "")
    if status == "pending":
        raise HTTPException(status_code=409, detail=_DIRECT_CANCEL_HINT)
    if status == "serving":
        raise HTTPException(status_code=409, detail="服务中请通过报告问题或客服处理")
    if status not in CANCELLABLE_STATUSES:
        raise HTTPException(status_code=409, detail="当前订单状态不能申请取消")

    pending = (
        db.query(OrderCancellationRequest)
        .filter(
            OrderCancellationRequest.order_id == order_id,
            OrderCancellationRequest.status == "pending",
        )
        .with_for_update()
        .first()
    )
    if pending:
        raise HTTPException(status_code=409, detail="已有待处理的取消申请")

    request = OrderCancellationRequest(
        request_no=generate_business_no("CN"),
        order_id=order.id,
        user_id=user.id,
        worker_id=order.worker_id,
        reason=reason.strip(),
        note=(note or "").strip() or None,
        status="pending",
        fee_amount=0,
    )
    db.add(request)
    db.flush()
    if order.worker_id:
        message_service.notify_cancel_requested(db, order, request)
    db.commit()
    db.refresh(request)
    return request


def withdraw_request(db: Session, user: User, order_id: int) -> OrderCancellationRequest:
    request = (
        db.query(OrderCancellationRequest)
        .filter(
            OrderCancellationRequest.order_id == order_id,
            OrderCancellationRequest.user_id == user.id,
            OrderCancellationRequest.status == "pending",
        )
        .order_by(OrderCancellationRequest.id.desc())
        .with_for_update()
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="没有可撤回的取消申请")
    request.status = "withdrawn"
    request.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(request)
    return request


def approve_request(
    db: Session,
    admin_id: int,
    request_id: int,
    remark: Optional[str] = None,
) -> OrderCancellationRequest:
    request = (
        db.query(OrderCancellationRequest)
        .filter(OrderCancellationRequest.id == request_id)
        .with_for_update()
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="取消申请不存在")
    if request.status != "pending":
        raise HTTPException(status_code=409, detail="取消申请已处理")

    order = (
        db.query(Order)
        .filter(Order.id == request.order_id)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if str(order.status) not in CANCELLABLE_STATUSES:
        raise HTTPException(status_code=409, detail="订单状态已变化，不能取消")

    now = datetime.utcnow()
    # v6.3：师傅已出发/到达后因用户原因取消，默认收取空跑费；会员按权益免除。
    empty_run_fields = {}
    if str(order.status) in {"departing", "arrived"}:
        from app.services.order_service import DEFAULT_EMPTY_RUN_FEE_AMOUNT

        owner = db.query(User).filter(User.id == order.user_id).first()
        is_member = bool(owner and int(owner.member_level or 0) > 0)
        empty_run_fields = {
            "empty_run_fee_state": "waived" if is_member else "pending",
            "empty_run_fee_amount": (
                Decimal("0") if is_member else DEFAULT_EMPTY_RUN_FEE_AMOUNT
            ),
        }
    _cas_update_status(
        db,
        order,
        "cancelled",
        allowed_from=list(CANCELLABLE_STATUSES),
        cancelled_at=now,
        **empty_run_fields,
    )
    db.refresh(order)
    request.status = "approved"
    request.reviewed_by_admin_id = admin_id
    request.reviewed_at = now
    request.review_remark = (remark or "").strip() or None
    request.updated_at = now
    message_service.notify_cancel_result(db, order, request, approved=True)
    db.commit()
    db.refresh(request)
    return request


def reject_request(
    db: Session,
    admin_id: int,
    request_id: int,
    remark: str,
) -> OrderCancellationRequest:
    request = (
        db.query(OrderCancellationRequest)
        .filter(OrderCancellationRequest.id == request_id)
        .with_for_update()
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="取消申请不存在")
    if request.status != "pending":
        raise HTTPException(status_code=409, detail="取消申请已处理")

    order = db.query(Order).filter(Order.id == request.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    now = datetime.utcnow()
    request.status = "rejected"
    request.reviewed_by_admin_id = admin_id
    request.reviewed_at = now
    request.review_remark = (remark or "").strip() or None
    request.updated_at = now
    message_service.notify_cancel_result(db, order, request, approved=False)
    db.commit()
    db.refresh(request)
    return request

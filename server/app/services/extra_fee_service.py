"""现场补差价业务逻辑"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.extra_fee import OrderExtraFee
from app.models.order import Order


def apply_extra_fee(db: Session, worker_id: int, order_id: int,
                    items: List[dict], total_amount: int, reason: str,
                    photo_urls: List[str]) -> OrderExtraFee:
    """师傅申请补差价"""
    order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.worker_id != worker_id:
        raise HTTPException(status_code=403, detail="无权操作该订单")
    if order.status != "serving":
        raise HTTPException(status_code=409, detail="仅服务中订单允许申请补差价")

    # 网络重试发送完全相同的待处理申请时返回原记录，不重复计次。
    pending_items = db.query(OrderExtraFee).filter(
        OrderExtraFee.order_id == order_id,
        OrderExtraFee.worker_id == worker_id,
        OrderExtraFee.status == "pending",
    ).all()
    for pending in pending_items:
        if (
            pending.items == items
            and pending.total_amount == total_amount
            and pending.reason == reason
            and (pending.photo_urls or []) == (photo_urls or [])
        ):
            return pending

    # 校验次数上限
    count = db.query(OrderExtraFee).filter(
        OrderExtraFee.order_id == order_id,
    ).count()
    if count >= 2:
        raise HTTPException(status_code=400, detail="该订单补差价次数已达上限")

    # 校验金额上限
    # 请求与 OrderExtraFee 使用“分”，历史订单价格字段使用“元”。
    base_amount_cents = int(round(float(order.final_price or order.budget or 0) * 100))
    if total_amount <= 0:
        raise HTTPException(status_code=400, detail="补差价金额必须大于0")
    if total_amount > base_amount_cents * 0.5:
        raise HTTPException(status_code=400, detail="补差价金额不能超过原订单金额的50%")

    extra = OrderExtraFee(
        order_id=order_id,
        worker_id=worker_id,
        user_id=order.user_id,
        items=items,
        total_amount=total_amount,
        reason=reason,
        photo_urls=photo_urls,
        retry_count=count + 1,
    )
    db.add(extra)
    db.commit()
    db.refresh(extra)
    return extra


def approve_extra_fee(db: Session, user_id: int, order_id: int, extra_fee_id: int) -> OrderExtraFee:
    """用户同意补差价"""
    extra = db.query(OrderExtraFee).filter(
        OrderExtraFee.id == extra_fee_id,
        OrderExtraFee.order_id == order_id,
        OrderExtraFee.user_id == user_id,
    ).with_for_update().first()
    if not extra:
        raise HTTPException(status_code=404, detail="补差价记录不存在")
    if extra.status == "approved":
        return extra
    if extra.status != "pending":
        raise HTTPException(status_code=409, detail="该记录已按其他结果处理")

    extra.status = "approved"
    extra.resolved_at = datetime.utcnow()

    # 更新订单金额
    order = db.query(Order).filter(Order.id == extra.order_id).with_for_update().first()
    if order:
        order.final_price = Decimal(str(order.final_price or 0)) + (Decimal(extra.total_amount) / Decimal(100))
        order.version = int(order.version or 0) + 1

    db.commit()
    db.refresh(extra)
    return extra


def reject_extra_fee(db: Session, user_id: int, order_id: int, extra_fee_id: int, remark: str) -> OrderExtraFee:
    """用户拒绝补差价"""
    extra = db.query(OrderExtraFee).filter(
        OrderExtraFee.id == extra_fee_id,
        OrderExtraFee.order_id == order_id,
        OrderExtraFee.user_id == user_id,
    ).with_for_update().first()
    if not extra:
        raise HTTPException(status_code=404, detail="补差价记录不存在")
    if extra.status == "rejected" and extra.user_remark == remark:
        return extra
    if extra.status != "pending":
        raise HTTPException(status_code=409, detail="该记录已按其他结果处理")

    extra.status = "rejected"
    extra.user_remark = remark
    extra.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(extra)
    return extra


def get_extra_fee_list(db: Session, order_id: int) -> List[OrderExtraFee]:
    """查询订单的补差价记录"""
    return db.query(OrderExtraFee).filter(
        OrderExtraFee.order_id == order_id,
    ).order_by(OrderExtraFee.created_at.asc()).limit(10).all()


def get_overdue_pending_ids(db: Session, hours: int = 24) -> List[int]:
    """返回需提醒/升级的超时申请，不修改状态、金额或处理时间。"""
    deadline = datetime.utcnow() - timedelta(hours=hours)
    return [
        row[0]
        for row in db.query(OrderExtraFee.id).filter(
            OrderExtraFee.status == "pending",
            OrderExtraFee.created_at < deadline,
        ).order_by(OrderExtraFee.created_at.asc()).limit(500).all()
    ]

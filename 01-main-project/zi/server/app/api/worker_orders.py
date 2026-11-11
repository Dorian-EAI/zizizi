"""师傅订单路由（v6.3 契约路径 /api/worker/orders/*）"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_worker
from app.models.user import Worker
from app.schemas.order import (
    AcceptOrderRequest,
    BiddingRequest,
    OrderResponse,
)
from app.services import order_service
from app.utils.response import success

router = APIRouter(prefix="/api/worker", tags=["师傅订单"])


def _worker_order_payload(db: Session, order, worker: Worker) -> dict:
    data = OrderResponse.model_validate(order).model_dump(mode="json")
    data.update(order_service.build_order_projection(db, order, "worker", worker))
    return data


@router.post("/orders/{order_id}/accept")
async def accept_order(
    order_id: int,
    req: AcceptOrderRequest,
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """一口价/自己定价订单原子抢单。"""
    order = await order_service.accept_order(db, worker, order_id, req.version)
    return success(
        data=_worker_order_payload(db, order, worker),
        message="接单成功",
    )


@router.post("/orders/{order_id}/quotes")
async def submit_quote(
    order_id: int,
    req: BiddingRequest,
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """报价模式提交报价（v6.3 契约路径）。"""
    bidding = await order_service.create_bidding(db, worker, order_id, req)
    data = {
        "id": bidding.id,
        "order_id": bidding.order_id,
        "worker_id": bidding.worker_id,
        "worker_name": worker.nickname,
        "worker_avatar": worker.avatar,
        "worker_rating": worker.rating,
        "worker_service_count": worker.service_count,
        "price": bidding.price,
        "message": bidding.message,
        "eta": bidding.eta,
        "is_selected": bidding.is_selected,
        "created_at": bidding.created_at,
    }
    return success(data=data, message="报价已提交")

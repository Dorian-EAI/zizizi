"""订单相关路由"""

import re
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.database import get_db
from app.dependencies import get_current_user, get_current_worker, get_current_account
from app.models.user import User, Worker
from app.models.order import Order
from app.schemas.order import (
    CreateOrderRequest,
    BiddingRequest,
    SelectWorkerRequest,
    ReviewRequest,
    UpdateOrderStatusRequest,
    OrderResponse,
    AvailableOrderResponse,
)
from app.services import order_service, payment_service
from app.services.map_service import (
    calculate_distance,
    get_order_coords,
)
from app.utils.response import success

router = APIRouter(prefix="/api/orders", tags=["订单"])


_DIALABLE_PHONE_RE = re.compile(r"^\+?[0-9][0-9() -]{5,18}[0-9]$")


def _dialable_phone(value: object) -> Optional[str]:
    """Return an actual dialable number, never a masked placeholder."""
    phone = str(value or "").strip()
    if not phone or "*" in phone or not _DIALABLE_PHONE_RE.fullmatch(phone):
        return None
    digits = re.sub(r"\D", "", phone)
    return phone if 7 <= len(digits) <= 15 else None


def _get_order_or_404(db: Session, order_id: int) -> Order:
    """获取订单或抛 404"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


@router.post("")
async def create_order(
    req: CreateOrderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建订单（用户）"""
    order = order_service.create_order(db, user, req)
    data = OrderResponse.model_validate(order).model_dump(mode="json")
    return success(data=data, message="订单创建成功")


@router.get("")
async def list_orders(
    status: Optional[str] = Query(None, description="订单状态筛选"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取用户订单列表（用户）"""
    orders = order_service.get_client_orders(db, user.id, status)
    data = [OrderResponse.model_validate(o).model_dump(mode="json") for o in orders]
    return success(data=data)


@router.get("/{order_id}/payment-quote")
async def get_payment_quote(
    order_id: int,
    coupon_id: Optional[int] = Query(None, gt=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回短时有效的服务端权威应付金额与可用渠道。"""
    quote = payment_service.get_order_payment_quote(db, user, order_id, coupon_id)
    return success(data=quote)


@router.get("/available")
async def available_orders(
    lat: Optional[float] = Query(None, ge=-90, le=90, description="师傅当前纬度"),
    lng: Optional[float] = Query(None, ge=-180, le=180, description="师傅当前经度"),
    sort_by: Literal["created", "distance"] = Query(
        "created", description="排序: created=时间, distance=距离"
    ),
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """获取可抢订单（师傅）

    当传入 lat/lng 时，会计算每个订单与师傅的距离，支持按距离排序。
    """
    orders = order_service.get_available_orders(db, worker)

    result = []
    for o in orders:
        item = AvailableOrderResponse.model_validate(o).model_dump(mode="json")
        item["description"] = order_service.redact_public_description(
            item.get("description")
        )
        # 计算距离
        if lat is not None and lng is not None:
            order_lat, order_lng = get_order_coords(o.address or "")
            if order_lat is not None and order_lng is not None:
                dist_info = await run_in_threadpool(
                    calculate_distance,
                    lat,
                    lng,
                    order_lat,
                    order_lng,
                )
                item["distance_meters"] = dist_info["distance_meters"]
                item["distance_text"] = dist_info["distance_text"]
                item["duration_seconds"] = dist_info.get("duration_seconds")
                item["route_mode"] = dist_info.get("route_mode")
            else:
                item["distance_meters"] = None
                item["distance_text"] = "未知"
        else:
            item["distance_meters"] = None
            item["distance_text"] = None
        result.append(item)

    # 按距离排序
    if sort_by == "distance" and lat is not None and lng is not None:
        result.sort(key=lambda x: (x.get("distance_meters") is None,
                                   x.get("distance_meters") or float("inf")))

    return success(data=result)


@router.get("/worker")
async def worker_orders(
    status: Optional[str] = Query(None, description="订单状态筛选"),
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """获取师傅订单列表（师傅）"""
    orders = order_service.get_worker_orders(db, worker.id, status)
    data = [OrderResponse.model_validate(o).model_dump(mode="json") for o in orders]
    return success(data=data)


@router.get("/{order_id}")
async def get_order(
    order_id: int,
    account: tuple = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """获取订单详情（通用）

    安全说明：
    - 仅订单的所属用户、被指派的师傅可查看
    - 防止 IDOR 越权：任意用户传 order_id 即可查他人订单
    """
    order = _get_order_or_404(db, order_id)
    account_obj, account_type = account

    # 归属校验：仅订单所有者或被指派师傅可查看
    if account_type == "user" and order.user_id != account_obj.id:
        raise HTTPException(status_code=403, detail="无权查看此订单")
    if account_type == "worker" and order.worker_id != account_obj.id:
        raise HTTPException(status_code=403, detail="无权查看此订单")

    data = OrderResponse.model_validate(order).model_dump(mode="json")
    data.update(order_service.build_order_projection(db, order, account_type, account_obj))
    # 联系方式只在双方已经建立订单关系后，按当前查看角色单向放行。
    # 列表和可抢单接口不经过这里，因此永远不会携带联系方式。
    if account_type == "user" and order.worker_id is not None:
        assigned_worker = db.query(Worker).filter(Worker.id == order.worker_id).first()
        worker_phone = _dialable_phone(assigned_worker.phone if assigned_worker else None)
        if worker_phone:
            data["worker_phone"] = worker_phone
    elif account_type == "worker":
        owner = db.query(User).filter(User.id == order.user_id).first()
        user_phone = _dialable_phone(owner.phone if owner else None)
        if user_phone:
            data["user_phone"] = user_phone
    return success(data=data)


@router.post("/{order_id}/bidding")
async def create_bidding(
    order_id: int,
    req: BiddingRequest,
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """师傅竞价（师傅）"""
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
    return success(data=data, message="竞价成功")


@router.get("/{order_id}/biddings")
async def list_biddings(
    order_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取竞价列表（用户）

    安全说明：
    - 仅订单所属用户可查看其订单的竞价列表
    - 防止 IDOR 越权：泄露其他用户订单的所有竞价（师傅价格、留言、ETA）
    """
    order = _get_order_or_404(db, order_id)
    if order.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权查看此订单的竞价")

    data = order_service.get_biddings(db, order_id)
    return success(data=data)


@router.post("/{order_id}/select")
async def select_worker(
    order_id: int,
    req: SelectWorkerRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """选择师傅（用户）"""
    order = await order_service.select_worker(db, user, order_id, req.bidding_id)
    data = OrderResponse.model_validate(order).model_dump(mode="json")
    return success(data=data, message="已选择师傅")


@router.put("/{order_id}/status")
async def update_status(
    order_id: int,
    req: UpdateOrderStatusRequest,
    account: tuple = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """更新订单状态（通用）"""
    account_obj, account_type = account
    order = await order_service.update_order_status(
        db, account_obj, account_type, order_id, req.status, req.price
    )
    data = OrderResponse.model_validate(order).model_dump(mode="json")
    return success(data=data, message="状态更新成功")


@router.post("/{order_id}/review")
async def create_review(
    order_id: int,
    req: ReviewRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """评价订单（用户）"""
    order = order_service.create_review(db, user, order_id, req)
    data = OrderResponse.model_validate(order).model_dump(mode="json")
    return success(data=data, message="评价成功")

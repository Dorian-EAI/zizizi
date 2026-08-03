"""LBS轨迹 + 实时追踪 API"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_worker, get_current_account, get_current_user
from app.models.user import Worker, User
from app.models.order import Order
from app.schemas.lbs_track import CheckinRequest, LbsTrackResponse
from app.services import lbs_track_service
from app.services import realtime_track_service
from app.utils.response import success

router = APIRouter(tags=["LBS轨迹"])


def _require_order_access(db: Session, order_id: int, current):
    account, account_type = current
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="订单不存在")
    allowed = order.user_id == account.id if account_type == "user" else order.worker_id == account.id
    if not allowed:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="无权查看该订单")
    return order


# ============================================================
# 原有签到接口
# ============================================================

@router.post("/api/worker/orders/{order_id}/checkin")
async def worker_checkin(
    order_id: int,
    req: CheckinRequest,
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """师傅签到"""
    track = lbs_track_service.checkin(
        db, worker.id, order_id, req.node_type,
        req.latitude, req.longitude, req.address,
        req.photo_url, req.remark,
    )
    return success(data=LbsTrackResponse.model_validate(track).model_dump(mode="json"))


@router.post("/api/worker/orders/{order_id}/checkin-abnormal")
async def worker_checkin_abnormal(
    order_id: int,
    req: CheckinRequest,
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """强制签到（位置异常时）"""
    track = lbs_track_service.checkin(
        db, worker.id, order_id, req.node_type,
        req.latitude, req.longitude, req.address,
        req.photo_url, req.remark,
        force=True,
    )
    return success(data=LbsTrackResponse.model_validate(track).model_dump(mode="json"))


@router.get("/api/orders/{order_id}/track")
async def get_order_track(
    order_id: int,
    current=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """查询订单服务轨迹（签到记录）"""
    _require_order_access(db, order_id, current)
    tracks = lbs_track_service.get_track_by_order(db, order_id)
    return success(data=[LbsTrackResponse.model_validate(t).model_dump(mode="json") for t in tracks])


# ============================================================
# 实时位置追踪 — 类外卖派送
# ============================================================

class ReportLocationRequest(BaseModel):
    latitude: float
    longitude: float
    heading: Optional[float] = None
    speed: Optional[float] = None


@router.post("/api/worker/location/report")
async def report_location(
    req: ReportLocationRequest,
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """师傅上报实时位置

    师傅端在出发后每 10-15 秒调用一次。
    """
    result = realtime_track_service.report_location(
        db, worker.id, req.latitude, req.longitude, req.heading, req.speed
    )
    return success(data=result)


@router.post("/api/worker/orders/{order_id}/depart")
async def start_departure(
    order_id: int,
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """师傅点击出发 — 开始实时追踪"""
    result = realtime_track_service.start_departure(db, worker.id, order_id)

    # 推送通知给用户
    from app.services import message_service
    from app.models.order import Order
    order = db.query(Order).filter(Order.id == order_id).first()
    if order:
        await message_service.send_inbox_message(
            db, "user", order.user_id, "order",
            "师傅已出发",
            f"您的订单「{order.service_name}」师傅已出发，正在赶来",
            {"order_id": order_id, "status": "departing"},
        )

    return success(data=result, message="已出发")


@router.post("/api/worker/orders/{order_id}/arrive")
async def arrive_destination(
    order_id: int,
    req: ReportLocationRequest = None,
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """师傅点击到达"""
    lat = req.latitude if req else None
    lng = req.longitude if req else None
    result = realtime_track_service.arrive_destination(db, worker.id, order_id, lat, lng)

    # 推送通知给用户
    from app.services import message_service
    from app.models.order import Order
    order = db.query(Order).filter(Order.id == order_id).first()
    if order:
        await message_service.send_inbox_message(
            db, "user", order.user_id, "order",
            "师傅已到达",
            f"您的订单「{order.service_name}」师傅已到达服务地点，请准备开门",
            {"order_id": order_id, "status": "arrived"},
        )

    return success(data=result, message="已到达")


@router.post("/api/worker/orders/{order_id}/start-service")
async def start_service(
    order_id: int,
    req: ReportLocationRequest = None,
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """师傅点击开始服务"""
    lat = req.latitude if req else None
    lng = req.longitude if req else None
    result = realtime_track_service.start_service(db, worker.id, order_id, lat, lng)
    return success(data=result, message="服务已开始")


@router.get("/api/orders/{order_id}/tracking")
async def get_tracking_info(
    order_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用户端查询师傅实时位置（类似外卖追踪）

    返回师傅当前位置、ETA、剩余距离、历史轨迹路线、订单时间线。
    用户端每 10 秒轮询此接口。
    """
    _require_order_access(db, order_id, (user, "user"))
    result = realtime_track_service.get_tracking_info(db, order_id)
    return success(data=result)


@router.get("/api/orders/{order_id}/route-history")
async def get_route_history(
    order_id: int,
    limit: int = Query(100, ge=1, le=500),
    current=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """获取订单的完整位置历史轨迹"""
    _require_order_access(db, order_id, current)
    result = realtime_track_service.get_location_history(db, order_id, limit)
    return success(data=result)

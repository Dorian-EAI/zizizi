"""实时位置追踪服务 — 类外卖派送追踪

核心流程:
  师傅接单 → 师傅点击出发 → 实时上报位置 → 用户端轮询查看 → 师傅到达 → 开始服务 → 完成

位置上报: 师傅端每 10-15 秒调用一次上报接口
位置查询: 用户端每 10 秒轮询查询接口
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.lbs_track import WorkerLiveLocation, LocationHistory, OrderLbsTrack
from app.models.order import Order
from app.models.user import Worker
from app.services.order_service import _cas_update_status
from app.services.map_service import (
    calculate_distance,
    get_order_coords,
    haversine_distance_text,
)

logger = logging.getLogger(__name__)

# 上报间隔超过此秒数认为位置可能已过期
STALE_THRESHOLD_SECONDS = 60


def report_location(
    db: Session,
    worker_id: int,
    latitude: float,
    longitude: float,
    heading: Optional[float] = None,
    speed: Optional[float] = None,
) -> Dict[str, Any]:
    """师傅上报实时位置

    逻辑:
    1. 更新 worker_live_locations 表（覆盖更新）
    2. 插入 location_histories 记录（用于绘制路线）
    3. 如果有关联订单，重新计算 ETA 和剩余距离
    """
    now = datetime.utcnow()

    # 查找或创建实时位置记录
    live = db.query(WorkerLiveLocation).filter(
        WorkerLiveLocation.worker_id == worker_id
    ).first()

    if not live:
        active_order = db.query(Order).filter(
            Order.worker_id == worker_id,
            Order.status == "departing",
        ).order_by(Order.departed_at.desc()).first()
        live = WorkerLiveLocation(
            worker_id=worker_id,
            order_id=active_order.id if active_order else None,
            latitude=latitude,
            longitude=longitude,
            heading=heading,
            speed=speed,
            track_status="idle",
            last_reported_at=now,
        )
        db.add(live)
    else:
        live.latitude = latitude
        live.longitude = longitude
        live.heading = heading
        live.speed = speed
        live.last_reported_at = now

    # 如果有关联订单，计算 ETA
    eta_info = None
    if live.order_id:
        order = db.query(Order).filter(Order.id == live.order_id).first()
        if order and order.address:
            order_lat, order_lng = get_order_coords(order.address)
            if order_lat and order_lng:
                dist_result = calculate_distance(
                    latitude, longitude, order_lat, order_lng, mode="driving"
                )
                live.distance_meters = int(dist_result["distance_meters"])
                live.eta_seconds = dist_result.get("duration_seconds")

                eta_info = {
                    "distance_meters": live.distance_meters,
                    "distance_text": dist_result["distance_text"],
                    "eta_seconds": live.eta_seconds,
                    "eta_text": _format_eta(live.eta_seconds),
                    "route_mode": dist_result.get("route_mode"),
                }

                # 接近目的地自动更新状态
                if live.distance_meters and live.distance_meters < 200:
                    if live.track_status == "to_pickup":
                        live.track_status = "arriving"

    db.flush()

    # 插入历史记录（每次上报都记录，用于绘制路线）
    history = LocationHistory(
        worker_id=worker_id,
        order_id=live.order_id,
        latitude=latitude,
        longitude=longitude,
        heading=heading,
        speed=speed,
    )
    db.add(history)

    db.commit()

    return {
        "worker_id": worker_id,
        "latitude": latitude,
        "longitude": longitude,
        "heading": heading,
        "speed": speed,
        "track_status": live.track_status,
        "order_id": live.order_id,
        "eta": eta_info,
        "reported_at": now.isoformat(),
    }


def start_departure(db: Session, worker_id: int, order_id: int) -> Dict[str, Any]:
    """师傅点击「出发」— 开始实时位置追踪

    1. 更新订单状态为 departed
    2. 创建/更新实时位置记录，关联订单，状态设为 to_pickup
    3. 创建 LBS 签到节点 depart
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.worker_id != worker_id:
        raise HTTPException(status_code=403, detail="无权操作该订单")

    now = datetime.utcnow()

    # 更新订单状态（CAS）
    if order.status == "accepted":
        _cas_update_status(
            db,
            order,
            "departing",
            allowed_from=["accepted"],
            departed_at=now,
        )
    elif order.status != "departing":
        raise HTTPException(status_code=400, detail=f"订单状态 {order.status} 不可出发")

    # 更新实时位置
    live = db.query(WorkerLiveLocation).filter(
        WorkerLiveLocation.worker_id == worker_id
    ).first()

    if live:
        live.order_id = order_id
        live.track_status = "to_pickup"

    # 创建 LBS 签到节点（如果还没有）
    existing_depart = db.query(OrderLbsTrack).filter(
        OrderLbsTrack.order_id == order_id,
        OrderLbsTrack.node_type == "depart",
    ).first()

    if not existing_depart:
        depart_track = OrderLbsTrack(
            order_id=order_id,
            worker_id=worker_id,
            node_type="depart",
            latitude=live.latitude if live else None,
            longitude=live.longitude if live else None,
            remark="师傅已出发",
        )
        db.add(depart_track)

    db.commit()

    return {
        "order_id": order_id,
        "status": "departing",
        "departed_at": now.isoformat(),
        "track_status": "to_pickup",
        "message": "已出发，用户可实时查看您的位置",
    }


def arrive_destination(db: Session, worker_id: int, order_id: int,
                       latitude: Optional[float] = None,
                       longitude: Optional[float] = None) -> Dict[str, Any]:
    """师傅点击「到达」"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.worker_id != worker_id:
        raise HTTPException(status_code=403, detail="无权操作该订单")

    now = datetime.utcnow()
    _cas_update_status(
        db,
        order,
        "arrived",
        allowed_from=["departing"],
        arrived_at=now,
    )

    # 更新实时位置状态
    live = db.query(WorkerLiveLocation).filter(
        WorkerLiveLocation.worker_id == worker_id
    ).first()
    if live:
        live.track_status = "arriving"
        if latitude:
            live.latitude = latitude
        if longitude:
            live.longitude = longitude
        live.last_reported_at = now

    # 创建到达签到
    arrive_track = OrderLbsTrack(
        order_id=order_id,
        worker_id=worker_id,
        node_type="arrive",
        latitude=latitude or (live.latitude if live else None),
        longitude=longitude or (live.longitude if live else None),
        remark="师傅已到达",
    )
    db.add(arrive_track)

    db.commit()

    return {
        "order_id": order_id,
        "status": "arrived",
        "arrived_at": now.isoformat(),
        "message": "已到达服务地点",
    }


def start_service(db: Session, worker_id: int, order_id: int,
                  latitude: Optional[float] = None,
                  longitude: Optional[float] = None) -> Dict[str, Any]:
    """师傅点击「开始服务」"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.worker_id != worker_id:
        raise HTTPException(status_code=403, detail="无权操作该订单")

    now = datetime.utcnow()
    _cas_update_status(
        db,
        order,
        "serving",
        allowed_from=["arrived"],
        started_at=now,
    )

    # 更新实时位置
    live = db.query(WorkerLiveLocation).filter(
        WorkerLiveLocation.worker_id == worker_id
    ).first()
    if live:
        live.track_status = "serving"

    # 创建开工签到
    start_track = OrderLbsTrack(
        order_id=order_id,
        worker_id=worker_id,
        node_type="start",
        latitude=latitude or (live.latitude if live else None),
        longitude=longitude or (live.longitude if live else None),
        remark="开始服务",
    )
    db.add(start_track)

    db.commit()

    return {
        "order_id": order_id,
        "status": "serving",
        "started_at": now.isoformat(),
        "message": "服务已开始",
    }


def get_tracking_info(db: Session, order_id: int) -> Dict[str, Any]:
    """用户端查询师傅实时位置（类似外卖追踪）

    返回:
    - 师傅当前位置（经纬度、方向、速度）
    - 预估到达时间 ETA
    - 剩余距离
    - 追踪状态
    - 最近的历史轨迹点（用于绘制路线）
    - 师傅基本信息
    - 订单状态时间线
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if not order.worker_id:
        raise HTTPException(status_code=400, detail="师傅尚未接单")

    # 获取师傅实时位置
    live = db.query(WorkerLiveLocation).filter(
        WorkerLiveLocation.worker_id == order.worker_id
    ).first()

    # 获取师傅信息
    worker = db.query(Worker).filter(Worker.id == order.worker_id).first()

    # 判断位置是否新鲜
    is_stale = False
    if live and live.last_reported_at:
        age = (datetime.utcnow() - live.last_reported_at).total_seconds()
        is_stale = age > STALE_THRESHOLD_SECONDS

    # 获取历史轨迹（最近 50 个点，用于绘制路线）
    history = db.query(LocationHistory).filter(
        LocationHistory.worker_id == order.worker_id,
        LocationHistory.order_id == order_id,
    ).order_by(LocationHistory.created_at.desc()).limit(50).all()

    # 反转为时间正序
    history.reverse()

    history_points = [
        {
            "latitude": h.latitude,
            "longitude": h.longitude,
            "heading": h.heading,
            "speed": h.speed,
            "time": h.created_at.isoformat(),
        }
        for h in history
    ]

    # 构建时间线
    timeline = _build_timeline(order)

    # 订单目的地坐标
    dest_lat, dest_lng = get_order_coords(order.address or "")

    result = {
        "order_id": order_id,
        "order_status": order.status,
        "service_name": order.service_name,
        "timeline": timeline,

        # 师傅信息
        "worker": {
            "id": worker.id if worker else None,
            "name": worker.nickname if worker else "师傅",
            "avatar": worker.avatar if worker else None,
            "phone": worker.phone if worker else None,
            "rating": float(worker.rating) if worker and worker.rating else None,
        } if worker else None,

        # 实时位置
        "location": {
            "latitude": live.latitude if live else None,
            "longitude": live.longitude if live else None,
            "heading": live.heading if live else None,
            "speed": live.speed if live else None,
            "track_status": live.track_status if live else "idle",
            "last_reported_at": live.last_reported_at.isoformat() if live and live.last_reported_at else None,
            "is_stale": is_stale,
        } if live else None,

        # 预估信息
        "eta": {
            "distance_meters": live.distance_meters if live else None,
            "distance_text": haversine_distance_text(live.distance_meters) if live and live.distance_meters else None,
            "eta_seconds": live.eta_seconds if live else None,
            "eta_text": _format_eta(live.eta_seconds) if live else None,
        } if live and live.eta_seconds else None,

        # 目的地
        "destination": {
            "latitude": dest_lat,
            "longitude": dest_lng,
        } if dest_lat and dest_lng else None,

        # 历史轨迹路线
        "route_points": history_points,

        # 状态文案
        "status_text": _get_status_text(order.status, live.track_status if live else None),
    }

    return result


def get_location_history(db: Session, order_id: int, limit: int = 100) -> List[Dict]:
    """获取订单的完整位置历史轨迹"""
    items = db.query(LocationHistory).filter(
        LocationHistory.order_id == order_id,
    ).order_by(LocationHistory.created_at.asc()).limit(limit).all()

    return [
        {
            "latitude": h.latitude,
            "longitude": h.longitude,
            "heading": h.heading,
            "speed": h.speed,
            "time": h.created_at.isoformat(),
        }
        for h in items
    ]


def clear_tracking(db: Session, worker_id: int):
    """服务完成后清除实时位置关联"""
    live = db.query(WorkerLiveLocation).filter(
        WorkerLiveLocation.worker_id == worker_id
    ).first()
    if live:
        live.order_id = None
        live.track_status = "idle"
        live.eta_seconds = None
        live.distance_meters = None
    db.commit()


# ============================================================
# 工具函数
# ============================================================

def _format_eta(seconds: Optional[int]) -> Optional[str]:
    """格式化预估时间"""
    if not seconds:
        return None
    if seconds < 60:
        return "即将到达"
    minutes = seconds // 60
    if minutes < 1:
        return "即将到达"
    if minutes < 5:
        return f"约{minutes}分钟到达"
    return f"约{minutes}分钟"

def _get_status_text(order_status: str, track_status: Optional[str]) -> str:
    """生成用户友好的状态文案"""
    status_map = {
        "accepted": "师傅已接单，等待出发",
        "departing": "师傅正在赶来",
        "arrived": "师傅已到达",
        "serving": "师傅正在提供服务",
        "completed": "服务已完成",
        "paid": "订单已支付",
        "cancelled": "订单已取消",
    }

    if order_status == "departing" and track_status == "arriving":
        return "师傅即将到达，请准备开门"
    if order_status == "departing" and track_status == "to_pickup":
        return "师傅正在赶来"

    return status_map.get(order_status, order_status)


def _build_timeline(order: Order) -> List[Dict]:
    """构建订单时间线"""
    timeline = []
    if order.accepted_at:
        timeline.append({"status": "accepted", "text": "师傅接单", "time": order.accepted_at.isoformat()})
    if order.departed_at:
        timeline.append({"status": "departing", "text": "师傅出发", "time": order.departed_at.isoformat()})
    if order.arrived_at:
        timeline.append({"status": "arrived", "text": "师傅到达", "time": order.arrived_at.isoformat()})
    if order.started_at:
        timeline.append({"status": "serving", "text": "开始服务", "time": order.started_at.isoformat()})
    if order.completed_at:
        timeline.append({"status": "completed", "text": "服务完成", "time": order.completed_at.isoformat()})
    if order.paid_at:
        timeline.append({"status": "paid", "text": "已支付", "time": order.paid_at.isoformat()})
    return timeline

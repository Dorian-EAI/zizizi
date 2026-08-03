"""LBS服务轨迹业务逻辑"""

import math
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.lbs_track import OrderLbsTrack
from app.models.order import Order
from app.services.map_service import calculate_distance, get_order_coords


def validate_geo_fence(order_lat: float, order_lng: float,
                       check_lat: float, check_lng: float,
                       threshold_meters: int = 500) -> dict:
    """地理围栏校验

    使用 map_service 计算距离：
    - 配置了高德/腾讯 API 时走驾车距离（更准确）
    - 未配置时走 Haversine 直线距离
    """
    result = calculate_distance(check_lat, check_lng, order_lat, order_lng, mode="driving")
    distance = result["distance_meters"]
    return {
        "distance_meters": int(distance),
        "is_abnormal": distance > threshold_meters,
        "threshold": threshold_meters,
        "route_mode": result.get("route_mode", "haversine"),
        "duration_seconds": result.get("duration_seconds"),
    }


def checkin(db: Session, worker_id: int, order_id: int, node_type: str,
            latitude: Optional[float], longitude: Optional[float],
            address: Optional[str], photo_url: Optional[str],
            remark: Optional[str], force: bool = False) -> OrderLbsTrack:
    """师傅签到"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.worker_id != worker_id:
        raise HTTPException(status_code=403, detail="无权操作该订单")

    # 校验节点顺序
    existing = db.query(OrderLbsTrack).filter(
        OrderLbsTrack.order_id == order_id,
    ).order_by(OrderLbsTrack.created_at.asc()).all()

    node_sequence = ["depart", "arrive", "start", "finish", "user_confirm"]
    if node_type not in node_sequence:
        raise HTTPException(status_code=400, detail="无效的节点类型")

    current_idx = node_sequence.index(node_type)
    for node in existing:
        if node.node_type == node_type:
            raise HTTPException(status_code=400, detail=f"该节点已签到: {node_type}")

    # 校验前置节点
    if current_idx > 0:
        prev_type = node_sequence[current_idx - 1]
        found_prev = any(n.node_type == prev_type for n in existing)
        if not found_prev:
            raise HTTPException(status_code=400, detail=f"请先完成前置签到: {prev_type}")

    # 地理围栏校验（到达/开工/完工时）
    is_abnormal = False
    distance_meters = None
    if node_type in ("arrive", "start", "finish") and latitude and longitude:
        if order.address:
            try:
                import json
                addr = json.loads(order.address)
                order_lat = addr.get("latitude")
                order_lng = addr.get("longitude")
                if order_lat and order_lng:
                    result = validate_geo_fence(order_lat, order_lng, latitude, longitude)
                    distance_meters = result["distance_meters"]
                    is_abnormal = result["is_abnormal"]
                    if is_abnormal and not force:
                        raise HTTPException(
                            status_code=400,
                            detail=f"距离服务地点约{distance_meters}米，似乎还未到达。如需强制签到请使用强制签到接口。"
                        )
            except HTTPException:
                raise
            except (TypeError, ValueError, KeyError):
                # 历史地址可能不是合法 JSON；无法取得坐标时保留签到，但不伪造围栏结果。
                distance_meters = None
                is_abnormal = False

    track = OrderLbsTrack(
        order_id=order_id,
        worker_id=worker_id,
        node_type=node_type,
        latitude=latitude,
        longitude=longitude,
        address=address,
        distance_meters=distance_meters,
        is_abnormal=is_abnormal,
        photo_url=photo_url,
        remark=remark,
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


def get_track_by_order(db: Session, order_id: int) -> List[OrderLbsTrack]:
    """查询订单完整轨迹"""
    return db.query(OrderLbsTrack).filter(
        OrderLbsTrack.order_id == order_id,
    ).order_by(OrderLbsTrack.created_at.asc()).all()

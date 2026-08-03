"""订单业务扩展（封装 rating 重算、距离排序等工具调用入口）"""

from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from app.models.user import Worker
from app.models.order import Order


def recalc_worker_rating_after_review(db: Session, worker_id: int) -> Optional[Worker]:
    """用户评价后重新计算师傅综合评分并写回 worker.rating"""
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        return None

    from app.utils.rating import calc_worker_rating
    new_rating = calc_worker_rating(db, worker)
    worker.rating = new_rating
    db.commit()
    db.refresh(worker)
    return worker


def get_worker_stats_summary(db: Session, worker_id: int) -> Dict[str, Any]:
    """获取师傅统计信息（评分+标签+完成率+响应速度）"""
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        return {}

    from app.utils.rating import (
        calc_worker_rating,
        summarize_review_tags,
        calc_service_completion_rate,
        respond_speed_minutes,
    )

    return {
        "worker_id": worker.id,
        "rating": calc_worker_rating(db, worker),
        "review_tags": summarize_review_tags(db, worker_id),
        "completion_rate": calc_service_completion_rate(db, worker_id),
        "respond_speed_minutes": respond_speed_minutes(db, worker_id),
        "service_count": worker.service_count or 0,
    }


def sort_workers_by_distance(
    workers: List[Worker],
    my_lat: float,
    my_lng: float,
    radius_km: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """根据用户位置按距离过滤并排序师傅列表
    workers: Worker 实例列表（需带 location_lat/lng 或通过 skill/service_area 查询，此处转 dict）
    """
    from app.utils.distance import filter_within_radius, haversine_km

    worker_dicts = []
    for w in workers:
        d = {
            "id": w.id,
            "nickname": w.nickname,
            "avatar": w.avatar,
            "rating": w.rating,
            "service_count": w.service_count,
            "lat": None,
            "lng": None,
        }
        if hasattr(w, "location_lat"):
            d["lat"] = getattr(w, "location_lat")
            d["lng"] = getattr(w, "location_lng")
        worker_dicts.append(d)

    if radius_km is not None:
        return filter_within_radius(worker_dicts, my_lat, my_lng, radius_km)

    for wd in worker_dicts:
        if wd["lat"] is not None and wd["lng"] is not None:
            wd["distance_km"] = round(haversine_km(my_lat, my_lng, wd["lat"], wd["lng"]), 2)
        else:
            wd["distance_km"] = None
    worker_dicts.sort(key=lambda x: (x["distance_km"] is None, x["distance_km"] or 0))
    return worker_dicts

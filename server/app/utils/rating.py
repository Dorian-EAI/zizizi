"""师傅评分算法工具"""

import json
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.user import Worker
from app.models.order import Order, Bidding


def calc_worker_rating(db: Session, worker: Worker) -> float:
    """
    计算师傅综合评分（0-5，一位小数）
    - 近 7 天评分 × 0.2
    - 近 30 天评分 × 0.3
    - 90 天内剩余 × 0.5
    - 服务次数 > 100 → +0.1（封顶 5.0）
    """
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)
    ninety_days_ago = now - timedelta(days=90)

    orders = (
        db.query(Order)
        .filter(
            Order.worker_id == worker.id,
            Order.rating.isnot(None),
            Order.created_at >= ninety_days_ago,
        )
        .all()
    )

    if not orders:
        return 5.0

    sum_7d = 0.0
    count_7d = 0
    sum_30d = 0.0
    count_30d = 0
    sum_90d = 0.0
    count_90d = 0

    for o in orders:
        rating = float(o.rating or 0)
        created = o.created_at or now

        if created >= seven_days_ago:
            sum_7d += rating
            count_7d += 1
        elif created >= thirty_days_ago:
            sum_30d += rating
            count_30d += 1
        else:
            sum_90d += rating
            count_90d += 1

    avg_7d = (sum_7d / count_7d) if count_7d > 0 else None
    avg_30d = (sum_30d / count_30d) if count_30d > 0 else None
    avg_90d = (sum_90d / count_90d) if count_90d > 0 else None

    weights = [0.2, 0.3, 0.5]
    avgs = [avg_7d, avg_30d, avg_90d]

    weighted_sum = 0.0
    weight_used = 0.0
    for i, avg in enumerate(avgs):
        if avg is not None:
            weighted_sum += avg * weights[i]
            weight_used += weights[i]

    if weight_used > 0:
        final = weighted_sum / weight_used
    else:
        final = 5.0

    service_count = worker.service_count or 0
    if service_count > 100:
        final = min(5.0, final + 0.1)

    final = max(0.0, min(5.0, final))
    return round(final, 1)


def summarize_review_tags(db: Session, worker_id: int) -> Dict[str, int]:
    """汇总师傅的评价标签计数"""
    orders = (
        db.query(Order)
        .filter(
            Order.worker_id == worker_id,
            Order.review_tags.isnot(None),
        )
        .all()
    )

    tag_counts: Dict[str, int] = defaultdict(int)
    for o in orders:
        try:
            tags = o.review_tags
            if isinstance(tags, str):
                tags = json.loads(tags)
            if isinstance(tags, list):
                for t in tags:
                    tag_name = str(t).strip()
                    if tag_name:
                        tag_counts[tag_name] += 1
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    return dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True))


def calc_service_completion_rate(db: Session, worker_id: int) -> float:
    """计算服务完成率：(接受订单数 - 师傅取消数) / 接受总数"""
    accepted_orders = (
        db.query(Order)
        .filter(
            Order.worker_id == worker_id,
            Order.status.in_(["accepted", "completed", "paid", "reviewed", "cancelled"]),
        )
        .all()
    )

    total = len(accepted_orders)
    if total == 0:
        return 1.0

    worker_cancelled = 0
    for o in accepted_orders:
        if o.status == "cancelled":
            worker_cancelled += 1

    completed = total - worker_cancelled
    rate = completed / total if total > 0 else 1.0
    return round(max(0.0, min(1.0, rate)), 2)


def respond_speed_minutes(db: Session, worker_id: int) -> float:
    """计算平均响应分钟数：Bidding.created_at - Order.created_at 的均值"""
    biddings = (
        db.query(Bidding)
        .filter(Bidding.worker_id == worker_id)
        .all()
    )

    if not biddings:
        return 0.0

    total_minutes = 0.0
    count = 0

    for b in biddings:
        order = db.query(Order).filter(Order.id == b.order_id).first()
        if not order or not order.created_at or not b.created_at:
            continue
        delta = b.created_at - order.created_at
        minutes = delta.total_seconds() / 60.0
        if minutes >= 0:
            total_minutes += minutes
            count += 1

    if count == 0:
        return 0.0

    return round(total_minutes / count, 1)

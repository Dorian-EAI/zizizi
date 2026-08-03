"""评论/评价业务逻辑

- 评价自动同步（从 Order 创建时触发）
- 评价审核（运营后台）
- 评价列表查询（带过滤、排序）
- 评价统计与精炼
- 师傅回复
- 点赞
"""

import json
from typing import List, Optional
from collections import Counter

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.review import Review, ReviewLike
from app.models.order import Order
from app.schemas.review import ReviewCreateRequest, ReviewAuditRequest


def sync_review_from_order(db: Session, order: Order) -> Review:
    """从订单评价字段自动同步到 Review 表

    在 order_service.create_review() 成功提交后调用。
    """
    existing = db.query(Review).filter(Review.order_id == order.id).first()
    if existing:
        return existing

    tags = []
    if order.review_tags:
        try:
            tags = json.loads(order.review_tags)
        except Exception:
            pass

    images = []
    if order.review_images:
        try:
            images = json.loads(order.review_images)
        except Exception:
            pass

    review = Review(
        order_id=order.id,
        user_id=order.user_id,
        worker_id=order.worker_id,
        service_type=order.service_type,
        rating=order.rating or 5,
        review_tags=json.dumps(tags, ensure_ascii=False) if tags else None,
        review_content=order.review_content,
        review_images=json.dumps(images, ensure_ascii=False) if images else None,
        is_anonymous=order.is_anonymous or False,
        status="pending",  # 默认待审核
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def get_reviews(
    db: Session,
    worker_id: Optional[int] = None,
    service_type: Optional[str] = None,
    rating: Optional[int] = None,
    tag: Optional[str] = None,
    status: str = "approved",
    page: int = 1,
    size: int = 10,
) -> tuple:
    """获取评价列表（分页）

    Returns: (reviews_list, total_count)
    """
    q = db.query(Review)
    if worker_id:
        q = q.filter(Review.worker_id == worker_id)
    if service_type:
        q = q.filter(Review.service_type == service_type)
    if rating:
        q = q.filter(Review.rating == rating)
    if status:
        q = q.filter(Review.status == status)
    if tag:
        q = q.filter(Review.review_tags.like(f'%"{tag}"%'))

    total = q.count()
    reviews = (
        q.order_by(Review.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return reviews, total


def get_review_detail(db: Session, review_id: int) -> Review:
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="评价不存在")
    return review


def audit_review(
    db: Session,
    review_id: int,
    req: ReviewAuditRequest,
    admin_id: int,
) -> Review:
    """审核评价"""
    review = get_review_detail(db, review_id)
    if review.status != "pending":
        raise HTTPException(status_code=400, detail="该评价已审核过")

    if req.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="审核状态必须为 approved 或 rejected")

    review.status = req.status
    review.reviewed_by = admin_id
    review.reviewed_at = datetime.utcnow()
    if req.status == "rejected":
        review.reject_reason = req.reject_reason or "内容不符合规范"

    db.commit()
    db.refresh(review)
    return review


def worker_reply(db: Session, review_id: int, worker_id: int, reply: str) -> Review:
    """师傅回复评价"""
    review = get_review_detail(db, review_id)
    if review.worker_id != worker_id:
        raise HTTPException(status_code=403, detail="无权回复该评价")
    if review.status != "approved":
        raise HTTPException(status_code=400, detail="评价未通过审核，无法回复")

    review.worker_reply = reply
    review.worker_reply_at = datetime.utcnow()
    db.commit()
    db.refresh(review)
    return review


def toggle_like(db: Session, review_id: int, user_id: int) -> dict:
    """点赞/取消点赞"""
    review = get_review_detail(db, review_id)
    if review.status != "approved":
        raise HTTPException(status_code=400, detail="评价未通过审核")

    existing = (
        db.query(ReviewLike)
        .filter(ReviewLike.review_id == review_id, ReviewLike.user_id == user_id)
        .first()
    )

    if existing:
        db.delete(existing)
        review.like_count = max(0, (review.like_count or 0) - 1)
        liked = False
    else:
        db.add(ReviewLike(review_id=review_id, user_id=user_id))
        review.like_count = (review.like_count or 0) + 1
        liked = True

    db.commit()
    return {"liked": liked, "like_count": review.like_count}


def get_review_stats(db: Session, worker_id: Optional[int] = None, service_type: Optional[str] = None) -> dict:
    """获取评价统计数据"""
    q = db.query(Review).filter(Review.status == "approved")
    if worker_id:
        q = q.filter(Review.worker_id == worker_id)
    if service_type:
        q = q.filter(Review.service_type == service_type)

    total = q.count()
    if total == 0:
        return {
            "total_count": 0,
            "avg_rating": 0.0,
            "rating_5_count": 0,
            "rating_4_count": 0,
            "rating_3_count": 0,
            "rating_2_count": 0,
            "rating_1_count": 0,
            "tag_counts": [],
            "highlight_summary": None,
        }

    avg_rating = q.with_entities(func.avg(Review.rating)).scalar() or 0

    rating_counts = {}
    for r in range(1, 6):
        rating_counts[r] = q.filter(Review.rating == r).count()

    # 标签聚合
    all_tags = []
    reviews_with_tags = q.filter(Review.review_tags.isnot(None)).all()
    for rv in reviews_with_tags:
        try:
            tags = json.loads(rv.review_tags)
            if isinstance(tags, list):
                all_tags.extend(tags)
        except Exception:
            pass

    tag_counts = [{"tag": tag, "count": cnt} for tag, cnt in Counter(all_tags).most_common(10)]

    # 取已有的 highlight_summary 或生成默认
    summary = None
    if worker_id:
        latest = q.filter(Review.highlight_summary.isnot(None)).order_by(Review.created_at.desc()).first()
        if latest:
            summary = latest.highlight_summary

    return {
        "total_count": total,
        "avg_rating": round(float(avg_rating), 2),
        "rating_5_count": rating_counts.get(5, 0),
        "rating_4_count": rating_counts.get(4, 0),
        "rating_3_count": rating_counts.get(3, 0),
        "rating_2_count": rating_counts.get(2, 0),
        "rating_1_count": rating_counts.get(1, 0),
        "tag_counts": tag_counts,
        "highlight_summary": summary,
    }


def generate_highlight_summary(db: Session, worker_id: int) -> Optional[str]:
    """为师傅生成评价精炼摘要（基于标签和关键词）

    简单实现：取高频标签拼接。
    后续可接入 AI 大模型做真正语义摘要。
    """
    stats = get_review_stats(db, worker_id=worker_id)
    tag_counts = stats.get("tag_counts", [])
    if not tag_counts:
        return None

    top_tags = [t["tag"] for t in tag_counts[:5]]
    if not top_tags:
        return None

    summary = f"用户一致称赞：{ '、'.join(top_tags) }"
    return summary


def update_highlight_summary(db: Session, worker_id: int, summary: Optional[str] = None) -> None:
    """更新师傅最新评价的摘要字段"""
    if summary is None:
        summary = generate_highlight_summary(db, worker_id)
    if not summary:
        return

    latest = (
        db.query(Review)
        .filter(Review.worker_id == worker_id, Review.status == "approved")
        .order_by(Review.created_at.desc())
        .first()
    )
    if latest:
        latest.highlight_summary = summary
        db.commit()


def get_my_reviews(
    db: Session,
    user_id: int,
    status: Optional[str] = None,
    page: int = 1,
    size: int = 10,
) -> tuple:
    """获取用户自己发表的评价列表"""
    q = db.query(Review).filter(Review.user_id == user_id)
    if status:
        q = q.filter(Review.status == status)
    total = q.count()
    reviews = (
        q.order_by(Review.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return reviews, total


def auto_approve_pending_reviews(db: Session, hours: int = 24) -> int:
    """自动审核通过 pending 超过指定小时数的评价"""
    from datetime import datetime, timedelta
    deadline = datetime.utcnow() - timedelta(hours=hours)
    pending = db.query(Review).filter(
        Review.status == "pending",
        Review.created_at < deadline,
    ).all()
    count = 0
    for review in pending:
        review.status = "approved"
        review.reviewed_at = datetime.utcnow()
        count += 1
    if count > 0:
        db.commit()
        for r in pending:
            if r.worker_id:
                update_highlight_summary(db, r.worker_id)
    return count


from datetime import datetime

"""收藏师傅业务逻辑"""

from typing import List, Optional
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User, Worker
from app.models.favorite import FavoriteWorker
from app.models.order import Order


def is_favorited(db: Session, user_id: int, worker_id: int) -> bool:
    """检查是否已收藏"""
    return (
        db.query(FavoriteWorker)
        .filter(FavoriteWorker.user_id == user_id, FavoriteWorker.worker_id == worker_id)
        .first() is not None
    )


def toggle_favorite(db: Session, user: User, worker_id: int) -> dict:
    """切换收藏状态：有就删，没有就加"""
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="师傅不存在")

    existing = (
        db.query(FavoriteWorker)
        .filter(FavoriteWorker.user_id == user.id, FavoriteWorker.worker_id == worker_id)
        .first()
    )

    if existing:
        db.delete(existing)
        db.commit()
        return {"is_favorite": False}
    else:
        fav = FavoriteWorker(user_id=user.id, worker_id=worker_id)
        db.add(fav)
        db.commit()
        return {"is_favorite": True}


def list_favorites(db: Session, user: User) -> List[dict]:
    """获取用户收藏的师傅列表，联表 Worker"""
    favs = (
        db.query(FavoriteWorker)
        .filter(FavoriteWorker.user_id == user.id)
        .order_by(FavoriteWorker.created_at.desc())
        .all()
    )

    result: List[dict] = []
    for fav in favs:
        worker = db.query(Worker).filter(Worker.id == fav.worker_id).first()
        if not worker:
            continue
        result.append({
            "worker_id": worker.id,
            "nickname": worker.nickname,
            "avatar": worker.avatar,
            "rating": worker.rating,
            "service_count": worker.service_count,
            "is_favorite": True,
            "created_at": fav.created_at,
        })
    return result


def get_worker_detail(db: Session, worker_id: int, current_user_id: Optional[int] = None) -> dict:
    """获取师傅详情页数据"""
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="师傅不存在")

    import json

    recent_reviews = (
        db.query(Order)
        .filter(Order.worker_id == worker_id, Order.rating.isnot(None))
        .order_by(Order.reviewed_at.desc())
        .limit(10)
        .all()
    )
    reviews = []
    for o in recent_reviews:
        reviews.append({
            "rating": o.rating,
            "review_content": o.review_content,
            "reviewed_at": o.reviewed_at,
            "review_tags": json.loads(o.review_tags) if o.review_tags else None,
        })

    favorited = is_favorited(db, current_user_id, worker_id) if current_user_id else False

    skills = json.loads(worker.skills) if worker.skills else []

    return {
        "id": worker.id,
        "nickname": worker.nickname,
        "avatar": worker.avatar,
        "rating": worker.rating,
        "service_count": worker.service_count,
        "real_name": worker.real_name,
        "skills": skills,
        "level": worker.level,
        "certified": worker.certified,
        "recent_reviews": reviews,
        "is_favorited": favorited,
    }

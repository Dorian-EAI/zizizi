"""意见反馈业务逻辑"""

import json
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.feedback import Feedback


ALLOWED_TYPES = {"suggestion", "bug", "complaint", "other"}
ALLOWED_STATUS = {"pending", "processing", "resolved"}


def submit(db: Session, user_or_none: Optional[User], data: dict) -> Feedback:
    """提交反馈（已登录或匿名均可）"""
    ftype = data.get("type", "").strip().lower()
    if ftype not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"反馈类型不合法，可选值: {', '.join(sorted(ALLOWED_TYPES))}")

    content = (data.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="请填写反馈内容")
    if len(content) > 2000:
        raise HTTPException(status_code=400, detail="反馈内容过长（最多 2000 字）")

    images = data.get("images") or []
    if not isinstance(images, list):
        images = []

    fb = Feedback(
        user_id=user_or_none.id if user_or_none else None,
        type=ftype,
        content=content,
        images=json.dumps(images, ensure_ascii=False) if images else None,
        contact=(data.get("contact") or None),
        status="pending",
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


def _fb_to_dict(fb: Feedback) -> dict:
    return {
        "id": fb.id,
        "type": fb.type,
        "content": fb.content,
        "images": json.loads(fb.images) if fb.images else [],
        "contact": fb.contact,
        "status": fb.status,
        "reply": fb.reply,
        "created_at": fb.created_at,
        "updated_at": fb.updated_at,
    }


def my_feedback(db: Session, user: User, page: int = 1, size: int = 20) -> dict:
    """获取当前用户提交的反馈（分页）"""
    page = max(page, 1)
    size = max(min(size, 100), 1)
    offset = (page - 1) * size

    q = db.query(Feedback).filter(Feedback.user_id == user.id)
    total = q.count()
    items = q.order_by(Feedback.created_at.desc()).offset(offset).limit(size).all()
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [_fb_to_dict(x) for x in items],
    }


def list_all(db: Session, page: int = 1, size: int = 20, status: Optional[str] = None) -> dict:
    """管理员获取全量反馈列表（可按状态筛选）"""
    page = max(page, 1)
    size = max(min(size, 200), 1)
    offset = (page - 1) * size

    q = db.query(Feedback)
    if status:
        if status not in ALLOWED_STATUS:
            raise HTTPException(status_code=400, detail=f"状态不合法，可选值: {', '.join(sorted(ALLOWED_STATUS))}")
        q = q.filter(Feedback.status == status)

    total = q.count()
    items = q.order_by(Feedback.created_at.desc()).offset(offset).limit(size).all()
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [_fb_to_dict(x) for x in items],
    }


def update_status(db: Session, fb_id: int, status: str, reply: Optional[str] = None) -> Feedback:
    """管理员更新反馈状态与回复"""
    status = (status or "").strip().lower()
    if status not in ALLOWED_STATUS:
        raise HTTPException(status_code=400, detail=f"状态不合法，可选值: {', '.join(sorted(ALLOWED_STATUS))}")

    fb = db.query(Feedback).filter(Feedback.id == fb_id).first()
    if not fb:
        raise HTTPException(status_code=404, detail="反馈记录不存在")

    fb.status = status
    if reply is not None:
        fb.reply = reply
    db.commit()
    db.refresh(fb)
    return fb

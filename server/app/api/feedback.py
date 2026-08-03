"""意见反馈相关路由"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, Query, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_current_admin
from app.models.user import User
from app.schemas.feedback import FeedbackCreateRequest, FeedbackUpdateRequest
from app.services import feedback_service
from app.utils.response import success

router = APIRouter(prefix="/api/feedback", tags=["意见反馈"])


def _try_get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """尝试解析用户，未登录则返回 None（允许匿名提交）"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        from app.utils.security import decode_access_token
        token = authorization.replace("Bearer ", "")
        payload = decode_access_token(token)
        if not payload or "sub" not in payload or payload.get("type", "user") != "user":
            return None
        user_id = int(payload["sub"])
        return db.query(User).filter(User.id == user_id).first()
    except Exception:
        return None


def _fb_to_dict(fb):
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


@router.post("")
async def submit_feedback(
    req: FeedbackCreateRequest,
    user: Optional[User] = Depends(_try_get_current_user),
    db: Session = Depends(get_db),
):
    """提交意见反馈（支持匿名，登录会自动关联 user_id）"""
    fb = feedback_service.submit(db, user, req.model_dump())
    return success(data=_fb_to_dict(fb), message="反馈提交成功，感谢您的意见")


@router.get("/mine")
async def my_feedback_list(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页条数"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的反馈记录"""
    data = feedback_service.my_feedback(db, user, page=page, size=size)
    return success(data=data)


@router.get("")
async def list_all_feedback(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=200, description="每页条数"),
    status: Optional[str] = Query(None, description="状态筛选 pending/processing/resolved"),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """管理员：获取全部反馈（可按状态筛选）"""
    data = feedback_service.list_all(db, page=page, size=size, status=status)
    return success(data=data)


@router.put("/{fb_id}")
async def update_feedback(
    fb_id: int,
    body: FeedbackUpdateRequest,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """管理员：更新反馈状态与回复"""
    fb = feedback_service.update_status(db, fb_id, body.status, body.reply)
    return success(data=_fb_to_dict(fb), message="反馈已更新")

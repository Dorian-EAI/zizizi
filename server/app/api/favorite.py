"""收藏师傅相关路由"""

from typing import Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services import favorite_service
from app.utils.response import success

router = APIRouter(prefix="/api/favorite", tags=["收藏"])


@router.post("/worker/{worker_id}")
async def toggle_worker_favorite(
    worker_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """切换收藏师傅"""
    data = favorite_service.toggle_favorite(db, user, worker_id)
    msg = "收藏成功" if data["is_favorite"] else "已取消收藏"
    return success(data=data, message=msg)


@router.get("/workers")
async def list_favorite_workers(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取收藏的师傅列表"""
    data = favorite_service.list_favorites(db, user)
    return success(data=data)


@router.get("/workers/exists/{worker_id}")
async def check_favorite_exists(
    worker_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """检查是否已收藏某师傅"""
    exists = favorite_service.is_favorited(db, user.id, worker_id)
    return success(data={"exists": exists})


@router.get("/workers/{worker_id}")
async def get_worker_detail(
    worker_id: int,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """师傅详情页（登录后会带 is_favorited）"""
    from app.utils.security import decode_access_token

    current_user_id = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        payload = decode_access_token(token)
        if payload and "sub" in payload and payload.get("type", "user") == "user":
            current_user_id = int(payload["sub"])

    data = favorite_service.get_worker_detail(db, worker_id, current_user_id)
    return success(data=data)

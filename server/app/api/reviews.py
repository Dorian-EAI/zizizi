"""评论/评价相关路由"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import (
    get_current_user,
    get_current_worker,
    get_current_account,
    get_current_admin,
    require_admin_operator,
)
from app.models.user import User, Worker
from app.schemas.review import ReviewAuditRequest, WorkerReplyRequest
from app.services import review_service
from app.utils.response import success

router = APIRouter(prefix="/api/reviews", tags=["评价"])


@router.get("")
async def list_reviews(
    worker_id: Optional[int] = Query(None),
    service_type: Optional[str] = Query(None),
    rating: Optional[int] = Query(None),
    tag: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """获取评价列表（公开，只展示已通过审核的）"""
    reviews, total = review_service.get_reviews(
        db,
        worker_id=worker_id,
        service_type=service_type,
        rating=rating,
        tag=tag,
        status="approved",
        page=page,
        size=size,
    )
    data = []
    for r in reviews:
        tags = []
        images = []
        try:
            import json
            if r.review_tags:
                tags = json.loads(r.review_tags)
            if r.review_images:
                images = json.loads(r.review_images)
        except Exception:
            pass
        data.append({
            "id": r.id,
            "order_id": r.order_id,
            "user_id": r.user_id,
            "worker_id": r.worker_id,
            "service_type": r.service_type,
            "rating": r.rating,
            "review_tags": tags,
            "review_content": r.review_content,
            "review_images": images,
            "is_anonymous": r.is_anonymous,
            "worker_reply": r.worker_reply,
            "worker_reply_at": r.worker_reply_at,
            "like_count": r.like_count,
            "highlight_summary": r.highlight_summary,
            "created_at": r.created_at,
        })
    return success(data={"list": data, "total": total, "page": page, "size": size})


@router.get("/stats")
async def review_stats(
    worker_id: Optional[int] = Query(None),
    service_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """获取评价统计数据（公开）"""
    stats = review_service.get_review_stats(db, worker_id=worker_id, service_type=service_type)
    return success(data=stats)


@router.post("/{review_id}/reply")
async def reply_review(
    review_id: int,
    req: WorkerReplyRequest,
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """师傅回复评价"""
    review = review_service.worker_reply(db, review_id, worker.id, req.reply)
    return success(data={"id": review.id, "worker_reply": review.worker_reply}, message="回复成功")


@router.post("/{review_id}/like")
async def like_review(
    review_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """点赞/取消点赞"""
    result = review_service.toggle_like(db, review_id, user.id)
    return success(data=result, message="操作成功")


@router.get("/mine")
async def my_reviews(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的评价列表（用户登录态）"""
    reviews, total = review_service.get_my_reviews(db, user.id, status, page, size)
    data = []
    for r in reviews:
        tags = []
        images = []
        try:
            import json
            if r.review_tags:
                tags = json.loads(r.review_tags)
            if r.review_images:
                images = json.loads(r.review_images)
        except Exception:
            pass
        data.append({
            "id": r.id, "order_id": r.order_id,
            "worker_id": r.worker_id, "service_type": r.service_type,
            "rating": r.rating, "review_tags": tags,
            "review_content": r.review_content, "review_images": images,
            "is_anonymous": r.is_anonymous, "status": r.status,
            "reject_reason": r.reject_reason,
            "worker_reply": r.worker_reply, "worker_reply_at": r.worker_reply_at,
            "like_count": r.like_count,
            "created_at": r.created_at,
        })
    return success(data={"list": data, "total": total, "page": page, "size": size})


@router.get("/worker/{worker_id}/detail")
async def worker_detail(
    worker_id: int,
    db: Session = Depends(get_db),
):
    """师傅详情：整合基本信息+评分统计+评价摘要"""
    from app.models.user import Worker as WorkerModel
    worker = db.query(WorkerModel).filter(WorkerModel.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="师傅不存在")
    stats = review_service.get_review_stats(db, worker_id=worker_id)
    recent_reviews, _ = review_service.get_reviews(db, worker_id=worker_id, status="approved", page=1, size=5)
    recent = []
    for r in recent_reviews:
        tags = []
        try:
            import json
            if r.review_tags:
                tags = json.loads(r.review_tags)
        except Exception:
            pass
        recent.append({
            "id": r.id, "rating": r.rating, "review_tags": tags,
            "review_content": r.review_content,
            "worker_reply": r.worker_reply, "created_at": r.created_at,
        })
    return success(data={
        "id": worker.id, "name": worker.real_name or worker.nickname,
        # 公开师傅档案不返回联系方式；真实号码仅由已指派订单详情放行。
        "avatar": worker.avatar,
        "service_types": worker.service_types,
        "rating": worker.rating,
        "total_orders": worker.total_orders or 0,
        "completed_orders": worker.completed_orders or 0,
        "certified": worker.certified,
        "stats": stats,
        "recent_reviews": recent,
    })


# ========== 运营后台接口 ==========

@router.get("/admin/pending")
async def pending_reviews(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    admin=Depends(require_admin_operator),
    db: Session = Depends(get_db),
):
    """运营后台：待审核评价列表"""
    reviews, total = review_service.get_reviews(
        db, status="pending", page=page, size=size
    )
    data = []
    for r in reviews:
        data.append({
            "id": r.id,
            "order_id": r.order_id,
            "user_id": r.user_id,
            "worker_id": r.worker_id,
            "rating": r.rating,
            "review_content": r.review_content,
            "review_images": r.review_images,
            "is_anonymous": r.is_anonymous,
            "created_at": r.created_at,
        })
    return success(data={"list": data, "total": total})


@router.put("/admin/{review_id}/audit")
async def audit_review_api(
    review_id: int,
    req: ReviewAuditRequest,
    admin=Depends(require_admin_operator),
    db: Session = Depends(get_db),
):
    """运营后台：审核评价"""
    review = review_service.audit_review(db, review_id, req, admin.id)
    # 审核通过后更新师傅摘要
    if review.status == "approved" and review.worker_id:
        review_service.update_highlight_summary(db, review.worker_id)
    return success(data={"id": review.id, "status": review.status}, message="审核完成")

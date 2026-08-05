"""质检回访 API"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_current_account, get_current_admin, require_admin_operator
from app.models.user import User
from app.schemas.quality import (
    InspectionFeedbackRequest,
    QualityInspectionResponse,
    AdminAuditInspectionRequest,
)
from app.services import quality_service
from app.utils.response import success

router = APIRouter(prefix="/api/quality", tags=["质检回访"])


@router.post("/orders/{order_id}/inspect")
async def create_inspection(
    order_id: int,
    admin=Depends(require_admin_operator),
    db: Session = Depends(get_db),
):
    """为订单创建回访任务（内部调用或管理员）"""
    inspection = quality_service.create_auto_inspection(db, order_id)
    return success(data=QualityInspectionResponse.model_validate(inspection).model_dump(mode="json"))


@router.post("/inspections/{inspection_id}/feedback")
async def submit_feedback(
    inspection_id: int,
    req: InspectionFeedbackRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用户提交回访反馈"""
    inspection = quality_service.submit_inspection_feedback(
        db, inspection_id, user.id, req.rating, req.feedback
    )
    return success(data=QualityInspectionResponse.model_validate(inspection).model_dump(mode="json"))


@router.get("/inspections/my")
async def my_inspections(
    status: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的回访列表"""
    from app.models.quality import QualityInspection
    q = db.query(QualityInspection).filter(QualityInspection.user_id == user.id)
    if status:
        q = q.filter(QualityInspection.status == status)
    items = q.order_by(QualityInspection.created_at.desc()).limit(200).all()
    return success(data=[
        QualityInspectionResponse.model_validate(i).model_dump(mode="json")
        for i in items
    ])


# ===== 管理员接口 =====

@router.get("/admin/inspections")
async def admin_inspections(
    status: Optional[str] = Query(None, pattern="^(pending|done|need_follow)$"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    admin=Depends(require_admin_operator),
    db: Session = Depends(get_db),
):
    """回访任务列表（后台）"""
    result = quality_service.list_inspections(db, status, page, size)
    return success(data={
        "total": result["total"],
        "page": result["page"],
        "size": result["size"],
        "items": [
            QualityInspectionResponse.model_validate(i).model_dump(mode="json")
            for i in result["items"]
        ],
    })


@router.put("/admin/inspections/{inspection_id}/audit")
async def audit_inspection(
    inspection_id: int,
    req: AdminAuditInspectionRequest,
    admin=Depends(require_admin_operator),
    db: Session = Depends(get_db),
):
    """客服处理回访"""
    inspection = quality_service.admin_audit_inspection(
        db, admin.id, inspection_id, req.status, req.remark
    )
    return success(data=QualityInspectionResponse.model_validate(inspection).model_dump(mode="json"))

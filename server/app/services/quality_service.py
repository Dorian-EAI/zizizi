"""质检回访业务逻辑"""

from datetime import datetime, timedelta
from typing import List
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.quality import QualityInspection
from app.models.order import Order


def create_auto_inspection(db: Session, order_id: int) -> QualityInspection:
    """订单完成后自动生成回访任务"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status not in {"paid", "reviewed"} or not order.worker_id:
        raise HTTPException(status_code=409, detail="订单尚未完成支付，不能创建回访")
    existing = db.query(QualityInspection).filter(
        QualityInspection.order_id == order_id
    ).first()
    if existing:
        return existing

    inspection = QualityInspection(
        order_id=order_id,
        user_id=order.user_id,
        worker_id=order.worker_id,
        inspect_type="auto",
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    return inspection


def submit_inspection_feedback(db: Session, inspection_id: int, user_id: int,
                               rating: int, feedback: str = None) -> QualityInspection:
    """用户提交回访反馈"""
    inspection = db.query(QualityInspection).filter(
        QualityInspection.id == inspection_id,
        QualityInspection.user_id == user_id,
    ).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="回访任务不存在")
    if inspection.status != "pending":
        raise HTTPException(status_code=400, detail="回访已处理")

    inspection.rating = rating
    inspection.feedback = feedback
    if rating <= 3:
        inspection.satisfaction = "dissatisfied"
        inspection.is_complaint = True
        # 这里可以自动生成投诉工单，先标记
    else:
        inspection.satisfaction = "satisfied" if rating >= 4 else "neutral"

    inspection.status = "done"
    db.commit()
    db.refresh(inspection)
    return inspection


def admin_audit_inspection(db: Session, admin_id: int, inspection_id: int,
                           status: str, remark: str = None) -> QualityInspection:
    """客服处理回访"""
    inspection = db.query(QualityInspection).filter(QualityInspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="回访任务不存在")

    inspection.status = status
    inspection.inspector_id = admin_id
    inspection.inspected_at = datetime.utcnow()
    if remark:
        inspection.feedback = (inspection.feedback or "") + f"\n[客服备注]: {remark}"
    db.commit()
    db.refresh(inspection)
    return inspection


def list_inspections(
    db: Session, status: str = None, page: int = 1, size: int = 20
) -> dict:
    """回访列表，可按状态筛选。"""
    q = db.query(QualityInspection)
    if status:
        q = q.filter(QualityInspection.status == status)
    total = q.count()
    items = q.order_by(QualityInspection.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return {"total": total, "items": items, "page": page, "size": size}


def get_inspections_to_send(db: Session) -> List[QualityInspection]:
    """获取需要发送回访通知的任务（订单完成超过24小时且未发送）"""
    deadline = datetime.utcnow() - timedelta(hours=24)
    return db.query(QualityInspection).filter(
        QualityInspection.status == "pending",
        QualityInspection.send_at.is_(None),
        QualityInspection.created_at < deadline,
    ).all()

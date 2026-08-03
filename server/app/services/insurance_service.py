"""安心保业务逻辑"""

from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.insurance import InsurancePolicy, InsuranceClaim
from app.models.order import Order


# 安心保档位配置
INSURANCE_CONFIGS = {
    "basic": {"premium": 300, "coverage": 50000},
    "standard": {"premium": 500, "coverage": 200000},
    "premium": {"premium": 1000, "coverage": 500000},
}


def create_policy(db: Session, order_id: int, user_id: int, level: str) -> InsurancePolicy:
    """保费支付回调接入前禁止直接生成 active 保单。"""
    if level not in INSURANCE_CONFIGS:
        raise HTTPException(status_code=400, detail="无效的保险档位")
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在或不属于当前用户")
    if db.query(InsurancePolicy).filter(InsurancePolicy.order_id == order_id).first():
        raise HTTPException(status_code=409, detail="该订单已存在保单")
    raise HTTPException(
        status_code=501,
        detail="安心保保费尚未接入真实支付回调，当前不会收费或生成保单",
    )


def get_policy_by_order(db: Session, order_id: int) -> Optional[InsurancePolicy]:
    """查询订单保单"""
    return db.query(InsurancePolicy).filter(InsurancePolicy.order_id == order_id).first()


def submit_claim(db: Session, user_id: int, policy_id: int, reason: str,
                 evidence_images: List[str], claim_amount: int) -> InsuranceClaim:
    """用户提交理赔申请"""
    policy = db.query(InsurancePolicy).filter(
        InsurancePolicy.id == policy_id,
        InsurancePolicy.user_id == user_id,
    ).first()
    if not policy:
        raise HTTPException(status_code=404, detail="保单不存在")
    if policy.status != "active":
        raise HTTPException(status_code=400, detail="保单已失效或已理赔")
    if policy.expired_at <= datetime.utcnow():
        policy.status = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="保单已过期")
    if claim_amount <= 0:
        raise HTTPException(status_code=400, detail="理赔金额必须大于 0")
    if claim_amount > policy.coverage:
        raise HTTPException(status_code=400, detail="理赔金额超过保单额度")

    # 校验订单完成时间是否在7天内
    order = db.query(Order).filter(Order.id == policy.order_id).first()
    if not order or order.status not in ("completed", "paid", "reviewed") or not order.completed_at:
        raise HTTPException(status_code=409, detail="订单尚未完成，不能申请理赔")
    if datetime.utcnow() - order.completed_at > timedelta(days=7):
        raise HTTPException(status_code=400, detail="已超过理赔申请期限（7天）")

    existing = db.query(InsuranceClaim).filter(
        InsuranceClaim.policy_id == policy_id,
        InsuranceClaim.status.in_(("pending", "approved")),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="该保单已有处理中或已通过的理赔申请")

    claim = InsuranceClaim(
        policy_id=policy_id,
        order_id=policy.order_id,
        user_id=user_id,
        worker_id=policy.worker_id,
        reason=reason,
        evidence_images=evidence_images,
        claim_amount=claim_amount,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


def audit_claim(db: Session, admin_id: int, claim_id: int, status: str,
                settled_amount: int, remark: str) -> InsuranceClaim:
    """客服审核理赔"""
    claim = db.query(InsuranceClaim).filter(InsuranceClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="理赔申请不存在")
    if claim.status != "pending":
        raise HTTPException(status_code=400, detail="理赔申请已处理")
    if status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="审核状态仅支持 approved/rejected")
    if status == "approved":
        raise HTTPException(
            status_code=501,
            detail="理赔打款通道尚未接入，当前不会标记已赔付",
        )
    if settled_amount:
        raise HTTPException(status_code=400, detail="驳回理赔时赔付金额必须为 0")

    claim.status = status
    claim.audit_remark = remark
    claim.audited_by = admin_id
    claim.audited_at = datetime.utcnow()

    claim.settled_amount = 0
    claim.settled_at = None

    db.commit()
    db.refresh(claim)
    return claim


def list_claims(db: Session, user_id: int = None, worker_id: int = None,
                status: str = None, page: int = 1, size: int = 20) -> dict:
    """理赔列表"""
    q = db.query(InsuranceClaim)
    if user_id:
        q = q.filter(InsuranceClaim.user_id == user_id)
    if worker_id:
        q = q.filter(InsuranceClaim.worker_id == worker_id)
    if status:
        q = q.filter(InsuranceClaim.status == status)

    total = q.count()
    items = q.order_by(InsuranceClaim.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return {"total": total, "items": items, "page": page, "size": size}


def expire_overdue_policies(db: Session):
    """将过期保单置为 expired"""
    db.query(InsurancePolicy).filter(
        InsurancePolicy.status == "active",
        InsurancePolicy.expired_at < datetime.utcnow(),
    ).update({"status": "expired"}, synchronize_session=False)
    db.commit()

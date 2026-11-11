"""优惠券相关路由"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_super_admin
from app.models.user import User
from app.models.coupon import CouponTemplate
from app.schemas.coupon import (
    CreateCouponTemplate,
    CouponTemplateResponse,
)
from app.services import coupon_service, admin_service
from app.utils.response import success

router = APIRouter(prefix="/api/coupons", tags=["优惠券"])


@router.get("/templates")
async def list_templates(db: Session = Depends(get_db)):
    """获取激活中的优惠券模板列表（公开）"""
    data = coupon_service.list_active_templates(db)
    return success(data=data)


@router.post("/claim/{template_id}")
async def claim_coupon(
    template_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用户领取优惠券"""
    coupon = coupon_service.claim_coupon(db, user, template_id)
    t = db.query(CouponTemplate).filter(CouponTemplate.id == template_id).first()
    tmpl = coupon_service._template_to_dict(t) if t else None
    data = {
        "id": coupon.id,
        "template_id": coupon.template_id,
        "user_id": coupon.user_id,
        "code": coupon.code,
        "status": coupon.status,
        "used_order_no": coupon.used_order_no,
        "used_at": coupon.used_at.strftime("%Y-%m-%d %H:%M:%S") if coupon.used_at else None,
        "expire_at": coupon.expire_at.strftime("%Y-%m-%d %H:%M:%S") if coupon.expire_at else None,
        "received_at": coupon.received_at.strftime("%Y-%m-%d %H:%M:%S") if coupon.received_at else None,
        "template": tmpl,
    }
    return success(data=data, message="领取成功")


@router.get("/mine")
async def my_coupons(
    status: Optional[str] = Query(None, description="状态筛选 available/used/expired"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询我的优惠券列表"""
    data = coupon_service.list_my_coupons(db, user, status)
    return success(data=data)


@router.get("/available")
async def available_for_order(
    amount: float = Query(..., description="订单金额"),
    service_type: Optional[str] = Query(None, description="服务类型 key"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询可用于该订单金额+服务类型的可用券"""
    data = coupon_service.list_available_for_order(db, user, amount, service_type)
    return success(data=data)


@router.post("/templates")
async def create_template(
    req: CreateCouponTemplate,
    admin=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """管理员创建优惠券模板。"""
    tmpl = coupon_service.create_template(db, req)
    admin_service.add_admin_audit(
        db, admin.id, "coupon_template.create", "coupon_template", tmpl.id, commit=True
    )
    data = CouponTemplateResponse.model_validate(tmpl).model_dump(mode="json")
    return success(data=data, message="模板创建成功")

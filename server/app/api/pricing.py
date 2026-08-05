"""动态定价 / 高峰加价 API"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_current_admin, require_super_admin
from app.models.user import User
from app.schemas.pricing import (
    CalculateAmountRequest,
    CalculateAmountResponse,
    PeakTimeConfigRequest,
    PeakTimeConfigResponse,
)
from app.services import pricing_service, admin_service
from app.utils.response import success

router = APIRouter(prefix="/api/pricing", tags=["动态定价"])


@router.get("/current-surcharge")
async def current_surcharge(
    db: Session = Depends(get_db),
):
    """获取当前高峰加价信息"""
    result = pricing_service.get_current_surcharge(db)
    return success(data=result)


@router.post("/calculate")
async def calculate_amount(
    req: CalculateAmountRequest,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """计算订单应付金额"""
    result = pricing_service.calculate_order_amount(
        db,
        user,
        req.base_amount,
        req.is_urgent,
        req.coupon_id,
        req.service_type,
        req.annual_card_id,
    )
    return success(data=result)


# ===== 管理员接口 =====

@router.get("/admin/peak-configs")
async def list_peak_configs(
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """高峰配置列表"""
    from app.models.pricing import PeakTimeConfig
    items = db.query(PeakTimeConfig).order_by(PeakTimeConfig.created_at.desc()).limit(500).all()
    return success(data=[
        PeakTimeConfigResponse.model_validate(i).model_dump(mode="json")
        for i in items
    ])


@router.post("/admin/peak-configs")
async def create_peak_config(
    req: PeakTimeConfigRequest,
    admin=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """创建高峰配置"""
    cfg = pricing_service.create_peak_config(
        db, req.name,
        [tr.model_dump() for tr in req.time_ranges],
        req.surcharge_rate, req.surcharge_max
    )
    admin_service.add_admin_audit(
        db, admin.id, "pricing_peak.create", "peak_time_config", cfg.id, commit=True
    )
    return success(data=PeakTimeConfigResponse.model_validate(cfg).model_dump(mode="json"))

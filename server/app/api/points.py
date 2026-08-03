"""积分相关路由"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.point import PointExchangeRequest
from app.services import point_service
from app.utils.response import success

router = APIRouter(prefix="/api/points", tags=["积分"])


@router.get("")
async def get_point_balance(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取积分余额、月度/累计获得、今日签到状态"""
    data = point_service.get_balance(db, user)
    return success(data=data)


@router.get("/logs")
async def list_point_logs(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页条数"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取积分流水列表（分页）"""
    data = point_service.list_logs(db, user, page=page, size=size)
    return success(data=data)


@router.post("/signin")
async def daily_signin(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """每日签到，返回获得积分和连续签到天数"""
    data = point_service.daily_signin(db, user)
    return success(data=data, message="签到成功")


@router.post("/exchange/coupon")
async def exchange_coupon(
    req: PointExchangeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """积分兑换优惠券"""
    data = point_service.exchange_coupon(db, user, req.coupon_template_id)
    return success(data=data, message="兑换成功")

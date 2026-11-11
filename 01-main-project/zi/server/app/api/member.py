"""会员中心路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.member import (
    LevelInfo,
    MemberResponse,
    TestAddGrowthRequest,
)
from app.services import member_service
from app.utils.response import success
from app.config import settings

router = APIRouter(prefix="/api/member", tags=["会员中心"])


@router.get("")
async def get_member_info(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户会员信息"""
    level_info_dict = member_service.get_level_info(user)
    level_info = LevelInfo(**level_info_dict)
    benefits = member_service.get_member_benefits(level_info.level)

    data = {
        "level_info": level_info.model_dump(),
        "growth_value": user.growth_value or 0,
        "benefits": benefits,
        "month_spend": member_service.get_month_spend(db, user.id),
        "coupon_count": member_service.get_available_coupon_count(db, user.id),
    }
    return success(data=data)


@router.get("/benefits")
async def get_all_benefits():
    """展示所有等级权益介绍"""
    data = member_service.get_all_levels_benefits()
    return success(data=data)


@router.post("/test/add-growth")
async def test_add_growth(
    req: TestAddGrowthRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """开发测试：手动增加成长值"""
    if settings.APP_ENV.lower() != "development" or not settings.APP_DEBUG:
        raise HTTPException(status_code=404, detail="接口不存在")
    user = member_service.add_growth_value(db, user, req.amount, req.reason)
    level_info_dict = member_service.get_level_info(user)
    return success(data={
        "growth_value": user.growth_value,
        "level_info": level_info_dict,
    }, message=f"已增加 {req.amount} 成长值")

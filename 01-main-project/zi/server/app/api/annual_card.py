"""家庭年卡 / 服务套餐 API"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.annual_card import (
    AnnualCardTemplateResponse,
    PurchaseCardRequest,
    UserAnnualCardResponse,
    UseCardRequest,
)
from app.services import annual_card_service
from app.utils.response import success

router = APIRouter(prefix="/api/annual-cards", tags=["家庭年卡"])


@router.get("/templates")
async def list_card_templates(
    db: Session = Depends(get_db),
):
    """年卡模板列表"""
    items = annual_card_service.list_templates(db)
    return success(data=[
        AnnualCardTemplateResponse.model_validate(i).model_dump(mode="json")
        for i in items
    ])


@router.post("/purchase")
async def purchase_card(
    req: PurchaseCardRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """购买年卡"""
    card = annual_card_service.purchase_card(db, user.id, req.template_id)
    return success(data=UserAnnualCardResponse.model_validate(card).model_dump(mode="json"))


@router.get("/my")
async def my_cards(
    status: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的年卡列表"""
    items = annual_card_service.get_my_cards(db, user.id, status)
    return success(data=[
        UserAnnualCardResponse.model_validate(i).model_dump(mode="json")
        for i in items
    ])


@router.post("/use")
async def use_card(
    req: UseCardRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """使用年卡抵扣订单"""
    result = annual_card_service.use_card_for_order(db, req.card_id, user.id)
    return success(data=result)


@router.post("/{card_id}/refund")
async def refund_card(
    card_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """申请退卡"""
    result = annual_card_service.refund_card(db, user.id, card_id)
    return success(data=result)

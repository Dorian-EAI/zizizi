"""家庭年卡业务逻辑"""

import time
import random
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.annual_card import AnnualCardTemplate, UserAnnualCard
from app.models.user import User


def _gen_card_order_no() -> str:
    return f"CARD{int(time.time())}{random.randint(1000, 9999)}"


def list_templates(db: Session, is_active: bool = True) -> List[AnnualCardTemplate]:
    """年卡模板列表"""
    q = db.query(AnnualCardTemplate)
    if is_active is not None:
        q = q.filter(AnnualCardTemplate.is_active == is_active)
    return q.order_by(AnnualCardTemplate.sort_order.asc()).all()


def purchase_card(db: Session, user_id: int, template_id: int) -> UserAnnualCard:
    """购买动作在支付回调能按业务用途激活年卡前保持关闭。

    旧实现未收款便直接创建 active 年卡，会造成平台资产损失。
    """
    raise HTTPException(
        status_code=501,
        detail="年卡支付尚未接入真实支付回调，当前不会创建或扣款",
    )


def use_card_for_order(db: Session, card_id: int, order_id: int) -> dict:
    """年卡抵扣需绑定并锁定具体订单，模型补齐前拒绝消费次数。"""
    raise HTTPException(
        status_code=501,
        detail="年卡抵扣尚未接入订单核销，当前不会消耗次数",
    )


def get_my_cards(db: Session, user_id: int, status: str = None) -> List[UserAnnualCard]:
    """我的年卡列表"""
    q = db.query(UserAnnualCard).filter(UserAnnualCard.user_id == user_id)
    if status:
        q = q.filter(UserAnnualCard.status == status)
    return q.order_by(UserAnnualCard.created_at.desc()).all()


def refund_card(db: Session, user_id: int, card_id: int) -> dict:
    """无法追溯原支付单时禁止伪造“原路退款成功”。"""
    raise HTTPException(
        status_code=501,
        detail="年卡退款尚未接入原支付渠道，当前不会变更年卡状态",
    )


def check_expiry(db: Session):
    """标记过期年卡"""
    now = datetime.utcnow()
    db.query(UserAnnualCard).filter(
        UserAnnualCard.status == "active",
        UserAnnualCard.valid_end < now,
    ).update({"status": "expired"}, synchronize_session=False)
    db.commit()

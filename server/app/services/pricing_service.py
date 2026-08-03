"""动态定价业务逻辑"""

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.pricing import PeakTimeConfig
from app.models.user import User


def get_current_surcharge(db: Session) -> dict:
    """获取当前时段加价信息"""
    configs = db.query(PeakTimeConfig).filter(PeakTimeConfig.is_active == True).all()
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    weekday = now.isoweekday()
    current_time = now.strftime("%H:%M")

    matches = []
    for cfg in configs:
        for tr in cfg.time_ranges or []:
            start = tr.get("start", "")
            end = tr.get("end", "")
            weekdays = tr.get("weekdays", [])
            if not start or not end:
                continue
            if start <= end:
                active = weekday in weekdays and start <= current_time <= end
            elif current_time >= start:
                active = weekday in weekdays
            else:
                previous_weekday = 7 if weekday == 1 else weekday - 1
                active = previous_weekday in weekdays and current_time <= end
            if active:
                matches.append(cfg)

    if matches:
        cfg = max(matches, key=lambda item: (float(item.surcharge_rate), item.surcharge_max))
        return {
            "is_peak_time": True,
            "surcharge_rate": float(cfg.surcharge_rate),
            "surcharge_max": cfg.surcharge_max,
        }
    return {
        "is_peak_time": False,
        "surcharge_rate": 0.0,
        "surcharge_max": 0,
    }


def calculate_order_amount(db: Session, user: Optional[User], base_amount: int,
                           is_urgent: bool = False, coupon_id: int = None,
                           service_type: str = None,
                           annual_card_id: int = None) -> dict:
    """计算订单应付金额"""
    from app.services.coupon_service import apply_coupon
    from app.services.member_service import MEMBER_DISCOUNT_UNAVAILABLE_REASON

    result = {
        "base_amount": base_amount,
        "peak_surcharge": 0,
        "urgent_amount": 0,
        "member_discount": 0,
        "member_discount_status": "unavailable",
        "member_discount_reason": MEMBER_DISCOUNT_UNAVAILABLE_REASON,
        "coupon_discount": 0,
        "annual_card_discount": 0,
        "final_amount": base_amount,
    }

    # 高峰加价
    surcharge = get_current_surcharge(db)
    if surcharge["is_peak_time"]:
        peak = min(int(base_amount * surcharge["surcharge_rate"]), surcharge["surcharge_max"])
        result["peak_surcharge"] = peak

    # 加急费
    if is_urgent:
        result["urgent_amount"] = 1000  # 默认10元

    subtotal = base_amount + result["peak_surcharge"] + result["urgent_amount"]

    # 会员等级目前只用于成长展示，尚未接入订单支付结算。
    # member_discount 必须保持为 0，避免报价接口与真实扣款产生差异。

    # 优惠券
    if coupon_id:
        if not user:
            raise HTTPException(status_code=401, detail="使用优惠券需要登录")
        amount_after_member_yuan = subtotal / 100
        coupon_result = apply_coupon(
            db,
            user,
            coupon_id,
            amount_after_member_yuan,
            service_type,
        )
        result["coupon_discount"] = int(round(coupon_result["discount_amount"] * 100))

    # 年卡抵扣（简化：抵扣上门费部分，假设固定500分）
    if annual_card_id:
        raise HTTPException(
            status_code=501,
            detail="年卡订单核销尚未接入，当前不会计算虚假抵扣",
        )

    final = (
        subtotal
        - result["member_discount"]
        - result["coupon_discount"]
        - result["annual_card_discount"]
    )
    result["final_amount"] = max(final, 0)
    return result


def create_peak_config(db: Session, name: str, time_ranges: list,
                       surcharge_rate: float, surcharge_max: int) -> PeakTimeConfig:
    """创建高峰配置"""
    cfg = PeakTimeConfig(
        name=name,
        time_ranges=time_ranges,
        surcharge_rate=surcharge_rate,
        surcharge_max=surcharge_max,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg

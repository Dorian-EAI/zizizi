"""会员成长值业务逻辑"""

import json
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Dict, Any, List
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.coupon import Coupon, CouponTemplate
from app.models.user import User
from app.models.wallet import PaymentOrder, RefundOrder
from app.services import message_service


LEVEL_TABLE = [
    (0, "普通会员", 0),
    (1, "银卡会员", 500),
    (2, "金卡会员", 2000),
    (3, "钻石会员", 8000),
]

MEMBER_DISCOUNT_UNAVAILABLE_REASON = "会员折扣尚未接入订单支付结算，当前不参与计价"

DAILY_LIMIT = {
    "review_add": 5,
    "review_image_add": 5,
}


def get_level_info(user: User) -> Dict[str, Any]:
    """获取会员等级信息"""
    growth = user.growth_value or 0
    current_level = 0
    current_level_name = "普通会员"
    next_level_growth = LEVEL_TABLE[1][2] if len(LEVEL_TABLE) > 1 else 0
    current_level_min = 0

    for i, (lvl, name, min_growth) in enumerate(LEVEL_TABLE):
        if growth >= min_growth:
            current_level = lvl
            current_level_name = name
            current_level_min = min_growth
            if i + 1 < len(LEVEL_TABLE):
                next_level_growth = LEVEL_TABLE[i + 1][2]
            else:
                next_level_growth = min_growth

    if next_level_growth <= current_level_min:
        progress_percent = 100
    else:
        progress_needed = next_level_growth - current_level_min
        progress_have = growth - current_level_min
        progress_percent = min(100, int(progress_have / progress_needed * 100))

    return {
        "level": current_level,
        "level_name": current_level_name,
        "growth": growth,
        "next_level_growth": next_level_growth,
        "progress_percent": progress_percent,
    }


def add_growth_value(db: Session, user: User, amount: int, reason: str) -> User:
    """增加成长值"""
    if amount <= 0:
        return user

    user.growth_value = (user.growth_value or 0) + amount
    db.commit()
    db.refresh(user)

    title = "获得成长值"
    content = f"获得 {amount} 成长值：{reason}"
    payload = {"amount": amount, "reason": reason}
    message_service.send_inbox_message(db, "user", user.id, "system", title, content, payload)

    check_level_upgrade(db, user)

    return user


def check_level_upgrade(db: Session, user: User) -> None:
    """检查会员等级是否变化，变化则升级并发通知"""
    old_level = user.member_level or 0
    level_info = get_level_info(user)
    new_level = level_info["level"]

    if new_level != old_level and new_level > old_level:
        user.member_level = new_level
        db.commit()
        db.refresh(user)

        level_name = level_info["level_name"]

        title = "恭喜升级"
        content = f"恭喜您点亮 {level_name} 成长等级，当前成长值为 {level_info['growth']}"
        payload = {
            "new_level": new_level,
            "level_name": level_name,
            "growth": level_info["growth"],
        }
        message_service.send_inbox_message(db, "user", user.id, "system", title, content, payload)


def calc_member_discount(db: Session, user: User, base_amount: float) -> Dict[str, Any]:
    """返回会员折扣的真实可用状态。

    会员等级目前只实现成长值与等级展示，尚未接入订单结算。保留这个函数是为了
    兼容已有调用方，但绝不能在支付链完成之前计算或宣传任何等级折扣。
    """
    final_amount = round(float(base_amount), 2)

    return {
        "final_amount": final_amount,
        "discount_amount": 0,
        "member_discount_rate": 1.0,
        "available": False,
        "status": "unavailable",
        "reason": MEMBER_DISCOUNT_UNAVAILABLE_REASON,
    }


def get_member_benefits(level: int) -> List[Dict[str, Any]]:
    """仅返回已经实现的成长等级展示能力，不承诺未上线的会员权益。"""
    level_row = next((row for row in LEVEL_TABLE if row[0] == level), LEVEL_TABLE[0])
    _, level_name, min_growth = level_row
    return [{
        "key": "growth_level",
        "name": "成长等级",
        "desc": f"累计成长值达到 {min_growth} 时展示 {level_name}",
        "status": "implemented",
    }]


def get_all_levels_benefits() -> List[Dict[str, Any]]:
    """返回已实现的成长等级规则，不返回尚未兑现的服务或价格权益。"""
    result = []
    for lvl, name, min_growth in LEVEL_TABLE:
        result.append({
            "level": lvl,
            "level_name": name,
            "min_growth": min_growth,
            "benefits": get_member_benefits(lvl),
        })
    return result


def _utc_month_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    """按中国本地自然月生成用于查询 UTC 无时区时间戳的半开区间。"""
    china_tz = ZoneInfo("Asia/Shanghai")
    if now is None:
        local_now = datetime.now(china_tz)
    elif now.tzinfo is None:
        local_now = now.replace(tzinfo=china_tz)
    else:
        local_now = now.astimezone(china_tz)

    local_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if local_start.month == 12:
        local_end = local_start.replace(year=local_start.year + 1, month=1)
    else:
        local_end = local_start.replace(month=local_start.month + 1)

    utc_start = local_start.astimezone(timezone.utc).replace(tzinfo=None)
    utc_end = local_end.astimezone(timezone.utc).replace(tzinfo=None)
    return utc_start, utc_end


def get_month_spend(db: Session, user_id: int, now: datetime | None = None) -> float:
    """统计用户本月订单实际净支付金额（元）。

    只统计已经支付且绑定业务订单的支付单，排除充值与未完成支付；成功退款会从
    对应的本月支付中扣除。分账/组合支付会按每一笔真实支付记录累计。
    """
    month_start, month_end = _utc_month_bounds(now)
    paid_statuses = ("paid", "partially_refunded", "refunded")

    paid_total = db.query(func.coalesce(func.sum(PaymentOrder.amount), 0)).filter(
        PaymentOrder.payer_type == "user",
        PaymentOrder.payer_id == user_id,
        PaymentOrder.order_no.isnot(None),
        PaymentOrder.status.in_(paid_statuses),
        PaymentOrder.paid_at.isnot(None),
        PaymentOrder.paid_at >= month_start,
        PaymentOrder.paid_at < month_end,
    ).scalar()

    refunded_total = (
        db.query(func.coalesce(func.sum(RefundOrder.amount), 0))
        .join(PaymentOrder, PaymentOrder.payment_no == RefundOrder.payment_no)
        .filter(
            PaymentOrder.payer_type == "user",
            PaymentOrder.payer_id == user_id,
            PaymentOrder.order_no.isnot(None),
            PaymentOrder.status.in_(paid_statuses),
            PaymentOrder.paid_at.isnot(None),
            PaymentOrder.paid_at >= month_start,
            PaymentOrder.paid_at < month_end,
            RefundOrder.status == "success",
        )
        .scalar()
    )

    net_spend = max(Decimal(str(paid_total or 0)) - Decimal(str(refunded_total or 0)), Decimal("0"))
    return float(net_spend.quantize(Decimal("0.01")))


def get_available_coupon_count(
    db: Session,
    user_id: int,
    now: datetime | None = None,
) -> int:
    """统计当前确实可用的用户优惠券数量。"""
    if now is None:
        query_now = datetime.utcnow()
    elif now.tzinfo is not None:
        query_now = now.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        query_now = now

    return int(
        db.query(func.count(Coupon.id))
        .join(CouponTemplate, CouponTemplate.id == Coupon.template_id)
        .filter(
            Coupon.user_id == user_id,
            Coupon.status == "available",
            or_(Coupon.expire_at.is_(None), Coupon.expire_at >= query_now),
            CouponTemplate.is_active.is_(True),
            or_(CouponTemplate.valid_start.is_(None), CouponTemplate.valid_start <= query_now),
            or_(CouponTemplate.valid_end.is_(None), CouponTemplate.valid_end >= query_now),
        )
        .scalar()
    )


def _get_today_growth_count(db: Session, user_id: int, reason_prefix: str) -> int:
    """简化版：用消息记录代替 growth log 表统计今日某类型成长值获取次数"""
    from app.models.message import Message

    today_start = datetime.combine(date.today(), datetime.min.time())
    msgs = (
        db.query(Message)
        .filter(
            Message.owner_type == "user",
            Message.owner_id == user_id,
            Message.type == "system",
            Message.created_at >= today_start,
            Message.title == "获得成长值",
        )
        .all()
    )
    count = 0
    for m in msgs:
        try:
            if m.payload:
                p = json.loads(m.payload) if isinstance(m.payload, str) else m.payload
                if p and p.get("reason", "").startswith(reason_prefix):
                    count += 1
        except (json.JSONDecodeError, TypeError):
            pass
    return count


def on_first_order_completed(db: Session, user: User) -> None:
    """首单完成奖励"""
    add_growth_value(db, user, 100, "首单奖励")


def on_order_paid(db: Session, user: User, amount_paid: float) -> None:
    """订单支付：每消费 ¥10 获得 1 成长值"""
    if amount_paid <= 0:
        return
    amount = int(amount_paid / 10)
    if amount > 0:
        add_growth_value(db, user, amount, f"订单消费 ¥{amount_paid}")


def on_order_reviewed(db: Session, user: User, has_images: bool = False) -> None:
    """评价订单：+20，配图再加 +10；检查日上限"""
    today_review_count = _get_today_growth_count(db, user.id, "订单评价")
    if today_review_count < DAILY_LIMIT["review_add"]:
        add_growth_value(db, user, 20, "订单评价")

    if has_images:
        today_img_count = _get_today_growth_count(db, user.id, "评价配图")
        if today_img_count < DAILY_LIMIT["review_image_add"]:
            add_growth_value(db, user, 10, "评价配图")

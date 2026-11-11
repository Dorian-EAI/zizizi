"""积分系统业务逻辑"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.user import User
from app.models.point import PointLog, PointRule


DEFAULT_RULES = [
    ("daily_signin", "每日签到", 5, 1),
    ("review_order", "评价订单", 10, 5),
    ("review_with_image", "带图评价", 10, 5),
    ("invite_user", "邀请好友", 100, 0),
]

POINT_REASON_LABELS = {key: name for key, name, _value, _limit in DEFAULT_RULES}


def ensure_rules(db: Session):
    """初始化 PointRule 表，没有的规则按 DEFAULT_RULES 插入"""
    for key, name, point_value, daily_limit in DEFAULT_RULES:
        existing = db.query(PointRule).filter(PointRule.key == key).first()
        if not existing:
            rule = PointRule(
                key=key,
                name=name,
                point_value=point_value,
                daily_limit=daily_limit,
                is_active=True,
            )
            db.add(rule)
    # 由外层业务事务统一提交，避免在积分发放前提前释放行锁。
    db.flush()


def _calc_balance(db: Session, user_id: int) -> int:
    """通过 PointLog 聚合计算用户当前积分余额"""
    result = (
        db.query(func.coalesce(func.sum(PointLog.change), 0))
        .filter(PointLog.user_id == user_id)
        .scalar()
    )
    return int(result or 0)


def get_balance(db: Session, user: User) -> dict:
    """获取用户积分汇总信息"""
    balance = _calc_balance(db, user.id)

    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    month_earn = (
        db.query(func.coalesce(func.sum(PointLog.change), 0))
        .filter(
            PointLog.user_id == user.id,
            PointLog.change > 0,
            PointLog.created_at >= month_start,
        )
        .scalar()
    ) or 0

    total_earn = (
        db.query(func.coalesce(func.sum(PointLog.change), 0))
        .filter(
            PointLog.user_id == user.id,
            PointLog.change > 0,
        )
        .scalar()
    ) or 0

    today_signin_count = (
        db.query(func.count(PointLog.id))
        .filter(
            PointLog.user_id == user.id,
            PointLog.reason.in_(("daily_signin", "每日签到")),
            PointLog.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0),
        )
        .scalar()
    ) or 0
    today_signin = today_signin_count > 0

    return {
        "balance": balance,
        "month_earn": int(month_earn),
        "total_earn": int(total_earn),
        "today_signin": today_signin,
    }


def add_points(
    db: Session,
    user: User,
    rule_key: str,
    extra_reason: Optional[str] = None,
    extra_amount: Optional[int] = None,
) -> int:
    """
    增加积分（基于规则）
    - 返回实际增加的积分数
    - 受日限制
    """
    ensure_rules(db)
    rule = db.query(PointRule).filter(PointRule.key == rule_key, PointRule.is_active == True).first()
    if not rule:
        raise HTTPException(status_code=400, detail=f"积分规则不存在或未启用: {rule_key}")

    # 锁定积分主体，避免并发签到/奖励同时基于同一个旧余额写流水。
    db.query(User).filter(User.id == user.id).with_for_update().one()

    # 检查日限。兼容历史中文 reason；新记录使用稳定 rule_key。
    if rule.daily_limit > 0:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = (
            db.query(func.count(PointLog.id))
            .filter(
                PointLog.user_id == user.id,
                PointLog.reason.in_((rule_key, rule.name)),
                PointLog.created_at >= today_start,
            )
            .scalar()
        ) or 0
        if today_count >= rule.daily_limit:
            raise HTTPException(status_code=400, detail=f"今日已达 {rule.name} 上限，明日再来吧")

    amount = extra_amount if extra_amount is not None else rule.point_value
    if amount <= 0:
        raise HTTPException(status_code=400, detail="积分数量必须为正")

    reason = extra_reason or rule_key
    current_balance = _calc_balance(db, user.id)
    new_balance = current_balance + amount

    log = PointLog(
        user_id=user.id,
        change=amount,
        balance_after=new_balance,
        reason=reason,
    )
    db.add(log)
    db.commit()
    return amount


def spend_points(db: Session, user: User, amount: int, reason: str) -> bool:
    """消费积分：检查够用，扣减，写 log"""
    if amount <= 0:
        raise HTTPException(status_code=400, detail="消费积分必须为正")

    db.query(User).filter(User.id == user.id).with_for_update().one()
    current_balance = _calc_balance(db, user.id)
    if current_balance < amount:
        raise HTTPException(status_code=400, detail="积分不足")

    new_balance = current_balance - amount
    log = PointLog(
        user_id=user.id,
        change=-amount,
        balance_after=new_balance,
        reason=reason,
    )
    db.add(log)
    db.commit()
    return True


def list_logs(db: Session, user: User, page: int = 1, size: int = 20) -> dict:
    """分页查询积分流水"""
    page = max(page, 1)
    size = max(min(size, 100), 1)
    offset = (page - 1) * size

    q = db.query(PointLog).filter(PointLog.user_id == user.id)
    total = q.count()
    logs = q.order_by(PointLog.created_at.desc()).offset(offset).limit(size).all()

    items = []
    for lg in logs:
        items.append({
            "id": lg.id,
            "change": lg.change,
            "balance_after": lg.balance_after,
            "reason": POINT_REASON_LABELS.get(lg.reason, lg.reason),
            "order_no": lg.order_no,
            "created_at": lg.created_at,
        })
    return {"total": total, "page": page, "size": size, "items": items}


def exchange_coupon(db: Session, user: User, coupon_template_id: int) -> dict:
    """积分兑换优惠券（尚未配置商品规则时安全关闭）。

    旧实现只扣积分却没有创建 ``Coupon`` 记录，会造成用户资产损失。
    在积分商品表、库存和兑换成本成为可运营配置前，明确拒绝请求。
    """
    raise HTTPException(
        status_code=501,
        detail="积分兑换商品尚未配置，当前不会扣除积分",
    )


def daily_signin(db: Session, user: User) -> dict:
    """
    每日签到
    - 今日已签 → 抛错
    - 未签 → 加积分 daily_signin + 计算连续签到天数
    返回: {got_points, streak_days}
    """
    ensure_rules(db)

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    today_log = (
        db.query(PointLog)
        .filter(
            PointLog.user_id == user.id,
            PointLog.reason.in_(("daily_signin", "每日签到")),
            PointLog.created_at >= today_start,
            PointLog.created_at < today_end,
        )
        .first()
    )
    if today_log:
        raise HTTPException(status_code=400, detail="今日已签到")

    # 加积分
    got_points = add_points(db, user, "daily_signin")

    # 计算连续签到天数
    streak = 0
    cursor_day = today_start
    while True:
        day_start = cursor_day
        day_end = cursor_day + timedelta(days=1)
        has_log = (
            db.query(func.count(PointLog.id))
            .filter(
                PointLog.user_id == user.id,
                PointLog.reason.in_(("daily_signin", "每日签到")),
                PointLog.created_at >= day_start,
                PointLog.created_at < day_end,
            )
            .scalar()
        )
        if has_log:
            streak += 1
            cursor_day -= timedelta(days=1)
        else:
            break

    return {"got_points": got_points, "streak_days": streak}

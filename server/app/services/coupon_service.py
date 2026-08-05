"""优惠券业务逻辑"""

import time
import random
import string
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.user import User
from app.models.coupon import CouponTemplate, Coupon
from app.schemas.coupon import CreateCouponTemplate


def _gen_coupon_code() -> str:
    """生成券码：C + 时间戳 + 6位随机字母数字"""
    ts = str(int(time.time()))
    rand = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"C{ts}{rand}"


def _template_to_dict(t: CouponTemplate, remaining: Optional[int] = None) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "type": t.type,
        "value": float(t.value),
        "min_spend": float(t.min_spend or 0),
        "service_type": t.service_type,
        "total_quota": t.total_quota,
        "per_user_limit": t.per_user_limit,
        "valid_start": t.valid_start.strftime("%Y-%m-%d %H:%M:%S") if t.valid_start else None,
        "valid_end": t.valid_end.strftime("%Y-%m-%d %H:%M:%S") if t.valid_end else None,
        "is_active": t.is_active,
        "created_at": t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else None,
        "remaining": remaining,
    }


def _coupon_to_dict_with_template(coupon: Coupon, template: CouponTemplate) -> dict:
    return {
        "id": coupon.id,
        "template_id": coupon.template_id,
        "user_id": coupon.user_id,
        "code": coupon.code,
        "status": coupon.status,
        "used_order_no": coupon.used_order_no,
        "used_at": coupon.used_at.strftime("%Y-%m-%d %H:%M:%S") if coupon.used_at else None,
        "expire_at": coupon.expire_at.strftime("%Y-%m-%d %H:%M:%S") if coupon.expire_at else None,
        "received_at": coupon.received_at.strftime("%Y-%m-%d %H:%M:%S") if coupon.received_at else None,
        "template": _template_to_dict(template),
    }


def _calc_discount(tmpl: CouponTemplate, order_amount: float) -> float:
    """根据模板类型计算抵扣金额"""
    if tmpl.type == "fixed":
        return float(tmpl.value)
    elif tmpl.type == "percent":
        ratio = max(0.0, min(1.0, float(tmpl.value)))
        return round(order_amount * (1 - ratio), 2)
    elif tmpl.type == "free":
        return float(order_amount)
    return 0.0


# ===== 模板管理 =====

def create_template(db: Session, data: CreateCouponTemplate) -> CouponTemplate:
    """创建优惠券模板"""
    if data.type not in ("fixed", "percent", "free"):
        raise HTTPException(status_code=400, detail="优惠券类型不合法")
    if data.type == "percent" and not (0 < data.value <= 1):
        raise HTTPException(status_code=400, detail="折扣券 value 必须在 0-1 之间")
    if data.value <= 0:
        raise HTTPException(status_code=400, detail="优惠券面值必须大于 0")

    tmpl = CouponTemplate(
        name=data.name,
        type=data.type,
        value=float(data.value),
        min_spend=float(data.min_spend or 0),
        service_type=data.service_type,
        total_quota=data.total_quota,
        per_user_limit=data.per_user_limit,
        valid_start=data.valid_start,
        valid_end=data.valid_end,
        is_active=data.is_active,
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


def list_active_templates(db: Session) -> List[dict]:
    """列出所有激活中的模板 + 剩余数量"""
    now = datetime.utcnow()
    q = db.query(CouponTemplate).filter(CouponTemplate.is_active == True)
    templates = q.order_by(CouponTemplate.created_at.desc()).limit(200).all()

    result: List[dict] = []
    for t in templates:
        claimed = db.query(func.count(Coupon.id)).filter(Coupon.template_id == t.id).scalar() or 0
        if t.total_quota == -1:
            remaining = -1
        else:
            remaining = max(0, t.total_quota - claimed)
        result.append(_template_to_dict(t, remaining=remaining))
    return result


# ===== 领券 =====

def claim_coupon(db: Session, user: User, template_id: int) -> Coupon:
    """用户领取优惠券"""
    # 锁定模板行，串行化配额检查，避免并发超领。
    tmpl = (
        db.query(CouponTemplate)
        .filter(CouponTemplate.id == template_id)
        .with_for_update()
        .first()
    )
    if not tmpl:
        raise HTTPException(status_code=404, detail="优惠券模板不存在")
    if not tmpl.is_active:
        raise HTTPException(status_code=400, detail="该优惠券已下架")

    now = datetime.utcnow()
    if tmpl.valid_start and now < tmpl.valid_start:
        raise HTTPException(status_code=400, detail="该优惠券尚未开始领取")
    if tmpl.valid_end and now > tmpl.valid_end:
        raise HTTPException(status_code=400, detail="该优惠券已结束领取")

    claimed_count = (
        db.query(func.count(Coupon.id))
        .filter(Coupon.template_id == template_id, Coupon.user_id == user.id)
        .scalar()
        or 0
    )
    if claimed_count >= tmpl.per_user_limit:
        raise HTTPException(status_code=400, detail="您已达到该券的领取上限")

    if tmpl.total_quota != -1:
        total_claimed = (
            db.query(func.count(Coupon.id))
            .filter(Coupon.template_id == template_id)
            .scalar()
            or 0
        )
        if total_claimed >= tmpl.total_quota:
            raise HTTPException(status_code=400, detail="该优惠券已被领完")

    code = _gen_coupon_code()
    expire_at = tmpl.valid_end if tmpl.valid_end else None

    coupon = Coupon(
        template_id=template_id,
        user_id=user.id,
        code=code,
        status="available",
        expire_at=expire_at,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


# ===== 查询 =====

def list_my_coupons(db: Session, user: User, status: Optional[str] = None) -> List[dict]:
    """查询我的优惠券"""
    q = db.query(Coupon).filter(Coupon.user_id == user.id)
    if status:
        q = q.filter(Coupon.status == status)
    coupons = q.order_by(Coupon.received_at.desc()).limit(500).all()

    tpl_cache: Dict[int, CouponTemplate] = {}
    result: List[dict] = []
    for c in coupons:
        if c.template_id not in tpl_cache:
            tpl = db.query(CouponTemplate).filter(CouponTemplate.id == c.template_id).first()
            tpl_cache[c.template_id] = tpl
        tpl = tpl_cache.get(c.template_id)
        result.append(_coupon_to_dict_with_template(c, tpl))
    return result


def list_available_for_order(
    db: Session,
    user: User,
    amount: float,
    service_type: Optional[str] = None,
) -> List[dict]:
    """查询可用于该订单金额+服务类型的可用券"""
    now = datetime.utcnow()
    coupons = (
        db.query(Coupon)
        .filter(Coupon.user_id == user.id)
        .filter(Coupon.status == "available")
        .filter((Coupon.expire_at == None) | (Coupon.expire_at >= now))
        .order_by(Coupon.received_at.desc())
        .limit(500)
        .all()
    )

    tpl_cache: Dict[int, CouponTemplate] = {}
    result: List[dict] = []
    for c in coupons:
        if c.template_id not in tpl_cache:
            tpl = db.query(CouponTemplate).filter(CouponTemplate.id == c.template_id).first()
            tpl_cache[c.template_id] = tpl
        tpl = tpl_cache.get(c.template_id)
        if not tpl or not tpl.is_active:
            continue

        if tpl.min_spend and amount < float(tpl.min_spend):
            continue
        if tpl.service_type and service_type and tpl.service_type != service_type:
            continue
        if tpl.valid_start and now < tpl.valid_start:
            continue
        if tpl.valid_end and now > tpl.valid_end:
            continue

        discount = _calc_discount(tpl, amount)
        final = max(round(amount - discount, 2), 0.0)
        item = _coupon_to_dict_with_template(c, tpl)
        item["discount_amount"] = round(discount, 2)
        item["final_amount"] = final
        result.append(item)

    result.sort(key=lambda x: x["discount_amount"], reverse=True)
    return result


# ===== 使用核销 =====

def apply_coupon(
    db: Session,
    user: User,
    coupon_id: int,
    order_amount: float,
    service_type: Optional[str] = None,
) -> Dict[str, Any]:
    """校验并计算优惠券抵扣"""
    # 支付前锁定券实例；并发支付会在此串行，再由支付单检查阻止重复占用。
    coupon = (
        db.query(Coupon)
        .filter(Coupon.id == coupon_id)
        .with_for_update()
        .first()
    )
    if not coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在")
    if coupon.user_id != user.id:
        raise HTTPException(status_code=400, detail="该优惠券不属于您")
    if coupon.status != "available":
        raise HTTPException(status_code=400, detail=f"优惠券状态异常: {coupon.status}")

    now = datetime.utcnow()
    if coupon.expire_at and now > coupon.expire_at:
        raise HTTPException(status_code=400, detail="优惠券已过期")

    tmpl = db.query(CouponTemplate).filter(CouponTemplate.id == coupon.template_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="优惠券模板不存在")
    if not tmpl.is_active:
        raise HTTPException(status_code=400, detail="该优惠券已下架")
    if tmpl.valid_start and now < tmpl.valid_start:
        raise HTTPException(status_code=400, detail="该优惠券尚未生效")
    if tmpl.valid_end and now > tmpl.valid_end:
        raise HTTPException(status_code=400, detail="该优惠券已失效")

    if tmpl.min_spend and order_amount < float(tmpl.min_spend):
        raise HTTPException(
            status_code=400,
            detail=f"订单金额需满 {tmpl.min_spend} 元才可使用该券",
        )
    if tmpl.service_type and service_type and tmpl.service_type != service_type:
        raise HTTPException(status_code=400, detail="该优惠券不适用于此服务类型")

    discount = _calc_discount(tmpl, order_amount)
    final_amount = max(round(order_amount - discount, 2), 0.0)

    return {
        "valid": True,
        "discount_amount": round(discount, 2),
        "final_amount": final_amount,
        "coupon": _coupon_to_dict_with_template(coupon, tmpl),
    }


def consume_coupon(db: Session, user: User, coupon_id: int, order_no: str) -> None:
    """支付成功后核销优惠券，由外层支付事务统一提交。"""
    coupon = (
        db.query(Coupon)
        .filter(Coupon.id == coupon_id)
        .with_for_update()
        .first()
    )
    if not coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在")
    if coupon.user_id != user.id:
        raise HTTPException(status_code=400, detail="该优惠券不属于您")
    if coupon.status != "available":
        raise HTTPException(status_code=400, detail=f"优惠券状态异常: {coupon.status}")

    coupon.status = "used"
    coupon.used_order_no = order_no
    coupon.used_at = datetime.utcnow()
    db.flush()


# ===== 定时任务 =====

def expire_overdue_coupons(db: Session) -> int:
    """将 expire_at < now 且 status=available 的券批量标记为 expired"""
    now = datetime.utcnow()
    count = (
        db.query(Coupon)
        .filter(Coupon.status == "available")
        .filter(Coupon.expire_at != None)
        .filter(Coupon.expire_at < now)
        .update({Coupon.status: "expired"}, synchronize_session=False)
    )
    db.commit()
    return count

"""订单业务逻辑"""

import json
import re
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Any, Set

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User, Worker
from app.models.order import Order, Bidding
from app.models.extra_fee import OrderExtraFee
from app.models.service import ServiceType
from app.schemas.order import (
    CreateOrderRequest,
    BiddingRequest,
    ReviewRequest,
    normalize_future_appointment,
    normalize_order_address,
)
from app.services import review_service
from app.services import message_service
from app.utils.snowflake import generate_business_no


def _gen_order_no() -> str:
    return generate_business_no("ORD")


_REQUIRED_WORKER_PROFILE_FIELDS = ("real_name", "phone", "id_card", "service_types")
_BOUND_USER_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
_PUBLIC_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
_PUBLIC_ID_CARD_RE = re.compile(r"(?<!\d)(\d{17}[\dXx])(?!\d)")


def _normalize_service_type(value: Any) -> str:
    return str(value or "").strip().casefold()


def redact_public_description(value: Optional[str]) -> Optional[str]:
    """Mask phone and mainland ID-card numbers in pre-assignment text."""
    if not value:
        return value
    result = _PUBLIC_PHONE_RE.sub(
        lambda match: match.group(1)[:3] + "****" + match.group(1)[-4:],
        value,
    )
    return _PUBLIC_ID_CARD_RE.sub(
        lambda match: match.group(1)[:4] + "*" * 10 + match.group(1)[-4:],
        result,
    )


def build_order_projection(
    db: Session,
    order: Order,
    active_role: str,
    account: Optional[Any] = None,
) -> dict:
    """Build the transitional multi-axis state and executable-action contract.

    The database still stores the legacy single ``Order.status`` value.  This
    projection keeps old clients compatible while making the server, rather
    than each page, the authority for visible actions.  Mutation endpoints
    continue to re-check ownership and state; these actions are not an auth
    token.
    """
    legacy_status = str(order.status or "pending")
    payment_state = (
        "paid" if legacy_status in {"paid", "reviewed"}
        else "not_applicable" if legacy_status == "cancelled"
        else "unpaid"
    )
    service_state = (
        "completed" if legacy_status == "paid" else legacy_status
    )

    extra_statuses = [
        row[0]
        for row in db.query(OrderExtraFee.status)
        .filter(OrderExtraFee.order_id == order.id)
        .order_by(OrderExtraFee.id.asc())
        .limit(10)
        .all()
    ]
    if "pending" in extra_statuses:
        price_adjust_state = "pending"
    elif extra_statuses:
        price_adjust_state = str(extra_statuses[-1])
    else:
        price_adjust_state = "none"

    actions: List[str] = []
    blocked_actions: List[dict] = []
    payment_methods: List[dict] = []

    if active_role == "client":
        if legacy_status == "pending":
            bid_exists = db.query(Bidding.id).filter(Bidding.order_id == order.id).first() is not None
            if bid_exists:
                actions.extend(["view_bids", "select_worker"])
            actions.extend(["cancel_order", "contact_support"])
        elif legacy_status == "accepted":
            actions.append("contact_worker")
        elif legacy_status == "departing":
            actions.extend(["track_worker", "contact_worker"])
        elif legacy_status in {"arrived", "serving"}:
            if price_adjust_state == "pending":
                actions.append("handle_extra_fee")
            actions.append("contact_worker")
        elif legacy_status == "completed":
            actions.extend(["confirm_and_pay", "contact_support"])
            has_openid = bool(getattr(account, "openid", None))
            payment_methods = [
                {
                    "key": "wechat",
                    "enabled": has_openid,
                    "disabled_reason": "当前账号未绑定微信" if not has_openid else "",
                },
                {"key": "wallet", "enabled": True, "disabled_reason": ""},
            ]
        elif legacy_status == "paid":
            actions.append("review_order")
        elif legacy_status in {"reviewed", "cancelled"}:
            actions.append("reorder")
    elif active_role == "worker":
        if legacy_status == "accepted":
            actions.extend(["depart_order", "contact_user"])
        elif legacy_status == "departing":
            actions.extend(["report_location", "arrive_order", "contact_user"])
        elif legacy_status == "arrived":
            actions.extend(["start_service", "contact_user"])
        elif legacy_status == "serving":
            actions.extend(["apply_extra_fee", "contact_user"])
            if price_adjust_state == "pending":
                blocked_actions.append({
                    "action": "complete_service",
                    "reason_code": "EXTRA_FEE_PENDING",
                    "message": "待用户处理补差价后才能完工",
                })
            else:
                actions.insert(0, "complete_service")
        elif legacy_status in {"completed", "paid", "reviewed"}:
            actions.append("view_settlement")

    return {
        "active_role": active_role,
        "service_state": service_state,
        "payment_state": payment_state,
        "aftersale_state": "none",
        "price_adjust_state": price_adjust_state,
        "primary_action": actions[0] if actions else None,
        # Transitional string keys are consumed by the current mini-program.
        "allowed_actions": actions,
        "blocked_actions": blocked_actions,
        "payment_methods": payment_methods,
    }


def _parse_worker_service_types(raw_value: Any) -> Set[str]:
    """Parse legacy JSON/text service type storage into normalized keys."""
    if raw_value is None:
        return set()

    parsed: Any = raw_value
    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return set()
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed = re.split(r"[,，;；|\s]+", text)

    if isinstance(parsed, dict):
        parsed = [key for key, enabled in parsed.items() if enabled]
    elif not isinstance(parsed, (list, tuple, set)):
        parsed = [parsed]

    result: Set[str] = set()
    for item in parsed:
        if isinstance(item, dict):
            item = item.get("key") or item.get("id") or item.get("value")
        normalized = _normalize_service_type(item)
        if normalized:
            result.add(normalized)
    return result


def ensure_worker_can_take_order(
    worker: Worker,
    service_type: Optional[str] = None,
) -> Set[str]:
    """Validate worker status, profile and category eligibility."""
    if not worker or not bool(worker.is_active):
        raise HTTPException(status_code=403, detail="师傅账号当前不可接单")
    if worker.certified != 2:
        raise HTTPException(status_code=403, detail="师傅尚未完成实名认证")

    missing = [
        field
        for field in _REQUIRED_WORKER_PROFILE_FIELDS
        if not str(getattr(worker, field, "") or "").strip()
    ]
    phone = str(worker.phone or "").strip()
    if phone and ("*" in phone or len(phone) < 7):
        missing.append("phone")
    if missing:
        raise HTTPException(status_code=403, detail="师傅接单资料不完整")

    service_types = _parse_worker_service_types(worker.service_types)
    if not service_types:
        raise HTTPException(status_code=403, detail="师傅尚未配置可接服务类型")

    requested = _normalize_service_type(service_type)
    if requested and requested not in service_types and not service_types.intersection({"*", "all"}):
        raise HTTPException(status_code=403, detail="师傅未取得该服务类型的接单资格")
    return service_types


def _load_dispatch_worker(
    db: Session,
    worker_or_id: Any,
    service_type: Optional[str] = None,
    lock: bool = False,
) -> tuple[Worker, Set[str]]:
    worker_id = getattr(worker_or_id, "id", worker_or_id)
    query = db.query(Worker).filter(Worker.id == worker_id)
    if lock:
        query = query.with_for_update()
    worker = query.first()
    if not worker:
        raise HTTPException(status_code=403, detail="师傅账号不存在或不可用")
    return worker, ensure_worker_can_take_order(worker, service_type)


def _cas_update_status(
    db: Session,
    order: Order,
    new_status: str,
    allowed_from: Optional[List[str]] = None,
    **fields,
) -> bool:
    """CAS 乐观锁更新订单状态

    Args:
        db: 数据库会话
        order: 订单实例（需含当前 version）
        new_status: 目标状态
        allowed_from: 允许的起始状态列表，None 表示不校验
        **fields: 其他需要同步更新的字段（如 accepted_at=xxx）

    Raises:
        HTTPException 400: 状态流转不合法
        HTTPException 409: 版本冲突，订单已被修改

    Returns:
        True: 更新成功
    """
    if allowed_from is not None and order.status not in allowed_from:
        raise HTTPException(
            status_code=400,
            detail=f"状态流转不合法: 当前{order.status}→{new_status}",
        )

    update_data = {
        "status": new_status,
        "version": Order.version + 1,
    }
    update_data.update(fields)

    rows_affected = (
        db.query(Order)
        .filter(Order.id == order.id, Order.version == order.version)
        .update(update_data, synchronize_session=False)
    )

    if rows_affected == 0:
        raise HTTPException(
            status_code=409,
            detail="订单已被修改，请刷新后重试",
        )

    return True


def create_order(db: Session, user: User, data: CreateOrderRequest) -> Order:
    """用户创建订单"""
    current_user = db.query(User).filter(User.id == user.id).first()
    if not current_user or not bool(current_user.is_active):
        raise HTTPException(status_code=403, detail="用户账号当前不可下单")
    phone = str(current_user.phone or "").strip()
    if not _BOUND_USER_PHONE_RE.fullmatch(phone):
        raise HTTPException(status_code=403, detail="请先绑定真实手机号后再下单")

    service_key = _normalize_service_type(data.service_type)
    service = (
        db.query(ServiceType)
        .filter(
            func.lower(func.trim(ServiceType.key)) == service_key,
            ServiceType.is_active.is_(True),
        )
        .first()
    )
    if not service:
        raise HTTPException(status_code=422, detail="服务类型不存在或已停用")

    # Schema 已做首轮校验；服务层再次规范化，防止内部调用绕过请求模型。
    address = normalize_order_address(data.address)
    appoint_time = normalize_future_appointment(data.appoint_time)
    order = Order(
        order_no=_gen_order_no(),
        user_id=current_user.id,
        service_type=service.key,
        service_name=service.name,
        description=data.description,
        images=json.dumps(data.images, ensure_ascii=False) if data.images else None,
        address=address,
        appoint_time=appoint_time,
        budget=data.budget if data.budget is not None else Decimal("0"),
        urgent=data.urgent,
        urgent_amount=(
            data.urgent_amount if data.urgent_amount is not None else Decimal("0")
        ),
        status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def get_client_orders(db: Session, user_id: int, status: Optional[str] = None) -> List[Order]:
    """获取用户的订单列表，按创建时间倒序"""
    q = db.query(Order).filter(Order.user_id == user_id)
    if status:
        q = q.filter(Order.status == status)
    # 兼容现有数组响应，同时给旧客户端列表设置硬上限，避免单账号历史数据无界装载。
    return q.order_by(Order.created_at.desc()).limit(200).all()


def get_worker_orders(db: Session, worker_id: int, status: Optional[str] = None) -> List[Order]:
    """获取师傅的订单列表，按创建时间倒序"""
    q = db.query(Order).filter(Order.worker_id == worker_id)
    if status:
        q = q.filter(Order.status == status)
    return q.order_by(Order.created_at.desc()).limit(200).all()


def get_order_detail(db: Session, order_id: int) -> Order:
    """获取订单详情"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


def get_available_orders(db: Session, worker_or_id: Any) -> List[Order]:
    """获取可抢订单：status=pending 且该师傅未竞价过"""
    worker, service_types = _load_dispatch_worker(db, worker_or_id)
    bid_order_ids = select(Bidding.order_id).where(Bidding.worker_id == worker.id)
    query = (
        db.query(Order)
        .filter(Order.status == "pending")
        .filter(~Order.id.in_(bid_order_ids))
    )
    if not service_types.intersection({"*", "all"}):
        query = query.filter(
            func.lower(func.trim(Order.service_type)).in_(sorted(service_types))
        )
    # 可抢单还会逐条做脱敏/距离计算，限制候选集可保护数据库和 API 延迟。
    return query.order_by(Order.created_at.desc()).limit(100).all()


async def create_bidding(db: Session, worker: Worker, order_id: int, data: BiddingRequest) -> Bidding:
    """师傅竞价"""
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status != "pending":
        raise HTTPException(status_code=409, detail="该订单当前状态不可竞价")

    locked_worker, _ = _load_dispatch_worker(
        db,
        worker.id,
        service_type=order.service_type,
        lock=True,
    )

    existing = (
        db.query(Bidding)
        .filter(Bidding.order_id == order_id, Bidding.worker_id == locked_worker.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="您已对该订单竞价，请勿重复操作")

    bidding = Bidding(
        order_id=order_id,
        worker_id=locked_worker.id,
        price=data.price,
        message=data.message,
        eta=data.eta,
    )
    db.add(bidding)
    db.commit()
    db.refresh(bidding)

    # 通知用户有新的竞价
    await message_service.notify_order_bidding_new(db, order, bidding)
    return bidding


def get_biddings(db: Session, order_id: int) -> List[dict]:
    """获取订单的竞价列表，关联师傅信息（name, avatar, rating, service_count）"""
    biddings = (
        db.query(Bidding)
        .filter(Bidding.order_id == order_id)
        .order_by(Bidding.created_at.asc())
        .limit(100)
        .all()
    )
    result: List[dict] = []
    for b in biddings:
        worker = db.query(Worker).filter(Worker.id == b.worker_id).first()
        result.append({
            "id": b.id,
            "order_id": b.order_id,
            "worker_id": b.worker_id,
            "worker_name": worker.nickname if worker else None,
            "worker_avatar": worker.avatar if worker else None,
            "worker_rating": worker.rating if worker else None,
            "worker_service_count": worker.service_count if worker else None,
            "price": b.price,
            "message": b.message,
            "eta": b.eta,
            "is_selected": b.is_selected,
            "created_at": b.created_at,
        })
    return result


async def select_worker(db: Session, user: User, order_id: int, bidding_id: int) -> Order:
    """用户选择师傅"""
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权操作该订单")

    bidding = (
        db.query(Bidding)
        .filter(Bidding.id == bidding_id, Bidding.order_id == order_id)
        .with_for_update()
        .first()
    )
    if not bidding:
        raise HTTPException(status_code=404, detail="竞价记录不存在")

    _load_dispatch_worker(
        db,
        bidding.worker_id,
        service_type=order.service_type,
        lock=True,
    )

    now = datetime.utcnow()
    _cas_update_status(
        db,
        order,
        "accepted",
        allowed_from=["pending"],
        worker_id=bidding.worker_id,
        accepted_at=now,
        final_price=bidding.price,
    )
    bidding.is_selected = True
    db.commit()
    db.refresh(order)

    # 通知师傅订单被选中
    await message_service.notify_order_accepted(db, order)
    return order


async def update_order_status(
    db: Session,
    account: Any,
    account_type: str,
    order_id: int,
    status: str,
    price: Optional[Decimal] = None,
) -> Order:
    """更新订单状态
    - 师傅: serving -> completed（需传 price）
    - 用户: pending -> cancelled
    """
    order = get_order_detail(db, order_id)
    now = datetime.utcnow()

    if account_type == "worker":
        if order.worker_id != account.id:
            raise HTTPException(status_code=403, detail="无权操作该订单")
        if status != "completed":
            raise HTTPException(status_code=400, detail="非法的状态变更")
        if price is None:
            raise HTTPException(status_code=400, detail="完成订单需提供最终价格")
        pending_extra_fee = db.query(OrderExtraFee.id).filter(
            OrderExtraFee.order_id == order.id,
            OrderExtraFee.status == "pending",
        ).first()
        if pending_extra_fee:
            raise HTTPException(status_code=409, detail="待用户处理补差价后才能完工")
        authoritative_price = Decimal(str(order.final_price or 0)).quantize(Decimal("0.01"))
        submitted_price = Decimal(str(price)).quantize(Decimal("0.01"))
        if submitted_price != authoritative_price:
            raise HTTPException(
                status_code=409,
                detail="最终价格已变更，请刷新订单后重试",
            )
        _cas_update_status(
            db,
            order,
            "completed",
            allowed_from=["serving"],
            final_price=authoritative_price,
            completed_at=now,
        )
        # 通知用户服务完成待支付
        await message_service.notify_service_finished(db, order)
    elif account_type == "user":
        if order.user_id != account.id:
            raise HTTPException(status_code=403, detail="无权操作该订单")
        if status != "cancelled":
            raise HTTPException(status_code=400, detail="非法的状态变更")
        _cas_update_status(
            db,
            order,
            "cancelled",
            allowed_from=["pending"],
            cancelled_at=now,
        )
    else:
        raise HTTPException(status_code=400, detail="未知的账号类型")

    db.commit()
    db.refresh(order)
    return order


def create_review(db: Session, user: User, order_id: int, data: ReviewRequest) -> Order:
    """用户评价订单"""
    order = get_order_detail(db, order_id)
    if order.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权操作该订单")

    if not (1 <= data.rating <= 5):
        raise HTTPException(status_code=400, detail="评分必须在 1-5 之间")

    now = datetime.utcnow()
    review_tags_json = json.dumps(data.tags, ensure_ascii=False) if data.tags else None
    review_images_json = json.dumps(data.images, ensure_ascii=False) if data.images else None

    _cas_update_status(
        db,
        order,
        "reviewed",
        allowed_from=["paid"],
        rating=data.rating,
        review_tags=review_tags_json,
        review_content=data.content,
        review_images=review_images_json,
        is_anonymous=data.is_anonymous,
        reviewed_at=now,
    )

    # 更新师傅评分和服务次数
    if order.worker_id:
        worker = db.query(Worker).filter(Worker.id == order.worker_id).first()
        if worker:
            total_score = worker.rating * worker.service_count + data.rating
            worker.service_count += 1
            worker.rating = round(total_score / worker.service_count, 2)

    db.commit()
    db.refresh(order)

    # 同步到独立 Review 表（异步审核机制）
    review_service.sync_review_from_order(db, order)

    return order

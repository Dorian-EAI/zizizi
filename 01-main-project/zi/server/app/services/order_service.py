"""订单业务逻辑"""

import json
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Any, Set

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User, Worker
from app.models.order import Order, Bidding, OrderCancellationRequest
from app.models.extra_fee import OrderExtraFee
from app.models.wallet import PaymentOrder, RefundOrder
from app.models.support_ticket import SupportTicket
from app.models.insurance import InsuranceClaim, InsurancePolicy
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

# v6.3 加速接单套餐由服务端定价，客户端只提交 package_key。
DISPATCH_ACCELERATION_PACKAGES = {
    "standard": {
        "key": "standard",
        "label": "标准加速",
        "amount": Decimal("19.00"),
        "promise_hours": 4,
    },
    "fast": {
        "key": "fast",
        "label": "极速接单",
        "amount": Decimal("39.00"),
        "promise_hours": 2,
    },
}
DEFAULT_EMPTY_RUN_FEE_AMOUNT = Decimal("30.00")
_ACTIVE_FULFILLMENT_STATUSES = ("accepted", "departing", "arrived", "serving")


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


_ACTION_META = {
    "cancel_order": ("取消订单", "danger", True),
    "view_bids": ("查看报价", "primary", False),
    "select_worker": ("选择师傅", "primary", False),
    "contact_worker": ("联系师傅", "secondary", False),
    "track_worker": ("查看实时位置", "primary", False),
    "handle_extra_fee": ("处理补差价", "primary", False),
    "confirm_and_pay": ("确认并支付", "primary", True),
    "open_dispute": ("报告问题", "danger", True),
    "contact_support": ("联系客服", "secondary", False),
    "review_order": ("评价服务", "primary", False),
    "request_refund": ("申请退款", "danger", True),
    "apply_claim": ("申请理赔", "danger", True),
    "reorder": ("再次发布", "secondary", False),
    "view_after_sale": ("查看售后", "secondary", False),
    "request_cancel": ("申请取消", "danger", True),
    "view_cancel_request": ("查看取消申请", "secondary", False),
    "accept_order": ("接单", "primary", True),
    "confirm_acceptance": ("确认验收", "primary", True),
    "view_acceptance": ("查看验收", "secondary", False),
    "handle_empty_run_fee": ("处理空跑费", "primary", False),
    "accelerate_dispatch": ("加速接单", "secondary", True),
    "depart_order": ("出发", "primary", False),
    "report_location": ("上报位置", "secondary", False),
    "arrive_order": ("确认到达", "primary", False),
    "start_service": ("开始服务", "primary", False),
    "apply_extra_fee": ("申请补差价", "secondary", False),
    "complete_service": ("完工", "primary", True),
    "view_settlement": ("查看结算", "secondary", False),
    "reply_review": ("回复评价", "secondary", False),
}


def _normalize_active_role(active_role: str) -> str:
    """把 API 的 user/worker 账号类型映射为投影使用的 client/worker 角色。"""
    value = str(active_role or "").strip().lower()
    if value == "worker":
        return "worker"
    if value in {"client", "user"}:
        return "client"
    return value


def _to_cents(value: Any) -> int:
    try:
        return int((Decimal(str(value or 0)) * 100).quantize(Decimal("1")))
    except (ArithmeticError, TypeError, ValueError):
        return 0


def _load_projection_context(db: Session, orders: List[Order]) -> dict:
    """批量加载投影所需事实，避免订单列表逐条查询。"""
    order_ids = [int(order.id) for order in orders if order.id]
    order_nos = [str(order.order_no) for order in orders if order.order_no]
    context = {
        "bids": {},
        "extra": {},
        "payments": {},
        "refunds": {},
        "tickets": {},
        "claims": {},
        "policies": {},
        "cancel_requests": {},
    }
    if not order_ids and not order_nos:
        return context

    if order_ids:
        bid_rows = (
            db.query(Bidding.order_id, func.count(Bidding.id))
            .filter(Bidding.order_id.in_(order_ids))
            .group_by(Bidding.order_id)
            .all()
        )
        context["bids"] = {row[0]: int(row[1] or 0) for row in bid_rows}

        for fee in (
            db.query(OrderExtraFee)
            .filter(OrderExtraFee.order_id.in_(order_ids))
            .order_by(OrderExtraFee.id.asc())
            .all()
        ):
            context["extra"].setdefault(fee.order_id, []).append(str(fee.status or ""))

        for ticket in (
            db.query(SupportTicket)
            .filter(SupportTicket.related_order_id.in_(order_ids))
            .order_by(SupportTicket.created_at.asc())
            .all()
        ):
            context["tickets"].setdefault(ticket.related_order_id, []).append(ticket)

        for claim in (
            db.query(InsuranceClaim)
            .filter(InsuranceClaim.order_id.in_(order_ids))
            .order_by(InsuranceClaim.created_at.asc())
            .all()
        ):
            context["claims"].setdefault(claim.order_id, []).append(claim)

        for policy in (
            db.query(InsurancePolicy)
            .filter(
                InsurancePolicy.order_id.in_(order_ids),
                InsurancePolicy.status == "active",
            )
            .all()
        ):
            context["policies"].setdefault(policy.order_id, []).append(policy)

        for request in (
            db.query(OrderCancellationRequest)
            .filter(OrderCancellationRequest.order_id.in_(order_ids))
            .order_by(OrderCancellationRequest.id.asc())
            .all()
        ):
            context["cancel_requests"][request.order_id] = request

    if order_nos:
        for payment in (
            db.query(PaymentOrder)
            .filter(PaymentOrder.order_no.in_(order_nos))
            .order_by(PaymentOrder.id.asc())
            .all()
        ):
            context["payments"].setdefault(payment.order_no, []).append(payment)

        for refund in (
            db.query(RefundOrder)
            .filter(RefundOrder.order_no.in_(order_nos))
            .order_by(RefundOrder.id.asc())
            .all()
        ):
            context["refunds"].setdefault(refund.order_no, []).append(refund)

    return context


def _payment_projection(order: Order, context: dict) -> tuple[str, dict, list]:
    payments = context["payments"].get(order.order_no, [])
    refunds = context["refunds"].get(order.order_no, [])
    paid_statuses = {"paid", "partially_refunded", "refunded"}
    paid_cents = sum(
        _to_cents(payment.amount)
        for payment in payments
        if str(payment.status or "") in paid_statuses
    )
    legacy_status = str(order.status or "pending")
    if paid_cents == 0 and legacy_status in {"paid", "reviewed"}:
        paid_cents = _to_cents(order.final_price or 0)

    refunded_cents = sum(
        _to_cents(refund.amount)
        for refund in refunds
        if str(refund.status or "") == "success"
    )
    has_pending_refund = any(
        str(refund.status or "") in {"pending", "processing"} for refund in refunds
    )

    if any(str(payment.status or "") == "refunded" for payment in payments) or (
        paid_cents and refunded_cents >= paid_cents
    ):
        payment_state = "refunded"
    elif has_pending_refund:
        payment_state = "refunding"
    elif paid_cents > 0 or legacy_status in {"paid", "reviewed"}:
        payment_state = "paid"
    elif any(str(payment.status or "") in {"pending", "reserved"} for payment in payments):
        payment_state = "processing"
    elif any(str(payment.status or "") == "failed" for payment in payments):
        payment_state = "failed"
    elif legacy_status == "cancelled":
        payment_state = "not_applicable"
    else:
        payment_state = "unpaid"

    summary = {
        "paid_amount": round(paid_cents / 100, 2),
        "refunded_amount": round(refunded_cents / 100, 2),
        "refundable_amount": round(max(paid_cents - refunded_cents, 0) / 100, 2),
    }
    return payment_state, summary, refunds


def _aftersale_projection(order: Order, context: dict, refunds: list) -> tuple[str, str | None, str | None]:
    events = []
    for ticket in context["tickets"].get(order.id, []):
        status = str(ticket.status or "open")
        if status == "open":
            state = "requested"
        elif status == "processing":
            state = "processing"
        elif status in {"resolved", "closed"}:
            state = "resolved"
        else:
            state = "processing"
        if str(ticket.ticket_type or "") == "appeal" and state in {"requested", "processing"}:
            state = "appealing"
        events.append((
            ticket.updated_at or ticket.created_at,
            state,
            str(ticket.ticket_type or "ticket"),
            str(ticket.ticket_no or ticket.id),
        ))

    for claim in context["claims"].get(order.id, []):
        state = {
            "pending": "requested",
            "approved": "resolved",
            "rejected": "rejected",
        }.get(str(claim.status or ""), "processing")
        events.append((
            claim.settled_at or claim.audited_at or claim.created_at,
            state,
            "claim",
            str(claim.id),
        ))

    for refund in refunds:
        state = {
            "pending": "processing",
            "success": "resolved",
            "failed": "rejected",
        }.get(str(refund.status or ""), "processing")
        events.append((
            refund.refunded_at or refund.created_at,
            state,
            "refund",
            str(refund.refund_no or refund.id),
        ))

    if not events:
        return "none", None, None
    latest = max(events, key=lambda item: item[0] or datetime.min)
    return latest[1], latest[2], latest[3]


def _build_action_contract(keys: List[str], disabled: dict) -> dict:
    actions = []
    for key in keys:
        label, priority, requires_confirm = _ACTION_META.get(
            key, (key, "secondary", False)
        )
        item = {
            "key": key,
            "label": label,
            "priority": priority,
            "requires_confirm": requires_confirm,
            "enabled": key not in disabled,
        }
        if key in disabled:
            item["reason"] = disabled[key]
        actions.append(item)

    enabled_keys = [item["key"] for item in actions if item["enabled"]]
    primary_action = next(
        (
            item["key"]
            for item in actions
            if item["enabled"] and item["priority"] == "primary"
        ),
        None,
    )
    return {
        "primary_action": primary_action,
        "allowed_actions": actions,
        "allowed_action_keys": enabled_keys,
        "blocked_actions": [item for item in actions if not item["enabled"]],
    }


def _build_projection_from_context(
    order: Order,
    active_role: str,
    account: Optional[Any],
    context: dict,
) -> dict:
    legacy_status = str(order.status or "pending")
    service_state = "completed" if legacy_status == "paid" else legacy_status
    payment_state, payment_summary, refunds = _payment_projection(order, context)
    pricing_mode = str(getattr(order, "pricing_mode", "bidding") or "bidding")
    acceptance_state = str(
        getattr(order, "acceptance_state", "not_required") or "not_required"
    )
    empty_run_fee_state = str(
        getattr(order, "empty_run_fee_state", "none") or "none"
    )

    extra_statuses = context["extra"].get(order.id, [])
    if "pending" in extra_statuses:
        price_adjust_state = "pending"
    elif extra_statuses:
        price_adjust_state = extra_statuses[-1]
    else:
        price_adjust_state = "none"

    aftersale_state, aftersale_type, aftersale_object_id = _aftersale_projection(
        order, context, refunds
    )
    cancel_request = context["cancel_requests"].get(order.id)
    cancel_request_state = (
        str(cancel_request.status or "none") if cancel_request else "none"
    )

    actions: List[str] = []
    disabled: dict = {}
    payment_methods: List[dict] = []

    def add(key: str) -> None:
        if key not in actions:
            actions.append(key)

    if active_role == "client":
        if legacy_status == "pending_dispatch":
            add("cancel_order")
            add("contact_support")
            if empty_run_fee_state in {"pending", "disputed"}:
                add("handle_empty_run_fee")
            if (
                pricing_mode in {"fixed_price", "self_priced"}
                and _to_cents(getattr(order, "dispatch_acceleration_fee", 0)) == 0
            ):
                add("accelerate_dispatch")
        elif legacy_status == "pending":
            if context["bids"].get(order.id, 0) > 0:
                add("view_bids")
                add("select_worker")
            add("cancel_order")
            add("contact_support")
        elif legacy_status == "accepted":
            add("contact_worker")
            if cancel_request_state == "pending":
                add("view_cancel_request")
            else:
                add("request_cancel")
        elif legacy_status == "departing":
            add("track_worker")
            add("contact_worker")
            if cancel_request_state == "pending":
                add("view_cancel_request")
            else:
                add("request_cancel")
        elif legacy_status == "arrived":
            add("contact_worker")
            if cancel_request_state == "pending":
                add("view_cancel_request")
            else:
                add("request_cancel")
            if price_adjust_state == "pending":
                add("handle_extra_fee")
        elif legacy_status == "serving":
            add("contact_worker")
            add("open_dispute")
            add("contact_support")
            if price_adjust_state == "pending":
                add("handle_extra_fee")
        elif legacy_status == "completed":
            if acceptance_state == "pending":
                add("confirm_acceptance")
                add("open_dispute")
                add("contact_support")
            elif acceptance_state == "disputed":
                add("open_dispute")
                add("contact_support")
                if aftersale_state != "none":
                    add("view_after_sale")
            else:
                if payment_state in {"unpaid", "failed"}:
                    add("confirm_and_pay")
                elif payment_state == "processing":
                    add("confirm_and_pay")
                    disabled["confirm_and_pay"] = "支付结果确认中，请稍后刷新"
                add("open_dispute")
                add("contact_support")
                if aftersale_state != "none":
                    add("view_after_sale")
                if payment_state == "paid":
                    add("review_order")
                    add("request_refund")
                    if context["policies"].get(order.id):
                        add("apply_claim")
        elif legacy_status == "paid":
            if payment_state == "paid":
                add("review_order")
                add("request_refund")
                if context["policies"].get(order.id):
                    add("apply_claim")
            add("contact_support")
            if aftersale_state != "none":
                add("view_after_sale")
        elif legacy_status == "reviewed":
            add("reorder")
            add("contact_support")
            if payment_state == "paid":
                add("request_refund")
                if context["policies"].get(order.id):
                    add("apply_claim")
            if aftersale_state != "none":
                add("view_after_sale")
        elif legacy_status in {"cancelled", "closed"}:
            add("reorder")
            add("contact_support")
            if aftersale_state != "none":
                add("view_after_sale")

        if empty_run_fee_state in {"pending", "disputed"}:
            add("handle_empty_run_fee")

        if legacy_status == "completed" and payment_state in {"unpaid", "failed"}:
            has_openid = bool(getattr(account, "openid", None))
            payment_methods = [
                {
                    "key": "wechat",
                    "enabled": has_openid,
                    "disabled_reason": "当前账号未绑定微信" if not has_openid else "",
                },
                {"key": "wallet", "enabled": True, "disabled_reason": ""},
            ]
    elif active_role == "worker":
        if legacy_status == "pending_dispatch":
            add("accept_order")
            add("contact_support")
        elif legacy_status == "accepted":
            add("depart_order")
            add("contact_user")
        elif legacy_status == "departing":
            add("report_location")
            add("arrive_order")
            add("contact_user")
        elif legacy_status == "arrived":
            add("start_service")
            add("contact_user")
        elif legacy_status == "serving":
            add("apply_extra_fee")
            add("contact_user")
            add("complete_service")
            if price_adjust_state == "pending":
                disabled["complete_service"] = "待用户处理补差价后才能完工"
        elif legacy_status == "completed":
            if acceptance_state == "pending":
                add("view_acceptance")
            add("view_settlement")
        elif legacy_status == "paid":
            add("view_settlement")
        elif legacy_status == "reviewed":
            add("view_settlement")
            add("reply_review")

    contract = _build_action_contract(actions, disabled)
    return {
        "active_role": active_role,
        "service_state": service_state,
        "pricing_mode": pricing_mode,
        "acceptance_state": acceptance_state,
        "empty_run_fee_state": empty_run_fee_state,
        "payment_state": payment_state,
        "aftersale_state": aftersale_state,
        "aftersale_type": aftersale_type,
        "aftersale_object_id": aftersale_object_id,
        "price_adjust_state": price_adjust_state,
        "cancel_request_state": cancel_request_state,
        "cancel_request_id": cancel_request.id if cancel_request else None,
        "cancel_request_no": cancel_request.request_no if cancel_request else None,
        "version": int(order.version or 0),
        "primary_action": contract["primary_action"],
        "allowed_actions": contract["allowed_actions"],
        "allowed_action_keys": contract["allowed_action_keys"],
        "blocked_actions": contract["blocked_actions"],
        "payment_methods": payment_methods,
        "payment_summary": payment_summary,
    }


def build_order_projection(
    db: Session,
    order: Order,
    active_role: str,
    account: Optional[Any] = None,
) -> dict:
    """构建多轴状态与可执行动作合同（单订单）。"""
    role = _normalize_active_role(active_role)
    context = _load_projection_context(db, [order])
    return _build_projection_from_context(order, role, account, context)


def build_order_projections(
    db: Session,
    orders: List[Order],
    active_role: str,
    account: Optional[Any] = None,
) -> List[dict]:
    """构建多轴状态与可执行动作合同（批量，避免订单列表 N+1 查询）。"""
    order_list = list(orders or [])
    if not order_list:
        return []
    role = _normalize_active_role(active_role)
    context = _load_projection_context(db, order_list)
    return [
        _build_projection_from_context(order, role, account, context)
        for order in order_list
    ]


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
    pricing_mode = data.pricing_mode
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
        final_price=(
            data.budget
            if pricing_mode in {"fixed_price", "self_priced"} and data.budget is not None
            else None
        ),
        urgent=data.urgent,
        urgent_amount=(
            data.urgent_amount if data.urgent_amount is not None else Decimal("0")
        ),
        pricing_mode=pricing_mode,
        acceptance_state="not_required",
        empty_run_fee_state="none",
        empty_run_fee_amount=Decimal("0"),
        dispatch_acceleration_fee=Decimal("0"),
        status="pending_dispatch" if pricing_mode in {"fixed_price", "self_priced"} else "pending",
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
    """获取可报价/可接单订单：pending（报价）或 pending_dispatch（一口价/自己定价）。"""
    worker, service_types = _load_dispatch_worker(db, worker_or_id)
    bid_order_ids = select(Bidding.order_id).where(Bidding.worker_id == worker.id)
    query = (
        db.query(Order)
        .filter(Order.status.in_(["pending", "pending_dispatch"]))
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
    from app.services.deposit_service import get_platform_cut_rate

    # 选中报价时快照费率，后续保证金等级/费率变化不追改既有订单。
    platform_fee_rate = get_platform_cut_rate(db, bidding.worker_id)
    _cas_update_status(
        db,
        order,
        "accepted",
        allowed_from=["pending"],
        worker_id=bidding.worker_id,
        accepted_at=now,
        final_price=bidding.price,
        platform_fee_rate=platform_fee_rate,
    )
    bidding.is_selected = True
    db.commit()
    db.refresh(order)

    # 通知师傅订单被选中
    await message_service.notify_order_accepted(db, order)
    return order


async def accept_order(
    db: Session,
    worker: Worker,
    order_id: int,
    version: Optional[int] = None,
) -> Order:
    """一口价/自己定价订单原子接单：首个有效请求成功，其余请求立即失效。"""
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if str(order.pricing_mode or "bidding") not in {"fixed_price", "self_priced"}:
        raise HTTPException(status_code=409, detail="报价订单需由用户选择报价后成交")
    if order.status != "pending_dispatch":
        raise HTTPException(status_code=409, detail="该订单已被接单或当前不可接单")
    if version is not None and int(order.version or 0) != int(version):
        raise HTTPException(status_code=409, detail="订单已被修改，请刷新后重试")

    locked_worker, _ = _load_dispatch_worker(
        db,
        worker.id,
        service_type=order.service_type,
        lock=True,
    )
    has_active_order = (
        db.query(Order.id)
        .filter(
            Order.worker_id == locked_worker.id,
            Order.status.in_(list(_ACTIVE_FULFILLMENT_STATUSES)),
        )
        .first()
    )
    if has_active_order:
        raise HTTPException(status_code=409, detail="您有进行中的订单，暂不可接单")

    from app.services.deposit_service import get_platform_cut_rate

    now = datetime.utcnow()
    _cas_update_status(
        db,
        order,
        "accepted",
        allowed_from=["pending_dispatch"],
        worker_id=locked_worker.id,
        accepted_at=now,
        platform_fee_rate=get_platform_cut_rate(db, locked_worker.id),
    )
    db.commit()
    db.refresh(order)
    await message_service.notify_order_accepted(db, order)
    return order


def confirm_acceptance(
    db: Session,
    user: User,
    order_id: int,
    action: str,
    reason: Optional[str] = None,
) -> Order:
    """用户验收：通过则进入结算，报告问题则冻结结算并进入售后。"""
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
    if order.status != "completed":
        raise HTTPException(status_code=409, detail="服务完成后才能验收")
    if str(order.acceptance_state or "") != "pending":
        raise HTTPException(status_code=409, detail="当前订单不在待验收状态")

    if action == "accept":
        _cas_update_status(
            db,
            order,
            "completed",
            allowed_from=["completed"],
            acceptance_state="accepted",
        )
        if order.worker_id:
            from app.services import worker_fund_service

            worker_fund_service.settle_order_income(db, order.order_no)
    elif action == "dispute":
        if not str(reason or "").strip():
            raise HTTPException(status_code=400, detail="报告问题需填写问题说明")
        _cas_update_status(
            db,
            order,
            "completed",
            allowed_from=["completed"],
            acceptance_state="disputed",
        )
    else:
        raise HTTPException(status_code=400, detail="不支持的验收动作")

    db.commit()
    db.refresh(order)
    return order


def get_acceptance_summary(order: Order) -> dict:
    """验收状态与剩余观察期。"""
    acceptance_state = str(order.acceptance_state or "not_required")
    deadline = order.acceptance_deadline
    remaining_seconds = None
    if deadline is not None:
        remaining_seconds = max(
            0, int((deadline - datetime.utcnow()).total_seconds())
        )
    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "service_state": str(order.status or ""),
        "acceptance_state": acceptance_state,
        "acceptance_deadline": (
            deadline.isoformat() + "Z" if deadline is not None else None
        ),
        "remaining_seconds": remaining_seconds,
        "empty_run_fee_state": str(order.empty_run_fee_state or "none"),
        "empty_run_fee_amount": float(order.empty_run_fee_amount or 0),
        "can_accept": str(order.status or "") == "completed"
        and acceptance_state == "pending",
        "can_dispute": str(order.status or "") == "completed"
        and acceptance_state == "pending",
    }


def confirm_risk_confirmation(
    db: Session,
    user: User,
    order_id: int,
    version: str,
    confirmed: bool,
) -> Order:
    """保存用户对风险确认书的确认版本。"""
    if not confirmed:
        raise HTTPException(status_code=422, detail="请先阅读并勾选风险确认书")
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
    if order.status not in {"pending", "pending_dispatch"}:
        raise HTTPException(status_code=409, detail="当前订单状态不可补充风险确认")

    service = (
        db.query(ServiceType)
        .filter(func.lower(func.trim(ServiceType.key)) == _normalize_service_type(order.service_type))
        .first()
    )
    expected_version = None
    if service and service.risk_confirmation:
        try:
            payload = json.loads(service.risk_confirmation)
        except (TypeError, ValueError):
            payload = None
        if isinstance(payload, dict):
            expected_version = str(payload.get("version") or "").strip() or None
    if expected_version and version != expected_version:
        raise HTTPException(status_code=409, detail="风险确认书已更新，请重新阅读")

    _cas_update_status(
        db,
        order,
        str(order.status),
        allowed_from=[str(order.status)],
        risk_confirmation_version=version,
    )
    db.commit()
    db.refresh(order)
    return order


def accelerate_dispatch(
    db: Session,
    user: User,
    order_id: int,
    package_key: str,
) -> tuple[Order, dict]:
    """购买加速接单增值服务；金额由服务端套餐决定。"""
    package = DISPATCH_ACCELERATION_PACKAGES.get(str(package_key or "").strip())
    if not package:
        raise HTTPException(status_code=422, detail="加速接单套餐不存在")
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
    if order.status != "pending_dispatch":
        raise HTTPException(status_code=409, detail="当前订单状态不可购买加速接单")
    if str(order.pricing_mode or "") not in {"fixed_price", "self_priced"}:
        raise HTTPException(status_code=409, detail="加速接单仅适用于一口价/自己定价订单")
    if _to_cents(order.dispatch_acceleration_fee) > 0:
        raise HTTPException(status_code=409, detail="该订单已购买加速接单")

    amount = package["amount"]
    current_price = Decimal(str(order.final_price or 0)).quantize(Decimal("0.01"))
    _cas_update_status(
        db,
        order,
        "pending_dispatch",
        allowed_from=["pending_dispatch"],
        dispatch_acceleration_fee=amount,
        final_price=current_price + amount,
    )
    db.commit()
    db.refresh(order)
    return order, {
        "package_key": package["key"],
        "label": package["label"],
        "amount": float(amount),
        "promise_hours": package["promise_hours"],
    }


def handle_empty_run_fee(
    db: Session,
    user: User,
    order_id: int,
    action: str,
    reason: Optional[str] = None,
) -> Order:
    """用户确认或申诉空跑费。"""
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
    current_state = str(order.empty_run_fee_state or "none")
    if current_state not in {"pending", "disputed"}:
        raise HTTPException(status_code=409, detail="当前订单没有待处理的空跑费")

    if action == "confirm":
        new_state = "paid"
    elif action == "dispute":
        if not str(reason or "").strip():
            raise HTTPException(status_code=400, detail="申请空跑费争议需填写说明")
        new_state = "disputed"
    else:
        raise HTTPException(status_code=400, detail="不支持的空跑费动作")

    _cas_update_status(
        db,
        order,
        str(order.status),
        allowed_from=[str(order.status)],
        empty_run_fee_state=new_state,
    )
    db.commit()
    db.refresh(order)
    return order


def auto_accept_overdue_orders(
    db: Session,
    now: Optional[datetime] = None,
    limit: int = 200,
) -> int:
    """观察期到期自动验收；不提交事务，由调用方统一提交。"""
    current = now or datetime.utcnow()
    orders = (
        db.query(Order)
        .filter(
            Order.status == "completed",
            Order.acceptance_state == "pending",
            Order.acceptance_deadline.isnot(None),
            Order.acceptance_deadline <= current,
        )
        .order_by(Order.acceptance_deadline.asc())
        .limit(limit)
        .all()
    )
    count = 0
    from app.services import worker_fund_service

    for order in orders:
        try:
            _cas_update_status(
                db,
                order,
                "completed",
                allowed_from=["completed"],
                acceptance_state="auto_accepted",
            )
            if order.worker_id:
                worker_fund_service.settle_order_income(db, order.order_no)
            count += 1
        except HTTPException:
            continue
    return count


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
    - 用户: pending/pending_dispatch -> cancelled
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
        # v6.3 基线：安装/清洗/保洁 3 天，其余 7 天；后续由品类配置覆盖。
        acceptance_days = (
            3
            if any(
                keyword in str(order.service_name or "")
                for keyword in ("安装", "清洗", "保洁")
            )
            else 7
        )
        _cas_update_status(
            db,
            order,
            "completed",
            allowed_from=["serving"],
            final_price=authoritative_price,
            completed_at=now,
            acceptance_state="pending",
            acceptance_deadline=now + timedelta(days=acceptance_days),
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
            allowed_from=["pending", "pending_dispatch"],
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

"""支付与钱包业务逻辑

提供钱包信息查询、交易记录、充值、提现、订单支付等功能。
Transaction 的 amount 始终为正数，通过 type 区分收入/支出。
"""

import random
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.user import User, Worker
from app.models.wallet import PaymentOrder, RefundOrder, Transaction
from app.services.order_service import _cas_update_status


# ===== 辅助函数 =====

def _gen_payment_no() -> str:
    """生成支付单号：PAY + 时间戳 + 随机数"""
    return "PAY" + datetime.utcnow().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999))


def _gen_refund_no() -> str:
    """生成退款单号：REF + 时间戳 + 随机数。"""
    return "REF" + datetime.utcnow().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999))


def _to_cents(value) -> int:
    """金额统一转换为整数分后参与比较与拆分。"""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(status_code=400, detail="金额格式错误")
    if not amount.is_finite():
        raise HTTPException(status_code=400, detail="金额格式错误")
    return int(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100)


def _from_cents(value: int) -> float:
    return float(Decimal(value) / Decimal(100))


def _add_transaction(
    db: Session,
    owner_type: str,
    owner_id: int,
    type: str,
    amount: float,
    balance_after: float,
    method: Optional[str] = None,
    order_id: Optional[str] = None,
    description: Optional[str] = None,
    status: str = "success",
    bank_info: Optional[str] = None,
) -> Transaction:
    """创建交易记录"""
    tx = Transaction(
        owner_type=owner_type,
        owner_id=owner_id,
        type=type,
        amount=amount,
        balance_after=balance_after,
        method=method,
        order_id=order_id,
        description=description,
        status=status,
        bank_info=bank_info,
    )
    db.add(tx)
    db.flush()
    return tx


def _tx_to_dict(tx: Transaction) -> dict:
    """将交易记录转为字典"""
    return {
        "id": tx.id,
        "type": tx.type,
        "amount": float(tx.amount),
        "balance_after": float(tx.balance_after) if tx.balance_after is not None else None,
        "method": tx.method,
        "order_id": tx.order_id,
        "description": tx.description,
        "status": tx.status,
        "created_at": tx.created_at.strftime("%Y-%m-%d %H:%M:%S") if tx.created_at else None,
    }


# ===== 钱包信息 =====

def get_wallet_info(db: Session, account, account_type: str) -> dict:
    """获取钱包信息：余额、本月收入、本月支出、累计收入

    Args:
        db: 数据库会话
        account: User 或 Worker 实例
        account_type: "user" 或 "worker"
    """
    owner_type = account_type
    owner_id = account.id
    now = datetime.utcnow()

    # 本月收入
    month_income = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.owner_type == owner_type,
            Transaction.owner_id == owner_id,
            Transaction.type == "income",
            Transaction.status == "success",
            extract("year", Transaction.created_at) == now.year,
            extract("month", Transaction.created_at) == now.month,
        )
        .scalar()
    ) or 0.0

    # 本月支出
    month_expense = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.owner_type == owner_type,
            Transaction.owner_id == owner_id,
            Transaction.type == "expense",
            Transaction.status == "success",
            extract("year", Transaction.created_at) == now.year,
            extract("month", Transaction.created_at) == now.month,
        )
        .scalar()
    ) or 0.0

    # 累计收入
    total_income = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.owner_type == owner_type,
            Transaction.owner_id == owner_id,
            Transaction.type == "income",
            Transaction.status == "success",
        )
        .scalar()
    ) or 0.0

    return {
        "balance": float(account.balance or 0),
        "month_income": float(month_income),
        "month_expense": float(month_expense),
        "total_income": float(total_income),
    }


# ===== 交易记录 =====

def get_transactions(
    db: Session,
    account,
    account_type: str,
    tx_type: str = "all",
    page: int = 1,
    size: int = 20,
) -> dict:
    """分页查询交易记录

    Args:
        tx_type: 交易类型筛选 income/expense/recharge/withdraw/all
        page: 页码（从 1 开始）
        size: 每页条数
    """
    owner_type = account_type
    owner_id = account.id

    query = db.query(Transaction).filter(
        Transaction.owner_type == owner_type,
        Transaction.owner_id == owner_id,
    )

    if tx_type and tx_type != "all":
        query = query.filter(Transaction.type == tx_type)

    total = query.count()
    offset = (page - 1) * size
    items = (
        query.order_by(Transaction.created_at.desc())
        .offset(offset)
        .limit(size)
        .all()
    )

    return {
        "list": [_tx_to_dict(t) for t in items],
        "total": total,
        "page": page,
        "has_more": (offset + size) < total,
    }


# ===== 充值 =====

def recharge(db: Session, account, account_type: str, amount: float, method: str) -> dict:
    """创建充值支付单。

    外部渠道充值不得在客户端请求阶段增加余额；只有验签且金额一致的微信
    支付回调会真正入账。
    """
    amount_cents = _to_cents(amount)
    if amount_cents <= 0:
        raise HTTPException(status_code=400, detail="充值金额必须大于 0")
    if method != "wechat":
        raise HTTPException(status_code=501, detail="当前仅支持微信充值")
    if not getattr(account, "openid", None):
        raise HTTPException(status_code=400, detail="当前账号未绑定微信 openid")

    from app.services.wechat_pay_service import create_jsapi_order

    try:
        payment = PaymentOrder(
            payment_no=_gen_payment_no(),
            order_no=None,
            amount=_from_cents(amount_cents),
            method="wechat",
            payer_type=account_type,
            payer_id=account.id,
            status="pending",
        )
        db.add(payment)
        db.flush()
        jsapi_params = create_jsapi_order(db, payment, account.openid)
        db.commit()
        return {
            "success": True,
            "status": "pending",
            "payment_no": payment.payment_no,
            "pay_amount": float(payment.amount),
            "jsapi_params": jsapi_params,
            "balance": float(account.balance or 0),
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


# ===== 提现 =====

def withdraw(
    db: Session,
    account,
    account_type: str,
    amount: float,
    method: str,
    bank_info: Optional[str] = None,
) -> dict:
    """提现

    Args:
        amount: 提现金额
        method: 提现方式 bank/wechat
        bank_info: 银行卡信息（JSON 字符串）
    """
    from app.config import settings

    if settings.APP_ENV.lower() != "development" or not settings.WX_PAY_MOCK_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="提现到账回调尚未接入，生产环境暂不受理提现",
        )
    if account_type != "worker":
        raise HTTPException(status_code=403, detail="仅师傅账号可以提现")
    if method != "wechat":
        raise HTTPException(status_code=501, detail="当前仅支持微信提现")

    amount_cents = _to_cents(amount)
    if amount_cents < 1000:
        raise HTTPException(status_code=400, detail="最低提现金额为 10 元")

    locked_account = db.query(Worker).filter(Worker.id == account.id).with_for_update().first()
    if not locked_account:
        raise HTTPException(status_code=404, detail="师傅账号不存在")
    if not locked_account.openid:
        raise HTTPException(status_code=400, detail="当前账号未绑定微信 openid")
    if _to_cents(locked_account.balance or 0) < amount_cents:
        raise HTTPException(status_code=400, detail="余额不足")

    owner_type = account_type
    owner_id = locked_account.id

    # 扣减余额
    locked_account.balance = _from_cents(_to_cents(locked_account.balance or 0) - amount_cents)
    db.flush()

    # 创建交易记录（提现为待审核状态）
    tx = _add_transaction(
        db,
        owner_type=owner_type,
        owner_id=owner_id,
        type="withdraw",
        amount=_from_cents(amount_cents),
        balance_after=float(locked_account.balance),
        method=method,
        description="提现申请",
        status="pending",
        bank_info=None,
    )
    db.commit()
    db.refresh(tx)

    return {
        "balance": float(locked_account.balance),
        "transaction": _tx_to_dict(tx),
    }


# ===== 订单支付 =====

async def pay_order(
    db: Session,
    user: User,
    order_no: str,
    method: str,
    coupon_id: Optional[int] = None,
    wallet_amount: Optional[float] = None,
    wechat_amount: Optional[float] = None,
) -> dict:
    """订单支付

    支持的支付方式：
      - wallet: 余额支付（全额从钱包扣）
      - wechat: 微信支付（全额走微信）
      - combined: 组合支付（部分钱包 + 部分微信）
      - offline: 线下支付（师傅上门收款，标记为待确认）

    Args:
        user: 当前用户
        order_no: 订单编号
        method: 支付方式 wallet/wechat/combined/offline
        coupon_id: 优惠券 ID（可选）
        wallet_amount: 组合支付时钱包抵扣金额
        wechat_amount: 组合支付时微信支付金额
    """
    if method not in {"wallet", "wechat", "combined", "offline"}:
        raise HTTPException(status_code=400, detail="不支持的支付方式")
    if method == "combined":
        from app.config import settings
        if settings.APP_ENV.lower() != "development" or not settings.WX_PAY_MOCK_ENABLED:
            raise HTTPException(
                status_code=501,
                detail="组合支付撤销与资金解冻尚未接入，生产环境暂不开放",
            )

    # 锁定订单，防止并发创建多个可支付单或重复扣款。
    order = (
        db.query(Order)
        .filter(Order.order_no == order_no)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=400, detail="订单不存在")

    if order.user_id != user.id:
        raise HTTPException(status_code=400, detail="无权支付该订单")

    if order.status != "completed":
        raise HTTPException(status_code=400, detail="订单未完成，无法支付")

    # 计算支付金额
    final_price_cents = _to_cents(order.final_price or 0)
    if final_price_cents < 0:
        raise HTTPException(status_code=400, detail="订单价格异常")
    final_price = _from_cents(final_price_cents)
    discount_amount = 0.0

    # 优惠券抵扣
    if coupon_id:
        from app.services.coupon_service import apply_coupon, consume_coupon
        coupon_result = apply_coupon(db, user, coupon_id, final_price, order.service_type)
        discount_amount = _from_cents(_to_cents(coupon_result["discount_amount"]))

    pay_amount_cents = max(final_price_cents - _to_cents(discount_amount), 0)
    pay_amount = _from_cents(pay_amount_cents)

    active_payment = (
        db.query(PaymentOrder)
        .filter(
            PaymentOrder.order_no == order.order_no,
            PaymentOrder.status.in_(("pending", "reserved")),
        )
        .first()
    )
    if active_payment:
        raise HTTPException(
            status_code=409,
            detail=f"订单已有待处理支付单: {active_payment.payment_no}",
        )
    if coupon_id:
        coupon_payment = (
            db.query(PaymentOrder)
            .filter(
                PaymentOrder.coupon_id == coupon_id,
                PaymentOrder.order_no != order.order_no,
                PaymentOrder.status.in_(("pending", "reserved")),
            )
            .first()
        )
        if coupon_payment:
            raise HTTPException(status_code=409, detail="该优惠券已有待处理支付")

    # 全额优惠无需调外部渠道，按站内零元支付完成。
    if pay_amount_cents == 0:
        method = "wallet"

    # ===== 线下支付 =====
    if method == "offline":
        payment = PaymentOrder(
            payment_no=_gen_payment_no(),
            order_no=order.order_no,
            amount=pay_amount,
            method="offline",
            coupon_id=coupon_id,
            discount_amount=discount_amount,
            payer_type="user",
            payer_id=user.id,
            status="pending",  # 线下支付需师傅确认收款
            paid_at=None,
        )
        db.add(payment)
        db.commit()
        return {
            "success": True,
            "status": "pending",
            "payment_no": payment.payment_no,
            "method": "offline",
            "message": "线下支付待指派师傅确认；确认前不会改变订单或钱包余额",
            "balance": float(user.balance or 0),
        }

    # ===== 组合支付 =====
    if method == "combined":
        if not wallet_amount and not wechat_amount:
            raise HTTPException(status_code=400, detail="组合支付需指定钱包金额和微信金额")

        user = db.query(User).filter(User.id == user.id).with_for_update().first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        wallet_pay_cents = _to_cents(wallet_amount or 0)
        wechat_pay_cents = _to_cents(wechat_amount or 0)
        wallet_pay = _from_cents(wallet_pay_cents)
        wechat_pay = _from_cents(wechat_pay_cents)

        if wallet_pay_cents + wechat_pay_cents != pay_amount_cents:
            raise HTTPException(
                status_code=400,
                detail=f"金额不匹配：钱包({wallet_pay})+微信({wechat_pay})≠应付({pay_amount})",
            )

        if wallet_pay > 0:
            if _to_cents(user.balance or 0) < wallet_pay_cents:
                raise HTTPException(status_code=400, detail="钱包余额不足")
            # 先从可用余额扣除并记为 reserved；微信成功回调后才正式结算。
            user.balance = _from_cents(_to_cents(user.balance or 0) - wallet_pay_cents)
            db.flush()

        # 钱包部分直接扣款
        payment_wallet = PaymentOrder(
            payment_no=_gen_payment_no(),
            order_no=order.order_no,
            amount=wallet_pay,
            method="wallet",
            coupon_id=coupon_id,
            discount_amount=discount_amount,
            payer_type="user",
            payer_id=user.id,
            status="reserved" if wechat_pay_cents > 0 else "paid",
            paid_at=None if wechat_pay_cents > 0 else datetime.utcnow(),
        )
        db.add(payment_wallet)
        db.flush()

        if wallet_pay > 0:
            _add_transaction(
                db,
                owner_type="user",
                owner_id=user.id,
                type="expense",
                amount=wallet_pay,
                balance_after=float(user.balance or 0),
                method="wallet",
                order_id=order.order_no,
                description=f"组合支付-钱包 {order.order_no}",
                status="pending" if wechat_pay_cents > 0 else "success",
            )

        # 微信部分创建预支付单（前端调起微信支付）
        if wechat_pay > 0:
            from app.services.wechat_pay_service import create_jsapi_order
            payment_wechat = PaymentOrder(
                payment_no=_gen_payment_no(),
                order_no=order.order_no,
                amount=wechat_pay,
                method="wechat",
                coupon_id=coupon_id,
                discount_amount=discount_amount,
                payer_type="user",
                payer_id=user.id,
                status="pending",
            )
            db.add(payment_wechat)
            db.flush()

            # 微信调起参数
            if not user.openid:
                raise HTTPException(status_code=400, detail="当前账号未绑定微信 openid")
            jsapi_params = create_jsapi_order(db, payment_wechat, user.openid)

            db.commit()
            return {
                "success": True,
                "status": "pending",
                "payment_no": payment_wechat.payment_no,
                "wallet_reserved": wallet_pay,
                "wechat_amount": wechat_pay,
                "jsapi_params": jsapi_params,
                "balance": float(user.balance or 0),
            }

        # 纯钱包部分已足够
        if coupon_id:
            consume_coupon(db, user, coupon_id, order.order_no)

        now = datetime.utcnow()
        _cas_update_status(
            db,
            order,
            "paid",
            allowed_from=["completed"],
            paid_at=now,
        )

        if order.worker_id:
            worker = db.query(Worker).filter(Worker.id == order.worker_id).first()
            if worker:
                worker.balance = float(worker.balance or 0) + wallet_pay
                db.flush()
                _add_transaction(
                    db,
                    owner_type="worker",
                    owner_id=worker.id,
                    type="income",
                    amount=wallet_pay,
                    balance_after=float(worker.balance),
                    method="wallet",
                    order_id=order.order_no,
                    description=f"订单收入 {order.order_no}",
                    status="success",
                )

        db.commit()
        return {
            "success": True,
            "payment_no": payment_wallet.payment_no,
            "wallet_paid": wallet_pay,
            "wechat_amount": 0,
            "balance": float(user.balance or 0),
        }

    # ===== 微信支付：仅创建 pending 支付单，到账由可信回调推进 =====
    if method == "wechat":
        if not user.openid:
            raise HTTPException(status_code=400, detail="当前账号未绑定微信 openid")
        from app.services.wechat_pay_service import create_jsapi_order

        payment = PaymentOrder(
            payment_no=_gen_payment_no(),
            order_no=order.order_no,
            amount=pay_amount,
            method="wechat",
            coupon_id=coupon_id,
            discount_amount=discount_amount,
            payer_type="user",
            payer_id=user.id,
            status="pending",
        )
        db.add(payment)
        db.flush()
        jsapi_params = create_jsapi_order(db, payment, user.openid)
        db.commit()
        return {
            "success": True,
            "status": "pending",
            "payment_no": payment.payment_no,
            "discount_amount": discount_amount,
            "pay_amount": pay_amount,
            "jsapi_params": jsapi_params,
            "balance": float(user.balance or 0),
        }

    # ===== 余额支付 =====
    if method == "wallet":
        user = db.query(User).filter(User.id == user.id).with_for_update().first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if _to_cents(user.balance or 0) < pay_amount_cents:
            raise HTTPException(status_code=400, detail="钱包余额不足")
        user.balance = _from_cents(_to_cents(user.balance or 0) - pay_amount_cents)
        db.flush()

    # 核销优惠券
    if coupon_id:
        from app.services.coupon_service import consume_coupon
        consume_coupon(db, user, coupon_id, order.order_no)

    # 创建支付订单
    payment = PaymentOrder(
        payment_no=_gen_payment_no(),
        order_no=order.order_no,
        amount=pay_amount,
        method=method,
        coupon_id=coupon_id,
        discount_amount=discount_amount,
        payer_type="user",
        payer_id=user.id,
        status="paid",
        paid_at=datetime.utcnow(),
    )
    db.add(payment)
    db.flush()

    # 创建用户支出交易记录
    _add_transaction(
        db,
        owner_type="user",
        owner_id=user.id,
        type="expense",
        amount=pay_amount,
        balance_after=float(user.balance or 0),
        method=method,
        order_id=order.order_no,
        description=f"支付订单 {order.order_no}",
        status="success",
    )

    # 更新订单状态（CAS）
    now = datetime.utcnow()
    _cas_update_status(
        db,
        order,
        "paid",
        allowed_from=["completed"],
        paid_at=now,
    )

    # 师傅收款：给师傅余额加款
    if order.worker_id:
        worker = db.query(Worker).filter(Worker.id == order.worker_id).first()
        if worker:
            worker.balance = float(worker.balance or 0) + pay_amount
            db.flush()
            _add_transaction(
                db,
                owner_type="worker",
                owner_id=worker.id,
                type="income",
                amount=pay_amount,
                balance_after=float(worker.balance),
                method=method,
                order_id=order.order_no,
                description=f"订单收入 {order.order_no}",
                status="success",
            )

    db.commit()

    # 发送支付成功通知
    from app.services import message_service
    await message_service.notify_payment_success(db, order)

    return {
        "success": True,
        "payment_no": payment.payment_no,
        "discount_amount": discount_amount,
        "pay_amount": pay_amount,
        "balance": float(user.balance or 0),
    }


def settle_wechat_order_payment(db: Session, payment: PaymentOrder) -> None:
    """结算一个已由可信微信回调标记为 paid 的订单支付单。

    此函数不提交事务，由回调处理函数统一 commit/rollback。组合支付的钱包部分在
    创建预支付时已从可用余额中扣除并标记 ``reserved``，这里只把预留转为实付。
    """
    if payment.method != "wechat" or payment.status != "paid" or not payment.order_no:
        raise HTTPException(status_code=409, detail="微信支付单状态不允许结算")

    order = (
        db.query(Order)
        .filter(Order.order_no == payment.order_no)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="业务订单不存在")
    if order.status != "completed":
        raise HTTPException(status_code=409, detail="业务订单状态不允许支付结算")
    if payment.payer_type != "user" or payment.payer_id != order.user_id:
        raise HTTPException(status_code=400, detail="支付方与业务订单不匹配")

    user = db.query(User).filter(User.id == order.user_id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="订单用户不存在")

    reserved_wallet_payments = (
        db.query(PaymentOrder)
        .filter(
            PaymentOrder.order_no == order.order_no,
            PaymentOrder.payer_id == user.id,
            PaymentOrder.method == "wallet",
            PaymentOrder.status == "reserved",
        )
        .with_for_update()
        .all()
    )
    wallet_cents = sum(_to_cents(item.amount) for item in reserved_wallet_payments)
    total_cents = _to_cents(payment.amount) + wallet_cents
    expected_cents = max(
        _to_cents(order.final_price or 0) - _to_cents(payment.discount_amount or 0),
        0,
    )
    if total_cents != expected_cents:
        raise HTTPException(status_code=409, detail="支付快照金额与订单应付金额不一致")

    now = datetime.utcnow()
    for wallet_payment in reserved_wallet_payments:
        wallet_payment.status = "paid"
        wallet_payment.paid_at = now

    if wallet_cents:
        pending_wallet_txs = (
            db.query(Transaction)
            .filter(
                Transaction.owner_type == "user",
                Transaction.owner_id == user.id,
                Transaction.order_id == order.order_no,
                Transaction.method == "wallet",
                Transaction.status == "pending",
            )
            .with_for_update()
            .all()
        )
        if len(pending_wallet_txs) != 1 or _to_cents(pending_wallet_txs[0].amount) != wallet_cents:
            raise HTTPException(status_code=409, detail="组合支付钱包预留记录不一致")
        pending_wallet_txs[0].status = "success"

    if _to_cents(payment.amount) > 0:
        _add_transaction(
            db,
            owner_type="user",
            owner_id=user.id,
            type="expense",
            amount=float(payment.amount),
            balance_after=float(user.balance or 0),
            method="wechat",
            order_id=order.order_no,
            description=f"微信支付订单 {order.order_no}",
            status="success",
        )

    if payment.coupon_id:
        from app.services.coupon_service import consume_coupon

        consume_coupon(db, user, payment.coupon_id, order.order_no)

    _cas_update_status(
        db,
        order,
        "paid",
        allowed_from=["completed"],
        paid_at=now,
    )

    if order.worker_id:
        worker = db.query(Worker).filter(Worker.id == order.worker_id).with_for_update().first()
        if worker:
            worker.balance = _from_cents(_to_cents(worker.balance or 0) + total_cents)
            db.flush()
            _add_transaction(
                db,
                owner_type="worker",
                owner_id=worker.id,
                type="income",
                amount=_from_cents(total_cents),
                balance_after=float(worker.balance),
                method="combined" if wallet_cents else "wechat",
                order_id=order.order_no,
                description=f"订单收入 {order.order_no}",
                status="success",
            )


def confirm_offline_payment(db: Session, worker: Worker, order_no: str) -> dict:
    """由订单指派师傅确认线下收款，并在一个事务中完成结算。"""
    try:
        order = (
            db.query(Order)
            .filter(Order.order_no == order_no)
            .with_for_update()
            .first()
        )
        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")
        if order.worker_id != worker.id:
            raise HTTPException(status_code=403, detail="仅订单指派师傅可确认线下收款")

        payment = (
            db.query(PaymentOrder)
            .filter(
                PaymentOrder.order_no == order_no,
                PaymentOrder.method == "offline",
            )
            .order_by(PaymentOrder.id.desc())
            .with_for_update()
            .first()
        )
        if not payment:
            raise HTTPException(status_code=404, detail="未找到线下支付单")
        if payment.status == "paid" and order.status == "paid":
            db.rollback()
            return {"order_no": order_no, "payment_no": payment.payment_no, "confirmed": True}
        if payment.status != "pending" or order.status != "completed":
            raise HTTPException(status_code=409, detail="线下支付单或订单状态不允许确认")
        if payment.payer_type != "user" or payment.payer_id != order.user_id:
            raise HTTPException(status_code=400, detail="线下支付方与订单不匹配")

        expected_cents = max(
            _to_cents(order.final_price or 0) - _to_cents(payment.discount_amount or 0),
            0,
        )
        if _to_cents(payment.amount) != expected_cents:
            raise HTTPException(status_code=409, detail="线下支付金额与订单应付金额不一致")

        user = db.query(User).filter(User.id == order.user_id).with_for_update().first()
        if not user:
            raise HTTPException(status_code=404, detail="订单用户不存在")
        now = datetime.utcnow()
        payment.status = "paid"
        payment.paid_at = now

        if payment.coupon_id:
            from app.services.coupon_service import consume_coupon

            consume_coupon(db, user, payment.coupon_id, order.order_no)

        _add_transaction(
            db,
            owner_type="user",
            owner_id=user.id,
            type="expense",
            amount=float(payment.amount),
            balance_after=float(user.balance or 0),
            method="offline",
            order_id=order.order_no,
            description=f"线下支付订单 {order.order_no}",
        )
        _cas_update_status(
            db,
            order,
            "paid",
            allowed_from=["completed"],
            paid_at=now,
        )

        locked_worker = db.query(Worker).filter(Worker.id == worker.id).with_for_update().first()
        if not locked_worker:
            raise HTTPException(status_code=404, detail="师傅不存在")
        locked_worker.balance = _from_cents(
            _to_cents(locked_worker.balance or 0) + _to_cents(payment.amount)
        )
        db.flush()
        _add_transaction(
            db,
            owner_type="worker",
            owner_id=locked_worker.id,
            type="income",
            amount=float(payment.amount),
            balance_after=float(locked_worker.balance),
            method="offline",
            order_id=order.order_no,
            description=f"线下收款 {order.order_no}",
        )
        db.commit()
        return {"order_no": order_no, "payment_no": payment.payment_no, "confirmed": True}
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def release_expired_wechat_payment(db: Session, payment_id: int) -> dict:
    """在微信已确认未支付/已关闭后，幂等释放组合支付的钱包预留。

    调用方必须先完成微信查单，且仅可在 NOT_FOUND/CLOSED/REVOKED/PAYERROR，
    或 NOTPAY 且微信关单成功后调用。本函数再次锁定并检查本地状态，避免与
    成功回调并发时重复释放。
    """
    try:
        payment = (
            db.query(PaymentOrder)
            .filter(PaymentOrder.id == payment_id)
            .with_for_update()
            .first()
        )
        if not payment:
            raise HTTPException(status_code=404, detail="支付单不存在")
        if payment.method != "wechat":
            raise HTTPException(status_code=400, detail="仅微信支付单可执行超时释放")
        if payment.status != "pending":
            db.rollback()
            return {"released": False, "payment_no": payment.payment_no, "amount": 0.0}

        reserved_payments = []
        if payment.order_no:
            reserved_payments = (
                db.query(PaymentOrder)
                .filter(
                    PaymentOrder.order_no == payment.order_no,
                    PaymentOrder.payer_type == payment.payer_type,
                    PaymentOrder.payer_id == payment.payer_id,
                    PaymentOrder.method == "wallet",
                    PaymentOrder.status == "reserved",
                )
                .with_for_update()
                .all()
            )
        reserved_cents = sum(_to_cents(item.amount) for item in reserved_payments)

        if reserved_cents:
            if payment.payer_type != "user":
                raise HTTPException(status_code=409, detail="组合支付预留的付款主体异常")
            user = (
                db.query(User)
                .filter(User.id == payment.payer_id)
                .with_for_update()
                .first()
            )
            if not user:
                raise HTTPException(status_code=404, detail="组合支付用户不存在")

            pending_txs = (
                db.query(Transaction)
                .filter(
                    Transaction.owner_type == "user",
                    Transaction.owner_id == user.id,
                    Transaction.order_id == payment.order_no,
                    Transaction.method == "wallet",
                    Transaction.status == "pending",
                )
                .with_for_update()
                .all()
            )
            if sum(_to_cents(tx.amount) for tx in pending_txs) != reserved_cents:
                raise HTTPException(status_code=409, detail="钱包预留与待处理流水不一致，拒绝自动释放")

            user.balance = _from_cents(_to_cents(user.balance or 0) + reserved_cents)
            for tx in pending_txs:
                tx.status = "failed"
            for reserved in reserved_payments:
                reserved.status = "failed"

        payment.status = "failed"
        db.commit()
        return {
            "released": True,
            "payment_no": payment.payment_no,
            "amount": _from_cents(reserved_cents),
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


# ===== 退款 =====

def refund_order(
    db: Session,
    order_no: str,
    reason: str,
    refund_amount: Optional[float] = None,
    admin_id: Optional[int] = None,
) -> dict:
    """按原支付渠道创建退款。

    钱包支付在本事务内退回站内钱包；微信支付只创建 ``pending`` 退款单并
    调用微信退款 API，到账和平台账务调整由可信退款回调完成。线下现金退款
    无法由系统验证，因此拒绝自动处理。
    """
    try:
        order = (
            db.query(Order)
            .filter(Order.order_no == order_no)
            .with_for_update()
            .first()
        )
        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")
        if order.status not in ("paid", "completed"):
            raise HTTPException(status_code=400, detail="订单状态不支持退款")

        payments = (
            db.query(PaymentOrder)
            .filter(
                PaymentOrder.order_no == order_no,
                PaymentOrder.status.in_(("paid", "partially_refunded", "refunded")),
            )
            .order_by(PaymentOrder.id.asc())
            .with_for_update()
            .all()
        )
        if not payments:
            raise HTTPException(status_code=400, detail="未找到有效支付记录")

        existing_refunds = (
            db.query(RefundOrder)
            .filter(
                RefundOrder.order_no == order_no,
                RefundOrder.status.in_(("pending", "success")),
            )
            .with_for_update()
            .all()
        )
        used_by_payment = {}
        for item in existing_refunds:
            used_by_payment[item.payment_no] = used_by_payment.get(item.payment_no, 0) + _to_cents(item.amount)

        available_by_payment = []
        total_available_cents = 0
        for payment in payments:
            available = max(_to_cents(payment.amount) - used_by_payment.get(payment.payment_no, 0), 0)
            if available:
                available_by_payment.append((payment, available))
                total_available_cents += available

        requested_cents = (
            _to_cents(refund_amount) if refund_amount is not None else total_available_cents
        )
        if requested_cents <= 0:
            raise HTTPException(status_code=400, detail="退款金额必须大于 0")
        if requested_cents > total_available_cents:
            raise HTTPException(status_code=400, detail="退款金额超过尚可退款金额")

        remaining = requested_cents
        allocations = []
        for payment, available in available_by_payment:
            allocated = min(available, remaining)
            if allocated:
                allocations.append((payment, allocated))
                remaining -= allocated
            if remaining == 0:
                break

        if any(payment.method == "offline" for payment, _ in allocations):
            raise HTTPException(status_code=409, detail="线下现金支付需线下退款并由运营人工登记")
        unsupported = [payment.method for payment, _ in allocations if payment.method not in ("wallet", "wechat")]
        if unsupported:
            raise HTTPException(status_code=501, detail=f"暂不支持 {unsupported[0]} 原路退款")

        user = db.query(User).filter(User.id == order.user_id).with_for_update().first()
        if not user:
            raise HTTPException(status_code=404, detail="订单用户不存在")
        worker = None
        if order.worker_id:
            worker = db.query(Worker).filter(Worker.id == order.worker_id).with_for_update().first()

        from app.services.wechat_pay_service import create_wechat_refund

        refund_results = []
        created_refunds = []
        now = datetime.utcnow()

        # 先为所有渠道创建退款占位，防止外部 API 调用期间释放数据库锁后，
        # 并发请求再次分配同一笔可退金额。
        for payment, allocated_cents in allocations:
            refund = RefundOrder(
                refund_no=_gen_refund_no(),
                payment_no=payment.payment_no,
                order_no=order.order_no,
                amount=_from_cents(allocated_cents),
                total_amount=float(payment.amount),
                method=payment.method,
                payer_type=payment.payer_type,
                payer_id=payment.payer_id,
                reason=reason,
                status="pending",
            )
            db.add(refund)
            db.flush()
            created_refunds.append(refund)

        has_wechat_allocation = any(payment.method == "wechat" for payment, _ in allocations)
        if has_wechat_allocation:
            db.commit()
            # commit 会释放原行锁；站内钱包退款前重新锁定双方账户。
            user = db.query(User).filter(User.id == order.user_id).with_for_update().first()
            worker = None
            if order.worker_id:
                worker = db.query(Worker).filter(Worker.id == order.worker_id).with_for_update().first()

        # 先完成站内钱包退款；微信退款占位已经持久化，可由对账任务安全续办。
        for (payment, allocated_cents), refund in zip(allocations, created_refunds):
            if payment.method != "wallet":
                continue

            refund.status = "success"
            refund.refunded_at = now
            user.balance = _from_cents(_to_cents(user.balance or 0) + allocated_cents)
            db.flush()
            _add_transaction(
                db,
                owner_type="user",
                owner_id=user.id,
                type="refund",
                amount=_from_cents(allocated_cents),
                balance_after=float(user.balance),
                method="wallet",
                order_id=order.order_no,
                description=f"钱包原路退款 {refund.refund_no}: {reason}",
            )
            if worker:
                # 余额不足时形成负余额待追偿，退款不能因此损害用户权益。
                worker.balance = _from_cents(_to_cents(worker.balance or 0) - allocated_cents)
                db.flush()
                _add_transaction(
                    db,
                    owner_type="worker",
                    owner_id=worker.id,
                    type="expense",
                    amount=_from_cents(allocated_cents),
                    balance_after=float(worker.balance),
                    method="wallet_refund",
                    order_id=order.order_no,
                    description=f"订单退款扣减 {refund.refund_no}",
                )
            refund_results.append(
                {"refund_no": refund.refund_no, "status": "SUCCESS", "method": "wallet"}
            )

        # 外部调用前提交全部退款占位及钱包退款。即使网络结果未知，回调/对账
        # 仍能按同一 refund_no 找到并幂等续办。
        if has_wechat_allocation:
            db.commit()

        for (payment, _allocated_cents), refund in zip(allocations, created_refunds):
            if payment.method == "wechat":
                try:
                    result = create_wechat_refund(db, refund, payment)
                    db.commit()
                except HTTPException:
                    # create_wechat_refund 已记录尝试次数和非敏感错误摘要。
                    db.commit()
                    raise
                refund_results.append(result)
                continue

        db.flush()
        # 刷新每个原支付单的累计成功退款状态。
        for payment, _ in allocations:
            successful = (
                db.query(RefundOrder)
                .filter(
                    RefundOrder.payment_no == payment.payment_no,
                    RefundOrder.status == "success",
                )
                .all()
            )
            refunded_cents = sum(_to_cents(item.amount) for item in successful)
            if refunded_cents >= _to_cents(payment.amount):
                payment.status = "refunded"
            elif refunded_cents:
                payment.status = "partially_refunded"

        has_pending = any(item.status == "pending" for item in created_refunds)
        if not has_pending:
            all_original_cents = sum(_to_cents(payment.amount) for payment in payments)
            all_success = (
                db.query(RefundOrder)
                .filter(RefundOrder.order_no == order_no, RefundOrder.status == "success")
                .all()
            )
            if sum(_to_cents(item.amount) for item in all_success) >= all_original_cents:
                _cas_update_status(
                    db,
                    order,
                    "refunded",
                    allowed_from=["paid", "completed"],
                )

        db.commit()
        return {
            "success": True,
            "status": "pending" if has_pending else "success",
            "order_no": order_no,
            "refund_amount": _from_cents(requested_cents),
            "refunds": refund_results,
            "user_balance": float(user.balance),
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

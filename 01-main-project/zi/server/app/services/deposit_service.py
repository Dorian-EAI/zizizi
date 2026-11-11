"""师傅保证金业务逻辑"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.deposit import WorkerDeposit, DepositTransaction
from app.models.order import Order


DEPOSIT_LEVELS = {
    "trainee": {"amount": 0, "daily_limit": 3, "cut_rate": 0.150},
    "formal": {"amount": 50000, "daily_limit": 10, "cut_rate": 0.120},
    "gold": {"amount": 200000, "daily_limit": 999, "cut_rate": 0.100},
}


def get_platform_cut_rate(db: Session, worker_id: int) -> Decimal:
    """读取师傅当前平台服务费率；无保证金账户时按见习档默认值。"""
    deposit = (
        db.query(WorkerDeposit.platform_cut_rate)
        .filter(WorkerDeposit.worker_id == worker_id)
        .first()
    )
    if deposit and deposit[0] is not None:
        return Decimal(str(deposit[0]))
    return Decimal(str(DEPOSIT_LEVELS["trainee"]["cut_rate"]))


def get_or_create_deposit(db: Session, worker_id: int) -> WorkerDeposit:
    """获取或创建保证金账户"""
    deposit = db.query(WorkerDeposit).filter(WorkerDeposit.worker_id == worker_id).first()
    if not deposit:
        deposit = WorkerDeposit(worker_id=worker_id)
        db.add(deposit)
        db.commit()
        db.refresh(deposit)
    return deposit


def deposit_pay(db: Session, worker_id: int, amount: int) -> WorkerDeposit:
    """开发环境模拟缴纳保证金；生产环境在真实支付回调接入前拒绝直到账。"""
    from app.config import settings
    if settings.APP_ENV.lower() != "development" or not settings.WX_PAY_MOCK_ENABLED:
        raise HTTPException(status_code=503, detail="保证金支付通道尚未完成真实回调接入")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="缴纳金额必须大于0")
    deposit = get_or_create_deposit(db, worker_id)
    deposit.balance += amount
    deposit.total_deposited += amount

    # 根据累计缴纳更新等级
    for level, cfg in sorted(DEPOSIT_LEVELS.items(), key=lambda x: x[1]["amount"], reverse=True):
        if deposit.total_deposited >= cfg["amount"]:
            deposit.deposit_level = level
            deposit.daily_order_limit = cfg["daily_limit"]
            deposit.platform_cut_rate = cfg["cut_rate"]
            break

    txn = DepositTransaction(
        worker_id=worker_id,
        type="deposit",
        amount=amount,
        balance_after=deposit.balance,
        reason="缴纳保证金",
    )
    db.add(txn)
    db.commit()
    db.refresh(deposit)
    return deposit


def deduct_deposit(db: Session, worker_id: int, amount: int, reason: str,
                   related_order_id: int = None, related_claim_id: int = None) -> WorkerDeposit:
    """扣除保证金（事务操作）"""
    if amount <= 0:
        raise HTTPException(status_code=400, detail="扣除金额必须大于0")
    deposit = get_or_create_deposit(db, worker_id)
    if deposit.balance < amount:
        raise HTTPException(status_code=400, detail="保证金余额不足")

    deposit.balance -= amount
    txn = DepositTransaction(
        worker_id=worker_id,
        type="deduct",
        amount=amount,
        balance_after=deposit.balance,
        reason=reason,
        related_order_id=related_order_id,
        related_claim_id=related_claim_id,
    )
    db.add(txn)
    db.commit()
    db.refresh(deposit)
    return deposit


def freeze_deposit(db: Session, worker_id: int, amount: int, reason: str) -> WorkerDeposit:
    """冻结保证金"""
    if amount <= 0:
        raise HTTPException(status_code=400, detail="冻结金额必须大于0")
    deposit = get_or_create_deposit(db, worker_id)

    if deposit.status == "refunding":
        raise HTTPException(status_code=409, detail="保证金退款申请已提交，请勿重复操作")
    if deposit.balance < amount:
        raise HTTPException(status_code=400, detail="保证金余额不足")

    deposit.balance -= amount
    deposit.frozen_amount += amount
    txn = DepositTransaction(
        worker_id=worker_id,
        type="freeze",
        amount=amount,
        balance_after=deposit.balance,
        reason=reason,
    )
    db.add(txn)
    db.commit()
    db.refresh(deposit)
    return deposit


def unfreeze_deposit(db: Session, worker_id: int, amount: int, reason: str) -> WorkerDeposit:
    """解冻保证金"""
    if amount <= 0:
        raise HTTPException(status_code=400, detail="解冻金额必须大于0")
    deposit = get_or_create_deposit(db, worker_id)
    if deposit.frozen_amount < amount:
        raise HTTPException(status_code=400, detail="冻结金额不足")

    deposit.frozen_amount -= amount
    deposit.balance += amount
    txn = DepositTransaction(
        worker_id=worker_id,
        type="unfreeze",
        amount=amount,
        balance_after=deposit.balance,
        reason=reason,
    )
    db.add(txn)
    db.commit()
    db.refresh(deposit)
    return deposit


def request_refund(db: Session, worker_id: int) -> dict:
    """申请退还保证金"""
    deposit = get_or_create_deposit(db, worker_id)

    if deposit.status == "refunding":
        raise HTTPException(status_code=409, detail="保证金退款申请已提交，请勿重复操作")

    # 校验条件
    if deposit.balance <= 0:
        raise HTTPException(status_code=400, detail="保证金余额为0")
    if deposit.frozen_amount > 0:
        raise HTTPException(status_code=409, detail="存在冻结保证金，处理完成前无法申请退还")

    has_active_order = db.query(Order).filter(
        Order.worker_id == worker_id,
        Order.status.in_(["accepted", "departing", "arrived", "serving", "completed"]),
    ).first()
    if has_active_order:
        raise HTTPException(status_code=400, detail="存在进行中的订单，无法退还")

    from sqlalchemy import or_
    from app.models.support_ticket import SupportTicket
    unresolved_ticket = (
        db.query(SupportTicket)
        .outerjoin(Order, SupportTicket.related_order_id == Order.id)
        .filter(
            SupportTicket.status.in_(["open", "processing"]),
            or_(
                (SupportTicket.creator_type == "worker") & (SupportTicket.creator_id == worker_id),
                Order.worker_id == worker_id,
            ),
        )
        .first()
    )
    if unresolved_ticket:
        raise HTTPException(status_code=400, detail="存在未处理工单，无法退还保证金")

    deposit.status = "refunding"
    deposit.refund_requested_at = datetime.utcnow()
    db.commit()
    return {"msg": "退还申请已提交，审核期7天", "refund_amount": deposit.balance}


def process_refund(db: Session, worker_id: int) -> dict:
    """执行退还（定时任务调用）"""
    from app.config import settings

    if settings.APP_ENV.lower() != "development" or not settings.WX_PAY_MOCK_ENABLED:
        return {
            "msg": "真实保证金退款通道尚未接入，申请保持待处理",
            "pending": True,
        }
    deposit = get_or_create_deposit(db, worker_id)
    if deposit.status != "refunding":
        return {"msg": "无需处理"}
    if not deposit.refund_requested_at or deposit.refund_requested_at > datetime.utcnow() - timedelta(days=7):
        return {"msg": "仍在7天审核期内"}
    if deposit.frozen_amount > 0:
        return {"msg": "存在冻结保证金，暂不处理", "pending": True}

    has_active_order = db.query(Order).filter(
        Order.worker_id == worker_id,
        Order.status.in_(["accepted", "departing", "arrived", "serving", "completed"]),
    ).first()
    if has_active_order:
        return {"msg": "存在进行中的订单，暂不处理", "pending": True}

    amount = deposit.balance
    deposit.balance = 0
    deposit.total_deposited = 0
    deposit.deposit_level = "trainee"
    deposit.daily_order_limit = 3
    deposit.platform_cut_rate = 0.150
    deposit.status = "normal"
    deposit.refund_requested_at = None

    txn = DepositTransaction(
        worker_id=worker_id,
        type="refund",
        amount=amount,
        balance_after=0,
        reason="退还保证金",
    )
    db.add(txn)
    db.commit()
    return {"msg": "退还完成", "amount": amount}


def get_deposit_detail(db: Session, worker_id: int) -> dict:
    """保证金详情+最近流水"""
    deposit = get_or_create_deposit(db, worker_id)
    txns = db.query(DepositTransaction).filter(
        DepositTransaction.worker_id == worker_id,
    ).order_by(DepositTransaction.created_at.desc()).limit(20).all()
    return {
        "deposit": deposit,
        "transactions": txns,
    }

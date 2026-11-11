"""师傅资金桶不可变账本服务

订单支付成功后收入先进入 ``pending_settlement``，等待期结束后由结算任务转入
``available`` 并增加可提现余额；退款优先冲减同订单尚未结算的待结算收入。
所有余额变动在修改 ``Worker.balance`` 之前先写分录，保证期初余额取变更前余额。
分录只追加不更新，重复调用由唯一键幂等吸收。
"""

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import Worker
from app.models.wallet import Transaction
from app.models.worker_fund import FUND_BUCKETS, WorkerFundEntry
from app.utils.snowflake import generate_business_no


def _money(value) -> Decimal:
    try:
        amount = Decimal(str(value if value is not None else 0))
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal("0")
    if not amount.is_finite():
        amount = Decimal("0")
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _entry_no() -> str:
    return generate_business_no("WFE")


def _settlement_hold_hours() -> int:
    try:
        return max(int(settings.WORKER_SETTLEMENT_HOLD_HOURS), 0)
    except (TypeError, ValueError):
        return 0


def _find_entry(
    db: Session,
    worker_id: int,
    reference_type: str,
    reference_id: str,
    bucket: str,
    direction: str,
) -> Optional[WorkerFundEntry]:
    return (
        db.query(WorkerFundEntry)
        .filter(
            WorkerFundEntry.worker_id == worker_id,
            WorkerFundEntry.reference_type == reference_type,
            WorkerFundEntry.reference_id == str(reference_id),
            WorkerFundEntry.bucket == bucket,
            WorkerFundEntry.direction == direction,
        )
        .first()
    )


def _bucket_total(db: Session, worker_id: int, bucket: str) -> Decimal:
    credits = (
        db.query(func.coalesce(func.sum(WorkerFundEntry.amount), 0))
        .filter(
            WorkerFundEntry.worker_id == worker_id,
            WorkerFundEntry.bucket == bucket,
            WorkerFundEntry.direction == "credit",
        )
        .scalar()
    ) or 0
    debits = (
        db.query(func.coalesce(func.sum(WorkerFundEntry.amount), 0))
        .filter(
            WorkerFundEntry.worker_id == worker_id,
            WorkerFundEntry.bucket == bucket,
            WorkerFundEntry.direction == "debit",
        )
        .scalar()
    ) or 0
    return _money(credits) - _money(debits)


def _consumed_amount(db: Session, entry_id: int) -> Decimal:
    """待结算来源分录已被结算或退款冲减的金额。"""
    value = (
        db.query(func.coalesce(func.sum(WorkerFundEntry.amount), 0))
        .filter(
            WorkerFundEntry.source_entry_id == entry_id,
            WorkerFundEntry.bucket == "pending_settlement",
            WorkerFundEntry.direction == "debit",
        )
        .scalar()
    )
    return _money(value)


def _consumed_map(db: Session, worker_id: int) -> dict[int, Decimal]:
    rows = (
        db.query(WorkerFundEntry.source_entry_id, func.sum(WorkerFundEntry.amount))
        .filter(
            WorkerFundEntry.worker_id == worker_id,
            WorkerFundEntry.bucket == "pending_settlement",
            WorkerFundEntry.direction == "debit",
            WorkerFundEntry.source_entry_id.isnot(None),
        )
        .group_by(WorkerFundEntry.source_entry_id)
        .all()
    )
    return {row[0]: _money(row[1]) for row in rows if row[0] is not None}


def _pending_remaining(db: Session, entry: WorkerFundEntry) -> Decimal:
    return _money(entry.amount) - _consumed_amount(db, entry.id)


def _frozen_for_refund(db: Session, worker_id: int, refund_no: str) -> Decimal:
    """某笔退款仍处于冻结中的金额。"""
    credit = (
        db.query(func.coalesce(func.sum(WorkerFundEntry.amount), 0))
        .filter(
            WorkerFundEntry.worker_id == worker_id,
            WorkerFundEntry.bucket == "frozen",
            WorkerFundEntry.direction == "credit",
            WorkerFundEntry.reference_type == "refund_freeze",
            WorkerFundEntry.reference_id == str(refund_no),
        )
        .scalar()
    ) or 0
    debit = (
        db.query(func.coalesce(func.sum(WorkerFundEntry.amount), 0))
        .filter(
            WorkerFundEntry.worker_id == worker_id,
            WorkerFundEntry.bucket == "frozen",
            WorkerFundEntry.direction == "debit",
            WorkerFundEntry.reference_type.in_(("refund", "refund_release")),
            WorkerFundEntry.reference_id == str(refund_no),
        )
        .scalar()
    ) or 0
    return _money(credit) - _money(debit)


def ensure_opening(db: Session, worker: Worker) -> Optional[WorkerFundEntry]:
    """写入期初分录；已有任何分录时直接返回，避免重复计量历史余额。"""
    if worker is None or worker.id is None:
        return None
    existing = (
        db.query(WorkerFundEntry.id)
        .filter(WorkerFundEntry.worker_id == worker.id)
        .first()
    )
    if existing:
        return None
    balance = _money(worker.balance)
    entry = WorkerFundEntry(
        entry_no=_entry_no(),
        worker_id=worker.id,
        bucket="available",
        direction="credit",
        amount=balance,
        balance_after=balance,
        reference_type="opening",
        reference_id=str(worker.id),
        description="期初可提现余额",
    )
    db.add(entry)
    db.flush()
    return entry


def _insert(
    db: Session,
    worker: Worker,
    *,
    bucket: str,
    direction: str,
    amount,
    reference_type: str,
    reference_id,
    order_no: Optional[str] = None,
    description: Optional[str] = None,
    source_entry_id: Optional[int] = None,
) -> Optional[WorkerFundEntry]:
    if worker is None or worker.id is None:
        return None
    if bucket not in FUND_BUCKETS:
        raise ValueError(f"未知资金桶: {bucket}")
    if direction not in ("credit", "debit"):
        raise ValueError(f"未知分录方向: {direction}")
    amount_value = _money(amount)
    if amount_value <= 0:
        return None

    reference_id = str(reference_id)
    existing = _find_entry(
        db, worker.id, reference_type, reference_id, bucket, direction
    )
    if existing:
        return existing

    balance_after = None
    if bucket == "available":
        current = _bucket_total(db, worker.id, "available")
        balance_after = (
            current + amount_value if direction == "credit" else current - amount_value
        )

    entry = WorkerFundEntry(
        entry_no=_entry_no(),
        worker_id=worker.id,
        order_no=order_no,
        bucket=bucket,
        direction=direction,
        amount=amount_value,
        balance_after=balance_after,
        reference_type=reference_type,
        reference_id=reference_id,
        source_entry_id=source_entry_id,
        description=description,
    )
    db.add(entry)
    db.flush()
    return entry


def record_entry(
    db: Session,
    worker: Worker,
    *,
    bucket: str,
    direction: str,
    amount,
    reference_type: str,
    reference_id,
    order_no: Optional[str] = None,
    description: Optional[str] = None,
    source_entry_id: Optional[int] = None,
) -> Optional[WorkerFundEntry]:
    """写入一条分录；调用方必须保证在余额变更前调用。"""
    if worker is None or worker.id is None:
        return None
    ensure_opening(db, worker)
    return _insert(
        db,
        worker,
        bucket=bucket,
        direction=direction,
        amount=amount,
        reference_type=reference_type,
        reference_id=reference_id,
        order_no=order_no,
        description=description,
        source_entry_id=source_entry_id,
    )


# ===== 业务动作 =====

def _rate(value) -> Decimal:
    try:
        rate = Decimal(str(value)) if value is not None else Decimal("0")
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")
    if not rate.is_finite() or rate < 0:
        return Decimal("0")
    return min(rate, Decimal("1"))


def _fee_amount(db: Session, income_entry_id: int) -> Decimal:
    """某笔订单收入已扣的平台服务费。"""
    value = (
        db.query(func.coalesce(func.sum(WorkerFundEntry.amount), 0))
        .filter(
            WorkerFundEntry.source_entry_id == income_entry_id,
            WorkerFundEntry.bucket == "pending_settlement",
            WorkerFundEntry.direction == "debit",
            WorkerFundEntry.reference_type == "platform_fee",
        )
        .scalar()
    )
    return _money(value)


def estimate_refund_clawback(
    db: Session,
    worker: Worker,
    *,
    payment_no: Optional[str],
    amount,
) -> Decimal:
    """按退款金额占订单收入的比例，估算应冲减的师傅净收入。"""
    gross_refund = _money(amount)
    if gross_refund <= 0 or worker is None or worker.id is None:
        return Decimal("0.00")
    entry = None
    if payment_no:
        entry = _find_entry(
            db, worker.id, "order_income", str(payment_no), "pending_settlement", "credit"
        )
    if entry is None:
        return gross_refund
    entry_gross = _money(entry.amount)
    if entry_gross <= 0:
        return gross_refund
    net = max(entry_gross - _fee_amount(db, entry.id), Decimal("0.00"))
    partial = min(gross_refund, entry_gross)
    clawback = (partial * net / entry_gross).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return min(clawback, net)


def record_order_income(
    db: Session,
    worker: Worker,
    *,
    order_no: str,
    payment_no: str,
    amount,
    method: Optional[str] = None,
    fee_rate=None,
) -> Optional[WorkerFundEntry]:
    """订单结算：收入进入待结算桶，并按成交快照费率扣平台服务费。"""
    if not order_no or not payment_no:
        return None
    gross = _money(amount)
    if gross <= 0:
        return None
    suffix = f"（{method}）" if method else ""
    income_entry = record_entry(
        db,
        worker,
        bucket="pending_settlement",
        direction="credit",
        amount=gross,
        reference_type="order_income",
        reference_id=payment_no,
        order_no=order_no,
        description=f"订单收入待结算 {order_no}{suffix}",
    )

    rate = _rate(fee_rate)
    fee = min((gross * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), gross)
    if fee > 0 and income_entry is not None:
        record_entry(
            db,
            worker,
            bucket="pending_settlement",
            direction="debit",
            amount=fee,
            reference_type="platform_fee",
            reference_id=payment_no,
            order_no=order_no,
            description=f"平台服务费 {order_no}",
            source_entry_id=income_entry.id,
        )
    return income_entry


def record_refund_reversal(
    db: Session,
    worker: Worker,
    *,
    refund_no: str,
    order_no: Optional[str],
    amount,
    payment_no: Optional[str] = None,
) -> Decimal:
    """退款冲减：优先冲减待结算收入，不足部分再扣可提现余额。

    有平台服务费时按退款占订单收入的比例冲减净收入。返回实际从
    ``available`` 桶扣减的金额，调用方据此同步 ``Worker.balance``。
    """
    clawback = estimate_refund_clawback(
        db, worker, payment_no=payment_no, amount=amount
    )
    remaining = clawback
    if not refund_no or remaining <= 0 or worker is None or worker.id is None:
        return Decimal("0.00")

    if order_no:
        pending_query = db.query(WorkerFundEntry).filter(
            WorkerFundEntry.worker_id == worker.id,
            WorkerFundEntry.order_no == order_no,
            WorkerFundEntry.bucket == "pending_settlement",
            WorkerFundEntry.direction == "credit",
            WorkerFundEntry.reference_type == "order_income",
        )
        if payment_no:
            pending_query = pending_query.filter(
                WorkerFundEntry.reference_id == str(payment_no)
            )
        pending_entries = pending_query.order_by(WorkerFundEntry.id.asc()).all()
        for entry in pending_entries:
            available_pending = _pending_remaining(db, entry)
            if available_pending <= 0:
                continue
            take = min(available_pending, remaining)
            record_entry(
                db,
                worker,
                bucket="pending_settlement",
                direction="debit",
                amount=take,
                reference_type="refund",
                reference_id=f"{refund_no}:{entry.id}",
                order_no=order_no,
                description=f"退款冲减待结算 {refund_no}",
                source_entry_id=entry.id,
            )
            remaining -= take
            if remaining <= 0:
                break

    available_cut = Decimal("0.00")
    if remaining > 0:
        # 微信退款在途时已冻结的可提现部分优先释放，不重复扣减余额。
        frozen_remaining = _frozen_for_refund(db, worker.id, refund_no)
        frozen_take = min(remaining, frozen_remaining)
        if frozen_take > 0:
            record_entry(
                db,
                worker,
                bucket="frozen",
                direction="debit",
                amount=frozen_take,
                reference_type="refund",
                reference_id=refund_no,
                order_no=order_no,
                description=f"退款冲减冻结收入 {refund_no}",
            )
            remaining -= frozen_take

    if remaining > 0:
        record_entry(
            db,
            worker,
            bucket="available",
            direction="debit",
            amount=remaining,
            reference_type="refund",
            reference_id=refund_no,
            order_no=order_no,
            description=f"订单退款冲减 {refund_no}",
        )
        available_cut = remaining

    record_entry(
        db,
        worker,
        bucket="reversed",
        direction="credit",
        amount=clawback,
        reference_type="refund",
        reference_id=refund_no,
        order_no=order_no,
        description=f"退款冲正 {refund_no}",
    )
    return available_cut


def record_refund_freeze(
    db: Session,
    worker: Worker,
    *,
    refund_no: str,
    order_no: Optional[str],
    amount,
) -> Decimal:
    """微信退款在途：将对应可提现收入移入冻结桶，避免回调前被提现。

    只能冻结当前 ``available`` 桶内的金额；待结算部分无需冻结，退款成功时
    可直接冲减。返回实际冻结金额。
    """
    desired = _money(amount)
    if not refund_no or desired <= 0 or worker is None or worker.id is None:
        return Decimal("0.00")

    ensure_opening(db, worker)
    existing = _find_entry(
        db, worker.id, "refund_freeze", str(refund_no), "frozen", "credit"
    )
    if existing:
        return _money(existing.amount)

    available_total = _bucket_total(db, worker.id, "available")
    freeze_amount = min(desired, available_total)
    if freeze_amount <= 0:
        return Decimal("0.00")

    record_entry(
        db,
        worker,
        bucket="available",
        direction="debit",
        amount=freeze_amount,
        reference_type="refund_freeze",
        reference_id=refund_no,
        order_no=order_no,
        description=f"退款在途冻结 {refund_no}",
    )
    record_entry(
        db,
        worker,
        bucket="frozen",
        direction="credit",
        amount=freeze_amount,
        reference_type="refund_freeze",
        reference_id=refund_no,
        order_no=order_no,
        description=f"退款在途冻结 {refund_no}",
    )
    worker.balance = _money(worker.balance) - freeze_amount
    db.flush()
    return freeze_amount


def release_refund_freeze(db: Session, worker: Worker, *, refund_no: str) -> Decimal:
    """退款失败时解除冻结，将金额退回可提现余额。"""
    if not refund_no or worker is None or worker.id is None:
        return Decimal("0.00")
    frozen = _frozen_for_refund(db, worker.id, refund_no)
    if frozen <= 0:
        return Decimal("0.00")

    record_entry(
        db,
        worker,
        bucket="frozen",
        direction="debit",
        amount=frozen,
        reference_type="refund_release",
        reference_id=refund_no,
        description=f"退款失败解冻 {refund_no}",
    )
    record_entry(
        db,
        worker,
        bucket="available",
        direction="credit",
        amount=frozen,
        reference_type="refund_release",
        reference_id=refund_no,
        description=f"退款失败解冻 {refund_no}",
    )
    worker.balance = _money(worker.balance) + frozen
    db.flush()
    return frozen


def record_withdraw_request(db: Session, worker: Worker, withdraw_tx: Transaction) -> None:
    """提现申请：可提现桶转入提现中桶。"""
    if withdraw_tx is None or withdraw_tx.id is None:
        return
    record_entry(
        db,
        worker,
        bucket="available",
        direction="debit",
        amount=withdraw_tx.amount,
        reference_type="withdraw_request",
        reference_id=str(withdraw_tx.id),
        description="提现申请冻结",
    )
    record_entry(
        db,
        worker,
        bucket="withdrawing",
        direction="credit",
        amount=withdraw_tx.amount,
        reference_type="withdraw_request",
        reference_id=str(withdraw_tx.id),
        description="提现处理中",
    )


def record_withdraw_success(db: Session, worker: Worker, withdraw_tx: Transaction) -> None:
    """提现到账：提现中桶转入已提现桶。"""
    if withdraw_tx is None or withdraw_tx.id is None:
        return
    reference_id = str(withdraw_tx.id)
    request_entry = _find_entry(
        db, worker.id, "withdraw_request", reference_id, "withdrawing", "credit"
    )
    if not request_entry:
        # 历史提现单缺少申请分录时补记转出，避免提现中桶出现负数。
        ensure_opening(db, worker)
        _insert(
            db,
            worker,
            bucket="withdrawing",
            direction="credit",
            amount=withdraw_tx.amount,
            reference_type="withdraw_request",
            reference_id=reference_id,
            description="提现处理中（补记）",
        )
    record_entry(
        db,
        worker,
        bucket="withdrawing",
        direction="debit",
        amount=withdraw_tx.amount,
        reference_type="withdraw_success",
        reference_id=reference_id,
        description="提现成功，结束处理中",
    )
    record_entry(
        db,
        worker,
        bucket="withdrawn",
        direction="credit",
        amount=withdraw_tx.amount,
        reference_type="withdraw_success",
        reference_id=reference_id,
        description="提现已到账",
    )


def record_withdraw_reject(db: Session, worker: Worker, withdraw_tx: Transaction) -> None:
    """提现驳回：提现中桶退回可提现余额。"""
    if withdraw_tx is None or withdraw_tx.id is None or worker is None:
        return
    reference_id = str(withdraw_tx.id)
    request_entry = _find_entry(
        db, worker.id, "withdraw_request", reference_id, "withdrawing", "credit"
    )
    if not request_entry:
        # 历史提现单缺少申请分录时补记，避免提现中桶出现负数。
        ensure_opening(db, worker)
        _insert(
            db,
            worker,
            bucket="withdrawing",
            direction="credit",
            amount=withdraw_tx.amount,
            reference_type="withdraw_request",
            reference_id=reference_id,
            description="提现处理中（补记）",
        )
    record_entry(
        db,
        worker,
        bucket="withdrawing",
        direction="debit",
        amount=withdraw_tx.amount,
        reference_type="withdraw_reject",
        reference_id=reference_id,
        description="提现驳回，结束处理中",
    )
    record_entry(
        db,
        worker,
        bucket="available",
        direction="credit",
        amount=withdraw_tx.amount,
        reference_type="withdraw_reject",
        reference_id=reference_id,
        description="提现驳回退回可提现",
    )
    worker.balance = _money(worker.balance) + _money(withdraw_tx.amount)
    db.flush()


def settle_pending_income(
    db: Session,
    *,
    now: Optional[datetime] = None,
    limit: Optional[int] = None,
    order_no: Optional[str] = None,
    ignore_hold: bool = False,
) -> dict:
    """将超过等待期的待结算收入转入可提现余额。

    验收放款可传 ``order_no`` 与 ``ignore_hold=True`` 只结算指定订单；
    不提交事务，由调用方统一 commit/rollback；重复执行由分录唯一键与来源
    分录已消费金额双重保证幂等。
    """
    from sqlalchemy.orm import aliased

    current = now or datetime.utcnow()
    cutoff = current if ignore_hold else current - timedelta(hours=_settlement_hold_hours())
    batch_size = limit or int(getattr(settings, "WORKER_SETTLEMENT_BATCH_SIZE", 200) or 200)

    consumed = aliased(WorkerFundEntry)
    consumed_amount = (
        db.query(func.coalesce(func.sum(consumed.amount), 0))
        .filter(
            consumed.source_entry_id == WorkerFundEntry.id,
            consumed.bucket == "pending_settlement",
            consumed.direction == "debit",
        )
        .scalar_subquery()
    )

    entries_query = (
        db.query(WorkerFundEntry)
        .filter(
            WorkerFundEntry.bucket == "pending_settlement",
            WorkerFundEntry.direction == "credit",
            WorkerFundEntry.reference_type == "order_income",
            WorkerFundEntry.created_at <= cutoff,
            # 已全部结算/冲减的历史分录不再占用批次，避免旧数据阻塞新结算。
            WorkerFundEntry.amount > consumed_amount,
        )
    )
    if order_no:
        entries_query = entries_query.filter(WorkerFundEntry.order_no == order_no)
    entries = (
        entries_query.order_by(WorkerFundEntry.created_at.asc(), WorkerFundEntry.id.asc())
        .limit(batch_size)
        .all()
    )

    settled_count = 0
    settled_amount = Decimal("0.00")
    for entry in entries:
        remaining = _pending_remaining(db, entry)
        if remaining <= 0:
            continue
        worker = (
            db.query(Worker)
            .filter(Worker.id == entry.worker_id)
            .with_for_update()
            .first()
        )
        if not worker:
            continue
        reference_id = str(entry.id)
        fee = _fee_amount(db, entry.id)
        settle_desc = f"订单结算到账 {entry.order_no or ''}".strip()
        if fee > 0:
            settle_desc = f"{settle_desc}（平台服务费 ¥{fee}）"
        record_entry(
            db,
            worker,
            bucket="pending_settlement",
            direction="debit",
            amount=remaining,
            reference_type="settlement",
            reference_id=reference_id,
            order_no=entry.order_no,
            description=f"待结算转出 {entry.order_no or ''}".strip(),
            source_entry_id=entry.id,
        )
        record_entry(
            db,
            worker,
            bucket="available",
            direction="credit",
            amount=remaining,
            reference_type="settlement",
            reference_id=reference_id,
            order_no=entry.order_no,
            description=settle_desc,
            source_entry_id=entry.id,
        )
        worker.balance = _money(worker.balance) + remaining
        db.flush()
        db.add(
            Transaction(
                owner_type="worker",
                owner_id=worker.id,
                type="income",
                amount=remaining,
                balance_after=worker.balance,
                method="settlement",
                order_id=entry.order_no,
                description=settle_desc,
                status="success",
            )
        )
        db.flush()
        settled_count += 1
        settled_amount += remaining

    return {"settled_count": settled_count, "settled_amount": float(settled_amount)}


def settle_order_income(db: Session, order_no: str) -> dict:
    """验收通过后立即放款：只结算该订单的待结算收入，不等固定等待期。"""
    if not order_no:
        return {"settled_count": 0, "settled_amount": 0.0}
    return settle_pending_income(db, order_no=order_no, ignore_hold=True)


# ===== 汇总 =====

def _legacy_sum(db: Session, worker_id: int, tx_type: str, status: str) -> float:
    value = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.owner_type == "worker",
            Transaction.owner_id == worker_id,
            Transaction.type == tx_type,
            Transaction.status == status,
        )
        .scalar()
    )
    return round(float(value or 0), 2)


def get_buckets(db: Session, worker: Worker) -> dict:
    """返回六桶汇总；无分录的历史账户回退到余额/交易汇总。"""
    hold_hours = _settlement_hold_hours()
    entries = _entries(db, worker.id)
    if not entries:
        return {
            "available": round(float(worker.balance or 0), 2),
            "pending_settlement": _legacy_sum(db, worker.id, "income", "pending"),
            "frozen": 0.0,
            "withdrawing": _legacy_sum(db, worker.id, "withdraw", "pending"),
            "withdrawn": _legacy_sum(db, worker.id, "withdraw", "success"),
            "reversed": 0.0,
            "settlement_hold_hours": hold_hours,
            "next_settle_at": None,
            "pending_items": [],
            "frozen_items": [],
            "ledger_complete": False,
            "note": "该师傅尚无账本分录，已按余额与历史交易回退汇总。",
        }

    totals = {bucket: Decimal("0.00") for bucket in FUND_BUCKETS}
    for entry in entries:
        if entry.bucket not in totals:
            continue
        amount = _money(entry.amount)
        if entry.direction == "credit":
            totals[entry.bucket] += amount
        else:
            totals[entry.bucket] -= amount

    consumed = _consumed_map(db, worker.id)
    frozen_debits: dict[str, Decimal] = {}
    for entry in entries:
        if entry.bucket == "frozen" and entry.direction == "debit":
            frozen_debits[entry.reference_id] = (
                frozen_debits.get(entry.reference_id, Decimal("0.00"))
                + _money(entry.amount)
            )

    pending_items = []
    frozen_items = []
    for entry in entries:
        if (
            entry.bucket == "pending_settlement"
            and entry.direction == "credit"
            and entry.reference_type == "order_income"
        ):
            remaining = _money(entry.amount) - consumed.get(entry.id, Decimal("0.00"))
            if remaining <= 0:
                continue
            expected_at = (
                entry.created_at + timedelta(hours=hold_hours)
                if entry.created_at is not None
                else None
            )
            pending_items.append(
                {
                    "order_no": entry.order_no,
                    "amount": round(float(remaining), 2),
                    "expected_settle_at": (
                        expected_at.isoformat() + "Z" if expected_at else None
                    ),
                    "_expected": expected_at,
                }
            )
        elif (
            entry.bucket == "frozen"
            and entry.direction == "credit"
            and entry.reference_type == "refund_freeze"
        ):
            remaining = _money(entry.amount) - frozen_debits.get(
                entry.reference_id, Decimal("0.00")
            )
            if remaining <= 0:
                continue
            frozen_items.append(
                {
                    "order_no": entry.order_no,
                    "refund_no": entry.reference_id,
                    "amount": round(float(remaining), 2),
                    "reason": "退款处理中",
                    "created_at": (
                        entry.created_at.isoformat() + "Z"
                        if entry.created_at is not None
                        else None
                    ),
                }
            )

    pending_items.sort(
        key=lambda item: (item["_expected"] is None, item["_expected"] or datetime.min)
    )
    for item in pending_items:
        item.pop("_expected", None)
    expected_times = [
        item["expected_settle_at"]
        for item in pending_items
        if item["expected_settle_at"]
    ]

    data = {bucket: round(float(value), 2) for bucket, value in totals.items()}
    data["settlement_hold_hours"] = hold_hours
    data["next_settle_at"] = expected_times[0] if expected_times else None
    data["pending_items"] = pending_items[:5]
    data["frozen_items"] = frozen_items[:5]
    data["ledger_complete"] = True
    data["note"] = (
        f"订单收入先进入待结算，等待 {hold_hours} 小时后自动转入可提现。"
        if hold_hours
        else "订单收入结算后直接进入可提现。"
    )
    return data


def get_settlements(
    db: Session,
    worker: Worker,
    page: int = 1,
    size: int = 20,
) -> dict:
    """按订单汇总师傅结算明细：订单收入、平台服务费、退款冲正与净收入。"""
    hold_hours = _settlement_hold_hours()
    entries = _entries(db, worker.id)
    consumed = _consumed_map(db, worker.id)
    groups: dict[str, dict] = {}

    for entry in entries:
        if not entry.order_no:
            continue
        group = groups.setdefault(
            entry.order_no,
            {
                "order_no": entry.order_no,
                "order_income": Decimal("0.00"),
                "platform_fee": Decimal("0.00"),
                "refund_reversal": Decimal("0.00"),
                "pending_net": Decimal("0.00"),
                "frozen_net": Decimal("0.00"),
                "settled_at": None,
                "expected": [],
                "latest": entry.created_at,
            },
        )
        if entry.created_at is not None and (
            group["latest"] is None or entry.created_at > group["latest"]
        ):
            group["latest"] = entry.created_at

        amount = _money(entry.amount)
        if entry.bucket == "pending_settlement":
            group["pending_net"] += (
                amount if entry.direction == "credit" else -amount
            )
        elif entry.bucket == "frozen":
            group["frozen_net"] += (
                amount if entry.direction == "credit" else -amount
            )

        if (
            entry.reference_type == "order_income"
            and entry.bucket == "pending_settlement"
            and entry.direction == "credit"
        ):
            group["order_income"] += amount
            remaining = amount - consumed.get(entry.id, Decimal("0.00"))
            if remaining > 0 and entry.created_at is not None:
                group["expected"].append(
                    entry.created_at + timedelta(hours=hold_hours)
                )
        elif (
            entry.reference_type == "platform_fee" and entry.direction == "debit"
        ):
            group["platform_fee"] += amount
        elif entry.reference_type == "refund" and entry.direction == "debit":
            group["refund_reversal"] += amount
        elif (
            entry.reference_type == "settlement"
            and entry.bucket == "available"
            and entry.direction == "credit"
        ):
            if entry.created_at is not None and (
                group["settled_at"] is None or entry.created_at > group["settled_at"]
            ):
                group["settled_at"] = entry.created_at

    items = []
    for group in groups.values():
        net_income = (
            group["order_income"]
            - group["platform_fee"]
            - group["refund_reversal"]
        )
        if group["pending_net"] > 0:
            status = "pending_settlement"
        elif group["frozen_net"] > 0:
            status = "frozen"
        elif net_income <= 0 and group["order_income"] > 0:
            status = "reversed"
        else:
            status = "settled"
        expected = min(group["expected"]) if group["expected"] else None
        items.append(
            {
                "order_no": group["order_no"],
                "order_income": round(float(group["order_income"]), 2),
                "platform_fee": round(float(group["platform_fee"]), 2),
                "refund_reversal": round(float(group["refund_reversal"]), 2),
                "net_income": round(float(net_income), 2),
                "status": status,
                "expected_settle_at": (
                    expected.isoformat() + "Z" if expected else None
                ),
                "settled_at": (
                    group["settled_at"].isoformat() + "Z"
                    if group["settled_at"]
                    else None
                ),
                "_latest": group["latest"],
            }
        )

    items.sort(
        key=lambda item: item["_latest"] or datetime.min,
        reverse=True,
    )
    for item in items:
        item.pop("_latest", None)

    total = len(items)
    offset = (page - 1) * size
    return {
        "list": items[offset: offset + size],
        "total": total,
        "page": page,
        "size": size,
        "has_more": offset + size < total,
        "settlement_hold_hours": hold_hours,
    }


def get_order_settlement(db: Session, order_no: str) -> dict:
    """按订单汇总结算状态：待结算、已到账、冻结、退款冲减与净收入。"""
    entries = (
        db.query(WorkerFundEntry)
        .filter(WorkerFundEntry.order_no == order_no)
        .order_by(WorkerFundEntry.id.asc())
        .all()
    )
    if not entries:
        return {
            "status": "not_applicable",
            "order_income": 0.0,
            "platform_fee": 0.0,
            "refund_reversal": 0.0,
            "net_income": 0.0,
            "pending_amount": 0.0,
            "available_amount": 0.0,
            "frozen_amount": 0.0,
            "settled_at": None,
            "settlement_hold_hours": _settlement_hold_hours(),
        }

    pending_net = Decimal("0.00")
    available_net = Decimal("0.00")
    frozen_net = Decimal("0.00")
    order_income = Decimal("0.00")
    platform_fee = Decimal("0.00")
    refund_reversal = Decimal("0.00")
    settled_at = None

    for entry in entries:
        amount = _money(entry.amount)
        signed = amount if entry.direction == "credit" else -amount
        if entry.bucket == "pending_settlement":
            pending_net += signed
        elif entry.bucket == "available":
            available_net += signed
        elif entry.bucket == "frozen":
            frozen_net += signed

        if (
            entry.reference_type == "order_income"
            and entry.bucket == "pending_settlement"
            and entry.direction == "credit"
        ):
            order_income += amount
        elif entry.reference_type == "platform_fee" and entry.direction == "debit":
            platform_fee += amount
        elif entry.reference_type == "refund" and entry.direction == "debit":
            refund_reversal += amount
        elif (
            entry.reference_type == "settlement"
            and entry.bucket == "available"
            and entry.direction == "credit"
        ):
            if entry.created_at is not None and (
                settled_at is None or entry.created_at > settled_at
            ):
                settled_at = entry.created_at

    if frozen_net > 0:
        status = "frozen"
    elif pending_net > 0:
        status = "pending_settlement"
    elif settled_at is not None or available_net > 0:
        status = "settled"
    else:
        status = "reversed"

    return {
        "status": status,
        "order_income": round(float(order_income), 2),
        "platform_fee": round(float(platform_fee), 2),
        "refund_reversal": round(float(refund_reversal), 2),
        "net_income": round(float(order_income - platform_fee - refund_reversal), 2),
        "pending_amount": round(float(pending_net), 2),
        "available_amount": round(float(available_net), 2),
        "frozen_amount": round(float(frozen_net), 2),
        "settled_at": settled_at.isoformat() + "Z" if settled_at else None,
        "settlement_hold_hours": _settlement_hold_hours(),
    }


def _entries(db: Session, worker_id: int) -> Iterable[WorkerFundEntry]:
    return (
        db.query(WorkerFundEntry)
        .filter(WorkerFundEntry.worker_id == worker_id)
        .all()
    )

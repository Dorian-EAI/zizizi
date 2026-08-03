"""财务统计服务

提供按日财务统计、平台汇总、师傅收入统计等报表能力。
"""

from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.user import User, Worker
from app.models.wallet import PaymentOrder, Transaction


# ===== 辅助函数 =====

def _date_range(start_date: date, end_date: date) -> List[date]:
    """生成[start_date, end_date]之间的所有日期"""
    days = (end_date - start_date).days
    return [start_date + timedelta(days=i) for i in range(days + 1)]


def _to_float(value) -> float:
    """将 SQL 聚合结果转为 float，兼容 None"""
    return float(value) if value is not None else 0.0


# ===== 按日财务统计 =====

def get_daily_stats(db: Session, start_date: date, end_date: date) -> List[dict]:
    """获取指定日期范围的每日财务统计。

    返回字段：
        date, order_count, order_amount, recharge_amount,
        withdraw_amount, platform_income, refund_amount
    """
    if start_date > end_date:
        raise ValueError("start_date 不能晚于 end_date")

    # 订单：按创建日期统计
    order_rows = {
        row.dt: {
            "order_count": int(row.cnt),
            "order_amount": _to_float(row.amt),
        }
        for row in db.query(
            func.date(Order.created_at).label("dt"),
            func.count(Order.id).label("cnt"),
            func.coalesce(func.sum(Order.final_price), 0).label("amt"),
        )
        .filter(func.date(Order.created_at).between(start_date, end_date))
        .group_by("dt")
        .all()
    }

    # 充值（成功）
    recharge_rows = {
        row.dt: _to_float(row.amt)
        for row in db.query(
            func.date(Transaction.created_at).label("dt"),
            func.coalesce(func.sum(Transaction.amount), 0).label("amt"),
        )
        .filter(
            Transaction.type == "recharge",
            Transaction.status == "success",
            func.date(Transaction.created_at).between(start_date, end_date),
        )
        .group_by("dt")
        .all()
    }

    # 提现（成功）
    withdraw_rows = {
        row.dt: _to_float(row.amt)
        for row in db.query(
            func.date(Transaction.created_at).label("dt"),
            func.coalesce(func.sum(Transaction.amount), 0).label("amt"),
        )
        .filter(
            Transaction.type == "withdraw",
            Transaction.status == "success",
            func.date(Transaction.created_at).between(start_date, end_date),
        )
        .group_by("dt")
        .all()
    }

    # 平台收入：用户实际支付成功的订单金额
    platform_income_rows = {
        row.dt: _to_float(row.amt)
        for row in db.query(
            func.date(PaymentOrder.created_at).label("dt"),
            func.coalesce(func.sum(PaymentOrder.amount), 0).label("amt"),
        )
        .filter(
            PaymentOrder.status == "paid",
            func.date(PaymentOrder.created_at).between(start_date, end_date),
        )
        .group_by("dt")
        .all()
    }

    # 退款：支付单状态为 refunded
    refund_rows = {
        row.dt: _to_float(row.amt)
        for row in db.query(
            func.date(PaymentOrder.created_at).label("dt"),
            func.coalesce(func.sum(PaymentOrder.amount), 0).label("amt"),
        )
        .filter(
            PaymentOrder.status == "refunded",
            func.date(PaymentOrder.created_at).between(start_date, end_date),
        )
        .group_by("dt")
        .all()
    }

    result = []
    for d in _date_range(start_date, end_date):
        order_info = order_rows.get(d, {"order_count": 0, "order_amount": 0.0})
        result.append({
            "date": d.isoformat(),
            "order_count": order_info["order_count"],
            "order_amount": order_info["order_amount"],
            "recharge_amount": recharge_rows.get(d, 0.0),
            "withdraw_amount": withdraw_rows.get(d, 0.0),
            "platform_income": platform_income_rows.get(d, 0.0),
            "refund_amount": refund_rows.get(d, 0.0),
        })

    return result


# ===== 平台财务汇总 =====

def get_platform_summary(db: Session) -> dict:
    """获取平台整体财务汇总。

    返回字段：
        total_order_amount, total_recharge, total_withdraw, total_refund,
        total_paid_orders, pending_withdraw, balance_in_system
    """
    # 用户实际支付成功的订单总金额
    total_order_amount = (
        db.query(func.coalesce(func.sum(PaymentOrder.amount), 0))
        .filter(PaymentOrder.status == "paid")
        .scalar()
    ) or 0.0

    # 总充值
    total_recharge = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.type == "recharge",
            Transaction.status == "success",
        )
        .scalar()
    ) or 0.0

    # 总提现（成功）
    total_withdraw = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.type == "withdraw",
            Transaction.status == "success",
        )
        .scalar()
    ) or 0.0

    # 总退款
    total_refund = (
        db.query(func.coalesce(func.sum(PaymentOrder.amount), 0))
        .filter(PaymentOrder.status == "refunded")
        .scalar()
    ) or 0.0

    # 已支付订单数（含已完成、已评价、已退款）
    paid_statuses = {"paid", "completed", "reviewed", "refunded"}
    total_paid_orders = (
        db.query(func.count(Order.id))
        .filter(Order.status.in_(paid_statuses))
        .scalar()
    ) or 0

    # 待提现金额
    pending_withdraw = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.type == "withdraw",
            Transaction.status == "pending",
        )
        .scalar()
    ) or 0.0

    # 系统内余额 = 用户余额 + 师傅余额
    user_balance = (
        db.query(func.coalesce(func.sum(User.balance), 0)).scalar()
    ) or 0.0
    worker_balance = (
        db.query(func.coalesce(func.sum(Worker.balance), 0)).scalar()
    ) or 0.0
    balance_in_system = user_balance + worker_balance

    return {
        "total_order_amount": float(total_order_amount),
        "total_recharge": float(total_recharge),
        "total_withdraw": float(total_withdraw),
        "total_refund": float(total_refund),
        "total_paid_orders": int(total_paid_orders),
        "pending_withdraw": float(pending_withdraw),
        "balance_in_system": float(balance_in_system),
    }


# ===== 师傅收入统计 =====

def get_worker_income_stats(
    db: Session,
    worker_id: Optional[int] = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    """分页获取师傅收入汇总。

    返回每个师傅的：
        worker_id, nickname, real_name, phone, total_income,
        order_count, balance
    """
    query = (
        db.query(
            Worker.id.label("worker_id"),
            Worker.nickname,
            Worker.real_name,
            Worker.phone,
            Worker.balance,
            func.coalesce(func.sum(Transaction.amount), 0).label("total_income"),
            func.count(Transaction.order_id.distinct()).label("order_count"),
        )
        .outerjoin(
            Transaction,
            (Worker.id == Transaction.owner_id)
            & (Transaction.owner_type == "worker")
            & (Transaction.type == "income")
            & (Transaction.status == "success"),
        )
        .group_by(Worker.id)
    )

    if worker_id is not None:
        query = query.filter(Worker.id == worker_id)

    total = query.count()
    offset = (page - 1) * size
    items = (
        query.order_by(func.sum(Transaction.amount).desc())
        .offset(offset)
        .limit(size)
        .all()
    )

    result_list = []
    for row in items:
        result_list.append({
            "worker_id": row.worker_id,
            "nickname": row.nickname,
            "real_name": row.real_name,
            "phone": row.phone,
            "total_income": float(row.total_income),
            "order_count": int(row.order_count),
            "balance": float(row.balance or 0),
        })

    return {
        "list": result_list,
        "total": total,
        "page": page,
        "size": size,
        "has_more": (offset + size) < total,
    }

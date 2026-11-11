"""Excel/CSV 导出服务"""

import csv
import io
from datetime import datetime, date, time
from typing import Iterable, Iterator, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.user import User, Worker
from app.models.wallet import Transaction

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    _OPENPYXL_AVAILABLE = True
except ImportError:  # pragma: no cover
    Workbook = None
    Font = None
    _OPENPYXL_AVAILABLE = False


# ===== 常量 =====

_ORDER_COLUMNS = [
    ("订单编号", "order_no"),
    ("服务类型", "service_type"),
    ("服务名称", "service_name"),
    ("用户ID", "user_id"),
    ("师傅ID", "worker_id"),
    ("订单金额", "amount"),
    ("状态", "status"),
    ("创建时间", "created_at"),
    ("完成时间", "completed_at"),
    ("支付时间", "paid_at"),
]

_USER_COLUMNS = [
    ("ID", "id"),
    ("昵称", "nickname"),
    ("手机号", "phone"),
    ("角色", "role"),
    ("会员等级", "member_level"),
    ("余额", "balance"),
    ("状态", "status"),
    ("注册时间", "created_at"),
]

_WORKER_COLUMNS = [
    ("ID", "id"),
    ("昵称", "nickname"),
    ("真实姓名", "real_name"),
    ("手机号", "phone"),
    ("认证状态", "certified"),
    ("评分", "rating"),
    ("服务次数", "service_count"),
    ("余额", "balance"),
    ("在线状态", "is_online"),
    ("注册时间", "created_at"),
]

_FINANCE_COLUMNS = [
    ("日期", "date"),
    ("订单数", "order_count"),
    ("订单金额", "order_amount"),
    ("收入金额", "income_amount"),
    ("充值金额", "recharge_amount"),
    ("提现金额", "withdraw_amount"),
    ("退款金额", "refund_amount"),
    ("平台净收入", "net_income"),
]

MAX_EXPORT_ROWS = 10_000
MAX_FINANCE_RANGE_DAYS = 366
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


# ===== 工具函数 =====

def _now_str() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _format_datetime(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _format_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _to_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    return _sanitize_spreadsheet_value(str(value))


def _sanitize_spreadsheet_value(value):
    """阻止用户可控文本被 Excel/CSV 解释为公式。"""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def _bounded_all(query, resource_name: str):
    """导出在数据库侧限流，避免一次请求无界占用内存。"""
    rows = query.limit(MAX_EXPORT_ROWS + 1).all()
    if len(rows) > MAX_EXPORT_ROWS:
        raise HTTPException(
            status_code=413,
            detail=f"{resource_name}超过单次 {MAX_EXPORT_ROWS} 条上限，请缩小筛选范围",
        )
    return rows


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")


def _chunked_buffer(buffer: io.BytesIO, chunk_size: int = 65536) -> Iterator[bytes]:
    """将内存中的字节缓冲区分块生成，用于 StreamingResponse"""
    buffer.seek(0)
    while True:
        chunk = buffer.read(chunk_size)
        if not chunk:
            break
        yield chunk


def _build_xlsx_buffer(rows: List[List], headers: List[str]) -> io.BytesIO:
    """使用 openpyxl 生成 Excel 文件并返回 BytesIO"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    # 表头加粗
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = Font(bold=True)

    # 数据行
    for row_idx, row in enumerate(rows, 2):
        for col_idx, value in enumerate(row, 1):
            ws.cell(row=row_idx, column=col_idx, value=_sanitize_spreadsheet_value(value))

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer


def _build_csv_buffer(rows: Iterable[Iterable]) -> io.BytesIO:
    """生成 UTF-8 CSV 文件（带 BOM，Excel 可直接打开中文）"""
    string_io = io.StringIO()
    writer = csv.writer(string_io)
    for row in rows:
        writer.writerow([_sanitize_spreadsheet_value(value) for value in row])
    # UTF-8 BOM 保证 Excel 识别中文
    return io.BytesIO(b"\xef\xbb\xbf" + string_io.getvalue().encode("utf-8"))


def _make_file_stream(
    rows: List[List],
    headers: List[str],
    base_filename: str,
) -> Tuple[str, str, Iterator[bytes]]:
    """根据 openpyxl 是否可用，返回 (filename, content_type, byte_iterator)"""
    if _OPENPYXL_AVAILABLE:
        buffer = _build_xlsx_buffer(rows, headers)
        filename = f"{base_filename}_{_now_str()}.xlsx"
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        buffer = _build_csv_buffer([headers] + rows)
        filename = f"{base_filename}_{_now_str()}.csv"
        content_type = "text/csv; charset=utf-8"
    return filename, content_type, _chunked_buffer(buffer)


# ===== 数据转换 =====

def _order_to_row(o: Order) -> List:
    # 订单金额：优先使用成交价，否则预算
    amount = o.final_price if o.final_price is not None else o.budget
    return [
        _to_str(o.order_no),
        _to_str(o.service_type),
        _to_str(o.service_name),
        _to_str(o.user_id),
        _to_str(o.worker_id),
        amount,
        _to_str(o.status),
        _format_datetime(o.created_at),
        _format_datetime(o.completed_at),
        _format_datetime(o.paid_at),
    ]


def _user_to_row(u: User) -> List:
    return [
        _to_str(u.id),
        _to_str(u.nickname),
        _to_str(u.phone),
        _to_str(u.role),
        _to_str(u.member_level),
        float(u.balance or 0),
        "启用" if u.is_active else "禁用",
        _format_datetime(u.created_at),
    ]


def _worker_to_row(w: Worker) -> List:
    return [
        _to_str(w.id),
        _to_str(w.nickname),
        _to_str(w.real_name),
        _to_str(w.phone),
        _to_str(w.certified),
        float(w.rating or 0),
        _to_str(w.service_count),
        float(w.balance or 0),
        "在线" if w.is_online else "离线",
        _format_datetime(w.created_at),
    ]


# ===== 导出函数 =====

def export_orders(
    db: Session,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """导出订单 Excel/CSV"""
    query = db.query(Order)

    if status:
        query = query.filter(Order.status == status)

    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start:
        query = query.filter(Order.created_at >= datetime.combine(start, time.min))
    if end:
        query = query.filter(Order.created_at <= datetime.combine(end, time.max))

    orders = _bounded_all(query.order_by(Order.created_at.desc()), "订单导出结果")
    rows = [_order_to_row(o) for o in orders]
    headers = [h for h, _ in _ORDER_COLUMNS]
    return _make_file_stream(rows, headers, "orders")


def export_users(
    db: Session,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
):
    """导出用户 Excel/CSV"""
    query = db.query(User)

    if status is not None:
        is_active = True if str(status).lower() in ("1", "true", "active") else False
        query = query.filter(User.is_active == is_active)

    if keyword:
        like = f"%{keyword}%"
        from sqlalchemy import or_
        query = query.filter(or_(
            User.nickname.like(like),
            User.phone.like(like),
        ))

    users = _bounded_all(query.order_by(User.created_at.desc()), "用户导出结果")
    rows = [_user_to_row(u) for u in users]
    headers = [h for h, _ in _USER_COLUMNS]
    return _make_file_stream(rows, headers, "users")


def export_workers(
    db: Session,
    certified: Optional[int] = None,
    keyword: Optional[str] = None,
):
    """导出师傅 Excel/CSV"""
    query = db.query(Worker)

    if certified is not None:
        query = query.filter(Worker.certified == int(certified))

    if keyword:
        like = f"%{keyword}%"
        from sqlalchemy import or_
        query = query.filter(or_(
            Worker.nickname.like(like),
            Worker.phone.like(like),
            Worker.real_name.like(like),
        ))

    workers = _bounded_all(query.order_by(Worker.created_at.desc()), "师傅导出结果")
    rows = [_worker_to_row(w) for w in workers]
    headers = [h for h, _ in _WORKER_COLUMNS]
    return _make_file_stream(rows, headers, "workers")


def export_finance_report(
    db: Session,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """导出每日财务汇总 Excel/CSV"""
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    if not start or not end:
        raise HTTPException(status_code=400, detail="start_date 和 end_date 不能为空")
    if end < start:
        raise HTTPException(status_code=400, detail="end_date 不能早于 start_date")
    if (end - start).days + 1 > MAX_FINANCE_RANGE_DAYS:
        raise HTTPException(
            status_code=413,
            detail=f"财务报表单次最多导出 {MAX_FINANCE_RANGE_DAYS} 天",
        )

    start_dt = datetime.combine(start, time.min)
    end_dt = datetime.combine(end, time.max)

    # 订单按日汇总
    order_stats = (
        db.query(
            func.date(Order.created_at).label("day"),
            func.count(Order.id).label("order_count"),
            func.coalesce(func.sum(Order.final_price), 0).label("order_amount"),
        )
        .filter(Order.created_at >= start_dt, Order.created_at <= end_dt)
        .group_by(func.date(Order.created_at))
        .all()
    )

    # 交易按日、按类型汇总
    tx_stats = (
        db.query(
            func.date(Transaction.created_at).label("day"),
            Transaction.type.label("type"),
            func.coalesce(func.sum(Transaction.amount), 0).label("amount"),
        )
        .filter(
            Transaction.created_at >= start_dt,
            Transaction.created_at <= end_dt,
            Transaction.status == "success",
        )
        .group_by(func.date(Transaction.created_at), Transaction.type)
        .all()
    )

    # 合并日期
    days = {row.day for row in order_stats}
    days.update({row.day for row in tx_stats})

    tx_map = {}
    for row in tx_stats:
        tx_map.setdefault(row.day, {})[row.type] = float(row.amount)

    order_map = {}
    for row in order_stats:
        order_map[row.day] = {
            "count": int(row.order_count),
            "amount": float(row.order_amount),
        }

    rows = []
    for day in sorted(days):
        order_count = order_map.get(day, {}).get("count", 0)
        order_amount = order_map.get(day, {}).get("amount", 0.0)
        income = tx_map.get(day, {}).get("income", 0.0)
        recharge = tx_map.get(day, {}).get("recharge", 0.0)
        withdraw = tx_map.get(day, {}).get("withdraw", 0.0)
        refund = tx_map.get(day, {}).get("refund", 0.0)
        net_income = income - refund
        rows.append([
            _format_date(day),
            order_count,
            order_amount,
            income,
            recharge,
            withdraw,
            refund,
            net_income,
        ])

    headers = [h for h, _ in _FINANCE_COLUMNS]
    return _make_file_stream(rows, headers, "finance_report")

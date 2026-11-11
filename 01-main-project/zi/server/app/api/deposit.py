"""师傅保证金 API"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_worker, get_current_admin, require_super_admin
from app.models.user import Worker
from app.schemas.deposit import DepositPayRequest, DepositDetailResponse, AdminDeductDepositRequest
from app.services import deposit_service
from app.utils.response import success

router = APIRouter(prefix="/api/worker/deposit", tags=["保证金"])


@router.post("/pay")
async def deposit_pay(
    req: DepositPayRequest,
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """缴纳保证金。开发环境为模拟直到账，生产环境在真实支付接入前关闭。"""
    deposit = deposit_service.deposit_pay(db, worker.id, req.amount)
    return success(data={
        "deposit_level": deposit.deposit_level,
        "balance": deposit.balance,
        "platform_cut_rate": float(deposit.platform_cut_rate),
        "daily_order_limit": deposit.daily_order_limit,
    })


@router.get("/")
async def deposit_detail(
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """保证金详情+流水"""
    detail = deposit_service.get_deposit_detail(db, worker.id)
    deposit = detail["deposit"]
    return success(data={
        "worker_id": deposit.worker_id,
        "deposit_level": deposit.deposit_level,
        "balance": deposit.balance,
        "frozen_amount": deposit.frozen_amount,
        "total_deposited": deposit.total_deposited,
        "platform_cut_rate": float(deposit.platform_cut_rate),
        "daily_order_limit": deposit.daily_order_limit,
        "status": deposit.status,
        "transactions": [
            {
                "id": t.id,
                "type": t.type,
                "amount": t.amount,
                "balance_after": t.balance_after,
                "reason": t.reason,
                "created_at": t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else None,
            }
            for t in detail["transactions"]
        ],
    })


@router.post("/refund")
async def request_refund(
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """申请退还保证金"""
    result = deposit_service.request_refund(db, worker.id)
    return success(data=result)


# ===== 管理员接口 =====

@router.get("/admin/worker/deposits")
async def admin_deposits(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """保证金账户列表"""
    from app.models.deposit import WorkerDeposit
    q = db.query(WorkerDeposit)
    total = q.count()
    items = q.offset((page - 1) * size).limit(size).all()
    return success(data={
        "total": total,
        "items": [
            {
                "worker_id": d.worker_id,
                "deposit_level": d.deposit_level,
                "balance": d.balance,
                "frozen_amount": d.frozen_amount,
                "status": d.status,
            }
            for d in items
        ],
    })


@router.put("/admin/worker/{worker_id}/deposit/deduct")
async def admin_deduct_deposit(
    worker_id: int,
    req: AdminDeductDepositRequest,
    admin=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """手动扣除保证金"""
    deposit = deposit_service.deduct_deposit(db, worker_id, req.amount, req.reason)
    return success(data={"balance": deposit.balance})

"""财务管理接口"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.services import finance_service
from app.utils.response import success

router = APIRouter(prefix="/api/admin", tags=["财务管理"])


@router.get("/finance/daily")
async def daily_finance_stats(
    start_date: date = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: date = Query(..., description="结束日期 YYYY-MM-DD"),
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """按日财务统计"""
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date 不能晚于 end_date")

    items = finance_service.get_daily_stats(db, start_date, end_date)
    return success(data={
        "list": items,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    })


@router.get("/finance/summary")
async def platform_finance_summary(
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """平台财务汇总"""
    summary = finance_service.get_platform_summary(db)
    return success(data=summary)


@router.get("/finance/worker-income")
async def worker_income_stats(
    worker_id: Optional[int] = Query(None, description="师傅 ID，不传则查全部"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """师傅收入统计"""
    result = finance_service.get_worker_income_stats(
        db, worker_id=worker_id, page=page, size=size
    )
    return success(data=result)

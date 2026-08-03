"""运营后台导出接口"""

from typing import Iterator, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.database import get_db
from app.dependencies import require_super_admin
from app.services import export_service

router = APIRouter(prefix="/api/admin/exports", tags=["运营后台-导出"])


def _build_streaming_response(
    filename: str,
    content_type: str,
    data: Iterator[bytes],
) -> StreamingResponse:
    """统一构造带下载头的 StreamingResponse"""
    return StreamingResponse(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"",
        },
    )


@router.get("/orders")
async def export_orders(
    status: Optional[str] = Query(None, description="订单状态筛选"),
    start_date: Optional[str] = Query(None, description="创建开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="创建结束日期 YYYY-MM-DD"),
    admin=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """导出订单列表"""
    filename, content_type, stream = export_service.export_orders(
        db, status=status, start_date=start_date, end_date=end_date
    )
    return _build_streaming_response(filename, content_type, stream)


@router.get("/users")
async def export_users(
    status: Optional[str] = Query(None, description="用户状态筛选 1/active/0/inactive"),
    keyword: Optional[str] = Query(None, description="昵称/手机号关键词"),
    admin=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """导出用户列表"""
    filename, content_type, stream = export_service.export_users(
        db, status=status, keyword=keyword
    )
    return _build_streaming_response(filename, content_type, stream)


@router.get("/workers")
async def export_workers(
    certified: Optional[int] = Query(None, description="认证状态 0/1/2/3"),
    keyword: Optional[str] = Query(None, description="昵称/手机号/真实姓名关键词"),
    admin=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """导出师傅列表"""
    filename, content_type, stream = export_service.export_workers(
        db, certified=certified, keyword=keyword
    )
    return _build_streaming_response(filename, content_type, stream)


@router.get("/finance-report")
async def export_finance_report(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    admin=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """导出每日财务汇总报表"""
    filename, content_type, stream = export_service.export_finance_report(
        db, start_date=start_date, end_date=end_date
    )
    return _build_streaming_response(filename, content_type, stream)

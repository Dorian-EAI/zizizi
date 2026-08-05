"""客服工单与仲裁 API"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import (
    get_current_user,
    get_current_worker,
    get_current_account,
    get_current_admin,
    require_admin_operator,
)
from app.models.user import User, Worker
from app.models.support_ticket import SupportTicket, TicketReply
from app.models.order import Order
from app.schemas.support_ticket import (
    CreateTicketRequest,
    TicketReplyRequest,
    TicketReplyResponse,
    SupportTicketResponse,
    AdminAssignTicketRequest,
    AdminResolveTicketRequest,
    AdminTicketReplyRequest,
)
from app.services import support_ticket_service
from app.utils.response import success

router = APIRouter(prefix="/api/support-tickets", tags=["客服工单"])


def _serialize_ticket(db: Session, ticket: SupportTicket, include_internal: bool = False) -> dict:
    data = SupportTicketResponse.model_validate(ticket).model_dump(mode="json")
    replies_q = db.query(TicketReply).filter(TicketReply.ticket_id == ticket.id)
    if not include_internal:
        replies_q = replies_q.filter(TicketReply.is_internal == False)
    replies = replies_q.order_by(TicketReply.created_at.asc()).limit(500).all()
    data["replies"] = [
        TicketReplyResponse.model_validate(item).model_dump(mode="json")
        for item in replies
    ]
    return data


def _require_ticket_owner(db: Session, ticket_id: int, account: tuple) -> SupportTicket:
    account_obj, account_type = account
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="工单不存在")
    if ticket.creator_type != account_type or ticket.creator_id != account_obj.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="无权查看或操作该工单")
    return ticket


@router.post("/")
async def create_ticket(
    req: CreateTicketRequest,
    db: Session = Depends(get_db),
    account: tuple = Depends(get_current_account),
):
    """创建工单"""
    account_obj, account_type = account
    creator_id = account_obj.id
    creator_name = getattr(account_obj, "nickname", None) or getattr(account_obj, "real_name", None) or "未知"
    creator_phone = getattr(account_obj, "phone", None)

    if req.related_order_id:
        order = db.query(Order).filter(Order.id == req.related_order_id).first()
        if not order:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="关联订单不存在")
        allowed = order.user_id == creator_id if account_type == "user" else order.worker_id == creator_id
        if not allowed:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="无权为该订单创建工单")

    ticket = support_ticket_service.create_ticket(
        db, account_type, creator_id, creator_name, creator_phone,
        req.ticket_type, req.title, req.description,
        req.related_order_id, req.evidence_urls,
    )
    return success(data=SupportTicketResponse.model_validate(ticket).model_dump(mode="json"))


@router.get("/my")
async def my_tickets(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    account: tuple = Depends(get_current_account),
):
    """我的工单列表"""
    account_obj, account_type = account
    result = support_ticket_service.list_tickets(
        db,
        status=status,
        page=1,
        size=100,
        creator_type=account_type,
        creator_id=account_obj.id,
    )
    return success(data=[
        _serialize_ticket(db, item)
        for item in result["items"]
    ])


@router.get("/{ticket_id}")
async def ticket_detail(
    ticket_id: int,
    account: tuple = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """工单详情"""
    _require_ticket_owner(db, ticket_id, account)
    ticket = support_ticket_service.get_ticket_detail(db, ticket_id)
    return success(data=_serialize_ticket(db, ticket))


@router.post("/{ticket_id}/reply")
async def reply_ticket(
    ticket_id: int,
    req: TicketReplyRequest,
    db: Session = Depends(get_db),
    account: tuple = Depends(get_current_account),
):
    """回复工单"""
    _require_ticket_owner(db, ticket_id, account)
    account_obj, account_type = account
    replier_name = getattr(account_obj, "nickname", None) or getattr(account_obj, "real_name", None) or "未知"
    reply = support_ticket_service.reply_ticket(
        db, ticket_id, account_type, account_obj.id, replier_name, req.content
    )
    return success(data=TicketReplyResponse.model_validate(reply).model_dump(mode="json"))


# ===== 管理员接口 =====

@router.get("/admin/tickets")
async def admin_tickets(
    status: Optional[str] = Query(None),
    ticket_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    admin=Depends(require_admin_operator),
    db: Session = Depends(get_db),
):
    """工单列表（后台）"""
    result = support_ticket_service.list_tickets(db, status, ticket_type, None, page, size)
    return success(data={
        "total": result["total"],
        "page": result["page"],
        "size": result["size"],
        "items": [
            _serialize_ticket(db, i, include_internal=True)
            for i in result["items"]
        ],
    })


@router.put("/admin/tickets/{ticket_id}/assign")
async def assign_ticket(
    ticket_id: int,
    req: AdminAssignTicketRequest,
    admin=Depends(require_admin_operator),
    db: Session = Depends(get_db),
):
    """分配工单"""
    ticket = support_ticket_service.assign_ticket(db, ticket_id, req.admin_id)
    return success(data=SupportTicketResponse.model_validate(ticket).model_dump(mode="json"))


@router.post("/admin/tickets/{ticket_id}/reply")
async def admin_reply_ticket(
    ticket_id: int,
    req: AdminTicketReplyRequest,
    admin=Depends(require_admin_operator),
    db: Session = Depends(get_db),
):
    """管理员回复工单；内部备注不会返回给用户端。"""
    replier_name = admin.real_name or admin.username
    reply = support_ticket_service.reply_ticket(
        db,
        ticket_id,
        "admin",
        admin.id,
        replier_name,
        req.content,
        req.is_internal,
    )
    return success(data=TicketReplyResponse.model_validate(reply).model_dump(mode="json"))


@router.put("/admin/tickets/{ticket_id}/resolve")
async def resolve_ticket(
    ticket_id: int,
    req: AdminResolveTicketRequest,
    admin=Depends(require_admin_operator),
    db: Session = Depends(get_db),
):
    """结单"""
    ticket = support_ticket_service.resolve_ticket(
        db, admin.id, ticket_id, req.resolution, req.refund_amount, req.deduct_deposit
    )
    return success(data=SupportTicketResponse.model_validate(ticket).model_dump(mode="json"))


@router.put("/admin/tickets/{ticket_id}/close")
async def close_ticket(
    ticket_id: int,
    admin=Depends(require_admin_operator),
    db: Session = Depends(get_db),
):
    """关闭工单"""
    ticket = support_ticket_service.close_ticket(db, ticket_id)
    return success(data=SupportTicketResponse.model_validate(ticket).model_dump(mode="json"))

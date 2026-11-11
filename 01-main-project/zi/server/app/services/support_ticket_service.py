"""客服工单业务逻辑"""

from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.support_ticket import SupportTicket, TicketReply
from app.models.admin import Admin
from app.utils.snowflake import generate_business_no


def _gen_ticket_no() -> str:
    return generate_business_no("TK")


def create_ticket(db: Session, creator_type: str, creator_id: int,
                  creator_name: str, creator_phone: str,
                  ticket_type: str, title: str, description: str,
                  related_order_id: int = None, evidence_urls: List[str] = None) -> SupportTicket:
    """创建工单"""
    ticket = SupportTicket(
        ticket_no=_gen_ticket_no(),
        ticket_type=ticket_type,
        creator_type=creator_type,
        creator_id=creator_id,
        creator_name=creator_name,
        creator_phone=creator_phone,
        related_order_id=related_order_id,
        title=title,
        description=description,
        evidence_urls=evidence_urls or [],
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def reply_ticket(db: Session, ticket_id: int, replier_type: str, replier_id: int,
                 replier_name: str, content: str, is_internal: bool = False) -> TicketReply:
    """回复工单"""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    if ticket.status == "closed":
        raise HTTPException(status_code=400, detail="工单已关闭")

    reply = TicketReply(
        ticket_id=ticket_id,
        reply_type=replier_type,
        replier_id=replier_id,
        replier_name=replier_name,
        content=content,
        is_internal=is_internal,
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return reply


def assign_ticket(db: Session, ticket_id: int, admin_id: int) -> SupportTicket:
    """分配工单"""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    if ticket.status == "closed":
        raise HTTPException(status_code=409, detail="已关闭工单不能重新分配")
    assignee = db.query(Admin).filter(Admin.id == admin_id, Admin.is_active == True).first()
    if not assignee:
        raise HTTPException(status_code=404, detail="被分配管理员不存在或已停用")
    ticket.assigned_to = admin_id
    ticket.status = "processing"
    db.commit()
    db.refresh(ticket)
    return ticket


def resolve_ticket(db: Session, admin_id: int, ticket_id: int,
                   resolution: str, refund_amount: int = 0, deduct_deposit: int = 0) -> SupportTicket:
    """客服结单"""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    if ticket.status == "closed":
        raise HTTPException(status_code=400, detail="工单已关闭")
    if refund_amount or deduct_deposit:
        raise HTTPException(
            status_code=501,
            detail="工单资金动作尚未接入专用退款/保证金流水，本次未结案也未变更资金",
        )

    ticket.status = "resolved"
    ticket.resolution = resolution
    ticket.refund_amount = refund_amount
    ticket.deduct_deposit = deduct_deposit
    ticket.resolved_by = admin_id
    ticket.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)
    return ticket


def close_ticket(db: Session, ticket_id: int) -> SupportTicket:
    """关闭工单"""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    if ticket.status != "resolved":
        raise HTTPException(status_code=409, detail="仅已解决工单可以关闭")
    ticket.status = "closed"
    ticket.closed_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)
    return ticket


def list_tickets(db: Session, status: str = None, ticket_type: str = None,
                 assigned_to: int = None, page: int = 1, size: int = 20,
                 creator_type: str = None, creator_id: int = None) -> dict:
    """工单列表"""
    q = db.query(SupportTicket)
    if status:
        q = q.filter(SupportTicket.status == status)
    if ticket_type:
        q = q.filter(SupportTicket.ticket_type == ticket_type)
    if assigned_to:
        q = q.filter(SupportTicket.assigned_to == assigned_to)
    if creator_type:
        q = q.filter(SupportTicket.creator_type == creator_type)
    if creator_id is not None:
        q = q.filter(SupportTicket.creator_id == creator_id)

    total = q.count()
    items = q.order_by(SupportTicket.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return {"total": total, "items": items, "page": page, "size": size}


def get_ticket_detail(db: Session, ticket_id: int) -> SupportTicket:
    """工单详情"""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    return ticket

"""消息中心路由"""

from typing import Optional, Tuple, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_account, require_super_admin
from app.config import settings
from app.schemas.message import (
    MessageResponse,
    MessageListResponse,
    TestSendMessageRequest,
)
from app.services import message_service
from app.utils.response import success

router = APIRouter(prefix="/api/messages", tags=["消息中心"])


@router.get("")
async def list_messages(
    type: Optional[str] = Query(None, description="消息类型 order/system/activity"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    account_and_type: Tuple[Any, str] = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """获取消息列表"""
    account, account_type = account_and_type
    result = message_service.get_messages(db, account_type, account.id, type, page, size)
    data = {
        "list": [MessageResponse.model_validate(m).model_dump(mode="json") for m in result["list"]],
        "total": result["total"],
        "unread_count": result["unread_count"],
        "page": result["page"],
        "has_more": result["has_more"],
    }
    return success(data=data)


@router.get("/unread-count")
async def get_unread_count(
    account_and_type: Tuple[Any, str] = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """获取未读消息数量"""
    account, account_type = account_and_type
    count = message_service.get_unread_count(db, account_type, account.id)
    return success(data={"unread_count": count})


@router.put("/{msg_id}/read")
async def mark_read(
    msg_id: int,
    account_and_type: Tuple[Any, str] = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """标记单条消息为已读"""
    account, account_type = account_and_type
    msg = message_service.mark_read(db, account_type, account.id, msg_id)
    return success(data=MessageResponse.model_validate(msg).model_dump(mode="json"), message="已标为已读")


@router.put("/read-all")
async def mark_all_read(
    account_and_type: Tuple[Any, str] = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """标记所有消息为已读"""
    account, account_type = account_and_type
    count = message_service.mark_all_read(db, account_type, account.id)
    return success(data={"updated": count}, message=f"已标记 {count} 条消息为已读")


@router.delete("/{msg_id}")
async def delete_message(
    msg_id: int,
    account_and_type: Tuple[Any, str] = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """删除单条消息"""
    account, account_type = account_and_type
    message_service.delete_message(db, account_type, account.id, msg_id)
    return success(message="删除成功")


@router.post("/test/send")
async def test_send_message(
    req: TestSendMessageRequest,
    admin=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """开发调试：手动发送一条消息"""
    if settings.is_deployed:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="调试接口在当前环境不可用")
    msg = message_service.send_inbox_message(
        db=db,
        owner_type=req.owner_type,
        owner_id=req.owner_id,
        msg_type=req.type,
        title=req.title,
        content=req.content,
    )
    return success(data=MessageResponse.model_validate(msg).model_dump(mode="json"), message="发送成功")

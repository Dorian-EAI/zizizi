"""系统设置相关路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_account
from app.schemas.setting import NotificationSettingUpdateRequest
from app.services import setting_service
from app.utils.response import success

router = APIRouter(prefix="/api/settings", tags=["系统设置"])


@router.get("/notification")
async def get_notification_setting(
    account: tuple = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """获取当前账号的通知设置"""
    account_obj, account_type = account
    owner_id = account_obj.id
    s = setting_service.get_notification_setting(db, account_type, owner_id)
    data = {
        "push_order": s.push_order,
        "push_system": s.push_system,
        "push_activity": s.push_activity,
        "push_sms": s.push_sms,
        "updated_at": s.updated_at,
    }
    return success(data=data)


@router.put("/notification")
async def update_notification_setting(
    req: NotificationSettingUpdateRequest,
    account: tuple = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """更新当前账号的通知设置"""
    account_obj, account_type = account
    owner_id = account_obj.id
    s = setting_service.update_notification_setting(
        db, account_type, owner_id, req.model_dump(exclude_unset=True)
    )
    data = {
        "push_order": s.push_order,
        "push_system": s.push_system,
        "push_activity": s.push_activity,
        "push_sms": s.push_sms,
        "updated_at": s.updated_at,
    }
    return success(data=data, message="通知设置已更新")

"""系统设置（通知设置等）业务逻辑"""

from typing import Optional, Tuple, Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.setting import NotificationSetting


ALLOWED_OWNER_TYPES = {"user", "worker"}


def get_notification_setting(
    db: Session,
    owner_type: str,
    owner_id: int,
) -> NotificationSetting:
    """获取通知设置（如果不存在则创建默认并返回）"""
    owner_type = (owner_type or "").strip().lower()
    if owner_type not in ALLOWED_OWNER_TYPES:
        raise HTTPException(status_code=400, detail=f"owner_type 非法，可选: {', '.join(sorted(ALLOWED_OWNER_TYPES))}")

    setting = (
        db.query(NotificationSetting)
        .filter(
            NotificationSetting.owner_type == owner_type,
            NotificationSetting.owner_id == owner_id,
        )
        .first()
    )
    if setting:
        return setting

    # 不存在则创建默认
    setting = NotificationSetting(
        owner_type=owner_type,
        owner_id=owner_id,
        push_order=True,
        push_system=True,
        push_activity=True,
        push_sms=False,
    )
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


def update_notification_setting(
    db: Session,
    owner_type: str,
    owner_id: int,
    data_dict: dict,
) -> NotificationSetting:
    """更新通知设置，data_dict 中每个开关有值才更新"""
    setting = get_notification_setting(db, owner_type, owner_id)

    fields = ["push_order", "push_system", "push_activity", "push_sms"]
    changed = False
    for f in fields:
        if f in data_dict and data_dict[f] is not None:
            v = bool(data_dict[f])
            if getattr(setting, f) != v:
                setattr(setting, f, v)
                changed = True
    if changed:
        db.commit()
        db.refresh(setting)
    return setting


def setting_to_dict(s: NotificationSetting) -> dict:
    return {
        "push_order": s.push_order,
        "push_system": s.push_system,
        "push_activity": s.push_activity,
        "push_sms": s.push_sms,
        "owner_type": s.owner_type,
        "owner_id": s.owner_id,
        "updated_at": s.updated_at,
    }

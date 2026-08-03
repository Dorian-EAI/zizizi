"""系统设置相关 Pydantic 模型"""

from typing import Optional
from pydantic import BaseModel


class NotificationSettingResponse(BaseModel):
    push_order: bool
    push_system: bool
    push_activity: bool
    push_sms: bool


class NotificationSettingUpdateRequest(BaseModel):
    push_order: Optional[bool] = None
    push_system: Optional[bool] = None
    push_activity: Optional[bool] = None
    push_sms: Optional[bool] = None

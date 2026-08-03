"""运营后台相关 Pydantic 模型"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


def _validate_bcrypt_password(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("密码 UTF-8 编码长度不得超过 72 字节")
    return value


# ===== 请求 =====
class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., max_length=32)
    password: str = Field(..., max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_bcrypt_password(value)


class AdminCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., max_length=32)
    password: str = Field(..., min_length=12, max_length=128)
    real_name: Optional[str] = Field(None, max_length=32)
    role: Literal["super_admin", "operator", "auditor"] = "operator"

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_bcrypt_password(value)


class ToggleActiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool


class WorkerCertifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 0=未认证 1=审核中 2=已认证 3=未通过
    certified: Literal[0, 1, 2, 3]


class UpdateOrderStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["cancelled"]
    remark: str = Field(..., min_length=2, max_length=512)


# ===== 响应 =====
class AdminLoginResponse(BaseModel):
    token: str = Field(..., max_length=256)
    admin_id: int
    role: str = Field(..., max_length=32)


class AdminInfoResponse(BaseModel):
    id: int
    username: str = Field(..., max_length=32)
    real_name: Optional[str] = Field(None, max_length=32)
    role: str = Field(..., max_length=32)
    is_active: bool
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    today_orders: int
    today_amount: float
    new_users: int
    new_workers: int
    pending_withdraw_count: int

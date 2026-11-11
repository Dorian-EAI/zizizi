"""短信验证码路由"""

import re
from fastapi import APIRouter, Request
from typing import Literal
from pydantic import BaseModel, Field, field_validator

from app.services import sms_service
from app.utils.response import success, error_response
from app.utils.rate_limit import limiter, LIMIT_SMS_SEND, LIMIT_SMS_SEND_DAILY, LIMIT_SMS_VERIFY

router = APIRouter(prefix="/api/sms", tags=["短信"])


# 简单的中国大陆手机号校验
_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


class SendCodeRequest(BaseModel):
    phone: str = Field(..., max_length=11, description="手机号")
    purpose: Literal["bind_phone", "worker_certification"] = "bind_phone"

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not v or not _PHONE_RE.match(v):
            raise ValueError("手机号格式不正确")
        return v


class VerifyCodeRequest(BaseModel):
    phone: str = Field(..., max_length=11, description="手机号")
    code: str = Field(..., min_length=4, max_length=8, description="验证码")
    purpose: Literal["bind_phone", "worker_certification"] = "bind_phone"

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not v or not _PHONE_RE.match(v):
            raise ValueError("手机号格式不正确")
        return v


@router.post("/send-code")
@limiter.limit(LIMIT_SMS_SEND)
@limiter.limit(LIMIT_SMS_SEND_DAILY)
def send_code(request: Request, req: SendCodeRequest):
    """发送短信验证码

    - 同一手机号 60 秒内不可重复发送（Redis 限流）
    - IP 维度限流：1/分钟 + 10/天（防短信轰炸）
    - 验证码缓存 5 分钟
    - 开发模式返回 code，生产模式不返回
    """
    if sms_service.is_rate_limited(req.phone):
        return error_response(
            message="发送过于频繁，请 60 秒后重试",
            status_code=429,
        )

    try:
        code = sms_service.send_verification_code(req.phone, purpose=req.purpose)
    except sms_service.SMSRateLimitError as exc:
        return error_response(message=str(exc), status_code=429)
    except sms_service.SMSServiceError:
        return error_response(message="短信服务暂不可用，请稍后重试", status_code=503)

    # 是否返回验证码由后端决定（mock / debug 模式会返回）
    data = {"sent": True}
    if code:
        data["code"] = code
    return success(data=data, message="验证码已发送")


@router.post("/verify-code")
@limiter.limit(LIMIT_SMS_VERIFY)
def verify_code(request: Request, req: VerifyCodeRequest):
    """校验短信验证码"""
    try:
        ok = sms_service.verify_code(req.phone, req.code, purpose=req.purpose)
    except sms_service.SMSServiceError:
        return error_response(message="短信服务暂不可用，请稍后重试", status_code=503)
    if not ok:
        return error_response(message="验证码错误或已过期", status_code=400)

    return success(data={"verified": True}, message="验证成功")

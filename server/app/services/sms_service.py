"""短信通知服务

支持阿里云 dysmsapi、腾讯云 SMS 与 mock（控制台打印）三种模式。
验证码使用 Redis 缓存 5 分钟；发送频率限制 60 秒/手机号。
"""

import hmac
import json
import secrets
import threading
import time
from typing import Dict, Optional, Tuple

from app.config import settings
from app.utils.logger import get_logger
from app.utils.redis_client import redis_client

logger = get_logger(__name__)

# Redis Key 前缀
_VERIFY_CODE_KEY = "sms:verify_code:{purpose}:{phone}"
_VERIFY_FAILURE_KEY = "sms:verify_failure:{purpose}:{phone}"
_RATE_LIMIT_KEY = "sms:rate_limit:{phone}"

# 验证码缓存与频率限制时长（秒）
_VERIFY_CODE_TTL = 300  # 5 分钟
_RATE_LIMIT_TTL = 60    # 60 秒

# Redis 不可用时，仅在非生产环境启用进程内兜底，保证本地联调可完成。
# 生产环境必须依赖共享存储，避免多进程验证码不一致和限流绕过。
_DEV_CODE_CACHE: Dict[str, Tuple[str, float]] = {}
_DEV_RATE_CACHE: Dict[str, float] = {}
_DEV_FAILURE_CACHE: Dict[str, int] = {}
_DEV_CACHE_LOCK = threading.Lock()


class SMSServiceError(RuntimeError):
    """短信服务不可用或发送失败。"""


class SMSRateLimitError(SMSServiceError):
    """手机号仍在发送冷却期。"""


# ============================================================
# 底层发送
# ============================================================

def send_sms(phone: str, template_id: str, params: Dict) -> Dict:
    """发送短信

    Args:
        phone: 手机号
        template_id: 短信模板 ID
        params: 模板参数

    Returns:
        {"success": True/False, "biz_id": "..."}
    """
    if not phone:
        return {"success": False, "biz_id": "", "error": "phone missing"}

    provider = (settings.SMS_PROVIDER or "mock").lower()

    # 本地 mock 不依赖第三方模板；真实通道必须显式配置模板 ID。
    if not template_id and provider != "mock":
        return {"success": False, "biz_id": "", "error": "template_id missing"}

    if provider == "mock":
        return _send_mock(phone, template_id, params)
    if provider == "aliyun":
        return _send_aliyun(phone, template_id, params)
    if provider == "tencent":
        return _send_tencent(phone, template_id, params)

    return {
        "success": False,
        "biz_id": "",
        "error": f"unsupported SMS_PROVIDER: {provider}",
    }


def _send_mock(phone: str, template_id: str, params: Dict) -> Dict:
    if settings.is_deployed:
        return {
            "success": False,
            "biz_id": "",
            "error": "mock SMS is disabled in production",
        }
    logger.info(
        "sms mock send",
        extra={
            "template_id": template_id,
        },
    )
    return {"success": True, "biz_id": "mock-biz-id"}


def _send_aliyun(phone: str, template_id: str, params: Dict) -> Dict:
    """阿里云 dysmsapi 发送"""
    try:
        from alibabacloud_dysmsapi20170525.client import Client as DysmsapiClient
        from alibabacloud_tea_openapi import models as open_api_models
        from alibabacloud_dysmsapi20170525 import models as dysmsapi_models
        from alibabacloud_tea_util import models as util_models
    except ImportError:
        logger.error("alibabacloud dysmsapi sdk not installed")
        return {
            "success": False,
            "biz_id": "",
            "error": "aliyun SMS SDK is not installed",
        }

    try:
        config = open_api_models.Config(
            access_key_id=settings.SMS_ACCESS_KEY,
            access_key_secret=settings.SMS_SECRET_KEY,
        )
        config.endpoint = "dysmsapi.aliyuncs.com"
        client = DysmsapiClient(config)

        send_req = dysmsapi_models.SendSmsRequest(
            phone_numbers=phone,
            sign_name=settings.SMS_SIGN_NAME,
            template_code=template_id,
            template_param=json.dumps(params, ensure_ascii=False),
        )
        resp = client.send_sms_with_options(send_req, util_models.RuntimeOptions())
        body = getattr(resp, "body", None)
        code = getattr(body, "code", "") if body else ""
        biz_id = getattr(body, "biz_id", "") if body else ""
        if code == "OK":
            return {"success": True, "biz_id": biz_id}
        msg = getattr(body, "message", "") if body else "unknown"
        logger.error("aliyun sms failed", extra={"code": code})
        return {"success": False, "biz_id": biz_id, "error": msg}
    except Exception:
        logger.exception("aliyun sms exception")
        return {"success": False, "biz_id": "", "error": "provider request failed"}


def _send_tencent(phone: str, template_id: str, params: Dict) -> Dict:
    """腾讯云 SMS 发送"""
    try:
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.sms.v20210111 import sms_client, models as sms_models
    except ImportError:
        logger.error("tencentcloud-sdk-python not installed")
        return {
            "success": False,
            "biz_id": "",
            "error": "tencent SMS SDK is not installed",
        }

    try:
        cred = credential.Credential(settings.SMS_ACCESS_KEY, settings.SMS_SECRET_KEY)
        http_profile = HttpProfile(endpoint="sms.tencentcloudapi.com")
        client_profile = ClientProfile(httpProfile=http_profile)
        region = settings.SMS_TENCENT_REGION or "ap-guangzhou"
        client = sms_client.SmsClient(cred, region, client_profile)

        req = sms_models.SendSmsRequest()
        req.SmsSdkAppId = settings.SMS_TENCENT_APP_ID
        req.SignName = settings.SMS_SIGN_NAME
        req.PhoneNumberSet = [f"+86{phone}"]
        req.TemplateId = template_id
        # 腾讯云模板参数顺序数组
        req.TemplateParamSet = [str(v) for v in params.values()]

        resp = client.SendSms(req)
        send_status_set = getattr(resp, "SendStatusSet", []) or []
        if send_status_set:
            status = send_status_set[0]
            if getattr(status, "Code", "") == "Ok":
                return {"success": True, "biz_id": getattr(status, "SerialNo", "")}
            return {
                "success": False,
                "biz_id": getattr(status, "SerialNo", ""),
                "error": getattr(status, "Message", "unknown"),
            }
        return {"success": False, "biz_id": "", "error": "empty response"}
    except Exception:
        logger.exception("tencent sms exception")
        return {"success": False, "biz_id": "", "error": "provider request failed"}


# ============================================================
# 业务模板方法
# ============================================================

def send_order_pending_reminder(phone: str, order_no: str, service_name: str) -> Dict:
    """订单待处理提醒：用户下单后未选师傅"""
    return send_sms(
        phone,
        settings.SMS_TEMPLATE_ORDER_PENDING,
        {"order_no": order_no, "service_name": service_name},
    )


def send_order_completed_notice(phone: str, order_no: str, service_name: str, amount) -> Dict:
    """服务完成通知：请用户支付"""
    return send_sms(
        phone,
        settings.SMS_TEMPLATE_ORDER_COMPLETED,
        {"order_no": order_no, "service_name": service_name, "amount": str(amount)},
    )


def send_order_paid_notice(phone: str, order_no: str, amount) -> Dict:
    """支付成功通知"""
    return send_sms(
        phone,
        settings.SMS_TEMPLATE_ORDER_PAID,
        {"order_no": order_no, "amount": str(amount)},
    )


def send_worker_withdraw_result(phone: str, amount, status: str) -> Dict:
    """提现结果通知：approved / rejected"""
    return send_sms(
        phone,
        settings.SMS_TEMPLATE_WITHDRAW,
        {"amount": str(amount), "status": status},
    )


# ============================================================
# 验证码
# ============================================================

def is_rate_limited(phone: str) -> bool:
    """是否在发送冷却期内（60s）"""
    if not phone:
        return False
    if redis_client.exists(_RATE_LIMIT_KEY.format(phone=phone)):
        return True
    if settings.is_deployed:
        return False
    now = time.monotonic()
    with _DEV_CACHE_LOCK:
        expires_at = _DEV_RATE_CACHE.get(phone, 0)
        if expires_at <= now:
            _DEV_RATE_CACHE.pop(phone, None)
            return False
        return True


def send_verification_code(
    phone: str,
    code: Optional[str] = None,
    *,
    purpose: str = "bind_phone",
) -> Optional[str]:
    """发送验证码

    - 生成 6 位数字验证码，缓存到 Redis 5 分钟
    - 频率限制：同一手机号 60 秒内不可重复发送（命中限流返回 None）
    - 开发模式（mock 或 APP_DEBUG）返回验证码，生产模式成功也返回 None

    调用方若需区分「限流」与「生产模式成功」，请先调用 ``is_rate_limited``。
    """
    if not phone:
        raise SMSServiceError("手机号不能为空")

    if not code:
        code = f"{secrets.randbelow(1_000_000):06d}"

    if purpose not in {"bind_phone", "worker_certification"}:
        raise SMSServiceError("验证码用途无效")
    cache_key = f"{purpose}:{phone}"
    code_key = _VERIFY_CODE_KEY.format(purpose=purpose, phone=phone)
    failure_key = _VERIFY_FAILURE_KEY.format(purpose=purpose, phone=phone)
    rate_key = _RATE_LIMIT_KEY.format(phone=phone)
    reserved = redis_client.reserve_verification_send(
        rate_key,
        code_key,
        failure_key,
        code,
        rate_ttl=_RATE_LIMIT_TTL,
        code_ttl=_VERIFY_CODE_TTL,
    )
    if reserved is False:
        logger.info("verify code rate limited", extra={"phone_tail": phone[-4:]})
        raise SMSRateLimitError("发送过于频繁，请 60 秒后重试")
    if reserved is None and settings.is_deployed:
        raise SMSServiceError("验证码存储不可用，请稍后重试")
    if reserved is None:
        now = time.monotonic()
        with _DEV_CACHE_LOCK:
            if _DEV_RATE_CACHE.get(phone, 0) > now:
                raise SMSRateLimitError("发送过于频繁，请 60 秒后重试")
            _DEV_CODE_CACHE[cache_key] = (code, now + _VERIFY_CODE_TTL)
            _DEV_FAILURE_CACHE.pop(cache_key, None)
            _DEV_RATE_CACHE[phone] = time.monotonic() + _RATE_LIMIT_TTL
        logger.warning("redis unavailable, using development-only memory cache")

    result = send_sms(
        phone,
        settings.SMS_TEMPLATE_VERIFY_CODE,
        {"code": code},
    )
    if not result.get("success"):
        redis_client.delete(code_key)
        redis_client.delete(rate_key)
        with _DEV_CACHE_LOCK:
            _DEV_CODE_CACHE.pop(cache_key, None)
            _DEV_FAILURE_CACHE.pop(cache_key, None)
            _DEV_RATE_CACHE.pop(phone, None)
        logger.error(
            "verification SMS delivery failed",
            extra={"provider": settings.SMS_PROVIDER},
        )
        raise SMSServiceError("短信发送失败，请稍后重试")

    # mock / debug 模式返回验证码便于联调
    if not settings.is_deployed and (
        settings.SMS_PROVIDER.lower() == "mock" or settings.APP_DEBUG
    ):
        return code
    return None


def verify_code(phone: str, code: str, *, purpose: str = "bind_phone") -> bool:
    """校验验证码

    匹配后立即删除，防止重复使用。
    """
    if not phone or not code:
        return False

    if purpose not in {"bind_phone", "worker_certification"}:
        return False
    code_key = _VERIFY_CODE_KEY.format(purpose=purpose, phone=phone)
    failure_key = _VERIFY_FAILURE_KEY.format(purpose=purpose, phone=phone)
    consumed = redis_client.consume_verification_code(
        code_key,
        failure_key,
        code,
        max_attempts=5,
        ttl_seconds=_VERIFY_CODE_TTL,
    )
    if consumed is not None:
        return consumed
    if settings.is_deployed:
        raise SMSServiceError("验证码存储不可用，请稍后重试")

    cache_key = f"{purpose}:{phone}"
    now = time.monotonic()
    with _DEV_CACHE_LOCK:
        cached_entry = _DEV_CODE_CACHE.get(cache_key)
        if not cached_entry or cached_entry[1] <= now:
            _DEV_CODE_CACHE.pop(cache_key, None)
            _DEV_FAILURE_CACHE.pop(cache_key, None)
            return False
        if hmac.compare_digest(cached_entry[0], code):
            _DEV_CODE_CACHE.pop(cache_key, None)
            _DEV_FAILURE_CACHE.pop(cache_key, None)
            return True
        attempts = _DEV_FAILURE_CACHE.get(cache_key, 0) + 1
        _DEV_FAILURE_CACHE[cache_key] = attempts
        if attempts >= 5:
            _DEV_CODE_CACHE.pop(cache_key, None)
        return False

"""无网络、无写入的部署依赖探测。"""

from __future__ import annotations

import importlib
import os

from app.config import settings


def _require_module(module_name: str, label: str, errors: list[str]) -> None:
    try:
        importlib.import_module(module_name)
    except Exception as exc:
        errors.append(f"缺少或无法导入 {label}（{module_name}）：{exc}")


def _validate_wechat_private_key(errors: list[str]) -> None:
    value = (settings.WX_MERCHANT_PRIVATE_KEY or "").strip()
    if not value:
        return
    pem = value.replace("\\n", "\n")
    if "-----BEGIN" not in pem:
        if not os.path.isabs(value):
            errors.append("WX_MERCHANT_PRIVATE_KEY 文件路径必须为绝对路径")
            return
        try:
            with open(value, "rb") as file:
                pem_bytes = file.read()
        except OSError as exc:
            errors.append(f"无法读取微信商户私钥文件：{exc}")
            return
    else:
        pem_bytes = pem.encode("utf-8")
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

        key = serialization.load_pem_private_key(pem_bytes, password=None)
        if not isinstance(key, RSAPrivateKey):
            errors.append("WX_MERCHANT_PRIVATE_KEY 必须是 RSA 私钥")
    except Exception as exc:
        errors.append(f"WX_MERCHANT_PRIVATE_KEY 无法解析：{exc}")


def deployment_dependency_errors() -> list[str]:
    """检查部署环境必需 SDK 与本地密钥格式，不发起外部请求。"""
    if not settings.is_deployed:
        return []

    errors: list[str] = []
    for module_name, label in (
        ("cryptography", "敏感字段加密 SDK"),
        ("slowapi", "API 限流 SDK"),
        ("redis", "Redis SDK"),
        ("wechatpayv3", "微信支付 SDK"),
    ):
        _require_module(module_name, label, errors)

    if settings.SMS_PROVIDER == "aliyun":
        _require_module("alibabacloud_dysmsapi20170525.client", "阿里云短信 SDK", errors)
    elif settings.SMS_PROVIDER == "tencent":
        _require_module("tencentcloud.sms.v20210111.sms_client", "腾讯云短信 SDK", errors)

    if settings.OSS_PROVIDER == "aliyun":
        _require_module("oss2", "阿里云 OSS SDK", errors)
    elif settings.OSS_PROVIDER == "tencent":
        _require_module("qcloud_cos", "腾讯云 COS SDK", errors)

    _validate_wechat_private_key(errors)
    return errors


def assert_deployment_dependencies() -> None:
    errors = deployment_dependency_errors()
    if errors:
        raise RuntimeError("部署运行依赖检查失败：\n  - " + "\n  - ".join(errors))

"""微信支付 API v3 服务。

安全边界：
- 只有通过微信平台签名校验并成功解密的通知才能推进支付/退款状态；
- mock 仅允许在 development 且显式开启时使用；
- 所有入账均在数据库事务内执行，并以商户单号、微信流水号双重幂等；
- 回调金额必须与服务端支付/退款单快照逐分一致。
"""

import hashlib
import hmac
import json
import logging
import random
import time
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.order import Order
from app.models.user import User, Worker
from app.models.wallet import PaymentOrder, RefundOrder, Transaction
from app.schemas.wxpay import WechatPayNotifyResult, WechatRefundNotifyResult
from app.services import worker_fund_service

logger = logging.getLogger(__name__)

_WECHATPAY_AVAILABLE = False
_WX_CLIENT = None

try:
    from wechatpayv3 import WeChatPay
    from wechatpayv3 import WeChatPayType

    _WECHATPAY_AVAILABLE = True
except ImportError:  # pragma: no cover - 由部署环境决定
    WeChatPay = None
    WeChatPayType = None


def _mock_enabled() -> bool:
    """支付 mock 只允许在本地开发环境显式开启。"""
    return settings.APP_ENV.lower() == "development" and settings.WX_PAY_MOCK_ENABLED


def _to_cents(value) -> int:
    """把数据库/API 金额规范为整数分，拒绝非数字和超过两位小数的歧义。"""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(status_code=400, detail="支付金额格式错误")
    if not amount.is_finite():
        raise HTTPException(status_code=400, detail="支付金额格式错误")
    rounded = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(rounded * 100)


def _read_merchant_private_key() -> str:
    value = (settings.WX_MERCHANT_PRIVATE_KEY or "").strip()
    if not value:
        raise RuntimeError("WX_MERCHANT_PRIVATE_KEY 未配置")

    if "-----BEGIN" not in value:
        key_path = Path(value)
        if not key_path.is_file():
            raise RuntimeError("WX_MERCHANT_PRIVATE_KEY 指向的文件不存在")
        value = key_path.read_text(encoding="utf-8").strip()
    else:
        value = value.replace("\\n", "\n")

    if "PRIVATE KEY-----" not in value:
        raise RuntimeError("WX_MERCHANT_PRIVATE_KEY 不是有效 PEM 私钥")
    return value


def _payment_configured() -> bool:
    return all(
        (
            settings.WX_APPID,
            settings.WX_MCH_ID,
            settings.WX_API_V3_KEY,
            settings.WX_MERCHANT_PRIVATE_KEY,
            settings.WX_MERCHANT_SERIAL_NO,
            settings.WX_PAY_NOTIFY_URL,
            settings.WX_REFUND_NOTIFY_URL,
        )
    )


def _get_wx_client():
    """获取真实微信支付客户端；真实模式配置/初始化失败时绝不降级 mock。"""
    global _WX_CLIENT

    if _mock_enabled():
        return None
    if not _WECHATPAY_AVAILABLE:
        raise HTTPException(status_code=503, detail="微信支付 SDK 未安装")
    if not _payment_configured():
        raise HTTPException(status_code=503, detail="微信支付商户配置不完整")
    if _WX_CLIENT is not None:
        return _WX_CLIENT

    try:
        _WX_CLIENT = WeChatPay(
            wechatpay_type=WeChatPayType.MINIPROG,
            mchid=settings.WX_MCH_ID,
            private_key=_read_merchant_private_key(),
            cert_serial_no=settings.WX_MERCHANT_SERIAL_NO,
            appid=settings.WX_APPID,
            apiv3_key=settings.WX_API_V3_KEY,
            notify_url=settings.WX_PAY_NOTIFY_URL,
            cert_dir=settings.WX_PLATFORM_CERT_DIR or None,
            timeout=settings.WX_PAY_TIMEOUT_SECONDS,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("微信支付客户端初始化失败")
        raise HTTPException(status_code=503, detail="微信支付服务初始化失败")
    return _WX_CLIENT


def _gen_nonce_str(length: int = 32) -> str:
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(random.SystemRandom().choice(chars) for _ in range(length))


def _gen_mock_sign(params: dict) -> str:
    sorted_keys = sorted(params.keys())
    raw = "&".join(f"{key}={params[key]}" for key in sorted_keys if params[key] is not None)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()


def _decode_sdk_response(result, operation: str) -> dict:
    """兼容 wechatpayv3 1.2.x 的 ``(status_code, body)`` 返回格式。"""
    if not isinstance(result, tuple) or len(result) != 2:
        raise HTTPException(status_code=502, detail=f"微信{operation}响应格式异常")
    status_code, body = result
    try:
        payload = json.loads(body) if isinstance(body, (str, bytes, bytearray)) else body
    except (TypeError, ValueError):
        payload = None
    if status_code not in range(200, 300) or not isinstance(payload, dict):
        logger.error("微信%s失败，HTTP=%s", operation, status_code)
        raise HTTPException(status_code=502, detail=f"微信{operation}失败")
    return payload


def _decode_query_response(result, operation: str) -> tuple[int, dict]:
    """解析查单响应；404 作为可对账的 NOT_FOUND 返回，其余异常失败关闭。"""
    if not isinstance(result, tuple) or len(result) != 2:
        raise HTTPException(status_code=502, detail=f"微信{operation}响应格式异常")
    status_code, body = result
    try:
        payload = json.loads(body) if isinstance(body, (str, bytes, bytearray)) and body else body
    except (TypeError, ValueError):
        payload = None
    if status_code == 404:
        return status_code, payload if isinstance(payload, dict) else {}
    if status_code not in range(200, 300) or not isinstance(payload, dict):
        logger.error("微信%s失败，HTTP=%s", operation, status_code)
        raise HTTPException(status_code=502, detail=f"微信{operation}失败")
    return status_code, payload


def _add_transaction(
    db: Session,
    owner_type: str,
    owner_id: int,
    type: str,
    amount: float,
    balance_after: float,
    method: Optional[str] = None,
    order_id: Optional[str] = None,
    description: Optional[str] = None,
    status: str = "success",
) -> Transaction:
    tx = Transaction(
        owner_type=owner_type,
        owner_id=owner_id,
        type=type,
        amount=amount,
        balance_after=balance_after,
        method=method,
        order_id=order_id,
        description=description,
        status=status,
    )
    db.add(tx)
    db.flush()
    return tx


def create_jsapi_order(db: Session, payment_order: PaymentOrder, openid: str) -> dict:
    """创建（或重新签发已有 prepay_id 的）小程序 JSAPI 调起参数。"""
    if payment_order.method != "wechat" or payment_order.status != "pending":
        raise HTTPException(status_code=409, detail="支付单状态不允许创建微信预支付")
    if not openid:
        raise HTTPException(status_code=400, detail="当前账号未绑定微信 openid")

    amount_total = _to_cents(payment_order.amount)
    if amount_total <= 0:
        raise HTTPException(status_code=400, detail="微信支付金额必须大于 0")

    appid = settings.WX_APPID or "mock_appid"
    prepay_id = payment_order.prepay_id
    client = _get_wx_client()

    if prepay_id and prepay_id.startswith("mock_prepay_") and not _mock_enabled():
        raise HTTPException(status_code=409, detail="Mock 预支付单不能用于真实支付")

    if not prepay_id:
        if client is None:
            prepay_id = "mock_prepay_" + _gen_nonce_str(20)
        else:
            try:
                payload = _decode_sdk_response(
                    client.pay(
                        description="自家人居家维修服务",
                        out_trade_no=payment_order.payment_no,
                        amount={"total": amount_total, "currency": "CNY"},
                        payer={"openid": openid},
                    ),
                    "统一下单",
                )
                prepay_id = payload.get("prepay_id")
            except HTTPException:
                raise
            except Exception:
                logger.exception("微信统一下单调用异常")
                raise HTTPException(status_code=502, detail="微信统一下单失败")
            if not prepay_id:
                raise HTTPException(status_code=502, detail="微信统一下单未返回 prepay_id")

        payment_order.prepay_id = prepay_id
        db.flush()

    timestamp = str(int(time.time()))
    nonce_str = _gen_nonce_str(32)
    package_val = f"prepay_id={prepay_id}"
    sign_params = {
        "appId": appid,
        "timeStamp": timestamp,
        "nonceStr": nonce_str,
        "package": package_val,
        "signType": "RSA",
    }

    if client is None:
        pay_sign = _gen_mock_sign(sign_params)
    else:
        try:
            pay_sign = client.sign([appid, timestamp, nonce_str, package_val])
        except Exception:
            logger.exception("微信 JSAPI 参数签名失败")
            raise HTTPException(status_code=502, detail="微信支付参数签名失败")

    return {**sign_params, "paySign": pay_sign}


def query_wechat_payment(payment_order: PaymentOrder) -> dict:
    """主动查询微信支付状态，不对本地账务做任何修改。"""
    if payment_order.method != "wechat":
        raise HTTPException(status_code=400, detail="仅支持查询微信支付单")
    if _mock_enabled():
        return {
            "trade_state": "NOTPAY",
            "out_trade_no": payment_order.payment_no,
            "transaction_id": "",
            "amount_total": _to_cents(payment_order.amount),
        }

    client = _get_wx_client()
    try:
        status_code, payload = _decode_query_response(
            client.query(out_trade_no=payment_order.payment_no),
            "支付查单",
        )
    except HTTPException:
        raise
    except Exception:
        logger.warning("微信支付查单异常", exc_info=True)
        raise HTTPException(status_code=502, detail="微信支付查单失败")

    if status_code == 404:
        return {
            "trade_state": "NOT_FOUND",
            "out_trade_no": payment_order.payment_no,
            "transaction_id": "",
            "amount_total": _to_cents(payment_order.amount),
        }
    if payload.get("out_trade_no") != payment_order.payment_no:
        raise HTTPException(status_code=409, detail="微信支付查单结果与本地支付单不匹配")
    if payload.get("appid") != settings.WX_APPID or payload.get("mchid") != settings.WX_MCH_ID:
        raise HTTPException(status_code=409, detail="微信支付查单商户身份不匹配")

    amount = payload.get("amount") if isinstance(payload.get("amount"), dict) else {}
    try:
        amount_total = int(amount.get("total"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=409, detail="微信支付查单金额缺失")
    if amount_total != _to_cents(payment_order.amount):
        raise HTTPException(status_code=409, detail="微信支付查单金额与本地支付单不一致")

    trade_state = str(payload.get("trade_state") or "")
    if trade_state not in {
        "SUCCESS", "REFUND", "NOTPAY", "CLOSED", "REVOKED", "USERPAYING", "PAYERROR"
    }:
        raise HTTPException(status_code=409, detail="微信支付查单返回未知状态")
    return {
        "trade_state": trade_state,
        "out_trade_no": payment_order.payment_no,
        "transaction_id": str(payload.get("transaction_id") or ""),
        "amount_total": amount_total,
    }


def close_wechat_payment(payment_order: PaymentOrder) -> bool:
    """关闭超时未支付微信单；仅 HTTP 2xx 才视为关闭成功。"""
    if payment_order.method != "wechat" or payment_order.status != "pending":
        raise HTTPException(status_code=409, detail="支付单状态不允许关单")
    if _mock_enabled():
        return True

    client = _get_wx_client()
    try:
        result = client.close(out_trade_no=payment_order.payment_no)
    except Exception:
        logger.warning("微信支付关单异常", exc_info=True)
        raise HTTPException(status_code=502, detail="微信支付关单失败")
    if not isinstance(result, tuple) or len(result) != 2:
        raise HTTPException(status_code=502, detail="微信支付关单响应格式异常")
    status_code, _ = result
    if status_code not in range(200, 300):
        # ORDERPAID 等冲突绝不能被当作已关闭，下一轮重新查单。
        raise HTTPException(status_code=409, detail="微信支付关单未确认成功")
    return True


def _canonical_callback_headers(headers: dict) -> dict:
    normalized = {str(key).lower(): value for key, value in headers.items()}
    return {
        "Wechatpay-Signature": normalized.get("wechatpay-signature", ""),
        "Wechatpay-Timestamp": normalized.get("wechatpay-timestamp", ""),
        "Wechatpay-Nonce": normalized.get("wechatpay-nonce", ""),
        "Wechatpay-Serial": normalized.get("wechatpay-serial", ""),
    }


def _validate_callback_headers(headers: dict) -> dict:
    canonical = _canonical_callback_headers(headers)
    if not all(canonical.values()):
        raise HTTPException(status_code=400, detail="微信回调签名头不完整")
    try:
        timestamp = int(canonical["Wechatpay-Timestamp"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="微信回调时间戳无效")
    if abs(int(time.time()) - timestamp) > 300:
        raise HTTPException(status_code=400, detail="微信回调已过期")
    return canonical


def _validate_mock_callback_secret(headers: dict) -> None:
    expected = settings.WX_PAY_MOCK_CALLBACK_SECRET
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Mock 支付回调密钥未配置，已拒绝回调",
        )
    normalized = {str(key).lower(): str(value) for key, value in headers.items()}
    received = normalized.get("x-mock-payment-secret", "")
    if not hmac.compare_digest(received, expected):
        raise HTTPException(status_code=401, detail="Mock 支付回调密钥无效")


def _decrypt_real_callback(headers: dict, raw_body: bytes) -> dict:
    canonical = _validate_callback_headers(headers)
    client = _get_wx_client()
    try:
        # callback() 在 SDK 内完成平台证书签名校验及 AES-GCM 解密。
        payload = client.callback(canonical, raw_body)
    except Exception:
        logger.warning("微信回调验签或解密失败", exc_info=True)
        raise HTTPException(status_code=400, detail="微信回调验签或解密失败")
    if not isinstance(payload, dict) or not isinstance(payload.get("resource"), dict):
        raise HTTPException(status_code=400, detail="微信回调验签或解密失败")
    return payload


def _parse_mock_payload(signature_headers: dict, raw_body: bytes) -> dict:
    if not _mock_enabled():
        raise HTTPException(status_code=400, detail="当前环境禁止 Mock 支付回调")
    _validate_mock_callback_secret(signature_headers)
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="无法解析 Mock 支付回调")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Mock 支付回调格式错误")
    resource = payload.get("resource", payload)
    if not isinstance(resource, dict):
        raise HTTPException(status_code=400, detail="Mock 支付回调格式错误")
    return {"event_type": payload.get("event_type"), "resource": resource}


def parse_payment_notification(signature_headers: dict, raw_body: bytes) -> WechatPayNotifyResult:
    """验签、解密并严格解析微信支付成功通知。"""
    payload = (
        _parse_mock_payload(signature_headers, raw_body)
        if _mock_enabled()
        else _decrypt_real_callback(signature_headers, raw_body)
    )
    resource = payload["resource"]
    amount = resource.get("amount") if isinstance(resource.get("amount"), dict) else {}
    amount_total = resource.get("amount_total") if _mock_enabled() else amount.get("total")
    trade_state = resource.get("trade_state")
    success_flag = resource.get("success")
    success = trade_state == "SUCCESS" if trade_state is not None else success_flag is True

    out_trade_no = str(resource.get("out_trade_no") or "")
    transaction_id = str(resource.get("transaction_id") or "")
    try:
        amount_total = int(amount_total)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="支付回调金额无效")
    if not out_trade_no or not transaction_id or amount_total <= 0:
        raise HTTPException(status_code=400, detail="支付回调必要字段缺失")
    if not success:
        raise HTTPException(status_code=400, detail="微信交易状态不是 SUCCESS")

    appid = resource.get("appid")
    mchid = resource.get("mchid")
    if not _mock_enabled():
        if appid != settings.WX_APPID or mchid != settings.WX_MCH_ID:
            raise HTTPException(status_code=400, detail="支付回调商户身份不匹配")

    return WechatPayNotifyResult(
        out_trade_no=out_trade_no,
        transaction_id=transaction_id,
        amount_total=amount_total,
        success=True,
        appid=appid,
        mchid=mchid,
    )


def handle_payment_success(
    db: Session,
    out_trade_no: str,
    transaction_id: str,
    amount_total: int,
    success: bool = True,
) -> None:
    """在单事务内幂等处理已验签的支付成功通知。"""
    if not success:
        raise HTTPException(status_code=400, detail="支付未成功")
    if not transaction_id:
        raise HTTPException(status_code=400, detail="微信支付流水号缺失")

    try:
        payment = (
            db.query(PaymentOrder)
            .filter(PaymentOrder.payment_no == out_trade_no)
            .with_for_update()
            .first()
        )
        if not payment:
            raise HTTPException(status_code=404, detail="支付订单不存在")
        if payment.method != "wechat":
            raise HTTPException(status_code=400, detail="支付渠道不匹配")
        if _to_cents(payment.amount) != int(amount_total):
            raise HTTPException(status_code=400, detail="支付回调金额与支付单不一致")

        reused = (
            db.query(PaymentOrder)
            .filter(
                PaymentOrder.transaction_id == transaction_id,
                PaymentOrder.id != payment.id,
            )
            .first()
        )
        if reused:
            raise HTTPException(status_code=409, detail="微信支付流水号已被其他支付单使用")

        if payment.status == "paid":
            if payment.transaction_id == transaction_id:
                db.rollback()
                return
            raise HTTPException(status_code=409, detail="支付单已由其他流水支付")
        if payment.status != "pending":
            raise HTTPException(status_code=409, detail="支付单当前状态不允许入账")

        payment.status = "paid"
        payment.transaction_id = transaction_id
        payment.paid_at = datetime.utcnow()

        amount = float(payment.amount)
        if payment.order_no is None:
            payer_model = User if payment.payer_type == "user" else Worker
            payer = (
                db.query(payer_model)
                .filter(payer_model.id == payment.payer_id)
                .with_for_update()
                .first()
            )
            if not payer:
                raise HTTPException(status_code=404, detail="付款方不存在")
            payer.balance = float(payer.balance or 0) + amount
            db.flush()
            _add_transaction(
                db,
                owner_type=payment.payer_type,
                owner_id=payment.payer_id,
                type="recharge",
                amount=amount,
                balance_after=float(payer.balance),
                method="wechat",
                description=f"微信充值 {payment.payment_no}",
            )
        else:
            # 延迟导入避免 payment_service -> wechat_pay_service 的循环依赖。
            from app.services.payment_service import settle_wechat_order_payment

            settle_wechat_order_payment(db, payment)

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="支付回调重复或流水号冲突")
    except Exception:
        db.rollback()
        logger.exception("处理微信支付回调失败")
        raise HTTPException(status_code=500, detail="处理支付回调失败")


def create_wechat_refund(
    db: Session,
    refund_order: RefundOrder,
    payment: PaymentOrder,
) -> dict:
    """向微信提交原路退款；退款结果最终以已验签通知为准。"""
    if refund_order.method != "wechat" or refund_order.status != "pending":
        raise HTTPException(status_code=409, detail="退款单状态或渠道不允许提交微信退款")
    if payment.status not in ("paid", "partially_refunded"):
        raise HTTPException(status_code=409, detail="原支付单状态不允许退款")

    refund_cents = _to_cents(refund_order.amount)
    total_cents = _to_cents(payment.amount)
    if refund_cents <= 0 or refund_cents > total_cents:
        raise HTTPException(status_code=400, detail="退款金额无效")

    refund_order.attempt_count = int(refund_order.attempt_count or 0) + 1
    refund_order.last_attempt_at = datetime.utcnow()
    refund_order.last_error = None
    db.flush()

    try:
        client = _get_wx_client()
    except HTTPException:
        refund_order.last_error = "微信退款服务配置或初始化不可用"
        db.flush()
        raise
    if client is None:
        refund_id = "mock_refund_" + _gen_nonce_str(20)
        refund_order.refund_id = refund_id
        db.flush()
        return {"refund_no": refund_order.refund_no, "refund_id": refund_id, "status": "PROCESSING"}

    try:
        payload = _decode_sdk_response(
            client.refund(
                out_refund_no=refund_order.refund_no,
                transaction_id=payment.transaction_id,
                out_trade_no=None if payment.transaction_id else payment.payment_no,
                amount={"refund": refund_cents, "total": total_cents, "currency": "CNY"},
                reason=(refund_order.reason or "订单退款")[:80],
                notify_url=settings.WX_REFUND_NOTIFY_URL,
            ),
            "退款申请",
        )
    except HTTPException:
        refund_order.last_error = "微信退款申请被拒绝或响应异常"
        db.flush()
        raise
    except Exception:
        logger.exception("微信退款申请调用异常")
        refund_order.last_error = "微信退款申请网络或 SDK 异常"
        db.flush()
        raise HTTPException(status_code=502, detail="微信退款申请失败")

    refund_order.refund_id = payload.get("refund_id") or refund_order.refund_id
    db.flush()
    return {
        "refund_no": refund_order.refund_no,
        "refund_id": refund_order.refund_id,
        "status": payload.get("status", "PROCESSING"),
    }


def query_wechat_refund(refund_order: RefundOrder) -> dict:
    """主动查询微信退款状态，不直接修改本地退款或余额。"""
    if refund_order.method != "wechat":
        raise HTTPException(status_code=400, detail="仅支持查询微信退款单")
    if _mock_enabled():
        return {
            "status": "PROCESSING",
            "out_refund_no": refund_order.refund_no,
            "out_trade_no": refund_order.payment_no,
            "refund_id": refund_order.refund_id or "",
            "refund_amount": _to_cents(refund_order.amount),
            "total_amount": _to_cents(refund_order.total_amount),
        }

    client = _get_wx_client()
    try:
        status_code, payload = _decode_query_response(
            client.query_refund(refund_order.refund_no),
            "退款查单",
        )
    except HTTPException:
        raise
    except Exception:
        logger.warning("微信退款查单异常", exc_info=True)
        raise HTTPException(status_code=502, detail="微信退款查单失败")

    if status_code == 404:
        return {
            "status": "NOT_FOUND",
            "out_refund_no": refund_order.refund_no,
            "out_trade_no": refund_order.payment_no,
            "refund_id": "",
            "refund_amount": _to_cents(refund_order.amount),
            "total_amount": _to_cents(refund_order.total_amount),
        }
    if payload.get("out_refund_no") != refund_order.refund_no:
        raise HTTPException(status_code=409, detail="微信退款查单结果与本地退款单不匹配")
    if payload.get("out_trade_no") != refund_order.payment_no:
        raise HTTPException(status_code=409, detail="微信退款查单原支付单不匹配")

    amount = payload.get("amount") if isinstance(payload.get("amount"), dict) else {}
    try:
        refund_amount = int(amount.get("refund"))
        total_amount = int(amount.get("total"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=409, detail="微信退款查单金额缺失")
    if refund_amount != _to_cents(refund_order.amount):
        raise HTTPException(status_code=409, detail="微信退款查单金额与本地退款单不一致")
    if total_amount != _to_cents(refund_order.total_amount):
        raise HTTPException(status_code=409, detail="微信退款查单原支付金额不一致")

    refund_status = str(payload.get("status") or "")
    if refund_status not in {"SUCCESS", "CLOSED", "PROCESSING", "ABNORMAL"}:
        raise HTTPException(status_code=409, detail="微信退款查单返回未知状态")
    return {
        "status": refund_status,
        "out_refund_no": refund_order.refund_no,
        "out_trade_no": refund_order.payment_no,
        "refund_id": str(payload.get("refund_id") or ""),
        "refund_amount": refund_amount,
        "total_amount": total_amount,
    }


def parse_refund_notification(signature_headers: dict, raw_body: bytes) -> WechatRefundNotifyResult:
    """验签、解密并严格解析微信退款成功通知。"""
    payload = (
        _parse_mock_payload(signature_headers, raw_body)
        if _mock_enabled()
        else _decrypt_real_callback(signature_headers, raw_body)
    )
    resource = payload["resource"]
    amount = resource.get("amount") if isinstance(resource.get("amount"), dict) else {}
    refund_amount = resource.get("refund_amount") if _mock_enabled() else amount.get("refund")
    total_amount = resource.get("total_amount") if _mock_enabled() else amount.get("total")
    refund_status = resource.get("refund_status")
    success_flag = resource.get("success")
    success = refund_status == "SUCCESS" if refund_status is not None else success_flag is True

    try:
        refund_amount = int(refund_amount)
        total_amount = int(total_amount)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="退款回调金额无效")

    result = WechatRefundNotifyResult(
        out_refund_no=str(resource.get("out_refund_no") or ""),
        out_trade_no=str(resource.get("out_trade_no") or ""),
        refund_id=str(resource.get("refund_id") or ""),
        refund_amount=refund_amount,
        total_amount=total_amount,
        success=success,
    )
    if (
        not result.out_refund_no
        or not result.out_trade_no
        or not result.refund_id
        or result.refund_amount <= 0
        or result.total_amount <= 0
        or not result.success
    ):
        raise HTTPException(status_code=400, detail="退款回调必要字段缺失或状态非 SUCCESS")
    return result


def handle_refund_success(
    db: Session,
    out_refund_no: str,
    out_trade_no: str,
    refund_id: str,
    refund_amount: int,
    total_amount: int,
) -> None:
    """幂等确认微信原路退款，并同步平台内师傅应收账。"""
    try:
        refund = (
            db.query(RefundOrder)
            .filter(RefundOrder.refund_no == out_refund_no)
            .with_for_update()
            .first()
        )
        if not refund:
            raise HTTPException(status_code=404, detail="退款单不存在")
        if refund.method != "wechat" or refund.payment_no != out_trade_no:
            raise HTTPException(status_code=400, detail="退款回调与原支付单不匹配")
        if _to_cents(refund.amount) != int(refund_amount):
            raise HTTPException(status_code=400, detail="退款回调金额与退款单不一致")
        if _to_cents(refund.total_amount) != int(total_amount):
            raise HTTPException(status_code=400, detail="退款回调原支付金额不一致")

        reused = (
            db.query(RefundOrder)
            .filter(RefundOrder.refund_id == refund_id, RefundOrder.id != refund.id)
            .first()
        )
        if reused:
            raise HTTPException(status_code=409, detail="微信退款流水号已被使用")
        if refund.status == "success":
            if refund.refund_id == refund_id:
                db.rollback()
                return
            raise HTTPException(status_code=409, detail="退款单已由其他流水完成")
        if refund.status != "pending":
            raise HTTPException(status_code=409, detail="退款单当前状态不允许确认")

        payment = (
            db.query(PaymentOrder)
            .filter(PaymentOrder.payment_no == refund.payment_no)
            .with_for_update()
            .first()
        )
        order = (
            db.query(Order)
            .filter(Order.order_no == refund.order_no)
            .with_for_update()
            .first()
        )
        if not payment or not order:
            raise HTTPException(status_code=404, detail="退款关联的支付单或订单不存在")

        refund.status = "success"
        refund.refund_id = refund_id
        refund.refunded_at = datetime.utcnow()

        amount = float(refund.amount)
        user = (
            db.query(User).filter(User.id == order.user_id).with_for_update().first()
        )
        if user:
            # 微信已原路退回，不增加站内余额，仅留不可变业务流水。
            _add_transaction(
                db,
                owner_type="user",
                owner_id=user.id,
                type="refund",
                amount=amount,
                balance_after=float(user.balance or 0),
                method="wechat",
                order_id=order.order_no,
                description=f"微信原路退款 {refund.refund_no}",
            )

        if order.worker_id:
            worker = (
                db.query(Worker).filter(Worker.id == order.worker_id).with_for_update().first()
            )
            if worker:
                available_cut = worker_fund_service.record_refund_reversal(
                    db,
                    worker,
                    refund_no=refund.refund_no,
                    order_no=order.order_no,
                    amount=amount,
                    payment_no=refund.payment_no,
                )
                available_cut_value = float(available_cut)
                if available_cut_value > 0:
                    # 仅扣减已结算部分；回调发生时外部退款已成功，不能因余额不足
                    # 拒绝入账，负余额代表待追偿。
                    worker.balance = float(worker.balance or 0) - available_cut_value
                    db.flush()
                    _add_transaction(
                        db,
                        owner_type="worker",
                        owner_id=worker.id,
                        type="expense",
                        amount=available_cut_value,
                        balance_after=float(worker.balance),
                        method="wechat_refund",
                        order_id=order.order_no,
                        description=f"订单退款扣减 {refund.refund_no}",
                    )

        successful_for_payment = (
            db.query(RefundOrder)
            .filter(
                RefundOrder.payment_no == payment.payment_no,
                RefundOrder.status == "success",
            )
            .all()
        )
        refunded_payment_cents = sum(_to_cents(item.amount) for item in successful_for_payment)
        payment.status = "refunded" if refunded_payment_cents >= _to_cents(payment.amount) else "partially_refunded"

        all_payments = (
            db.query(PaymentOrder)
            .filter(
                PaymentOrder.order_no == order.order_no,
                PaymentOrder.status.in_(("paid", "partially_refunded", "refunded")),
            )
            .all()
        )
        all_refunds = (
            db.query(RefundOrder)
            .filter(RefundOrder.order_no == order.order_no, RefundOrder.status == "success")
            .all()
        )
        if all_payments and sum(_to_cents(p.amount) for p in all_payments) <= sum(
            _to_cents(item.amount) for item in all_refunds
        ):
            order.status = "refunded"

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="退款回调重复或流水号冲突")
    except Exception:
        db.rollback()
        logger.exception("处理微信退款回调失败")
        raise HTTPException(status_code=500, detail="处理退款回调失败")


def reconcile_pending_wechat_payments(
    db: Session,
    now: Optional[datetime] = None,
    limit: Optional[int] = None,
) -> dict:
    """对账超时微信支付，并仅在微信明确未支付/关单后释放钱包预留。"""
    now = now or datetime.utcnow()
    batch_size = min(max(int(limit or settings.WX_RECONCILE_BATCH_SIZE), 1), 1000)
    deadline = now - timedelta(minutes=settings.WX_PAYMENT_PENDING_TIMEOUT_MINUTES)
    candidate_ids = [
        row[0]
        for row in (
            db.query(PaymentOrder.id)
            .filter(
                PaymentOrder.method == "wechat",
                PaymentOrder.status == "pending",
                PaymentOrder.created_at <= deadline,
            )
            .order_by(PaymentOrder.id.asc())
            .limit(batch_size)
            .all()
        )
    ]
    db.rollback()

    stats = {"checked": 0, "settled": 0, "released": 0, "deferred": 0, "errors": 0}
    terminal_unpaid = {"NOT_FOUND", "CLOSED", "REVOKED", "PAYERROR"}
    for payment_id in candidate_ids:
        payment = db.query(PaymentOrder).filter(PaymentOrder.id == payment_id).first()
        if not payment or payment.status != "pending":
            db.rollback()
            continue
        stats["checked"] += 1
        try:
            result = query_wechat_payment(payment)
        except HTTPException:
            db.rollback()
            stats["errors"] += 1
            continue
        db.rollback()

        state = result["trade_state"]
        try:
            if state == "SUCCESS":
                if not result["transaction_id"]:
                    raise HTTPException(status_code=409, detail="微信成功订单缺少交易流水号")
                handle_payment_success(
                    db,
                    out_trade_no=result["out_trade_no"],
                    transaction_id=result["transaction_id"],
                    amount_total=result["amount_total"],
                    success=True,
                )
                stats["settled"] += 1
            elif state == "USERPAYING":
                # 用户支付中绝不能关单或释放，留待下一轮查询。
                stats["deferred"] += 1
            elif state == "NOTPAY":
                latest = db.query(PaymentOrder).filter(PaymentOrder.id == payment_id).first()
                if not latest or latest.status != "pending":
                    db.rollback()
                    continue
                close_wechat_payment(latest)
                db.rollback()
                from app.services.payment_service import release_expired_wechat_payment

                released = release_expired_wechat_payment(db, payment_id)
                stats["released"] += int(bool(released["released"]))
            elif state in terminal_unpaid:
                from app.services.payment_service import release_expired_wechat_payment

                released = release_expired_wechat_payment(db, payment_id)
                stats["released"] += int(bool(released["released"]))
            else:
                # REFUND 等异常态不自动更改本地余额，交由人工对账。
                stats["deferred"] += 1
        except HTTPException:
            db.rollback()
            stats["errors"] += 1
        except Exception:
            db.rollback()
            logger.exception("微信支付对账处理异常 payment_id=%s", payment_id)
            stats["errors"] += 1
    return stats


def _update_pending_refund_state(
    db: Session,
    refund_id: int,
    *,
    status: Optional[str] = None,
    last_error: Optional[str] = None,
) -> bool:
    try:
        refund = (
            db.query(RefundOrder)
            .filter(RefundOrder.id == refund_id)
            .with_for_update()
            .first()
        )
        if not refund or refund.status != "pending":
            db.rollback()
            return False
        if status is not None:
            refund.status = status
        refund.last_error = last_error
        if status == "failed":
            # 退款确认失败：解除在途冻结，收入回到可提现余额。
            order = (
                db.query(Order).filter(Order.order_no == refund.order_no).first()
            )
            if order and order.worker_id:
                worker = (
                    db.query(Worker)
                    .filter(Worker.id == order.worker_id)
                    .with_for_update()
                    .first()
                )
                if worker:
                    worker_fund_service.release_refund_freeze(
                        db, worker, refund_no=refund.refund_no
                    )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def reconcile_pending_wechat_refunds(
    db: Session,
    now: Optional[datetime] = None,
    limit: Optional[int] = None,
) -> dict:
    """对账待处理微信退款；查无记录时按同一 refund_no 有界重试。"""
    now = now or datetime.utcnow()
    batch_size = min(max(int(limit or settings.WX_RECONCILE_BATCH_SIZE), 1), 1000)
    retry_before = now - timedelta(minutes=settings.WX_REFUND_RETRY_INTERVAL_MINUTES)
    candidate_ids = [
        row[0]
        for row in (
            db.query(RefundOrder.id)
            .filter(
                RefundOrder.method == "wechat",
                RefundOrder.status == "pending",
                (
                    (RefundOrder.last_attempt_at.is_(None))
                    | (RefundOrder.last_attempt_at <= retry_before)
                ),
            )
            .order_by(RefundOrder.id.asc())
            .limit(batch_size)
            .all()
        )
    ]
    db.rollback()

    stats = {"checked": 0, "settled": 0, "retried": 0, "deferred": 0, "failed": 0, "errors": 0}
    for refund_pk in candidate_ids:
        refund = db.query(RefundOrder).filter(RefundOrder.id == refund_pk).first()
        if not refund or refund.status != "pending":
            db.rollback()
            continue
        stats["checked"] += 1
        try:
            result = query_wechat_refund(refund)
        except HTTPException:
            # 网络、验签或未知响应均不改变退款状态，也不重复提交。
            db.rollback()
            stats["errors"] += 1
            continue
        db.rollback()

        state = result["status"]
        try:
            if state == "SUCCESS":
                if not result["refund_id"]:
                    raise HTTPException(status_code=409, detail="微信成功退款缺少退款流水号")
                handle_refund_success(
                    db,
                    out_refund_no=result["out_refund_no"],
                    out_trade_no=result["out_trade_no"],
                    refund_id=result["refund_id"],
                    refund_amount=result["refund_amount"],
                    total_amount=result["total_amount"],
                )
                stats["settled"] += 1
            elif state == "CLOSED":
                if _update_pending_refund_state(
                    db,
                    refund_pk,
                    status="failed",
                    last_error="微信退款已关闭，可重新发起退款",
                ):
                    stats["failed"] += 1
            elif state == "ABNORMAL":
                _update_pending_refund_state(
                    db,
                    refund_pk,
                    last_error="微信退款状态异常，需人工处理",
                )
                stats["deferred"] += 1
            elif state == "PROCESSING":
                stats["deferred"] += 1
            elif state == "NOT_FOUND":
                refund = (
                    db.query(RefundOrder)
                    .filter(RefundOrder.id == refund_pk)
                    .with_for_update()
                    .first()
                )
                if not refund or refund.status != "pending":
                    db.rollback()
                    continue
                if int(refund.attempt_count or 0) >= settings.WX_REFUND_MAX_RETRIES:
                    refund.last_error = "微信查无退款且已达自动重试上限，需人工处理"
                    db.commit()
                    stats["deferred"] += 1
                    continue
                payment = (
                    db.query(PaymentOrder)
                    .filter(PaymentOrder.payment_no == refund.payment_no)
                    .with_for_update()
                    .first()
                )
                if not payment:
                    refund.last_error = "原支付单不存在，拒绝自动重试"
                    db.commit()
                    stats["errors"] += 1
                    continue
                try:
                    create_wechat_refund(db, refund, payment)
                    db.commit()
                    stats["retried"] += 1
                except HTTPException:
                    # 保存 attempt_count/last_error；同一 refund_no 可安全再次查单。
                    db.commit()
                    stats["errors"] += 1
            else:
                stats["deferred"] += 1
        except HTTPException:
            db.rollback()
            stats["errors"] += 1
        except Exception:
            db.rollback()
            logger.exception("微信退款对账处理异常 refund_id=%s", refund_pk)
            stats["errors"] += 1
    return stats


def create_transfer_to_worker(db: Session, withdraw_tx: Transaction, worker: Worker) -> dict:
    """开发环境模拟转账；真实到账确认未完成前，其他环境一律失败关闭。"""
    if not _mock_enabled():
        raise HTTPException(
            status_code=503,
            detail="真实商家转账到账确认尚未启用，已拒绝提交",
        )

    transfer_id = "mock_transfer_" + _gen_nonce_str(16)
    withdraw_tx.status = "success"
    if worker is None and withdraw_tx.owner_type == "worker":
        worker = db.query(Worker).filter(Worker.id == withdraw_tx.owner_id).first()
    if worker is not None:
        worker_fund_service.record_withdraw_success(db, worker, withdraw_tx)
    db.commit()
    db.refresh(withdraw_tx)
    return {"success": True, "transfer_id": transfer_id, "mock": True}

"""消息推送业务逻辑"""

import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models.message import Message
from app.models.user import User, Worker
from app.models.order import Order, Bidding
from app.models.wallet import Transaction
from app.services import sms_service
from app.utils.logger import get_logger
from app.utils.redis_client import redis_client


logger = get_logger(__name__)
_WX_ACCESS_TOKEN_KEY = "wechat:access_token"


def send_inbox_message(
    db: Session,
    owner_type: str,
    owner_id: int,
    msg_type: str,
    title: str,
    content: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Message:
    """发送站内消息"""
    message = Message(
        owner_type=owner_type,
        owner_id=owner_id,
        type=msg_type,
        title=title,
        content=content,
        payload=json.dumps(payload, ensure_ascii=False) if payload else None,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_messages(
    db: Session,
    owner_type: str,
    owner_id: int,
    msg_type: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> Dict[str, Any]:
    """获取消息列表（分页）"""
    q = db.query(Message).filter(
        Message.owner_type == owner_type,
        Message.owner_id == owner_id,
    )
    if msg_type:
        q = q.filter(Message.type == msg_type)

    total = q.count()
    offset = (page - 1) * size
    messages = (
        q.order_by(Message.created_at.desc())
        .offset(offset)
        .limit(size)
        .all()
    )

    for msg in messages:
        if msg.payload:
            try:
                msg.payload = json.loads(msg.payload)
            except (json.JSONDecodeError, TypeError):
                msg.payload = None

    has_more = (offset + size) < total
    unread_count = get_unread_count(db, owner_type, owner_id)

    return {
        "list": messages,
        "total": total,
        "unread_count": unread_count,
        "page": page,
        "has_more": has_more,
    }


def get_unread_count(db: Session, owner_type: str, owner_id: int) -> int:
    """获取未读消息数量"""
    return (
        db.query(Message)
        .filter(
            Message.owner_type == owner_type,
            Message.owner_id == owner_id,
            Message.is_read == False,
        )
        .count()
    )


def mark_read(db: Session, owner_type: str, owner_id: int, msg_id: int) -> Message:
    """标记单条消息为已读"""
    message = (
        db.query(Message)
        .filter(
            Message.id == msg_id,
            Message.owner_type == owner_type,
            Message.owner_id == owner_id,
        )
        .first()
    )
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")
    if not message.is_read:
        message.is_read = True
        message.read_at = datetime.utcnow()
        db.commit()
        db.refresh(message)
    return message


def mark_all_read(db: Session, owner_type: str, owner_id: int) -> int:
    """标记所有消息为已读，返回更新的条数"""
    messages = (
        db.query(Message)
        .filter(
            Message.owner_type == owner_type,
            Message.owner_id == owner_id,
            Message.is_read == False,
        )
        .all()
    )
    count = 0
    now = datetime.utcnow()
    for msg in messages:
        msg.is_read = True
        msg.read_at = now
        count += 1
    if count > 0:
        db.commit()
    return count


def delete_message(db: Session, owner_type: str, owner_id: int, msg_id: int) -> None:
    """删除单条消息"""
    message = (
        db.query(Message)
        .filter(
            Message.id == msg_id,
            Message.owner_type == owner_type,
            Message.owner_id == owner_id,
        )
        .first()
    )
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")
    db.delete(message)
    db.commit()


async def _get_wx_access_token() -> Optional[str]:
    """获取并缓存微信 access_token。"""
    if not settings.WX_APPID or not settings.WX_SECRET:
        return None
    cached = redis_client.get_str(_WX_ACCESS_TOKEN_KEY)
    if cached:
        return cached
    try:
        import httpx
        url = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": settings.WX_APPID,
            "secret": settings.WX_SECRET,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            token = data.get("access_token")
            if not token:
                logger.error("wechat access token response missing token")
                return None
            ttl = max(int(data.get("expires_in", 7200)) - 300, 60)
            redis_client.set(_WX_ACCESS_TOKEN_KEY, token, ex=ttl)
            return token
    except Exception:
        logger.exception("failed to get wechat access token")
        return None


async def send_wx_subscribe(
    openid: str,
    template_id: str,
    data: Dict[str, Any],
    page_path: Optional[str] = None,
) -> Dict[str, Any]:
    """发送微信订阅消息；真实配置缺失或调用失败时明确返回失败。"""
    if not openid or not template_id:
        return {"success": False, "error": "openid or template_id missing"}
    if not settings.WX_APPID or not settings.WX_SECRET:
        if settings.is_deployed:
            return {"success": False, "error": "wechat messaging is not configured"}
        logger.info("wechat subscribe mock send", extra={"openid": openid, "template_id": template_id})
        return {"success": True, "mock": True}

    access_token = await _get_wx_access_token()
    if not access_token:
        return {"success": False, "error": "无法获取 access_token"}

    try:
        import httpx
        url = f"https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={access_token}"
        payload = {
            "touser": openid,
            "template_id": template_id,
            "data": data,
        }
        if page_path:
            payload["page"] = page_path

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            if result.get("errcode") == 0:
                return {"success": True}
            return {"success": False, "error": result.get("errmsg", "unknown")}
    except Exception as e:
        logger.exception("wechat subscribe send failed")
        return {"success": False, "error": str(e)}


async def notify_order_bidding_new(db: Session, order: Order, bidding: Bidding) -> None:
    """用户收到「师傅竞价」站内 + 微信通知"""
    title = "有师傅新报价"
    content = f"您的订单「{order.service_name}」收到新的师傅报价，报价 ¥{bidding.price} 元"
    payload = {"order_id": order.id, "order_no": order.order_no, "worker_id": bidding.worker_id, "price": bidding.price}

    send_inbox_message(db, "user", order.user_id, "order", title, content, payload)

    user = db.query(User).filter(User.id == order.user_id).first()
    if user and user.openid:
        await send_wx_subscribe(
            openid=user.openid,
            template_id=settings.WX_TEMPLATE_ORDER_BIDDING,
            data={
                "thing1": {"value": order.service_name},
                "amount2": {"value": f"¥{bidding.price}"},
                "thing3": {"value": "请尽快查看并选择师傅"},
            },
            page_path=f"pages/order/detail/detail?id={order.id}",
        )


async def notify_order_accepted(db: Session, order: Order) -> None:
    """师傅「订单被选中」通知"""
    if not order.worker_id:
        return
    worker = db.query(Worker).filter(Worker.id == order.worker_id).first()
    if not worker:
        return

    amount = float(order.final_price or 0)
    title = "您的订单被选中"
    content = f"恭喜您！订单「{order.service_name}」被用户选中，最终价 ¥{order.final_price} 元，请按时服务"
    payload = {"order_id": order.id, "order_no": order.order_no, "final_price": amount}

    send_inbox_message(db, "worker", worker.id, "order", title, content, payload)

    if worker.openid:
        await send_wx_subscribe(
            openid=worker.openid,
            template_id=settings.WX_TEMPLATE_ORDER_ACCEPTED,
            data={
                "thing1": {"value": order.service_name},
                "amount2": {"value": f"¥{order.final_price}"},
                "thing3": {"value": "请准时上门"},
            },
            page_path=f"pages/worker/order-detail/order-detail?id={order.id}",
        )


async def notify_service_finished(db: Session, order: Order) -> None:
    """用户「待支付」通知"""
    amount = float(order.final_price or 0)
    title = "服务已完成，待支付"
    content = f"您的订单「{order.service_name}」服务已完成，需支付 ¥{order.final_price} 元"
    payload = {"order_id": order.id, "order_no": order.order_no, "final_price": amount}

    send_inbox_message(db, "user", order.user_id, "order", title, content, payload)

    user = db.query(User).filter(User.id == order.user_id).first()
    if user and user.openid:
        await send_wx_subscribe(
            openid=user.openid,
            template_id=settings.WX_TEMPLATE_SERVICE_FINISHED,
            data={
                "thing1": {"value": order.service_name},
                "amount2": {"value": f"¥{order.final_price}"},
                "thing3": {"value": "点击前往支付"},
            },
            page_path=f"pages/order/detail/detail?id={order.id}",
        )

    # 短信通知：服务已完成，请支付
    if user and getattr(user, "phone", None):
        try:
            sms_service.send_order_completed_notice(
                user.phone, order.order_no, order.service_name, order.final_price
            )
        except Exception:
            pass


async def notify_payment_success(db: Session, order: Order) -> None:
    """双方「支付成功」通知"""
    amount = float(order.final_price or 0)
    title_user = "支付成功"
    content_user = f"订单「{order.service_name}」已支付 ¥{order.final_price} 元，感谢您的使用"
    payload_user = {"order_id": order.id, "order_no": order.order_no, "amount": amount}
    send_inbox_message(db, "user", order.user_id, "order", title_user, content_user, payload_user)

    user = db.query(User).filter(User.id == order.user_id).first()
    if user and user.openid:
        await send_wx_subscribe(
            openid=user.openid,
            template_id=settings.WX_TEMPLATE_PAYMENT_SUCCESS_USER,
            data={
                "thing1": {"value": order.service_name},
                "amount2": {"value": f"¥{order.final_price}"},
                "thing3": {"value": "可查看服务详情"},
            },
            page_path=f"pages/order/detail/detail?id={order.id}",
        )

    if order.worker_id:
        title_worker = "订单已收款"
        content_worker = f"订单「{order.service_name}」已收款 ¥{order.final_price} 元"
        payload_worker = {"order_id": order.id, "order_no": order.order_no, "amount": amount}
        send_inbox_message(db, "worker", order.worker_id, "order", title_worker, content_worker, payload_worker)

        worker = db.query(Worker).filter(Worker.id == order.worker_id).first()
        if worker and worker.openid:
            await send_wx_subscribe(
                openid=worker.openid,
                template_id=settings.WX_TEMPLATE_PAYMENT_SUCCESS_WORKER,
                data={
                    "thing1": {"value": order.service_name},
                    "amount2": {"value": f"¥{order.final_price}"},
                    "thing3": {"value": "已到账"},
                },
                page_path=f"pages/worker/order-detail/order-detail?id={order.id}",
            )

        # 短信通知师傅：订单已收款
        if worker and getattr(worker, "phone", None):
            try:
                sms_service.send_order_paid_notice(
                    worker.phone, order.order_no, order.final_price
                )
            except Exception:
                pass


async def notify_withdraw_success(db: Session, withdraw_tx: Transaction) -> None:
    """师傅「提现到账」通知"""
    if withdraw_tx.owner_type != "worker":
        return

    title = "提现到账"
    content = f"您申请的 ¥{withdraw_tx.amount} 元提现已到账"
    payload = {"tx_id": withdraw_tx.id, "amount": float(withdraw_tx.amount)}

    send_inbox_message(db, "worker", withdraw_tx.owner_id, "system", title, content, payload)

    worker = db.query(Worker).filter(Worker.id == withdraw_tx.owner_id).first()
    if worker and worker.openid:
        await send_wx_subscribe(
            openid=worker.openid,
            template_id=settings.WX_TEMPLATE_WITHDRAW_SUCCESS,
            data={
                "amount1": {"value": f"¥{withdraw_tx.amount}"},
                "thing2": {"value": "已到账"},
            },
            page_path="pages/worker/wallet/wallet",
        )

    # 短信通知师傅：提现已到账
    if worker and getattr(worker, "phone", None):
        try:
            sms_service.send_worker_withdraw_result(
                worker.phone, withdraw_tx.amount, "approved"
            )
        except Exception:
            pass


async def notify_coupon_expire_soon(db: Session, user: User, coupon: Any, days_left: int = 3) -> None:
    """「优惠券 X 天内到期」通知"""
    title = "优惠券即将到期"
    coupon_name = getattr(coupon, "name", "优惠券")
    content = f"您的「{coupon_name}」还有 {days_left} 天到期，快去使用吧"
    payload = {"coupon_id": getattr(coupon, "id", None), "days_left": days_left}

    send_inbox_message(db, "user", user.id, "activity", title, content, payload)

    if user.openid:
        await send_wx_subscribe(
            openid=user.openid,
            template_id=settings.WX_TEMPLATE_COUPON_EXPIRE,
            data={
                "thing1": {"value": coupon_name},
                "time2": {"value": f"{days_left} 天"},
            },
            page_path="pages/coupons/coupons",
        )

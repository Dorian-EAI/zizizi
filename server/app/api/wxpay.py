"""微信支付相关路由"""

import random
from datetime import datetime

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, require_super_admin
from app.models.order import Order
from app.models.user import Worker
from app.models.wallet import PaymentOrder, Transaction
from app.schemas.wxpay import (
    JSAPIPayResponse,
    OrderJSAPIRequest,
    RechargeJSAPIRequest,
)
from app.services import wechat_pay_service
from app.utils.response import success

router = APIRouter(prefix="/api/wxpay", tags=["微信支付"])


def _gen_payment_no() -> str:
    return "PAY" + datetime.utcnow().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999))


@router.post("/recharge/jsapi")
async def recharge_jsapi(
    req: RechargeJSAPIRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用户端：创建充值 JSAPI 支付订单"""
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="充值金额必须大于 0")
    if req.method != "wechat":
        raise HTTPException(status_code=400, detail="JSAPI 充值仅支持微信支付")
    if not user.openid:
        raise HTTPException(status_code=400, detail="当前账号未绑定微信 openid")

    payer_type = "worker" if user.role == "worker" else "user"
    payment = PaymentOrder(
        payment_no=_gen_payment_no(),
        order_no=None,
        amount=req.amount,
        method=req.method or "wechat",
        payer_type=payer_type,
        payer_id=user.id,
        status="pending",
    )
    db.add(payment)
    db.flush()

    try:
        pay_params = wechat_pay_service.create_jsapi_order(db, payment, user.openid)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(payment)

    resp = JSAPIPayResponse(**pay_params).model_dump()
    resp["payment_no"] = payment.payment_no
    return success(data=resp, message="支付参数生成成功")


@router.post("/order/jsapi")
async def order_jsapi(
    req: OrderJSAPIRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用户端：创建订单 JSAPI 支付订单"""
    order = (
        db.query(Order)
        .filter(Order.order_no == req.order_no)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=400, detail="订单不存在")
    if order.user_id != user.id:
        raise HTTPException(status_code=400, detail="无权支付该订单")
    if order.status != "completed":
        raise HTTPException(status_code=400, detail="订单未完成，无法支付")

    if not user.openid:
        raise HTTPException(status_code=400, detail="当前账号未绑定微信 openid")

    active_payment = (
        db.query(PaymentOrder)
        .filter(
            PaymentOrder.order_no == order.order_no,
            PaymentOrder.status.in_(("pending", "reserved")),
        )
        .first()
    )
    if active_payment:
        if active_payment.method != "wechat" or active_payment.payer_id != user.id:
            raise HTTPException(status_code=409, detail="订单已有其他待处理支付")
        pay_params = wechat_pay_service.create_jsapi_order(db, active_payment, user.openid)
        db.commit()
        resp = JSAPIPayResponse(**pay_params).model_dump()
        resp["payment_no"] = active_payment.payment_no
        return success(data=resp, message="返回待支付订单")

    from app.services.payment_service import _from_cents, _to_cents

    final_price = _from_cents(_to_cents(order.final_price or 0))
    discount_amount = 0.0
    if req.coupon_id:
        from app.services.coupon_service import apply_coupon

        coupon_in_use = (
            db.query(PaymentOrder)
            .filter(
                PaymentOrder.coupon_id == req.coupon_id,
                PaymentOrder.order_no != order.order_no,
                PaymentOrder.status.in_(("pending", "reserved")),
            )
            .first()
        )
        if coupon_in_use:
            raise HTTPException(status_code=409, detail="该优惠券已有待处理支付")
        discount_amount = _from_cents(
            _to_cents(
                apply_coupon(db, user, req.coupon_id, final_price, order.service_type)[
                    "discount_amount"
                ]
            )
        )
    pay_amount = _from_cents(max(_to_cents(final_price) - _to_cents(discount_amount), 0))
    if _to_cents(pay_amount) <= 0:
        raise HTTPException(status_code=400, detail="零元订单请使用站内支付完成")

    payment = PaymentOrder(
        payment_no=_gen_payment_no(),
        order_no=order.order_no,
        amount=pay_amount,
        method="wechat",
        coupon_id=req.coupon_id,
        discount_amount=discount_amount,
        payer_type="user",
        payer_id=user.id,
        status="pending",
    )
    db.add(payment)
    db.flush()

    try:
        pay_params = wechat_pay_service.create_jsapi_order(db, payment, user.openid)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(payment)

    resp = JSAPIPayResponse(**pay_params).model_dump()
    resp["payment_no"] = payment.payment_no
    return success(data=resp, message="支付参数生成成功")


@router.post("/notify/payment")
async def notify_payment(request: Request, db: Session = Depends(get_db)):
    """微信支付回调（公开接口）"""
    raw_body = await request.body()
    headers = dict(request.headers)

    try:
        result = wechat_pay_service.parse_payment_notification(headers, raw_body)
        wechat_pay_service.handle_payment_success(
            db,
            out_trade_no=result.out_trade_no,
            transaction_id=result.transaction_id,
            amount_total=result.amount_total,
            success=result.success,
        )
    except HTTPException:
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": "支付通知处理失败"},
        )
    return {"code": "SUCCESS", "message": "成功"}


@router.post("/notify/refund")
async def notify_refund(request: Request, db: Session = Depends(get_db)):
    """微信退款结果通知（公开接口，必须通过平台签名校验）。"""
    raw_body = await request.body()
    headers = dict(request.headers)
    try:
        result = wechat_pay_service.parse_refund_notification(headers, raw_body)
        wechat_pay_service.handle_refund_success(
            db,
            out_refund_no=result.out_refund_no,
            out_trade_no=result.out_trade_no,
            refund_id=result.refund_id,
            refund_amount=result.refund_amount,
            total_amount=result.total_amount,
        )
    except HTTPException:
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": "退款通知处理失败"},
        )
    return {"code": "SUCCESS", "message": "成功"}


@router.post("/notify/transfer")
async def notify_transfer(request: Request, db: Session = Depends(get_db)):
    """提现到账回调占位；真实环境未验签实现前绝不确认成功。"""
    if settings.APP_ENV.lower() == "development" and settings.WX_PAY_MOCK_ENABLED:
        return {"code": "SUCCESS", "message": "Mock 成功"}
    return JSONResponse(
        status_code=501,
        content={"code": "FAIL", "message": "转账通知处理尚未启用"},
    )


@router.post("/transfer/approve/{tx_id}")
async def transfer_approve(
    tx_id: int,
    admin=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """管理员：审核通过后提交微信商家转账。"""

    tx = (
        db.query(Transaction)
        .filter(Transaction.id == tx_id)
        .with_for_update()
        .first()
    )
    if not tx:
        raise HTTPException(status_code=404, detail="提现记录不存在")
    if tx.type != "withdraw":
        raise HTTPException(status_code=400, detail="非提现交易")
    if tx.status != "pending":
        raise HTTPException(status_code=400, detail="该提现阶段不可审批")
    if tx.owner_type != "worker":
        raise HTTPException(status_code=400, detail="仅支持师傅提现审批")
    if tx.method != "wechat":
        raise HTTPException(status_code=400, detail="仅支持微信提现审批")

    from app.services.payment_service import _to_cents

    if _to_cents(tx.amount) < 1000:
        raise HTTPException(status_code=400, detail="提现金额低于最低限额")

    worker = (
        db.query(Worker)
        .filter(Worker.id == tx.owner_id)
        .with_for_update()
        .first()
    )
    if not worker:
        raise HTTPException(status_code=404, detail="师傅不存在")
    if not worker.is_active:
        raise HTTPException(status_code=403, detail="师傅账号已禁用")
    if worker.certified != 2:
        raise HTTPException(status_code=403, detail="仅已实名认证师傅可提现")
    if not worker.openid:
        raise HTTPException(status_code=400, detail="师傅未绑定微信 openid")

    result = wechat_pay_service.create_transfer_to_worker(db, tx, worker)
    return success(data=result, message="审批完成")

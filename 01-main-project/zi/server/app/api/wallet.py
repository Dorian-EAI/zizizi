"""钱包与支付路由"""

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_account, get_current_user, get_current_worker, require_super_admin
from app.schemas.wallet import (
    OfflineConfirmRequest,
    PayRequest,
    RechargeRequest,
    RefundRequest,
    WithdrawRequest,
)
from app.services import payment_service
from app.services.idempotency_service import (
    claim_financial_request,
    complete_financial_request,
    fail_financial_request,
)
from app.utils.response import success
from app.utils.rate_limit import limiter, LIMIT_WITHDRAW

router = APIRouter(prefix="/api/wallet", tags=["钱包与支付"])


@router.get("")
async def wallet_info(
    account_data=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """获取钱包信息（余额、本月收入、本月支出、累计收入）"""
    account, account_type = account_data
    info = payment_service.get_wallet_info(db, account, account_type)
    return success(info, "success")


@router.get("/transactions")
async def transactions(
    type: str = Query("all", description="交易类型: income/expense/recharge/withdraw/all"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页条数"),
    account_data=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """交易记录列表（分页、按类型筛选）"""
    account, account_type = account_data
    result = payment_service.get_transactions(db, account, account_type, type, page, size)
    return success(result, "success")


@router.post("/recharge")
async def recharge(
    req: RechargeRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用户钱包充值；师傅收入钱包不开放充值。"""
    claim = claim_financial_request(
        db,
        raw_key=idempotency_key,
        owner_type="user",
        owner_id=user.id,
        operation="wallet.recharge",
        payload={
            "amount_cents": payment_service._to_cents(req.amount),
            "method": req.method,
        },
    )
    if claim.is_replay:
        return claim.replay_response
    try:
        result = payment_service.recharge(db, user, "user", req.amount, req.method)
        response = success(result, "充值支付单已创建，请完成支付")
        return complete_financial_request(
            db,
            claim,
            response,
            resource_type="payment_order",
            resource_id=result.get("payment_no"),
        )
    except Exception as exc:
        fail_financial_request(db, claim, exc)
        raise


@router.post("/withdraw")
@limiter.limit(LIMIT_WITHDRAW)
async def withdraw(
    request: Request,
    req: WithdrawRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    worker=Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """师傅收入钱包提现；用户余额不可提现。"""
    claim = claim_financial_request(
        db,
        raw_key=idempotency_key,
        owner_type="worker",
        owner_id=worker.id,
        operation="wallet.withdraw",
        payload={
            "amount_cents": payment_service._to_cents(req.amount),
            "method": req.method,
            "bank_info": req.bank_info,
        },
    )
    if claim.is_replay:
        return claim.replay_response
    try:
        result = payment_service.withdraw(db, worker, "worker", req.amount, req.method, req.bank_info)
        response = success(result, "提现申请已提交")
        transaction = result.get("transaction") if isinstance(result, dict) else None
        return complete_financial_request(
            db,
            claim,
            response,
            resource_type="transaction",
            resource_id=(transaction or {}).get("id"),
        )
    except Exception as exc:
        fail_financial_request(db, claim, exc)
        raise


@router.post("/pay")
async def pay(
    req: PayRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """订单支付

    支持方式：
    - wallet: 余额支付
    - wechat: 微信支付
    - combined: 组合支付（需传 wallet_amount + wechat_amount）
    - offline: 线下支付（师傅上门收款）
    """
    claim = claim_financial_request(
        db,
        raw_key=idempotency_key,
        owner_type="user",
        owner_id=user.id,
        operation="wallet.pay_order",
        payload={
            "order_no": req.order_no,
            "method": req.method,
            "coupon_id": req.coupon_id,
            "wallet_amount_cents": (
                payment_service._to_cents(req.wallet_amount)
                if req.wallet_amount is not None
                else None
            ),
            "wechat_amount_cents": (
                payment_service._to_cents(req.wechat_amount)
                if req.wechat_amount is not None
                else None
            ),
            "order_version": req.order_version,
        },
    )
    if claim.is_replay:
        return claim.replay_response
    try:
        result = await payment_service.pay_order(
            db, user, req.order_no, req.method, req.coupon_id,
            req.wallet_amount, req.wechat_amount, req.order_version,
        )
        status_value = str(result.get("status", "")).lower() if isinstance(result, dict) else ""
        message = "支付成功" if status_value in {"success", "paid"} else "支付请求已提交"
        response = success(result, message)
        return complete_financial_request(
            db,
            claim,
            response,
            resource_type="payment_order",
            resource_id=result.get("payment_no") if isinstance(result, dict) else None,
        )
    except Exception as exc:
        fail_financial_request(db, claim, exc)
        raise


# ===== 退款（管理员） =====

@router.post("/refund")
async def refund(
    req: RefundRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    admin=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """订单退款（管理员）"""
    claim = claim_financial_request(
        db,
        raw_key=idempotency_key,
        owner_type="admin",
        owner_id=admin.id,
        operation="wallet.refund_order",
        payload={
            "order_no": req.order_no,
            "reason": req.reason,
            "amount_cents": (
                payment_service._to_cents(req.amount)
                if req.amount is not None
                else None
            ),
        },
    )
    if claim.is_replay:
        return claim.replay_response
    try:
        result = payment_service.refund_order(
            db, req.order_no, req.reason, req.amount, admin.id
        )
        response = success(result, "退款申请已受理")
        return complete_financial_request(
            db,
            claim,
            response,
            resource_type="order_refund",
            resource_id=req.order_no,
        )
    except Exception as exc:
        fail_financial_request(db, claim, exc)
        raise


# ===== 师傅确认线下收款 =====

@router.post("/offline/confirm")
async def confirm_offline_payment(
    body: OfflineConfirmRequest,
    account_data=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """师傅确认线下收款"""
    from fastapi import HTTPException
    account, account_type = account_data
    if account_type != "worker":
        raise HTTPException(status_code=403, detail="仅师傅可确认收款")

    result = payment_service.confirm_offline_payment(db, account, body.order_no)
    return success(result, "收款已确认")

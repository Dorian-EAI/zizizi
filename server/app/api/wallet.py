"""钱包与支付路由"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_account, get_current_user, require_super_admin
from app.schemas.wallet import (
    OfflineConfirmRequest,
    PayRequest,
    RechargeRequest,
    RefundRequest,
    WithdrawRequest,
)
from app.services import payment_service
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
    account_data=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """钱包充值"""
    account, account_type = account_data
    result = payment_service.recharge(db, account, account_type, req.amount, req.method)
    return success(result, "充值成功")


@router.post("/withdraw")
@limiter.limit(LIMIT_WITHDRAW)
async def withdraw(
    request: Request,
    req: WithdrawRequest,
    account_data=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """提现申请"""
    account, account_type = account_data
    result = payment_service.withdraw(db, account, account_type, req.amount, req.method, req.bank_info)
    return success(result, "提现申请已提交")


@router.post("/pay")
async def pay(
    req: PayRequest,
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
    result = await payment_service.pay_order(
        db, user, req.order_no, req.method, req.coupon_id,
        req.wallet_amount, req.wechat_amount,
    )
    return success(result, "支付成功")


# ===== 退款（管理员） =====

@router.post("/refund")
async def refund(
    req: RefundRequest,
    admin=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """订单退款（管理员）"""
    result = payment_service.refund_order(db, req.order_no, req.reason, req.amount, admin.id)
    return success(result, "退款成功")


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

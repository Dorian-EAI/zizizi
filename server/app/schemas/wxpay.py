"""微信支付相关 Pydantic 模型"""

from typing import Optional
from pydantic import BaseModel


class JSAPIPayResponse(BaseModel):
    """JSAPI 调起支付返回参数"""
    appId: str
    timeStamp: str
    nonceStr: str
    package: str
    signType: str = "RSA"
    paySign: str


class WechatPayNotifyResult(BaseModel):
    """微信支付回调解析结果"""
    out_trade_no: str
    transaction_id: str
    amount_total: int
    success: bool
    appid: Optional[str] = None
    mchid: Optional[str] = None


class WechatRefundNotifyResult(BaseModel):
    """微信退款结果通知解密后的必要字段。"""
    out_refund_no: str
    out_trade_no: str
    refund_id: str
    refund_amount: int
    total_amount: int
    success: bool


class RechargeJSAPIRequest(BaseModel):
    """充值 JSAPI 请求"""
    amount: float
    method: str = "wechat"


class OrderJSAPIRequest(BaseModel):
    """订单 JSAPI 支付请求"""
    order_no: str
    coupon_id: Optional[int] = None


class ToggleActiveRequest(BaseModel):
    is_active: bool


class WorkerCertifyRequest(BaseModel):
    certified: int


class UpdateOrderStatusRequest(BaseModel):
    status: str
    remark: Optional[str] = None

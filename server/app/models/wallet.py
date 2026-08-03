"""钱包与交易记录数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, Text
from app.database import Base


class Transaction(Base):
    """交易记录表 — 收入/支出/充值/提现"""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 主体: user_id 或 worker_id
    owner_type = Column(String(16), nullable=False, comment="user / worker")
    owner_id = Column(Integer, index=True, nullable=False, comment="用户或师傅 ID")

    # 交易信息
    type = Column(String(16), nullable=False, comment="income/expense/recharge/withdraw")
    amount = Column(Numeric(12, 2), nullable=False, comment="金额（正数，元）")
    balance_after = Column(Numeric(12, 2), nullable=True, comment="交易后余额（元）")
    method = Column(String(16), nullable=True, comment="wechat/alipay/wallet/bank")

    # 关联
    order_id = Column(String(32), nullable=True, comment="关联订单号")
    description = Column(String(128), nullable=True, comment="交易描述")

    # 状态: pending/success/failed
    status = Column(String(16), default="success", nullable=False)

    # 提现附加信息
    bank_info = Column(Text, nullable=True, comment="提现银行卡信息 JSON")

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class PaymentOrder(Base):
    """支付订单表 — 记录每笔支付请求"""
    __tablename__ = "payment_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_no = Column(String(32), unique=True, index=True, nullable=False, comment="支付单号")
    order_no = Column(String(32), index=True, nullable=True, comment="关联业务订单号")

    # 支付信息
    amount = Column(Numeric(12, 2), nullable=False, comment="支付金额（元）")
    method = Column(String(16), nullable=False, comment="wechat/alipay/wallet")
    coupon_id = Column(Integer, nullable=True, comment="使用的优惠券 ID")
    discount_amount = Column(Numeric(12, 2), default=0, comment="优惠抵扣金额（元）")

    # 主体
    payer_type = Column(String(16), nullable=False, comment="user / worker")
    payer_id = Column(Integer, nullable=False)

    # 状态: pending/reserved/paid/failed/partially_refunded/refunded
    status = Column(String(24), default="pending", nullable=False)

    # 微信支付附加
    prepay_id = Column(String(128), nullable=True, comment="微信预支付 ID")
    # 微信支付流水号全局唯一；除业务层幂等校验外，由数据库阻止并发重复入账。
    transaction_id = Column(String(64), unique=True, index=True, nullable=True, comment="微信支付流水号")

    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)


class RefundOrder(Base):
    """退款单 — 每次退款申请独立记录，并按原支付渠道结算。"""
    __tablename__ = "refund_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    refund_no = Column(String(32), unique=True, index=True, nullable=False, comment="商户退款单号")
    payment_no = Column(String(32), index=True, nullable=False, comment="原支付单号")
    order_no = Column(String(32), index=True, nullable=False, comment="业务订单号")

    amount = Column(Numeric(12, 2), nullable=False, comment="本次退款金额（元）")
    total_amount = Column(Numeric(12, 2), nullable=False, comment="原支付单金额（元）")
    method = Column(String(16), nullable=False, comment="原支付渠道")
    payer_type = Column(String(16), nullable=False)
    payer_id = Column(Integer, nullable=False)
    reason = Column(String(512), nullable=True)

    # pending/success/failed
    status = Column(String(16), default="pending", nullable=False, index=True)
    refund_id = Column(String(64), unique=True, index=True, nullable=True, comment="微信退款单号")
    attempt_count = Column(Integer, default=0, nullable=False, comment="提交微信退款尝试次数")
    last_attempt_at = Column(DateTime, nullable=True, comment="最近一次提交时间")
    last_error = Column(String(512), nullable=True, comment="最近一次提交/查询错误（不含敏感数据）")
    created_at = Column(DateTime, default=datetime.utcnow)
    refunded_at = Column(DateTime, nullable=True)

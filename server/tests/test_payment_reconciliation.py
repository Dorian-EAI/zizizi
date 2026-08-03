from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from fastapi import HTTPException

from tests._support import isolated_engine, session_factory
from app.config import settings
from app.models.order import Order
from app.models.user import User
from app.models.wallet import PaymentOrder, RefundOrder, Transaction
from app.services.payment_service import release_expired_wechat_payment
from app.services.wechat_pay_service import (
    _validate_mock_callback_secret,
    reconcile_pending_wechat_payments,
    reconcile_pending_wechat_refunds,
)


class PaymentReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        User.__table__.create(self.engine)
        Order.__table__.create(self.engine)
        Transaction.__table__.create(self.engine)
        PaymentOrder.__table__.create(self.engine)
        RefundOrder.__table__.create(self.engine)
        self.Session = session_factory(self.engine)

    def tearDown(self) -> None:
        RefundOrder.__table__.drop(self.engine)
        PaymentOrder.__table__.drop(self.engine)
        Transaction.__table__.drop(self.engine)
        Order.__table__.drop(self.engine)
        User.__table__.drop(self.engine)
        self.engine.dispose()

    def _seed_combined_payment(self, created_at: datetime) -> tuple[int, int]:
        db = self.Session()
        try:
            user = User(openid="openid-reserved", balance=Decimal("70.00"))
            db.add(user)
            db.flush()
            order = Order(
                order_no="ORDER-RESERVED",
                user_id=user.id,
                service_type="repair",
                service_name="维修",
                final_price=Decimal("100.00"),
                status="completed",
            )
            db.add(order)
            db.flush()
            db.add(
                PaymentOrder(
                    payment_no="PAY-WALLET-RESERVED",
                    order_no=order.order_no,
                    amount=Decimal("30.00"),
                    method="wallet",
                    payer_type="user",
                    payer_id=user.id,
                    status="reserved",
                    created_at=created_at,
                )
            )
            wechat = PaymentOrder(
                payment_no="PAY-WECHAT-PENDING",
                order_no=order.order_no,
                amount=Decimal("70.00"),
                method="wechat",
                payer_type="user",
                payer_id=user.id,
                status="pending",
                created_at=created_at,
            )
            db.add(wechat)
            db.add(
                Transaction(
                    owner_type="user",
                    owner_id=user.id,
                    type="expense",
                    amount=Decimal("30.00"),
                    balance_after=Decimal("70.00"),
                    method="wallet",
                    order_id=order.order_no,
                    status="pending",
                )
            )
            db.commit()
            return user.id, wechat.id
        finally:
            db.close()

    def test_notpay_is_closed_before_reserved_balance_is_released(self) -> None:
        now = datetime.utcnow()
        user_id, payment_id = self._seed_combined_payment(now - timedelta(hours=1))
        db = self.Session()
        try:
            with (
                patch(
                    "app.services.wechat_pay_service.query_wechat_payment",
                    return_value={
                        "trade_state": "NOTPAY",
                        "out_trade_no": "PAY-WECHAT-PENDING",
                        "transaction_id": "",
                        "amount_total": 7000,
                    },
                ),
                patch(
                    "app.services.wechat_pay_service.close_wechat_payment",
                    return_value=True,
                ) as close_payment,
            ):
                stats = reconcile_pending_wechat_payments(db, now=now)

            self.assertEqual(stats["released"], 1)
            close_payment.assert_called_once()
            user = db.query(User).filter(User.id == user_id).one()
            self.assertEqual(user.balance, Decimal("100.00"))
            statuses = {
                item.method: item.status
                for item in db.query(PaymentOrder).order_by(PaymentOrder.id).all()
            }
            self.assertEqual(statuses, {"wallet": "failed", "wechat": "failed"})
            self.assertEqual(db.query(Transaction).one().status, "failed")

            # 幂等：重复释放不会再次增加余额。
            repeated = release_expired_wechat_payment(db, payment_id)
            self.assertFalse(repeated["released"])
            self.assertEqual(db.query(User).filter(User.id == user_id).one().balance, Decimal("100.00"))
        finally:
            db.close()

    def test_userpaying_or_query_error_never_releases_balance(self) -> None:
        now = datetime.utcnow()
        user_id, _ = self._seed_combined_payment(now - timedelta(hours=1))
        db = self.Session()
        try:
            with (
                patch(
                    "app.services.wechat_pay_service.query_wechat_payment",
                    return_value={
                        "trade_state": "USERPAYING",
                        "out_trade_no": "PAY-WECHAT-PENDING",
                        "transaction_id": "",
                        "amount_total": 7000,
                    },
                ),
                patch("app.services.wechat_pay_service.close_wechat_payment") as close_payment,
            ):
                stats = reconcile_pending_wechat_payments(db, now=now)
            self.assertEqual(stats["deferred"], 1)
            close_payment.assert_not_called()
            self.assertEqual(db.query(User).filter(User.id == user_id).one().balance, Decimal("70.00"))

            with patch(
                "app.services.wechat_pay_service.query_wechat_payment",
                side_effect=HTTPException(status_code=502, detail="network"),
            ):
                stats = reconcile_pending_wechat_payments(db, now=now)
            self.assertEqual(stats["errors"], 1)
            self.assertEqual(db.query(User).filter(User.id == user_id).one().balance, Decimal("70.00"))
            self.assertTrue(all(p.status in {"pending", "reserved"} for p in db.query(PaymentOrder).all()))
        finally:
            db.close()

    def test_refund_not_found_retries_with_same_refund_record(self) -> None:
        now = datetime.utcnow()
        db = self.Session()
        try:
            payment = PaymentOrder(
                payment_no="PAY-REFUND-ORIGIN",
                order_no="ORDER-REFUND",
                amount=Decimal("20.00"),
                method="wechat",
                payer_type="user",
                payer_id=1,
                status="paid",
                transaction_id="WX-REFUND-ORIGIN",
            )
            db.add(payment)
            db.add(
                RefundOrder(
                    refund_no="REF-PENDING",
                    payment_no=payment.payment_no,
                    order_no="ORDER-REFUND",
                    amount=Decimal("20.00"),
                    total_amount=Decimal("20.00"),
                    method="wechat",
                    payer_type="user",
                    payer_id=1,
                    status="pending",
                    attempt_count=0,
                )
            )
            db.commit()

            def fake_submit(session, refund, _payment):
                refund.attempt_count += 1
                refund.last_attempt_at = now
                return {"status": "PROCESSING", "refund_no": refund.refund_no}

            with (
                patch(
                    "app.services.wechat_pay_service.query_wechat_refund",
                    return_value={
                        "status": "NOT_FOUND",
                        "out_refund_no": "REF-PENDING",
                        "out_trade_no": "PAY-REFUND-ORIGIN",
                        "refund_id": "",
                        "refund_amount": 2000,
                        "total_amount": 2000,
                    },
                ),
                patch(
                    "app.services.wechat_pay_service.create_wechat_refund",
                    side_effect=fake_submit,
                ) as submit,
            ):
                stats = reconcile_pending_wechat_refunds(db, now=now)

            self.assertEqual(stats["retried"], 1)
            submit.assert_called_once()
            refund = db.query(RefundOrder).one()
            self.assertEqual(refund.status, "pending")
            self.assertEqual(refund.attempt_count, 1)
        finally:
            db.close()


class MockCallbackSecretTests(unittest.TestCase):
    def test_empty_or_wrong_mock_callback_secret_fails_closed(self) -> None:
        with patch.object(settings, "WX_PAY_MOCK_CALLBACK_SECRET", ""):
            with self.assertRaises(HTTPException) as missing:
                _validate_mock_callback_secret({})
            self.assertEqual(missing.exception.status_code, 503)

        with patch.object(settings, "WX_PAY_MOCK_CALLBACK_SECRET", "expected"):
            with self.assertRaises(HTTPException) as wrong:
                _validate_mock_callback_secret({"X-Mock-Payment-Secret": "wrong"})
            self.assertEqual(wrong.exception.status_code, 401)
            _validate_mock_callback_secret({"X-Mock-Payment-Secret": "expected"})


if __name__ == "__main__":
    unittest.main()

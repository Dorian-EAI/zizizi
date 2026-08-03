from __future__ import annotations

import unittest
from decimal import Decimal

from fastapi import HTTPException

from tests._support import isolated_engine, session_factory
from app.models.user import User
from app.models.wallet import PaymentOrder, Transaction
from app.services.wechat_pay_service import handle_payment_success


class PaymentCallbackIdempotencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        User.__table__.create(self.engine)
        Transaction.__table__.create(self.engine)
        PaymentOrder.__table__.create(self.engine)
        self.Session = session_factory(self.engine)

    def tearDown(self) -> None:
        PaymentOrder.__table__.drop(self.engine)
        Transaction.__table__.drop(self.engine)
        User.__table__.drop(self.engine)
        self.engine.dispose()

    def _seed_recharge(self, payment_no: str = "PAY-IDEMPOTENT") -> None:
        db = self.Session()
        try:
            user = User(openid="openid-idempotent", balance=Decimal("0.00"))
            db.add(user)
            db.flush()
            db.add(
                PaymentOrder(
                    payment_no=payment_no,
                    amount=Decimal("12.34"),
                    method="wechat",
                    payer_type="user",
                    payer_id=user.id,
                    status="pending",
                )
            )
            db.commit()
        finally:
            db.close()

    def test_same_callback_credits_balance_once(self) -> None:
        self._seed_recharge()
        db = self.Session()
        try:
            kwargs = {
                "out_trade_no": "PAY-IDEMPOTENT",
                "transaction_id": "WX-TX-ONE",
                "amount_total": 1234,
                "success": True,
            }
            handle_payment_success(db, **kwargs)
            handle_payment_success(db, **kwargs)

            user = db.query(User).filter(User.openid == "openid-idempotent").one()
            payment = db.query(PaymentOrder).one()
            transactions = db.query(Transaction).all()
            self.assertEqual(user.balance, Decimal("12.34"))
            self.assertEqual(payment.status, "paid")
            self.assertEqual(payment.transaction_id, "WX-TX-ONE")
            self.assertEqual(len(transactions), 1)
            self.assertEqual(transactions[0].type, "recharge")
        finally:
            db.close()

    def test_callback_rejects_wrong_amount_without_side_effects(self) -> None:
        self._seed_recharge("PAY-WRONG-AMOUNT")
        db = self.Session()
        try:
            with self.assertRaises(HTTPException) as raised:
                handle_payment_success(
                    db,
                    out_trade_no="PAY-WRONG-AMOUNT",
                    transaction_id="WX-TX-WRONG",
                    amount_total=1200,
                )
            self.assertEqual(raised.exception.status_code, 400)
            payment = db.query(PaymentOrder).one()
            user = db.query(User).one()
            self.assertEqual(payment.status, "pending")
            self.assertIsNone(payment.transaction_id)
            self.assertEqual(user.balance, Decimal("0.00"))
            self.assertEqual(db.query(Transaction).count(), 0)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

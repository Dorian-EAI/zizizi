from __future__ import annotations

import asyncio
import unittest
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException

from tests._support import isolated_engine, session_factory
from app.models.extra_fee import OrderExtraFee
from app.models.order import Bidding, Order
from app.models.wallet import PaymentOrder
from app.services.extra_fee_service import approve_extra_fee, reject_extra_fee
from app.services.order_service import build_order_projection, update_order_status
from app.services.payment_service import get_order_payment_quote


class OrderProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        Order.__table__.create(self.engine)
        Bidding.__table__.create(self.engine)
        OrderExtraFee.__table__.create(self.engine)
        PaymentOrder.__table__.create(self.engine)
        self.Session = session_factory(self.engine)

    def tearDown(self) -> None:
        PaymentOrder.__table__.drop(self.engine)
        OrderExtraFee.__table__.drop(self.engine)
        Bidding.__table__.drop(self.engine)
        Order.__table__.drop(self.engine)
        self.engine.dispose()

    def _order(self, db, *, status: str, final_price: str = "100.00") -> Order:
        order = Order(
            order_no=f"ORD-{status}-{id(self)}-{db.query(Order).count()}",
            user_id=7,
            worker_id=9,
            service_type="repair",
            service_name="Repair",
            status=status,
            final_price=Decimal(final_price),
            version=2,
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    def test_client_completed_projection_authorizes_only_server_payment_methods(self) -> None:
        db = self.Session()
        try:
            order = self._order(db, status="completed")
            projection = build_order_projection(
                db,
                order,
                "client",
                SimpleNamespace(openid="wx-user"),
            )
            self.assertEqual(projection["service_state"], "completed")
            self.assertEqual(projection["payment_state"], "unpaid")
            self.assertIn("confirm_and_pay", projection["allowed_actions"])
            self.assertEqual(
                [item["key"] for item in projection["payment_methods"]],
                ["wechat", "wallet"],
            )
            self.assertNotIn("offline", [item["key"] for item in projection["payment_methods"]])
        finally:
            db.close()

    def test_payment_quote_uses_server_amount_version_and_recovers_active_payment(self) -> None:
        db = self.Session()
        try:
            order = self._order(db, status="completed", final_price="66.80")
            user = SimpleNamespace(id=7, openid="wx-user", balance=Decimal("100.00"))
            quote = get_order_payment_quote(db, user, order.id)
            self.assertEqual(quote["original_amount"], 66.8)
            self.assertEqual(quote["payable_amount"], 66.8)
            self.assertEqual(quote["order_version"], 2)
            self.assertIsNone(quote["active_payment"])

            payment = PaymentOrder(
                payment_no="PAY-QUOTE-RECOVERY",
                order_no=order.order_no,
                amount=Decimal("56.80"),
                method="wechat",
                coupon_id=3,
                discount_amount=Decimal("10.00"),
                payer_type="user",
                payer_id=7,
                status="pending",
            )
            db.add(payment)
            db.commit()
            recovered = get_order_payment_quote(db, user, order.id)
            self.assertEqual(recovered["payable_amount"], 56.8)
            self.assertEqual(recovered["coupon_id"], 3)
            self.assertEqual(recovered["active_payment"]["payment_no"], "PAY-QUOTE-RECOVERY")
        finally:
            db.close()

    def test_pending_extra_fee_is_visible_to_client_and_blocks_worker_completion(self) -> None:
        db = self.Session()
        try:
            order = self._order(db, status="serving")
            db.add(OrderExtraFee(
                order_id=order.id,
                worker_id=9,
                user_id=7,
                items=[{"name": "material", "price": 1000, "unit": "item"}],
                total_amount=1000,
                reason="material",
                status="pending",
            ))
            db.commit()

            client = build_order_projection(db, order, "client", SimpleNamespace(openid="wx"))
            worker = build_order_projection(db, order, "worker", SimpleNamespace(id=9))
            self.assertIn("handle_extra_fee", client["allowed_actions"])
            self.assertNotIn("complete_service", worker["allowed_actions"])
            self.assertEqual(worker["blocked_actions"][0]["reason_code"], "EXTRA_FEE_PENDING")

            with self.assertRaises(HTTPException) as caught:
                asyncio.run(update_order_status(
                    db,
                    SimpleNamespace(id=9),
                    "worker",
                    order.id,
                    "completed",
                    Decimal("100.00"),
                ))
            self.assertEqual(caught.exception.status_code, 409)
        finally:
            db.close()

    def test_approve_replay_does_not_increment_amount_or_version_twice(self) -> None:
        db = self.Session()
        try:
            order = self._order(db, status="serving")
            fee = OrderExtraFee(
                order_id=order.id,
                worker_id=9,
                user_id=7,
                items=[{"name": "material", "price": 1250, "unit": "item"}],
                total_amount=1250,
                reason="material",
                status="pending",
            )
            db.add(fee)
            db.commit()
            db.refresh(fee)

            approve_extra_fee(db, 7, order.id, fee.id)
            approve_extra_fee(db, 7, order.id, fee.id)
            db.expire_all()
            persisted = db.get(Order, order.id)
            self.assertEqual(persisted.final_price, Decimal("112.50"))
            self.assertEqual(persisted.version, 3)
        finally:
            db.close()

    def test_reject_same_result_is_replay_but_conflicting_result_is_rejected(self) -> None:
        db = self.Session()
        try:
            order = self._order(db, status="serving")
            fee = OrderExtraFee(
                order_id=order.id,
                worker_id=9,
                user_id=7,
                items=[{"name": "material", "price": 900, "unit": "item"}],
                total_amount=900,
                reason="material",
                status="pending",
            )
            db.add(fee)
            db.commit()
            db.refresh(fee)

            reject_extra_fee(db, 7, order.id, fee.id, "not needed")
            replay = reject_extra_fee(db, 7, order.id, fee.id, "not needed")
            self.assertEqual(replay.status, "rejected")
            with self.assertRaises(HTTPException) as caught:
                reject_extra_fee(db, 7, order.id, fee.id, "different")
            self.assertEqual(caught.exception.status_code, 409)
        finally:
            db.close()

    def test_worker_cannot_override_authoritative_completion_price(self) -> None:
        db = self.Session()
        try:
            order = self._order(db, status="serving", final_price="88.00")
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(update_order_status(
                    db,
                    SimpleNamespace(id=9),
                    "worker",
                    order.id,
                    "completed",
                    Decimal("188.00"),
                ))
            self.assertEqual(caught.exception.status_code, 409)
            db.expire_all()
            self.assertEqual(db.get(Order, order.id).status, "serving")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

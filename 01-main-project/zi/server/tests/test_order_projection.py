from __future__ import annotations

import asyncio
import unittest
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException

from tests._support import isolated_engine, session_factory
from app.models.admin import Admin
from app.models.extra_fee import OrderExtraFee
from app.models.insurance import InsuranceClaim, InsurancePolicy
from app.models.order import Bidding, Order, OrderCancellationRequest
from app.models.support_ticket import SupportTicket
from app.models.user import User, Worker
from app.models.wallet import PaymentOrder, RefundOrder
from app.services.extra_fee_service import approve_extra_fee, reject_extra_fee
from app.services.order_service import (
    build_order_projection,
    build_order_projections,
    update_order_status,
)
from app.services.payment_service import get_order_payment_quote


class OrderProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        Admin.__table__.create(self.engine)
        User.__table__.create(self.engine)
        Worker.__table__.create(self.engine)
        Order.__table__.create(self.engine)
        Bidding.__table__.create(self.engine)
        OrderExtraFee.__table__.create(self.engine)
        PaymentOrder.__table__.create(self.engine)
        RefundOrder.__table__.create(self.engine)
        InsurancePolicy.__table__.create(self.engine)
        InsuranceClaim.__table__.create(self.engine)
        SupportTicket.__table__.create(self.engine)
        OrderCancellationRequest.__table__.create(self.engine)
        self.Session = session_factory(self.engine)

    def tearDown(self) -> None:
        OrderCancellationRequest.__table__.drop(self.engine)
        SupportTicket.__table__.drop(self.engine)
        InsuranceClaim.__table__.drop(self.engine)
        InsurancePolicy.__table__.drop(self.engine)
        RefundOrder.__table__.drop(self.engine)
        PaymentOrder.__table__.drop(self.engine)
        OrderExtraFee.__table__.drop(self.engine)
        Bidding.__table__.drop(self.engine)
        Order.__table__.drop(self.engine)
        Worker.__table__.drop(self.engine)
        User.__table__.drop(self.engine)
        Admin.__table__.drop(self.engine)
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
            self.assertIn("confirm_and_pay", projection["allowed_action_keys"])
            confirm = next(
                item for item in projection["allowed_actions"]
                if item["key"] == "confirm_and_pay"
            )
            self.assertEqual(confirm["label"], "确认并支付")
            self.assertTrue(confirm["requires_confirm"])
            self.assertTrue(confirm["enabled"])
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
            self.assertIn("handle_extra_fee", client["allowed_action_keys"])
            self.assertNotIn("complete_service", worker["allowed_action_keys"])
            complete = next(
                item for item in worker["allowed_actions"]
                if item["key"] == "complete_service"
            )
            self.assertFalse(complete["enabled"])
            self.assertIn("补差价", complete["reason"])
            self.assertEqual(worker["blocked_actions"][0]["key"], "complete_service")

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

    def test_api_user_role_alias_returns_client_action_contract(self) -> None:
        db = self.Session()
        try:
            order = self._order(db, status="completed")
            projection = build_order_projection(
                db,
                order,
                "user",
                SimpleNamespace(openid="wx-user"),
            )
            self.assertEqual(projection["active_role"], "client")
            self.assertIn("confirm_and_pay", projection["allowed_action_keys"])
            self.assertTrue(all(isinstance(item, dict) for item in projection["allowed_actions"]))
        finally:
            db.close()

    def test_pending_payment_marks_processing_and_disables_pay(self) -> None:
        db = self.Session()
        try:
            order = self._order(db, status="completed")
            db.add(PaymentOrder(
                payment_no="PAY-PENDING-001",
                order_no=order.order_no,
                amount=Decimal("100.00"),
                method="wechat",
                payer_type="user",
                payer_id=7,
                status="pending",
            ))
            db.commit()

            projection = build_order_projection(db, order, "client", SimpleNamespace(openid="wx"))
            self.assertEqual(projection["payment_state"], "processing")
            confirm = next(
                item for item in projection["allowed_actions"]
                if item["key"] == "confirm_and_pay"
            )
            self.assertFalse(confirm["enabled"])
            self.assertIn("支付结果确认中", confirm["reason"])
            self.assertNotIn("confirm_and_pay", projection["allowed_action_keys"])
        finally:
            db.close()

    def test_support_ticket_drives_aftersale_state(self) -> None:
        db = self.Session()
        try:
            order = self._order(db, status="paid")
            db.add(SupportTicket(
                ticket_no="TICKET-001",
                ticket_type="complaint",
                status="processing",
                creator_type="user",
                creator_id=7,
                creator_name="User",
                related_order_id=order.id,
                title="Service issue",
                description="The service did not match the quote.",
            ))
            db.commit()

            projection = build_order_projection(db, order, "client", SimpleNamespace(openid="wx"))
            self.assertEqual(projection["aftersale_state"], "processing")
            self.assertEqual(projection["aftersale_type"], "complaint")
            self.assertEqual(projection["aftersale_object_id"], "TICKET-001")
            self.assertIn("view_after_sale", projection["allowed_action_keys"])
        finally:
            db.close()

    def test_refund_pending_and_partial_refund_payment_summary(self) -> None:
        db = self.Session()
        try:
            order = self._order(db, status="paid", final_price="100.00")
            db.add(PaymentOrder(
                payment_no="PAY-REFUND-001",
                order_no=order.order_no,
                amount=Decimal("100.00"),
                method="wechat",
                payer_type="user",
                payer_id=7,
                status="paid",
            ))
            refund = RefundOrder(
                refund_no="REFUND-001",
                payment_no="PAY-REFUND-001",
                order_no=order.order_no,
                amount=Decimal("20.00"),
                total_amount=Decimal("100.00"),
                method="wechat",
                payer_type="user",
                payer_id=7,
                status="pending",
            )
            db.add(refund)
            db.commit()

            pending = build_order_projection(db, order, "client", SimpleNamespace(openid="wx"))
            self.assertEqual(pending["payment_state"], "refunding")
            self.assertEqual(pending["payment_summary"]["paid_amount"], 100.0)
            self.assertEqual(pending["payment_summary"]["refunded_amount"], 0.0)
            self.assertEqual(pending["payment_summary"]["refundable_amount"], 100.0)
            self.assertEqual(pending["aftersale_state"], "processing")

            refund.status = "success"
            db.commit()
            partial = build_order_projection(db, order, "client", SimpleNamespace(openid="wx"))
            self.assertEqual(partial["payment_state"], "paid")
            self.assertEqual(partial["payment_summary"]["refunded_amount"], 20.0)
            self.assertEqual(partial["payment_summary"]["refundable_amount"], 80.0)
            self.assertEqual(partial["aftersale_state"], "resolved")
        finally:
            db.close()

    def test_batch_projection_is_aligned_with_orders(self) -> None:
        db = self.Session()
        try:
            first = self._order(db, status="pending")
            second = self._order(db, status="accepted")
            projections = build_order_projections(
                db,
                [first, second],
                "user",
                SimpleNamespace(openid="wx"),
            )
            self.assertEqual(len(projections), 2)
            self.assertEqual(projections[0]["service_state"], "pending")
            self.assertEqual(projections[1]["service_state"], "accepted")
            self.assertEqual(projections[0]["active_role"], "client")
            self.assertIn("request_cancel", projections[1]["allowed_action_keys"])
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

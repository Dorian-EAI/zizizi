from __future__ import annotations

import unittest
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException

from tests._support import isolated_engine, session_factory
from app.models.admin import Admin
from app.models.extra_fee import OrderExtraFee
from app.models.insurance import InsuranceClaim, InsurancePolicy
from app.models.message import Message
from app.models.order import Bidding, Order, OrderCancellationRequest
from app.models.support_ticket import SupportTicket
from app.models.user import User, Worker
from app.models.wallet import PaymentOrder, RefundOrder
from app.services import cancellation_service
from app.services.order_service import build_order_projection


class OrderCancellationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        self.tables = [
            Admin.__table__,
            User.__table__,
            Worker.__table__,
            Order.__table__,
            Bidding.__table__,
            OrderExtraFee.__table__,
            PaymentOrder.__table__,
            RefundOrder.__table__,
            InsurancePolicy.__table__,
            InsuranceClaim.__table__,
            SupportTicket.__table__,
            OrderCancellationRequest.__table__,
            Message.__table__,
        ]
        for table in self.tables:
            table.create(self.engine)
        self.Session = session_factory(self.engine)
        self.user = SimpleNamespace(id=7, openid="wx-user")
        self.admin = Admin(
            id=1,
            username="admin",
            password_hash="x",
            role="super_admin",
            token_version=1,
            must_change_password=False,
            is_active=True,
        )

    def tearDown(self) -> None:
        for table in reversed(self.tables):
            table.drop(self.engine)
        self.engine.dispose()

    def _order(self, db, status: str = "accepted") -> Order:
        order = Order(
            order_no=f"ORD-CANCEL-{status}-{db.query(Order).count()}",
            user_id=7,
            worker_id=9,
            service_type="repair",
            service_name="维修服务",
            status=status,
            final_price=Decimal("100.00"),
            version=4,
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    def test_pending_order_must_use_direct_cancel(self) -> None:
        db = self.Session()
        try:
            order = self._order(db, "pending")
            with self.assertRaises(HTTPException) as caught:
                cancellation_service.create_request(db, self.user, order.id, "计划有变")
            self.assertEqual(caught.exception.status_code, 409)
            self.assertIn("直接取消", caught.exception.detail)
        finally:
            db.close()

    def test_create_projection_withdraw_and_duplicate_guard(self) -> None:
        db = self.Session()
        try:
            order = self._order(db, "accepted")
            request = cancellation_service.create_request(
                db, self.user, order.id, "计划有变", "临时出差"
            )
            self.assertEqual(request.status, "pending")

            projection = build_order_projection(db, order, "user", self.user)
            self.assertEqual(projection["cancel_request_state"], "pending")
            self.assertIn("view_cancel_request", projection["allowed_action_keys"])
            self.assertNotIn("request_cancel", projection["allowed_action_keys"])

            with self.assertRaises(HTTPException) as caught:
                cancellation_service.create_request(db, self.user, order.id, "再次申请")
            self.assertEqual(caught.exception.status_code, 409)

            withdrawn = cancellation_service.withdraw_request(db, self.user, order.id)
            self.assertEqual(withdrawn.status, "withdrawn")
            db.refresh(order)
            again = build_order_projection(db, order, "user", self.user)
            self.assertEqual(again["cancel_request_state"], "withdrawn")
            self.assertIn("request_cancel", again["allowed_action_keys"])
        finally:
            db.close()

    def test_approve_cancels_order_and_writes_messages(self) -> None:
        db = self.Session()
        try:
            order = self._order(db, "departing")
            request = cancellation_service.create_request(
                db, self.user, order.id, "师傅迟到"
            )
            approved = cancellation_service.approve_request(
                db, self.admin.id, request.id, "同意取消"
            )
            db.refresh(order)
            self.assertEqual(approved.status, "approved")
            self.assertEqual(order.status, "cancelled")
            self.assertEqual(order.version, 5)
            self.assertGreaterEqual(
                db.query(Message).filter(Message.owner_type == "user").count(), 1
            )
            self.assertGreaterEqual(
                db.query(Message).filter(Message.owner_type == "worker").count(), 1
            )
        finally:
            db.close()

    def test_reject_keeps_order(self) -> None:
        db = self.Session()
        try:
            order = self._order(db, "arrived")
            request = cancellation_service.create_request(
                db, self.user, order.id, "价格问题"
            )
            rejected = cancellation_service.reject_request(
                db, self.admin.id, request.id, "师傅已到达，建议协商继续服务"
            )
            db.refresh(order)
            self.assertEqual(rejected.status, "rejected")
            self.assertEqual(order.status, "arrived")
            projection = build_order_projection(db, order, "user", self.user)
            self.assertIn("request_cancel", projection["allowed_action_keys"])
        finally:
            db.close()

    def test_serving_order_must_use_dispute(self) -> None:
        db = self.Session()
        try:
            order = self._order(db, "serving")
            with self.assertRaises(HTTPException) as caught:
                cancellation_service.create_request(db, self.user, order.id, "不想做了")
            self.assertEqual(caught.exception.status_code, 409)
            self.assertIn("报告问题", caught.exception.detail)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

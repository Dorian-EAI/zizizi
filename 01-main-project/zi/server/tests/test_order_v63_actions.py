from __future__ import annotations

import asyncio
import json
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException

from tests._support import isolated_engine, session_factory
from app.models.message import Message
from app.models.order import Order
from app.models.service import ServiceType
from app.models.user import User, Worker
from app.models.deposit import WorkerDeposit
from app.models.wallet import Transaction
from app.models.worker_fund import WorkerFundEntry
from app.services import order_service, worker_fund_service


class OrderV63ActionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        self.tables = [
            User.__table__,
            Worker.__table__,
            WorkerDeposit.__table__,
            ServiceType.__table__,
            Order.__table__,
            Message.__table__,
            WorkerFundEntry.__table__,
            Transaction.__table__,
        ]
        for table in self.tables:
            table.create(self.engine)
        self.Session = session_factory(self.engine)

    def tearDown(self) -> None:
        for table in reversed(self.tables):
            table.drop(self.engine)
        self.engine.dispose()

    def _worker(self, db, openid: str = "wx-worker") -> Worker:
        worker = Worker(
            openid=openid,
            phone="13800000000",
            real_name="张师傅",
            id_card="encrypted-id",
            service_types=json.dumps(["repair"]),
            certified=2,
            is_active=True,
            balance=Decimal("0.00"),
        )
        db.add(worker)
        db.commit()
        db.refresh(worker)
        return worker

    def _order(
        self,
        db,
        *,
        status: str = "pending_dispatch",
        pricing_mode: str = "fixed_price",
        user_id: int = 7,
        worker_id: int | None = None,
        **extra,
    ) -> Order:
        order = Order(
            order_no=f"ORD-V63-{status}-{db.query(Order).count()}",
            user_id=user_id,
            worker_id=worker_id,
            service_type="repair",
            service_name="上门维修",
            status=status,
            pricing_mode=pricing_mode,
            budget=Decimal("100.00"),
            final_price=Decimal("100.00"),
            version=0,
            acceptance_state=extra.pop("acceptance_state", "not_required"),
            empty_run_fee_state=extra.pop("empty_run_fee_state", "none"),
            empty_run_fee_amount=extra.pop("empty_run_fee_amount", Decimal("0.00")),
            dispatch_acceleration_fee=extra.pop(
                "dispatch_acceleration_fee", Decimal("0.00")
            ),
            **extra,
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    def test_fixed_price_accept_is_atomic_and_rejects_bidding_order(self) -> None:
        db = self.Session()
        try:
            first = self._worker(db, "wx-first")
            second = self._worker(db, "wx-second")
            order = self._order(db)

            accepted = asyncio.run(order_service.accept_order(db, first, order.id))
            self.assertEqual(accepted.status, "accepted")
            self.assertEqual(accepted.worker_id, first.id)

            with self.assertRaises(HTTPException) as raised:
                asyncio.run(order_service.accept_order(db, second, order.id))
            self.assertEqual(raised.exception.status_code, 409)

            bidding_order = self._order(db, pricing_mode="bidding", status="pending")
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(order_service.accept_order(db, second, bidding_order.id))
            self.assertEqual(raised.exception.status_code, 409)
        finally:
            db.close()

    def test_confirm_acceptance_releases_pending_income(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            order = self._order(
                db,
                status="completed",
                worker_id=worker.id,
                acceptance_state="pending",
                acceptance_deadline=datetime.utcnow() + timedelta(days=7),
            )
            worker_fund_service.record_order_income(
                db,
                worker,
                order_no=order.order_no,
                payment_no="PAY-V63",
                amount=100,
            )
            db.commit()

            user = SimpleNamespace(id=order.user_id)
            accepted = order_service.confirm_acceptance(db, user, order.id, "accept")
            self.assertEqual(accepted.acceptance_state, "accepted")

            db.expire_all()
            self.assertEqual(db.get(Worker, worker.id).balance, Decimal("100.00"))
            buckets = worker_fund_service.get_buckets(db, db.get(Worker, worker.id))
            self.assertEqual(buckets["pending_settlement"], 0.0)
            self.assertEqual(buckets["available"], 100.0)
        finally:
            db.close()

    def test_dispute_requires_reason_and_keeps_order_frozen(self) -> None:
        db = self.Session()
        try:
            order = self._order(
                db,
                status="completed",
                acceptance_state="pending",
                acceptance_deadline=datetime.utcnow() + timedelta(days=7),
            )
            user = SimpleNamespace(id=order.user_id)
            with self.assertRaises(HTTPException) as raised:
                order_service.confirm_acceptance(db, user, order.id, "dispute")
            self.assertEqual(raised.exception.status_code, 400)

            disputed = order_service.confirm_acceptance(
                db, user, order.id, "dispute", "同一条管道仍然漏水"
            )
            self.assertEqual(disputed.acceptance_state, "disputed")
        finally:
            db.close()

    def test_empty_run_fee_confirm_and_dispute(self) -> None:
        db = self.Session()
        try:
            order = self._order(
                db,
                status="cancelled",
                empty_run_fee_state="pending",
                empty_run_fee_amount=Decimal("30.00"),
            )
            user = SimpleNamespace(id=order.user_id)

            paid = order_service.handle_empty_run_fee(db, user, order.id, "confirm")
            self.assertEqual(paid.empty_run_fee_state, "paid")

            order.empty_run_fee_state = "pending"
            db.commit()
            with self.assertRaises(HTTPException) as raised:
                order_service.handle_empty_run_fee(db, user, order.id, "dispute")
            self.assertEqual(raised.exception.status_code, 400)

            disputed = order_service.handle_empty_run_fee(
                db, user, order.id, "dispute", "师傅并未出发"
            )
            self.assertEqual(disputed.empty_run_fee_state, "disputed")
        finally:
            db.close()

    def test_accelerate_dispatch_charges_server_price_once(self) -> None:
        db = self.Session()
        try:
            order = self._order(db)
            user = SimpleNamespace(id=order.user_id)

            accelerated, package = order_service.accelerate_dispatch(
                db, user, order.id, "standard"
            )
            self.assertEqual(package["amount"], 19.0)
            self.assertEqual(accelerated.dispatch_acceleration_fee, Decimal("19.00"))
            self.assertEqual(accelerated.final_price, Decimal("119.00"))
            self.assertGreater(accelerated.version, 0)

            with self.assertRaises(HTTPException) as raised:
                order_service.accelerate_dispatch(db, user, order.id, "fast")
            self.assertEqual(raised.exception.status_code, 409)

            with self.assertRaises(HTTPException) as raised:
                order_service.accelerate_dispatch(db, user, order.id, "unknown")
            self.assertEqual(raised.exception.status_code, 422)
        finally:
            db.close()

    def test_risk_confirmation_validates_version_and_checkbox(self) -> None:
        db = self.Session()
        try:
            db.add(
                ServiceType(
                    key="repair",
                    name="上门维修",
                    risk_confirmation=json.dumps(
                        {"version": "v1", "items": ["高空作业需系安全绳"]},
                        ensure_ascii=False,
                    ),
                )
            )
            db.commit()
            order = self._order(db, status="pending_dispatch")
            user = SimpleNamespace(id=order.user_id)

            with self.assertRaises(HTTPException) as raised:
                order_service.confirm_risk_confirmation(
                    db, user, order.id, "v1", False
                )
            self.assertEqual(raised.exception.status_code, 422)

            with self.assertRaises(HTTPException) as raised:
                order_service.confirm_risk_confirmation(
                    db, user, order.id, "v0", True
                )
            self.assertEqual(raised.exception.status_code, 409)

            confirmed = order_service.confirm_risk_confirmation(
                db, user, order.id, "v1", True
            )
            self.assertEqual(confirmed.risk_confirmation_version, "v1")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

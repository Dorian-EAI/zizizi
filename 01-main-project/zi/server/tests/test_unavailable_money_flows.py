from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from fastapi import HTTPException

from tests._support import isolated_engine, session_factory
from app.config import settings
from app.database import Base
from app.models.admin import Admin
from app.models.annual_card import AnnualCardTemplate, UserAnnualCard
from app.models.coupon import Coupon, CouponTemplate
from app.models.insurance import InsuranceClaim, InsurancePolicy
from app.models.order import Order
from app.models.point import PointLog
from app.models.user import User, Worker
from app.models.wallet import Transaction
from app.services import (
    annual_card_service,
    insurance_service,
    payment_service,
    point_service,
)


class UnavailableMoneyFlowTests(unittest.TestCase):
    """Unimplemented money movement must fail before changing stored assets."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tables = [
            User.__table__,
            Worker.__table__,
            Admin.__table__,
            Order.__table__,
            AnnualCardTemplate.__table__,
            UserAnnualCard.__table__,
            PointLog.__table__,
            CouponTemplate.__table__,
            Coupon.__table__,
            InsurancePolicy.__table__,
            InsuranceClaim.__table__,
            Transaction.__table__,
        ]

    def setUp(self) -> None:
        self.engine = isolated_engine()
        Base.metadata.create_all(self.engine, tables=self.tables)
        self.db = session_factory(self.engine)()

    def tearDown(self) -> None:
        self.db.rollback()
        self.db.close()
        self.engine.dispose()

    def test_annual_card_purchase_does_not_charge_or_create_card(self) -> None:
        user = User(openid="annual-card-user", balance=Decimal("88.00"))
        template = AnnualCardTemplate(
            name="Standard annual card",
            price=9900,
            total_value=12000,
            service_count=6,
            is_active=True,
        )
        self.db.add_all([user, template])
        self.db.commit()

        with self.assertRaises(HTTPException) as raised:
            annual_card_service.purchase_card(self.db, user.id, template.id)
        self.assertEqual(raised.exception.status_code, 501)

        self.db.expire_all()
        self.assertEqual(self.db.get(User, user.id).balance, Decimal("88.00"))
        self.assertEqual(self.db.query(UserAnnualCard).count(), 0)
        self.assertFalse(self.db.new)
        self.assertFalse(self.db.dirty)

    def test_point_exchange_does_not_spend_points_or_issue_coupon(self) -> None:
        user = User(openid="point-exchange-user", balance=Decimal("0.00"))
        self.db.add(user)
        self.db.flush()
        self.db.add(
            PointLog(
                user_id=user.id,
                change=500,
                balance_after=500,
                reason="test credit",
            )
        )
        template = CouponTemplate(
            name="Exchange coupon",
            type="fixed",
            value=Decimal("10.0000"),
            min_spend=Decimal("50.00"),
            is_active=True,
        )
        self.db.add(template)
        self.db.commit()

        with self.assertRaises(HTTPException) as raised:
            point_service.exchange_coupon(self.db, user, template.id)
        self.assertEqual(raised.exception.status_code, 501)

        self.assertEqual(point_service._calc_balance(self.db, user.id), 500)
        self.assertEqual(self.db.query(PointLog).count(), 1)
        self.assertEqual(self.db.query(Coupon).count(), 0)
        self.assertFalse(self.db.new)
        self.assertFalse(self.db.dirty)

    def test_approved_insurance_claim_does_not_mark_or_pay_claim(self) -> None:
        user = User(openid="insurance-user", balance=Decimal("10.00"))
        worker = Worker(openid="insurance-worker", balance=Decimal("20.00"))
        admin = Admin(
            username="insurance-admin",
            password_hash="unused",
            role="super_admin",
            is_active=True,
        )
        self.db.add_all([user, worker, admin])
        self.db.flush()
        order = Order(
            order_no="ORD-INSURANCE-FAIL-CLOSED",
            user_id=user.id,
            worker_id=worker.id,
            service_type="repair",
            service_name="Repair",
            status="paid",
            completed_at=datetime.utcnow(),
        )
        self.db.add(order)
        self.db.flush()
        policy = InsurancePolicy(
            order_id=order.id,
            user_id=user.id,
            worker_id=worker.id,
            level="standard",
            premium=500,
            coverage=200000,
            status="active",
            claimed_amount=0,
            expired_at=datetime.utcnow() + timedelta(days=30),
        )
        self.db.add(policy)
        self.db.flush()
        claim = InsuranceClaim(
            policy_id=policy.id,
            order_id=order.id,
            user_id=user.id,
            worker_id=worker.id,
            reason="Covered accidental damage",
            evidence_images=["https://example.invalid/evidence.jpg"],
            claim_amount=5000,
            status="pending",
            settled_amount=0,
        )
        self.db.add(claim)
        self.db.commit()

        with self.assertRaises(HTTPException) as raised:
            insurance_service.audit_claim(
                self.db,
                admin_id=admin.id,
                claim_id=claim.id,
                status="approved",
                settled_amount=5000,
                remark="approved for test",
            )
        self.assertEqual(raised.exception.status_code, 501)

        self.db.expire_all()
        stored_claim = self.db.get(InsuranceClaim, claim.id)
        stored_policy = self.db.get(InsurancePolicy, policy.id)
        self.assertEqual(stored_claim.status, "pending")
        self.assertEqual(stored_claim.settled_amount, 0)
        self.assertIsNone(stored_claim.audited_at)
        self.assertIsNone(stored_claim.settled_at)
        self.assertEqual(stored_policy.status, "active")
        self.assertEqual(stored_policy.claimed_amount, 0)
        self.assertEqual(self.db.get(User, user.id).balance, Decimal("10.00"))
        self.assertEqual(self.db.get(Worker, worker.id).balance, Decimal("20.00"))
        self.assertFalse(self.db.new)
        self.assertFalse(self.db.dirty)

    def test_production_withdrawal_does_not_reserve_balance_or_create_tx(self) -> None:
        worker = Worker(
            openid="production-withdraw-worker",
            balance=Decimal("100.00"),
        )
        self.db.add(worker)
        self.db.commit()

        with (
            patch.object(settings, "APP_ENV", "production"),
            patch.object(settings, "WX_PAY_MOCK_ENABLED", False),
        ):
            with self.assertRaises(HTTPException) as raised:
                payment_service.withdraw(
                    self.db,
                    worker,
                    "worker",
                    20.00,
                    "wechat",
                )
        self.assertEqual(raised.exception.status_code, 503)

        self.db.expire_all()
        self.assertEqual(self.db.get(Worker, worker.id).balance, Decimal("100.00"))
        self.assertEqual(self.db.query(Transaction).count(), 0)
        self.assertFalse(self.db.new)
        self.assertFalse(self.db.dirty)


if __name__ == "__main__":
    unittest.main()

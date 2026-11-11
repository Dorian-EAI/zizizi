from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from tests._support import isolated_engine, session_factory
from app.models.extra_fee import OrderExtraFee
from app.models.order import Order
from app.models.user import User, Worker
from app.services.extra_fee_service import get_overdue_pending_ids


class ExtraFeeOverdueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        User.__table__.create(self.engine)
        Worker.__table__.create(self.engine)
        Order.__table__.create(self.engine)
        OrderExtraFee.__table__.create(self.engine)
        self.Session = session_factory(self.engine)

    def tearDown(self) -> None:
        OrderExtraFee.__table__.drop(self.engine)
        Order.__table__.drop(self.engine)
        Worker.__table__.drop(self.engine)
        User.__table__.drop(self.engine)
        self.engine.dispose()

    def test_overdue_scan_never_changes_status_or_amount(self) -> None:
        now = datetime.utcnow()
        db = self.Session()
        try:
            overdue = OrderExtraFee(
                order_id=1,
                worker_id=1,
                user_id=1,
                items=[],
                total_amount=2500,
                reason="材料升级",
                status="pending",
                created_at=now - timedelta(hours=25),
            )
            recent = OrderExtraFee(
                order_id=2,
                worker_id=1,
                user_id=2,
                items=[],
                total_amount=3000,
                reason="新增项目",
                status="pending",
                created_at=now - timedelta(hours=1),
            )
            db.add_all([overdue, recent])
            db.commit()

            self.assertEqual(get_overdue_pending_ids(db), [overdue.id])
            db.expire_all()
            persisted = db.query(OrderExtraFee).filter(OrderExtraFee.id == overdue.id).one()
            self.assertEqual(persisted.status, "pending")
            self.assertEqual(persisted.total_amount, 2500)
            self.assertIsNone(persisted.resolved_at)
            self.assertIsNone(persisted.user_remark)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

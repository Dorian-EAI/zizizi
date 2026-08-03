from __future__ import annotations

import unittest

from fastapi import HTTPException

from tests._support import isolated_engine, session_factory
from app.database import Base
from app.models.order import Order
from app.services.order_service import _cas_update_status


class OrderStateMachineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        Order.__table__.create(self.engine)
        self.Session = session_factory(self.engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine, tables=[Order.__table__])
        self.engine.dispose()

    def _new_order(self, status: str = "pending") -> Order:
        db = self.Session()
        try:
            order = Order(
                order_no=f"ORD-{status}-{id(self)}",
                user_id=1,
                service_type="repair",
                service_name="Repair",
                status=status,
                version=0,
            )
            db.add(order)
            db.commit()
            db.expunge(order)
            return order
        finally:
            db.close()

    def test_valid_transition_increments_version(self) -> None:
        detached = self._new_order()
        db = self.Session()
        try:
            order = db.get(Order, detached.id)
            self.assertTrue(
                _cas_update_status(
                    db,
                    order,
                    "accepted",
                    allowed_from=["pending"],
                    worker_id=9,
                )
            )
            db.commit()
            db.expire_all()
            updated = db.get(Order, detached.id)
            self.assertEqual(updated.status, "accepted")
            self.assertEqual(updated.worker_id, 9)
            self.assertEqual(updated.version, 1)
        finally:
            db.close()

    def test_illegal_transition_is_rejected(self) -> None:
        detached = self._new_order()
        db = self.Session()
        try:
            order = db.get(Order, detached.id)
            with self.assertRaises(HTTPException) as raised:
                _cas_update_status(
                    db,
                    order,
                    "paid",
                    allowed_from=["completed"],
                )
            self.assertEqual(raised.exception.status_code, 400)
            self.assertEqual(db.get(Order, detached.id).status, "pending")
        finally:
            db.close()

    def test_stale_version_returns_conflict(self) -> None:
        detached = self._new_order()
        db = self.Session()
        try:
            stale = db.get(Order, detached.id)
            db.query(Order).filter(Order.id == detached.id).update(
                {"status": "accepted", "version": 1},
                synchronize_session=False,
            )
            db.commit()

            # expire_on_commit=False deliberately leaves ``stale.version`` at
            # zero, reproducing an update based on an outdated API read.
            self.assertEqual(stale.version, 0)
            with self.assertRaises(HTTPException) as raised:
                _cas_update_status(
                    db,
                    stale,
                    "cancelled",
                    allowed_from=["pending"],
                )
            self.assertEqual(raised.exception.status_code, 409)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

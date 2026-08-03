from __future__ import annotations

import asyncio
import unittest
from decimal import Decimal
from unittest.mock import patch

from fastapi import HTTPException

from tests._support import isolated_engine, session_factory
from app.api.wxpay import transfer_approve
from app.models.user import Worker
from app.models.wallet import Transaction


class WithdrawApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        Worker.__table__.create(self.engine)
        Transaction.__table__.create(self.engine)
        self.Session = session_factory(self.engine)

    def tearDown(self) -> None:
        Transaction.__table__.drop(self.engine)
        Worker.__table__.drop(self.engine)
        self.engine.dispose()

    def _seed(self, *, active: bool, certified: int) -> int:
        db = self.Session()
        try:
            worker = Worker(
                openid=f"worker-{active}-{certified}",
                is_active=active,
                certified=certified,
                balance=Decimal("90.00"),
            )
            db.add(worker)
            db.flush()
            tx = Transaction(
                owner_type="worker",
                owner_id=worker.id,
                type="withdraw",
                amount=Decimal("10.00"),
                balance_after=Decimal("90.00"),
                method="wechat",
                status="pending",
            )
            db.add(tx)
            db.commit()
            return tx.id
        finally:
            db.close()

    def test_disabled_or_uncertified_worker_cannot_be_approved(self) -> None:
        for active, certified, expected_status in ((False, 2, 403), (True, 1, 403)):
            tx_id = self._seed(active=active, certified=certified)
            db = self.Session()
            try:
                with patch(
                    "app.api.wxpay.wechat_pay_service.create_transfer_to_worker"
                ) as transfer:
                    with self.assertRaises(HTTPException) as raised:
                        asyncio.run(transfer_approve(tx_id, admin=object(), db=db))
                self.assertEqual(raised.exception.status_code, expected_status)
                transfer.assert_not_called()
            finally:
                db.close()

    def test_active_certified_worker_reaches_fail_closed_transfer_service(self) -> None:
        tx_id = self._seed(active=True, certified=2)
        db = self.Session()
        try:
            with patch(
                "app.api.wxpay.wechat_pay_service.create_transfer_to_worker",
                side_effect=HTTPException(status_code=503, detail="真实转账未启用"),
            ) as transfer:
                with self.assertRaises(HTTPException) as raised:
                    asyncio.run(transfer_approve(tx_id, admin=object(), db=db))
            self.assertEqual(raised.exception.status_code, 503)
            transfer.assert_called_once()
            self.assertEqual(db.query(Transaction).filter(Transaction.id == tx_id).one().status, "pending")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

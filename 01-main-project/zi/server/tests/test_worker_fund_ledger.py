from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from tests._support import isolated_engine, session_factory
from app.config import settings
from app.models.admin import AdminAuditLog
from app.models.deposit import WorkerDeposit
from app.models.order import Order
from app.models.user import Worker
from app.models.wallet import RefundOrder, Transaction
from app.models.worker_fund import WorkerFundEntry
from app.services import (
    admin_service,
    deposit_service,
    payment_service,
    wechat_pay_service,
    worker_fund_service,
)


class WorkerFundLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        Worker.__table__.create(self.engine)
        Transaction.__table__.create(self.engine)
        WorkerFundEntry.__table__.create(self.engine)
        self.Session = session_factory(self.engine)

    def tearDown(self) -> None:
        WorkerFundEntry.__table__.drop(self.engine)
        Transaction.__table__.drop(self.engine)
        Worker.__table__.drop(self.engine)
        self.engine.dispose()

    def _worker(self, db, balance: str = "100.00") -> Worker:
        worker = Worker(openid=f"ledger-{balance}", balance=Decimal(balance))
        db.add(worker)
        db.commit()
        return worker

    def _entries(self, db, worker: Worker) -> list[WorkerFundEntry]:
        return (
            db.query(WorkerFundEntry)
            .filter(WorkerFundEntry.worker_id == worker.id)
            .order_by(WorkerFundEntry.id.asc())
            .all()
        )

    def _income(self, db, worker: Worker, amount=30, order_no="ORD-1", payment_no="PAY-1"):
        worker_fund_service.record_order_income(
            db, worker, order_no=order_no, payment_no=payment_no, amount=amount
        )
        db.commit()

    def _backdate_pending(self, db, worker: Worker, hours: int = 25) -> None:
        db.query(WorkerFundEntry).filter(
            WorkerFundEntry.worker_id == worker.id,
            WorkerFundEntry.bucket == "pending_settlement",
        ).update({"created_at": datetime.utcnow() - timedelta(hours=hours)})
        db.commit()

    def test_opening_entry_uses_balance_before_change(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db, "100.00")
            self._income(db, worker, 30)

            entries = self._entries(db, worker)
            opening = [item for item in entries if item.reference_type == "opening"]
            self.assertEqual(len(opening), 1)
            self.assertEqual(opening[0].amount, Decimal("100.00"))
            self.assertEqual(opening[0].balance_after, Decimal("100.00"))

            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertEqual(buckets["available"], 100.0)
            self.assertEqual(buckets["pending_settlement"], 30.0)
            self.assertTrue(buckets["ledger_complete"])
            self.assertEqual(buckets["settlement_hold_hours"], 24)
            self.assertIsNotNone(buckets["next_settle_at"])
            self.assertEqual(db.get(Worker, worker.id).balance, Decimal("100.00"))
        finally:
            db.close()

    def test_order_income_is_idempotent(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            for _ in range(2):
                worker_fund_service.record_order_income(
                    db, worker, order_no="ORD-1", payment_no="PAY-1", amount=30
                )
            db.commit()

            incomes = [
                item
                for item in self._entries(db, worker)
                if item.reference_type == "order_income"
            ]
            self.assertEqual(len(incomes), 1)
            self.assertEqual(incomes[0].amount, Decimal("30.00"))
            self.assertEqual(incomes[0].bucket, "pending_settlement")
        finally:
            db.close()

    def test_settlement_releases_pending_income_after_hold(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            self._income(db, worker, 30)
            self._backdate_pending(db, worker)

            stats = worker_fund_service.settle_pending_income(db)
            db.commit()
            self.assertEqual(stats["settled_count"], 1)
            self.assertEqual(stats["settled_amount"], 30.0)

            db.expire_all()
            worker = db.get(Worker, worker.id)
            self.assertEqual(worker.balance, Decimal("130.00"))
            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertEqual(buckets["pending_settlement"], 0.0)
            self.assertEqual(buckets["available"], 130.0)
            self.assertIsNone(buckets["next_settle_at"])

            income_txs = (
                db.query(Transaction)
                .filter(Transaction.owner_type == "worker", Transaction.type == "income")
                .all()
            )
            self.assertEqual(len(income_txs), 1)
            self.assertEqual(income_txs[0].amount, Decimal("30.00"))
        finally:
            db.close()

    def test_settlement_is_idempotent(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            self._income(db, worker, 30)
            self._backdate_pending(db, worker)

            worker_fund_service.settle_pending_income(db)
            db.commit()
            second = worker_fund_service.settle_pending_income(db)
            db.commit()

            self.assertEqual(second["settled_count"], 0)
            db.expire_all()
            self.assertEqual(db.get(Worker, worker.id).balance, Decimal("130.00"))
            self.assertEqual(
                db.query(Transaction)
                .filter(Transaction.owner_type == "worker", Transaction.type == "income")
                .count(),
                1,
            )
        finally:
            db.close()

    def test_settlement_waits_for_hold_period(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            self._income(db, worker, 30)

            with patch.object(settings, "WORKER_SETTLEMENT_HOLD_HOURS", 24):
                stats = worker_fund_service.settle_pending_income(db)
            db.commit()

            self.assertEqual(stats["settled_count"], 0)
            db.expire_all()
            self.assertEqual(db.get(Worker, worker.id).balance, Decimal("100.00"))
            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertEqual(buckets["pending_settlement"], 30.0)
        finally:
            db.close()

    def test_refund_during_hold_reverses_pending_first(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            self._income(db, worker, 50)

            available_cut = worker_fund_service.record_refund_reversal(
                db, worker, refund_no="REF-1", order_no="ORD-1", amount=20
            )
            db.commit()

            self.assertEqual(available_cut, Decimal("0.00"))
            db.expire_all()
            self.assertEqual(db.get(Worker, worker.id).balance, Decimal("100.00"))
            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertEqual(buckets["pending_settlement"], 30.0)
            self.assertEqual(buckets["available"], 100.0)
            self.assertEqual(buckets["reversed"], 20.0)

            # 剩余待结算金额到期仍可正常结算
            self._backdate_pending(db, worker)
            stats = worker_fund_service.settle_pending_income(db)
            db.commit()
            self.assertEqual(stats["settled_amount"], 30.0)
            db.expire_all()
            self.assertEqual(db.get(Worker, worker.id).balance, Decimal("130.00"))
        finally:
            db.close()

    def test_refund_after_settlement_debits_available(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            self._income(db, worker, 30)
            self._backdate_pending(db, worker)
            worker_fund_service.settle_pending_income(db)
            db.commit()

            available_cut = worker_fund_service.record_refund_reversal(
                db, worker, refund_no="REF-2", order_no="ORD-1", amount=20
            )
            db.commit()

            self.assertEqual(available_cut, Decimal("20.00"))
            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertEqual(buckets["pending_settlement"], 0.0)
            self.assertEqual(buckets["available"], 110.0)
            self.assertEqual(buckets["reversed"], 20.0)
        finally:
            db.close()

    def test_fully_refunded_pending_does_not_block_batch(self) -> None:
        db = self.Session()
        try:
            refunded = Worker(openid="ledger-refunded", balance=Decimal("0.00"))
            pending = Worker(openid="ledger-pending", balance=Decimal("100.00"))
            db.add_all([refunded, pending])
            db.commit()

            self._income(db, refunded, 20, order_no="ORD-R", payment_no="PAY-R")
            self._income(db, pending, 30, order_no="ORD-P", payment_no="PAY-P")
            worker_fund_service.record_refund_reversal(
                db, refunded, refund_no="REF-FULL", order_no="ORD-R", amount=20
            )
            db.commit()

            for worker in (refunded, pending):
                db.query(WorkerFundEntry).filter(
                    WorkerFundEntry.worker_id == worker.id,
                    WorkerFundEntry.bucket == "pending_settlement",
                ).update(
                    {"created_at": datetime.utcnow() - timedelta(hours=25)},
                    synchronize_session=False,
                )
            db.commit()

            stats = worker_fund_service.settle_pending_income(db, limit=1)
            db.commit()
            self.assertEqual(stats["settled_count"], 1)
            self.assertEqual(stats["settled_amount"], 30.0)

            db.expire_all()
            self.assertEqual(db.get(Worker, pending.id).balance, Decimal("130.00"))
            refunded_buckets = worker_fund_service.get_buckets(db, db.get(Worker, refunded.id))
            self.assertEqual(refunded_buckets["pending_settlement"], 0.0)
            self.assertEqual(refunded_buckets["reversed"], 20.0)
        finally:
            db.close()

    def test_refund_freeze_then_reversal_does_not_double_debit_balance(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            self._income(db, worker, 50)
            self._backdate_pending(db, worker)
            worker_fund_service.settle_pending_income(db)
            db.commit()

            frozen = worker_fund_service.record_refund_freeze(
                db, worker, refund_no="REF-F", order_no="ORD-1", amount=30
            )
            db.commit()
            self.assertEqual(frozen, Decimal("30.00"))
            db.expire_all()
            worker = db.get(Worker, worker.id)
            self.assertEqual(worker.balance, Decimal("120.00"))
            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertEqual(buckets["available"], 120.0)
            self.assertEqual(buckets["frozen"], 30.0)

            available_cut = worker_fund_service.record_refund_reversal(
                db, worker, refund_no="REF-F", order_no="ORD-1", amount=30
            )
            db.commit()
            self.assertEqual(available_cut, Decimal("0.00"))
            db.expire_all()
            worker = db.get(Worker, worker.id)
            self.assertEqual(worker.balance, Decimal("120.00"))
            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertEqual(buckets["frozen"], 0.0)
            self.assertEqual(buckets["available"], 120.0)
            self.assertEqual(buckets["reversed"], 30.0)
        finally:
            db.close()

    def test_refund_freeze_release_restores_available(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            frozen = worker_fund_service.record_refund_freeze(
                db, worker, refund_no="REF-R", order_no="ORD-1", amount=30
            )
            db.commit()
            self.assertEqual(frozen, Decimal("30.00"))

            released = worker_fund_service.release_refund_freeze(
                db, worker, refund_no="REF-R"
            )
            db.commit()
            self.assertEqual(released, Decimal("30.00"))
            db.expire_all()
            worker = db.get(Worker, worker.id)
            self.assertEqual(worker.balance, Decimal("100.00"))
            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertEqual(buckets["available"], 100.0)
            self.assertEqual(buckets["frozen"], 0.0)
            self.assertEqual(
                worker_fund_service.release_refund_freeze(db, worker, refund_no="REF-R"),
                Decimal("0.00"),
            )
        finally:
            db.close()

    def test_refund_freeze_is_idempotent_and_capped_by_available(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            first = worker_fund_service.record_refund_freeze(
                db, worker, refund_no="REF-C", order_no="ORD-1", amount=150
            )
            db.commit()
            self.assertEqual(first, Decimal("100.00"))

            second = worker_fund_service.record_refund_freeze(
                db, worker, refund_no="REF-C", order_no="ORD-1", amount=150
            )
            db.commit()
            self.assertEqual(second, Decimal("100.00"))

            db.expire_all()
            worker = db.get(Worker, worker.id)
            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertEqual(buckets["available"], 0.0)
            self.assertEqual(buckets["frozen"], 100.0)
        finally:
            db.close()

    def test_refund_failure_releases_frozen_income(self) -> None:
        Order.__table__.create(self.engine)
        RefundOrder.__table__.create(self.engine)
        try:
            db = self.Session()
            try:
                worker = self._worker(db)
                worker_fund_service.record_refund_freeze(
                    db, worker, refund_no="REF-X", order_no="ORD-X", amount=40
                )
                order = Order(
                    order_no="ORD-X",
                    user_id=1,
                    worker_id=worker.id,
                    service_type="repair",
                    service_name="维修",
                    final_price=Decimal("40.00"),
                    status="paid",
                )
                db.add(order)
                db.flush()
                refund = RefundOrder(
                    refund_no="REF-X",
                    payment_no="PAY-X",
                    order_no="ORD-X",
                    amount=Decimal("40.00"),
                    total_amount=Decimal("40.00"),
                    method="wechat",
                    payer_type="user",
                    payer_id=1,
                    status="pending",
                )
                db.add(refund)
                db.commit()

                released = wechat_pay_service._update_pending_refund_state(
                    db, refund.id, status="failed", last_error="微信退款已关闭"
                )
                self.assertTrue(released)

                db.expire_all()
                stored = db.get(RefundOrder, refund.id)
                self.assertEqual(stored.status, "failed")
                worker = db.get(Worker, worker.id)
                self.assertEqual(worker.balance, Decimal("100.00"))
                buckets = worker_fund_service.get_buckets(db, worker)
                self.assertEqual(buckets["frozen"], 0.0)
                self.assertEqual(buckets["available"], 100.0)
            finally:
                db.close()
        finally:
            RefundOrder.__table__.drop(self.engine)
            Order.__table__.drop(self.engine)

    def test_bucket_composition_items(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            self._income(db, worker, 30)

            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertEqual(len(buckets["pending_items"]), 1)
            item = buckets["pending_items"][0]
            self.assertEqual(item["order_no"], "ORD-1")
            self.assertEqual(item["amount"], 30.0)
            self.assertIsNotNone(item["expected_settle_at"])
            self.assertEqual(buckets["frozen_items"], [])

            self._backdate_pending(db, worker)
            worker_fund_service.settle_pending_income(db)
            db.commit()
            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertEqual(buckets["pending_items"], [])

            worker_fund_service.record_refund_freeze(
                db, worker, refund_no="REF-I", order_no="ORD-1", amount=20
            )
            db.commit()
            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertEqual(len(buckets["frozen_items"]), 1)
            self.assertEqual(buckets["frozen_items"][0]["amount"], 20.0)
            self.assertEqual(buckets["frozen_items"][0]["refund_no"], "REF-I")
        finally:
            db.close()

    def test_order_income_applies_snapshot_fee(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            worker_fund_service.record_order_income(
                db,
                worker,
                order_no="ORD-FEE",
                payment_no="PAY-FEE",
                amount=100,
                fee_rate=0.12,
            )
            db.commit()

            entries = self._entries(db, worker)
            fee_entries = [
                item for item in entries if item.reference_type == "platform_fee"
            ]
            self.assertEqual(len(fee_entries), 1)
            self.assertEqual(fee_entries[0].amount, Decimal("12.00"))
            self.assertEqual(fee_entries[0].direction, "debit")
            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertEqual(buckets["pending_settlement"], 88.0)
            self.assertEqual(buckets["available"], 100.0)
        finally:
            db.close()

    def test_refund_clawback_is_proportional_to_net_income(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            worker_fund_service.record_order_income(
                db,
                worker,
                order_no="ORD-FEE",
                payment_no="PAY-FEE",
                amount=100,
                fee_rate=0.12,
            )
            db.commit()

            available_cut = worker_fund_service.record_refund_reversal(
                db,
                worker,
                refund_no="REF-FEE",
                order_no="ORD-FEE",
                amount=50,
                payment_no="PAY-FEE",
            )
            db.commit()

            self.assertEqual(available_cut, Decimal("0.00"))
            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertEqual(buckets["pending_settlement"], 44.0)
            self.assertEqual(buckets["reversed"], 44.0)
            self.assertEqual(buckets["available"], 100.0)
        finally:
            db.close()

    def test_settlement_uses_net_income_and_reports_fee(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            worker_fund_service.record_order_income(
                db,
                worker,
                order_no="ORD-FEE",
                payment_no="PAY-FEE",
                amount=100,
                fee_rate=0.12,
            )
            db.commit()
            self._backdate_pending(db, worker)

            stats = worker_fund_service.settle_pending_income(db)
            db.commit()
            self.assertEqual(stats["settled_amount"], 88.0)

            db.expire_all()
            worker = db.get(Worker, worker.id)
            self.assertEqual(worker.balance, Decimal("188.00"))
            tx = (
                db.query(Transaction)
                .filter(Transaction.owner_type == "worker", Transaction.type == "income")
                .one()
            )
            self.assertEqual(tx.amount, Decimal("88.00"))
            self.assertIn("平台服务费", tx.description)
        finally:
            db.close()

    def test_platform_cut_rate_defaults_and_follows_deposit(self) -> None:
        WorkerDeposit.__table__.create(self.engine)
        try:
            db = self.Session()
            try:
                worker = self._worker(db)
                default_rate = deposit_service.get_platform_cut_rate(db, worker.id)
                self.assertEqual(default_rate, Decimal("0.15"))

                db.add(
                    WorkerDeposit(
                        worker_id=worker.id,
                        deposit_level="gold",
                        platform_cut_rate=Decimal("0.100"),
                    )
                )
                db.commit()
                rate = deposit_service.get_platform_cut_rate(db, worker.id)
                self.assertEqual(rate, Decimal("0.10"))
            finally:
                db.close()
        finally:
            WorkerDeposit.__table__.drop(self.engine)

    def test_settlement_list_shows_fee_and_status(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            worker_fund_service.record_order_income(
                db,
                worker,
                order_no="ORD-FEE",
                payment_no="PAY-FEE",
                amount=100,
                fee_rate=0.12,
            )
            db.commit()

            result = worker_fund_service.get_settlements(db, worker)
            self.assertEqual(result["total"], 1)
            item = result["list"][0]
            self.assertEqual(item["order_income"], 100.0)
            self.assertEqual(item["platform_fee"], 12.0)
            self.assertEqual(item["net_income"], 88.0)
            self.assertEqual(item["status"], "pending_settlement")
            self.assertIsNotNone(item["expected_settle_at"])
            self.assertIsNone(item["settled_at"])

            self._backdate_pending(db, worker)
            worker_fund_service.settle_pending_income(db)
            db.commit()

            result = worker_fund_service.get_settlements(db, worker)
            item = result["list"][0]
            self.assertEqual(item["status"], "settled")
            self.assertEqual(item["net_income"], 88.0)
            self.assertIsNotNone(item["settled_at"])
        finally:
            db.close()

    def test_withdraw_config_and_quote(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            with (
                patch.object(settings, "WITHDRAW_MIN_AMOUNT", 10.0),
                patch.object(settings, "WITHDRAW_FEE_RATE", 0.0),
                patch.object(settings, "WITHDRAW_FEE_FIXED", 0.0),
                patch.object(settings, "WITHDRAW_DAILY_LIMIT", 3),
            ):
                config = payment_service.get_withdraw_config(db, worker)
                self.assertEqual(config["min_amount"], 10.0)
                self.assertEqual(config["daily_limit"], 3)
                self.assertEqual(config["remaining_today"], 3)
                methods = {item["key"]: item for item in config["methods"]}
                self.assertTrue(methods["wechat"]["enabled"])
                self.assertFalse(methods["bank"]["enabled"])

                valid = payment_service.get_withdraw_quote(db, worker, 50)
                self.assertTrue(valid["valid"])
                self.assertEqual(valid["fee"], 0.0)
                self.assertEqual(valid["arrival_amount"], 50.0)

                too_small = payment_service.get_withdraw_quote(db, worker, 5)
                self.assertFalse(too_small["valid"])
                self.assertIn("最低提现", too_small["reason"])

                too_large = payment_service.get_withdraw_quote(db, worker, 150)
                self.assertFalse(too_large["valid"])
                self.assertIn("余额不足", too_large["reason"])
        finally:
            db.close()

    def test_withdraw_quote_applies_fee(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            with (
                patch.object(settings, "WITHDRAW_FEE_RATE", 0.01),
                patch.object(settings, "WITHDRAW_FEE_FIXED", 1.0),
            ):
                quote = payment_service.get_withdraw_quote(db, worker, 100)
            self.assertEqual(quote["fee"], 2.0)
            self.assertEqual(quote["arrival_amount"], 98.0)
        finally:
            db.close()

    def test_withdraw_rejects_when_daily_limit_reached(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            for _ in range(3):
                db.add(
                    Transaction(
                        owner_type="worker",
                        owner_id=worker.id,
                        type="withdraw",
                        amount=Decimal("10.00"),
                        balance_after=Decimal("90.00"),
                        method="wechat",
                        status="pending",
                    )
                )
            db.commit()

            with (
                patch.object(settings, "APP_ENV", "development"),
                patch.object(settings, "WX_PAY_MOCK_ENABLED", True),
                patch.object(settings, "WITHDRAW_DAILY_LIMIT", 3),
            ):
                with self.assertRaises(HTTPException) as raised:
                    payment_service.withdraw(db, worker, "worker", 10, "wechat")
            self.assertEqual(raised.exception.status_code, 400)
            self.assertIn("上限", raised.exception.detail)
            db.expire_all()
            self.assertEqual(db.get(Worker, worker.id).balance, Decimal("100.00"))
        finally:
            db.close()

    def test_withdraw_reject_returns_funds_to_available(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            tx = Transaction(
                owner_type="worker",
                owner_id=worker.id,
                type="withdraw",
                amount=Decimal("30.00"),
                balance_after=Decimal("70.00"),
                method="wechat",
                status="pending",
            )
            db.add(tx)
            db.commit()

            # 与真实提现顺序一致：先写期初，再扣余额、记申请分录。
            worker_fund_service.ensure_opening(db, worker)
            worker.balance = Decimal("70.00")
            worker_fund_service.record_withdraw_request(db, worker, tx)
            db.commit()

            worker_fund_service.record_withdraw_reject(db, worker, tx)
            db.commit()

            db.expire_all()
            worker = db.get(Worker, worker.id)
            self.assertEqual(worker.balance, Decimal("100.00"))
            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertEqual(buckets["available"], 100.0)
            self.assertEqual(buckets["withdrawing"], 0.0)
            self.assertEqual(buckets["withdrawn"], 0.0)
        finally:
            db.close()

    def test_admin_reject_withdraw_restores_balance(self) -> None:
        AdminAuditLog.__table__.create(self.engine)
        try:
            db = self.Session()
            try:
                worker = self._worker(db)
                tx = Transaction(
                    owner_type="worker",
                    owner_id=worker.id,
                    type="withdraw",
                    amount=Decimal("30.00"),
                    balance_after=Decimal("70.00"),
                    method="wechat",
                    status="pending",
                )
                db.add(tx)
                db.commit()
                worker_fund_service.ensure_opening(db, worker)
                worker.balance = Decimal("70.00")
                worker_fund_service.record_withdraw_request(db, worker, tx)
                db.commit()

                with patch(
                    "app.services.message_service.notify_withdraw_failed",
                    new=AsyncMock(),
                ):
                    result = asyncio.run(
                        admin_service.reject_withdraw(
                            db, tx.id, admin_id=1, reason="收款账户信息有误"
                        )
                    )

                self.assertEqual(result["status"], "failed")
                db.expire_all()
                stored = db.get(Transaction, tx.id)
                self.assertEqual(stored.status, "failed")
                self.assertIn("驳回", stored.description)
                worker = db.get(Worker, worker.id)
                self.assertEqual(worker.balance, Decimal("100.00"))
                buckets = worker_fund_service.get_buckets(db, worker)
                self.assertEqual(buckets["available"], 100.0)
                self.assertEqual(buckets["withdrawing"], 0.0)
            finally:
                db.close()
        finally:
            AdminAuditLog.__table__.drop(self.engine)

    def test_worker_wallet_info_includes_bucket_fields(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            db.add(
                Transaction(
                    owner_type="worker",
                    owner_id=worker.id,
                    type="withdraw",
                    amount=Decimal("20.00"),
                    balance_after=Decimal("80.00"),
                    method="wechat",
                    status="success",
                )
            )
            db.commit()

            info = payment_service.get_wallet_info(db, worker, "worker")
            self.assertEqual(info["available"], 100.0)
            self.assertEqual(info["pending_settlement"], 0.0)
            self.assertEqual(info["frozen"], 0.0)
            self.assertEqual(info["total_withdrawn"], 20.0)

            worker_fund_service.record_order_income(
                db, worker, order_no="ORD-W", payment_no="PAY-W", amount=30
            )
            db.commit()
            info = payment_service.get_wallet_info(db, worker, "worker")
            self.assertEqual(info["pending_settlement"], 30.0)
        finally:
            db.close()

    def test_withdraw_request_and_success_move_between_buckets(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db)
            tx = Transaction(
                owner_type="worker",
                owner_id=worker.id,
                type="withdraw",
                amount=Decimal("30.00"),
                balance_after=Decimal("70.00"),
                method="wechat",
                status="pending",
            )
            db.add(tx)
            db.commit()

            worker_fund_service.record_withdraw_request(db, worker, tx)
            db.commit()

            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertEqual(buckets["available"], 70.0)
            self.assertEqual(buckets["withdrawing"], 30.0)
            self.assertEqual(buckets["withdrawn"], 0.0)

            worker_fund_service.record_withdraw_success(db, worker, tx)
            db.commit()

            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertEqual(buckets["withdrawing"], 0.0)
            self.assertEqual(buckets["withdrawn"], 30.0)
        finally:
            db.close()

    def test_withdraw_success_backfills_missing_request_entry(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db, "70.00")
            tx = Transaction(
                owner_type="worker",
                owner_id=worker.id,
                type="withdraw",
                amount=Decimal("30.00"),
                balance_after=Decimal("70.00"),
                method="wechat",
                status="success",
            )
            db.add(tx)
            db.commit()

            worker_fund_service.record_withdraw_success(db, worker, tx)
            db.commit()

            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertEqual(buckets["withdrawing"], 0.0)
            self.assertEqual(buckets["withdrawn"], 30.0)
        finally:
            db.close()

    def test_get_buckets_falls_back_to_balance_and_transactions(self) -> None:
        db = self.Session()
        try:
            worker = self._worker(db, "80.00")
            db.add(
                Transaction(
                    owner_type="worker",
                    owner_id=worker.id,
                    type="withdraw",
                    amount=Decimal("20.00"),
                    balance_after=Decimal("80.00"),
                    method="wechat",
                    status="pending",
                )
            )
            db.commit()

            buckets = worker_fund_service.get_buckets(db, worker)
            self.assertFalse(buckets["ledger_complete"])
            self.assertEqual(buckets["available"], 80.0)
            self.assertEqual(buckets["withdrawing"], 20.0)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

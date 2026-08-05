from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from tests._support import import_all_models, isolated_engine, session_factory

import_all_models()

from app.api.wallet import router as wallet_router
from app.config import settings
from app.database import Base, get_db
from app.dependencies import get_current_user, get_current_worker, require_super_admin
from app.models.idempotency import IdempotencyRequest
from app.models.order import Order
from app.models.user import User, Worker
from app.models.wallet import PaymentOrder, RefundOrder, Transaction
from app.services import payment_service


PAY_PARAMS = {
    "appId": "wx24ce7985708686b4",
    "timeStamp": "1",
    "nonceStr": "nonce",
    "package": "prepay_id=mock",
    "signType": "RSA",
    "paySign": "signature",
}


class FinancialRequestIdempotencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        Base.metadata.create_all(self.engine)
        self.Session = session_factory(self.engine)
        db = self.Session()
        try:
            self.user = User(
                openid="financial-idempotency-user",
                nickname="用户",
                balance=Decimal("100.00"),
                is_active=True,
            )
            db.add(self.user)
            db.flush()
            self.worker = Worker(
                openid="financial-idempotency-worker",
                nickname="师傅",
                balance=Decimal("100.00"),
                is_active=True,
            )
            db.add(self.worker)
            db.flush()
            db.add(
                Order(
                    order_no="ORD-IDEMPOTENCY-001",
                    user_id=self.user.id,
                    service_type="repair",
                    service_name="维修",
                    final_price=Decimal("10.00"),
                    status="completed",
                )
            )
            db.commit()
        finally:
            db.close()

        app = FastAPI()
        app.include_router(wallet_router)

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_current_worker] = lambda: self.worker
        app.dependency_overrides[require_super_admin] = lambda: SimpleNamespace(id=99)
        self.client = TestClient(app)
        self.create_order_patcher = patch(
            "app.services.wechat_pay_service.create_jsapi_order",
            return_value=PAY_PARAMS,
        )
        self.create_order_mock = self.create_order_patcher.start()
        self.notify_patcher = patch(
            "app.services.message_service.notify_payment_success",
            new=AsyncMock(return_value=None),
        )
        self.notify_patcher.start()

    def tearDown(self) -> None:
        self.notify_patcher.stop()
        self.create_order_patcher.stop()
        self.client.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    @staticmethod
    def _headers(key: str) -> dict:
        return {"Idempotency-Key": key}

    def test_wallet_recharge_replays_one_payment(self) -> None:
        first = self.client.post(
            "/api/wallet/recharge",
            headers=self._headers("wallet-recharge-0001"),
            json={"amount": 20, "method": "wechat"},
        )
        second = self.client.post(
            "/api/wallet/recharge",
            headers=self._headers("wallet-recharge-0001"),
            json={"amount": 20, "method": "wechat"},
        )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json(), first.json())
        self.assertEqual(self.create_order_mock.call_count, 1)
        db = self.Session()
        try:
            self.assertEqual(db.query(PaymentOrder).count(), 1)
            self.assertEqual(db.query(IdempotencyRequest).count(), 1)
        finally:
            db.close()

    def test_same_user_key_cannot_cross_operation_or_change_payload(self) -> None:
        key = "cross-operation-key-0001"
        created = self.client.post(
            "/api/wallet/recharge",
            headers=self._headers(key),
            json={"amount": 20, "method": "wechat"},
        )
        amount_conflict = self.client.post(
            "/api/wallet/recharge",
            headers=self._headers(key),
            json={"amount": 21, "method": "wechat"},
        )
        operation_conflict = self.client.post(
            "/api/wallet/pay",
            headers=self._headers(key),
            json={"order_no": "ORD-IDEMPOTENCY-001", "method": "wallet"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(amount_conflict.status_code, 409, amount_conflict.text)
        self.assertEqual(operation_conflict.status_code, 409, operation_conflict.text)
        db = self.Session()
        try:
            self.assertEqual(db.query(IdempotencyRequest).count(), 1)
            self.assertEqual(db.query(PaymentOrder).count(), 1)
        finally:
            db.close()

    def test_wallet_pay_replays_without_second_debit(self) -> None:
        payload = {"order_no": "ORD-IDEMPOTENCY-001", "method": "wallet"}
        headers = self._headers("wallet-payment-key-0001")
        first = self.client.post("/api/wallet/pay", headers=headers, json=payload)
        second = self.client.post("/api/wallet/pay", headers=headers, json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json(), first.json())
        db = self.Session()
        try:
            user = db.query(User).filter(User.id == self.user.id).one()
            self.assertEqual(user.balance, Decimal("90.00"))
            self.assertEqual(db.query(PaymentOrder).count(), 1)
            self.assertEqual(
                db.query(Transaction).filter(Transaction.type == "expense").count(),
                1,
            )
        finally:
            db.close()

    def test_wallet_pay_rejects_stale_quote_version_before_debit(self) -> None:
        response = self.client.post(
            "/api/wallet/pay",
            headers=self._headers("stale-payment-quote-0001"),
            json={
                "order_no": "ORD-IDEMPOTENCY-001",
                "method": "wallet",
                "order_version": 999,
            },
        )
        self.assertEqual(response.status_code, 409, response.text)
        db = self.Session()
        try:
            self.assertEqual(db.get(User, self.user.id).balance, Decimal("100.00"))
            self.assertEqual(db.query(PaymentOrder).count(), 0)
        finally:
            db.close()

    def test_deployed_wallet_pay_requires_quote_version(self) -> None:
        with patch.object(settings, "APP_ENV", "production"):
            response = self.client.post(
                "/api/wallet/pay",
                headers=self._headers("missing-quote-version-0001"),
                json={"order_no": "ORD-IDEMPOTENCY-001", "method": "wallet"},
            )
        self.assertEqual(response.status_code, 428, response.text)
        db = self.Session()
        try:
            self.assertEqual(db.get(User, self.user.id).balance, Decimal("100.00"))
            self.assertEqual(db.query(PaymentOrder).count(), 0)
        finally:
            db.close()

    def test_worker_withdraw_replays_without_second_reservation(self) -> None:
        headers = self._headers("worker-withdraw-key-0001")
        with (
            patch.object(settings, "APP_ENV", "development"),
            patch.object(settings, "WX_PAY_MOCK_ENABLED", True),
        ):
            first = self.client.post(
                "/api/wallet/withdraw",
                headers=headers,
                json={"amount": 20, "method": "wechat"},
            )
            second = self.client.post(
                "/api/wallet/withdraw",
                headers=headers,
                json={"amount": 20, "method": "wechat"},
            )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json(), first.json())
        db = self.Session()
        try:
            self.assertEqual(db.get(Worker, self.worker.id).balance, Decimal("80.00"))
            self.assertEqual(
                db.query(Transaction).filter(Transaction.type == "withdraw").count(),
                1,
            )
        finally:
            db.close()

    def test_refund_replays_without_second_credit(self) -> None:
        pay = self.client.post(
            "/api/wallet/pay",
            headers=self._headers("refund-setup-payment-0001"),
            json={"order_no": "ORD-IDEMPOTENCY-001", "method": "wallet"},
        )
        self.assertEqual(pay.status_code, 200, pay.text)
        refund_payload = {
            "order_no": "ORD-IDEMPOTENCY-001",
            "reason": "用户售后退款",
            "amount": 5,
        }
        headers = self._headers("refund-command-key-0001")
        first = self.client.post(
            "/api/wallet/refund", headers=headers, json=refund_payload
        )
        second = self.client.post(
            "/api/wallet/refund", headers=headers, json=refund_payload
        )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json(), first.json())
        db = self.Session()
        try:
            user = db.query(User).filter(User.id == self.user.id).one()
            self.assertEqual(user.balance, Decimal("95.00"))
            self.assertEqual(db.query(RefundOrder).count(), 1)
            self.assertEqual(
                db.query(Transaction).filter(Transaction.type == "refund").count(),
                1,
            )
        finally:
            db.close()

    def test_known_failure_is_replayed_without_side_effect(self) -> None:
        db = self.Session()
        try:
            order = db.query(Order).filter(Order.order_no == "ORD-IDEMPOTENCY-001").one()
            order.final_price = Decimal("200.00")
            db.commit()
        finally:
            db.close()
        payload = {"order_no": "ORD-IDEMPOTENCY-001", "method": "wallet"}
        headers = self._headers("failed-payment-key-0001")
        first = self.client.post("/api/wallet/pay", headers=headers, json=payload)
        second = self.client.post("/api/wallet/pay", headers=headers, json=payload)
        self.assertEqual(first.status_code, 400, first.text)
        self.assertEqual(second.status_code, 400, second.text)
        self.assertEqual(second.json(), first.json())
        db = self.Session()
        try:
            record = db.query(IdempotencyRequest).one()
            self.assertEqual(record.status, "failed")
            self.assertEqual(db.query(PaymentOrder).count(), 0)
            self.assertEqual(db.query(Transaction).count(), 0)
        finally:
            db.close()

    def test_payment_service_rejects_worker_recharge(self) -> None:
        db = self.Session()
        try:
            worker = Worker(openid="no-worker-recharge", balance=0, is_active=True)
            db.add(worker)
            db.commit()
            with self.assertRaises(HTTPException) as raised:
                payment_service.recharge(db, worker, "worker", 100, "wechat")
            self.assertEqual(raised.exception.status_code, 403)
            self.assertEqual(db.query(PaymentOrder).count(), 0)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

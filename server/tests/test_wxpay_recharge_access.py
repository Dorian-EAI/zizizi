from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests._support import import_all_models, isolated_engine, session_factory

import_all_models()

from app.api.wxpay import router as wxpay_router
from app.api.wallet import router as wallet_router
from app.config import settings
from app.database import Base, get_db
from app.models.idempotency import IdempotencyRequest
from app.models.order import Order
from app.models.user import User, Worker
from app.models.wallet import PaymentOrder
from app.utils.security import create_access_token


PAY_PARAMS = {
    "appId": "wx24ce7985708686b4",
    "timeStamp": "1",
    "nonceStr": "nonce",
    "package": "prepay_id=mock",
    "signType": "RSA",
    "paySign": "signature",
}


class WxpayRechargeAccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        Base.metadata.create_all(self.engine)
        self.Session = session_factory(self.engine)
        db = self.Session()
        try:
            user = User(openid="recharge-user", nickname="用户", is_active=True)
            worker = Worker(openid="recharge-worker", nickname="师傅", is_active=True)
            db.add_all([user, worker])
            db.flush()
            db.add(
                Order(
                    order_no="ORD-WXPAY-IDEMPOTENT",
                    user_id=user.id,
                    service_type="repair",
                    service_name="维修",
                    final_price=88,
                    status="completed",
                )
            )
            db.commit()
            self.user_id = user.id
            self.worker_id = worker.id
        finally:
            db.close()

        app = FastAPI()
        app.include_router(wxpay_router)
        app.include_router(wallet_router)

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.blacklist = patch(
            "app.dependencies.redis_client.is_token_blacklisted", return_value=False
        )
        self.create_order = patch(
            "app.api.wxpay.wechat_pay_service.create_jsapi_order",
            return_value=PAY_PARAMS,
        )
        self.blacklist.start()
        self.create_order_mock = self.create_order.start()

    def tearDown(self) -> None:
        self.create_order.stop()
        self.blacklist.stop()
        self.client.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    @staticmethod
    def _headers(
        account_id: int,
        account_type: str,
        idempotency_key: str | None = None,
    ) -> dict:
        token = create_access_token(
            {"sub": account_id, "type": account_type, "ver": 1}
        )
        headers = {"Authorization": "Bearer " + token}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def test_user_recharge_replays_same_result_once(self) -> None:
        headers = self._headers(self.user_id, "user", "recharge-key-0001")
        first = self.client.post(
            "/api/wxpay/recharge/jsapi",
            headers=headers,
            json={"amount": 100, "method": "wechat"},
        )
        second = self.client.post(
            "/api/wxpay/recharge/jsapi",
            headers=headers,
            json={"amount": 100, "method": "wechat"},
        )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json(), first.json())
        payment_no = first.json()["data"]["payment_no"]
        self.assertLessEqual(len(payment_no), 32)
        self.assertEqual(self.create_order_mock.call_count, 1)

        status = self.client.get(
            f"/api/wxpay/payments/{payment_no}", headers=headers
        )
        self.assertEqual(status.status_code, 200, status.text)
        self.assertEqual(status.json()["data"]["status"], "pending")

        db = self.Session()
        try:
            payment = db.query(PaymentOrder).one()
            record = db.query(IdempotencyRequest).one()
            self.assertEqual(payment.payment_no, payment_no)
            self.assertEqual(payment.payer_type, "user")
            self.assertEqual(payment.payer_id, self.user_id)
            self.assertEqual(record.status, "completed")
            self.assertEqual(record.resource_id, payment_no)
        finally:
            db.close()

    def test_same_key_with_different_amount_is_rejected(self) -> None:
        headers = self._headers(self.user_id, "user", "recharge-key-0002")
        first = self.client.post(
            "/api/wxpay/recharge/jsapi",
            headers=headers,
            json={"amount": 100, "method": "wechat"},
        )
        conflict = self.client.post(
            "/api/wxpay/recharge/jsapi",
            headers=headers,
            json={"amount": 101, "method": "wechat"},
        )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(conflict.status_code, 409, conflict.text)
        db = self.Session()
        try:
            self.assertEqual(db.query(PaymentOrder).count(), 1)
        finally:
            db.close()

    def test_worker_token_cannot_recharge_income_wallet(self) -> None:
        for path, key in (
            ("/api/wxpay/recharge/jsapi", "worker-key-0001"),
            ("/api/wallet/recharge", "worker-key-0002"),
        ):
            with self.subTest(path=path):
                response = self.client.post(
                    path,
                    headers=self._headers(self.worker_id, "worker", key),
                    json={"amount": 100, "method": "wechat"},
                )
                self.assertEqual(response.status_code, 401, response.text)
        db = self.Session()
        try:
            self.assertEqual(db.query(PaymentOrder).count(), 0)
            self.assertEqual(db.query(IdempotencyRequest).count(), 0)
        finally:
            db.close()

    def test_deployed_recharge_requires_client_key(self) -> None:
        with patch.object(settings, "APP_ENV", "production"):
            response = self.client.post(
                "/api/wxpay/recharge/jsapi",
                headers=self._headers(self.user_id, "user"),
                json={"amount": 100, "method": "wechat"},
            )
        self.assertEqual(response.status_code, 428, response.text)
        db = self.Session()
        try:
            self.assertEqual(db.query(PaymentOrder).count(), 0)
        finally:
            db.close()

    def test_order_jsapi_replays_same_payment_parameters(self) -> None:
        headers = self._headers(self.user_id, "user", "order-jsapi-key-0001")
        payload = {"order_no": "ORD-WXPAY-IDEMPOTENT"}
        first = self.client.post(
            "/api/wxpay/order/jsapi", headers=headers, json=payload
        )
        second = self.client.post(
            "/api/wxpay/order/jsapi", headers=headers, json=payload
        )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json(), first.json())
        self.assertEqual(self.create_order_mock.call_count, 1)
        db = self.Session()
        try:
            payment = db.query(PaymentOrder).one()
            record = db.query(IdempotencyRequest).one()
            self.assertEqual(payment.order_no, "ORD-WXPAY-IDEMPOTENT")
            self.assertEqual(record.operation, "wxpay.order_jsapi")
            self.assertEqual(record.resource_id, payment.payment_no)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

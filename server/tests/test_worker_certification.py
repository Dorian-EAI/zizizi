from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests._support import import_all_models, isolated_engine, session_factory

import_all_models()

from app.api.auth import router as auth_router
from app.database import Base, get_db
from app.models.coupon import Coupon
from app.models.favorite import FavoriteWorker
from app.models.message import Message
from app.models.order import Order
from app.models.review import Review
from app.models.user import Address, User, Worker
from app.schemas.user import AddressResponse, AddressUpdate
from app.services import auth_service
from app.utils.aes import decrypt_field
from app.utils.security import create_access_token


VALID_ID_CARD = "11010519491231002X"


def _application(id_card: str = VALID_ID_CARD) -> dict:
    return {
        "real_name": "张师傅",
        "phone": "13800000001",
        "phone_verification_code": "123456",
        "id_card": id_card,
        "id_front": "/uploads/certificate/id-front.jpg",
        "id_back": "/uploads/certificate/id-back.jpg",
        "certificate_images": [
            "/uploads/certificate/electrician.jpg",
            "https://cdn.example.com/certificate/plumbing.jpg",
        ],
        "health_certificate": "/uploads/certificate/health.jpg",
        "service_city": "北京市",
        "service_districts": ["朝阳区", "海淀区"],
        "service_types": ["水电维修", "管道疏通"],
        "price_min": "80.00",
        "price_max": "500.00",
    }


class WorkerCertificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        Base.metadata.create_all(self.engine)
        self.Session = session_factory(self.engine)
        db = self.Session()
        try:
            worker = Worker(openid="cert-worker", nickname="待认证师傅", is_active=True)
            user = User(openid="cert-user", nickname="普通用户", is_active=True)
            db.add_all([worker, user])
            db.commit()
            self.worker_id = worker.id
            self.user_id = user.id
        finally:
            db.close()

        api = FastAPI()
        api.include_router(auth_router)

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        api.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(api)
        self.worker_token = create_access_token({"sub": self.worker_id, "type": "worker", "ver": 1})
        self.user_token = create_access_token({"sub": self.user_id, "type": "user", "ver": 1})
        self.redis_patcher = patch(
            "app.dependencies.redis_client.is_token_blacklisted",
            return_value=False,
        )
        self.redis_patcher.start()

    def tearDown(self) -> None:
        self.redis_patcher.stop()
        self.client.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _worker_headers(self) -> dict:
        return {"Authorization": "Bearer " + self.worker_token}

    def test_worker_submission_encrypts_id_and_returns_only_safe_snapshot(self) -> None:
        with (
            patch.object(auth_service.logger, "info") as logged,
            patch("app.services.sms_service.verify_code", return_value=True) as verify_code,
        ):
            response = self.client.post(
                "/api/auth/worker/certification",
                headers=self._worker_headers(),
                json=_application(),
            )

        self.assertEqual(response.status_code, 200, response.text)
        verify_code.assert_called_once_with("13800000001", "123456")
        self.assertNotIn(VALID_ID_CARD, response.text)
        self.assertNotIn(VALID_ID_CARD, str(logged.mock_calls))
        body = response.json()["data"]
        self.assertEqual(body["certified"], 1)
        self.assertEqual(body["certification_status"], "pending")
        self.assertEqual(body["application"]["id_card_masked"], "1101**********002X")
        self.assertNotIn("id_card", body["application"])

        db = self.Session()
        try:
            worker = db.query(Worker).filter(Worker.id == self.worker_id).one()
            self.assertEqual(worker.certified, 1)
            self.assertNotEqual(worker.id_card, VALID_ID_CARD)
            self.assertEqual(decrypt_field(worker.id_card), VALID_ID_CARD)
            self.assertNotIn(VALID_ID_CARD, json.dumps(worker.certification_data, ensure_ascii=False))
            self.assertNotIn("id_card", worker.certification_data)
            self.assertEqual(worker.service_types, '["水电维修", "管道疏通"]')
            self.assertEqual(worker.service_area, "北京市 · 朝阳区、海淀区")
        finally:
            db.close()

        profile = self.client.get("/api/auth/worker/me", headers=self._worker_headers())
        self.assertEqual(profile.status_code, 200, profile.text)
        self.assertNotIn(VALID_ID_CARD, profile.text)
        self.assertEqual(
            profile.json()["data"]["certification_data"]["id_card_masked"],
            "1101**********002X",
        )

    def test_invalid_id_error_does_not_echo_plaintext(self) -> None:
        invalid_id = "110105194912310021"
        response = self.client.post(
            "/api/auth/worker/certification",
            headers=self._worker_headers(),
            json=_application(invalid_id),
        )
        self.assertEqual(response.status_code, 422, response.text)
        self.assertNotIn(invalid_id, response.text)
        self.assertIn("id_card", response.json()["detail"]["fields"])

        db = self.Session()
        try:
            worker = db.query(Worker).filter(Worker.id == self.worker_id).one()
            self.assertEqual(worker.certified, 0)
            self.assertIsNone(worker.id_card)
        finally:
            db.close()

    def test_invalid_sms_code_does_not_mutate_worker(self) -> None:
        with patch("app.services.sms_service.verify_code", return_value=False):
            response = self.client.post(
                "/api/auth/worker/certification",
                headers=self._worker_headers(),
                json=_application(),
            )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertNotIn("123456", response.text)

        db = self.Session()
        try:
            worker = db.query(Worker).filter(Worker.id == self.worker_id).one()
            self.assertEqual(worker.certified, 0)
            self.assertIsNone(worker.phone)
            self.assertIsNone(worker.id_card)
            self.assertIsNone(worker.certification_data)
        finally:
            db.close()

    def test_endpoint_requires_worker_token(self) -> None:
        no_token = self.client.post(
            "/api/auth/worker/certification",
            json=_application(),
        )
        self.assertEqual(no_token.status_code, 401)

        user_token = self.client.post(
            "/api/auth/worker/certification",
            headers={"Authorization": "Bearer " + self.user_token},
            json=_application(),
        )
        self.assertEqual(user_token.status_code, 401)


class AuthSummaryAndAddressCoordinateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        Base.metadata.create_all(self.engine)
        self.Session = session_factory(self.engine)
        self.db = self.Session()
        user = User(openid="summary-user", nickname="统计用户", is_active=True)
        self.db.add(user)
        self.db.commit()
        self.user = user

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_me_summary_uses_real_database_counts(self) -> None:
        order = Order(
            order_no="SUMMARY-1",
            user_id=self.user.id,
            service_type="electric",
            service_name="水电维修",
            status="reviewed",
        )
        self.db.add(order)
        self.db.flush()
        self.db.add_all([
            Review(
                order_id=order.id,
                user_id=self.user.id,
                rating=5,
                status="approved",
            ),
            FavoriteWorker(user_id=self.user.id, worker_id=88),
            Coupon(
                template_id=1,
                user_id=self.user.id,
                code="AVAILABLE-1",
                status="available",
                expire_at=datetime.utcnow() + timedelta(days=1),
            ),
            Coupon(
                template_id=1,
                user_id=self.user.id,
                code="EXPIRED-1",
                status="available",
                expire_at=datetime.utcnow() - timedelta(days=1),
            ),
            Message(
                owner_type="user",
                owner_id=self.user.id,
                type="system",
                title="未读消息",
                content="内容",
                is_read=False,
            ),
        ])
        self.db.commit()

        summary = auth_service.get_user_info(self.db, self.user)["summary"]
        self.assertEqual(summary, {
            "orders": 1,
            "reviews": 1,
            "favorites": 1,
            "available_coupons": 1,
            "unread_messages": 1,
        })

    def test_address_update_and_response_preserve_coordinates(self) -> None:
        address = Address(
            user_id=self.user.id,
            name="张三",
            phone="13800000002",
            province="北京市",
            city="北京市",
            district="朝阳区",
            detail="测试路 1 号",
            label="家",
            is_default=False,
        )
        self.db.add(address)
        self.db.commit()

        updated = auth_service.update_address(
            self.db,
            self.user,
            address.id,
            AddressUpdate(location_lat=39.9042, location_lng=116.4074),
        )
        response = AddressResponse.model_validate(updated)
        self.assertEqual(response.location_lat, 39.9042)
        self.assertEqual(response.location_lng, 116.4074)


if __name__ == "__main__":
    unittest.main()

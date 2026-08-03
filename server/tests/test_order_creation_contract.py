from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from tests._support import isolated_engine, session_factory
from app.api.orders import available_orders, router as orders_router
from app.database import Base, get_db
from app.dependencies import get_current_worker
from app.models.order import Bidding, Order
from app.models.service import ServiceType
from app.models.user import User, Worker
from app.schemas.order import (
    BiddingRequest,
    CreateOrderRequest,
    UpdateOrderStatusRequest,
)
from app.services import order_service


class OrderCreationContractTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        self.tables = [
            User.__table__,
            Worker.__table__,
            ServiceType.__table__,
            Order.__table__,
            Bidding.__table__,
        ]
        Base.metadata.create_all(self.engine, tables=self.tables)
        self.Session = session_factory(self.engine)
        self.db = self.Session()

        self.user = User(
            openid="creation-user",
            nickname="下单用户",
            phone="13800138000",
            is_active=True,
        )
        self.worker = Worker(
            openid="creation-worker",
            nickname="接单师傅",
            real_name="张师傅",
            phone="13900139000",
            id_card="encrypted-id-card",
            certified=2,
            service_types='["plumbing"]',
            is_active=True,
        )
        self.service = ServiceType(
            key="plumbing",
            name="管道维修（服务端）",
            is_active=True,
        )
        self.db.add_all([self.user, self.worker, self.service])
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine, tables=list(reversed(self.tables)))
        self.engine.dispose()

    def _request(self, **overrides) -> CreateOrderRequest:
        payload = {
            "service_type": "plumbing",
            "description": "厨房水管漏水",
            "images": [],
            "address": {
                "address": "北京市朝阳区真实服务地址 101 室",
                "latitude": 39.9001,
                "longitude": 116.4001,
            },
            "appoint_time": datetime.utcnow() + timedelta(hours=1),
            "budget": "100.50",
            "urgent": False,
            "urgent_amount": "0.00",
        }
        payload.update(overrides)
        return CreateOrderRequest(**payload)

    def test_create_uses_enabled_catalog_name_and_canonical_address(self) -> None:
        request = self._request(
            service_type=" Plumbing ",
            service_name="客户端伪造名称",
        )
        order = order_service.create_order(self.db, self.user, request)

        self.assertEqual(order.service_type, self.service.key)
        self.assertEqual(order.service_name, self.service.name)
        self.assertEqual(order.budget, Decimal("100.50"))
        self.assertEqual(
            json.loads(order.address),
            {
                "address": "北京市朝阳区真实服务地址 101 室",
                "latitude": 39.9001,
                "longitude": 116.4001,
            },
        )

    def test_inactive_or_unknown_service_type_is_rejected(self) -> None:
        self.service.is_active = False
        self.db.commit()
        with self.assertRaises(HTTPException) as inactive:
            order_service.create_order(self.db, self.user, self._request())
        self.assertEqual(inactive.exception.status_code, 422)

        self.service.is_active = True
        self.db.commit()
        with self.assertRaises(HTTPException) as unknown:
            order_service.create_order(
                self.db,
                self.user,
                self._request(service_type="unknown-service"),
            )
        self.assertEqual(unknown.exception.status_code, 422)
        self.assertEqual(self.db.query(Order).count(), 0)

    def test_user_must_have_a_real_bound_phone(self) -> None:
        for phone in (None, "", "138****8000", "12345678901"):
            with self.subTest(phone=phone):
                self.user.phone = phone
                self.db.commit()
                with self.assertRaises(HTTPException) as raised:
                    order_service.create_order(self.db, self.user, self._request())
                self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(self.db.query(Order).count(), 0)

    def test_address_and_appointment_reject_fake_or_invalid_values(self) -> None:
        invalid_addresses = [
            "北京市朝阳区某小区",
            {"address": "", "latitude": 39.9, "longitude": 116.4},
            {"address": "某小区", "latitude": 39.9},
            {"address": "某小区", "latitude": "39.9", "longitude": 116.4},
            {"address": "某小区", "latitude": True, "longitude": 116.4},
            {"address": "某小区", "latitude": 91, "longitude": 116.4},
            {"address": "某小区", "latitude": 39.9, "longitude": 181},
            {"address": "某小区", "latitude": 0, "longitude": 0},
        ]
        for address in invalid_addresses:
            with self.subTest(address=address):
                with self.assertRaises(ValidationError):
                    self._request(address=address)

        with self.assertRaises(ValidationError):
            self._request(appoint_time=datetime.utcnow() - timedelta(seconds=1))

    def test_legacy_json_object_is_accepted_but_extra_contact_data_is_not(self) -> None:
        legacy_json = json.dumps(
            {
                "address": "上海市徐汇区服务地址",
                "latitude": 31.18,
                "longitude": 121.43,
            },
            ensure_ascii=False,
        )
        request = self._request(address=legacy_json)
        self.assertEqual(request.address.address, "上海市徐汇区服务地址")

        with self.assertRaises(ValidationError):
            self._request(
                address={
                    "address": "上海市徐汇区服务地址",
                    "latitude": 31.18,
                    "longitude": 121.43,
                    "phone": "13800138000",
                }
            )

    def test_money_requests_reject_more_than_two_decimal_places(self) -> None:
        with self.assertRaises(ValidationError):
            self._request(budget="1.234")
        with self.assertRaises(ValidationError):
            self._request(urgent_amount="1.234")
        with self.assertRaises(ValidationError):
            BiddingRequest(price="88.501")
        with self.assertRaises(ValidationError):
            UpdateOrderStatusRequest(status="completed", price="88.501")

    async def test_available_description_masks_phone_and_id_card(self) -> None:
        request = self._request(
            description="请联系13800138000，身份证11010519491231002X请尽快",
        )
        order_service.create_order(self.db, self.user, request)
        response = await available_orders(
            lat=None,
            lng=None,
            sort_by="created",
            worker=self.worker,
            db=self.db,
        )
        description = response["data"][0]["description"]
        self.assertEqual(
            description,
            "请联系138****8000，身份证1101**********002X请尽快",
        )
        self.assertNotIn("13800138000", description)
        self.assertNotIn("11010519491231002X", description)

    def test_available_query_parameters_have_bounds_and_enum(self) -> None:
        test_app = FastAPI()
        test_app.include_router(orders_router)

        def override_db():
            yield self.db

        test_app.dependency_overrides[get_db] = override_db
        test_app.dependency_overrides[get_current_worker] = lambda: self.worker
        with TestClient(test_app) as client:
            self.assertEqual(
                client.get("/api/orders/available?lat=91&lng=116").status_code,
                422,
            )
            self.assertEqual(
                client.get("/api/orders/available?lat=39&lng=181").status_code,
                422,
            )
            self.assertEqual(
                client.get("/api/orders/available?sort_by=nearest").status_code,
                422,
            )


if __name__ == "__main__":
    unittest.main()

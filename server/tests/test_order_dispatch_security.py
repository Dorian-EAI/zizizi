from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from tests._support import isolated_engine, session_factory
from app.api.orders import available_orders, get_order, list_orders, worker_orders
from app.api.reviews import worker_detail as public_review_worker_detail
from app.api.services import _worker_to_dict
from app.database import Base
from app.models.order import Bidding, Order
from app.models.user import User, Worker
from app.schemas.order import BiddingRequest
from app.services import order_service


class OrderDispatchSecurityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        self.tables = [
            User.__table__,
            Worker.__table__,
            Order.__table__,
            Bidding.__table__,
        ]
        Base.metadata.create_all(self.engine, tables=self.tables)
        self.Session = session_factory(self.engine)
        self.db = self.Session()

        self.user = User(
            openid="dispatch-user",
            nickname="订单用户",
            phone="13800138000",
            is_active=True,
        )
        self.worker = Worker(
            openid="dispatch-worker",
            nickname="合格师傅",
            real_name="张师傅",
            phone="13900139000",
            id_card="encrypted-id-card",
            certified=2,
            service_types=json.dumps(["plumbing"]),
            is_active=True,
        )
        self.db.add_all([self.user, self.worker])
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine, tables=list(reversed(self.tables)))
        self.engine.dispose()

    def _order(
        self,
        suffix: str,
        *,
        service_type: str = "plumbing",
        status: str = "pending",
        worker_id: int | None = None,
    ) -> Order:
        order = Order(
            order_no=f"ORD-DISPATCH-{suffix}",
            user_id=self.user.id,
            worker_id=worker_id,
            service_type=service_type,
            service_name="上门维修",
            description="水管漏水",
            images="[]",
            address=json.dumps(
                {
                    "address": "北京市朝阳区精确门牌 101 室",
                    "latitude": 39.9001,
                    "longitude": 116.4001,
                    "phone": "13700137000",
                },
                ensure_ascii=False,
            ),
            budget=100,
            urgent=False,
            urgent_amount=0,
            status=status,
            version=0,
        )
        self.db.add(order)
        self.db.commit()
        return order

    async def test_available_orders_require_eligible_matching_worker_and_are_redacted(self) -> None:
        matching = self._order("MATCH")
        self._order("OTHER", service_type="electrical")

        response = await available_orders(
            lat=None,
            lng=None,
            sort_by="created",
            worker=self.worker,
            db=self.db,
        )
        data = response["data"]
        self.assertEqual([item["id"] for item in data], [matching.id])

        forbidden = {
            "order_no",
            "user_id",
            "worker_id",
            "address",
            "latitude",
            "longitude",
            "lat",
            "lng",
            "phone",
            "user_phone",
            "worker_phone",
        }
        self.assertTrue(forbidden.isdisjoint(data[0]))
        serialized = json.dumps(data, ensure_ascii=False)
        self.assertNotIn("精确门牌", serialized)
        self.assertNotIn("13700137000", serialized)

        self.worker.certified = 1
        self.db.commit()
        with self.assertRaises(HTTPException) as raised:
            order_service.get_available_orders(self.db, self.worker)
        self.assertEqual(raised.exception.status_code, 403)

    def test_worker_profile_and_service_type_are_revalidated(self) -> None:
        variants = [
            Worker(
                real_name="张师傅",
                phone="13900139000",
                id_card="encrypted",
                certified=2,
                service_types='["plumbing"]',
                is_active=False,
            ),
            Worker(
                real_name="",
                phone="13900139000",
                id_card="encrypted",
                certified=2,
                service_types='["plumbing"]',
                is_active=True,
            ),
            Worker(
                real_name="张师傅",
                phone="139****9000",
                id_card="encrypted",
                certified=2,
                service_types='["plumbing"]',
                is_active=True,
            ),
        ]
        for worker in variants:
            with self.subTest(worker=worker):
                with self.assertRaises(HTTPException) as raised:
                    order_service.ensure_worker_can_take_order(worker, "plumbing")
                self.assertEqual(raised.exception.status_code, 403)

        with self.assertRaises(HTTPException) as mismatch:
            order_service.ensure_worker_can_take_order(self.worker, "electrical")
        self.assertEqual(mismatch.exception.status_code, 403)

    async def test_bidding_locks_and_rejects_duplicate_or_service_mismatch(self) -> None:
        order = self._order("BID")
        req = BiddingRequest(price=88.50, message="可以上门", eta="30分钟")
        with patch(
            "app.services.order_service.message_service.notify_order_bidding_new",
            new_callable=AsyncMock,
        ) as notify:
            bidding = await order_service.create_bidding(
                self.db, self.worker, order.id, req
            )
            self.assertEqual(bidding.worker_id, self.worker.id)
            notify.assert_awaited_once()

            with self.assertRaises(HTTPException) as duplicate:
                await order_service.create_bidding(
                    self.db, self.worker, order.id, req
                )
            self.assertEqual(duplicate.exception.status_code, 409)

        self.assertEqual(
            self.db.query(Bidding).filter(Bidding.order_id == order.id).count(),
            1,
        )

        mismatch_order = self._order("BID-MISMATCH", service_type="electrical")
        with self.assertRaises(HTTPException) as mismatch:
            await order_service.create_bidding(
                self.db, self.worker, mismatch_order.id, req
            )
        self.assertEqual(mismatch.exception.status_code, 403)
        self.assertEqual(
            self.db.query(Bidding)
            .filter(Bidding.order_id == mismatch_order.id)
            .count(),
            0,
        )

    async def test_select_worker_rechecks_qualification_before_mutation(self) -> None:
        order = self._order("SELECT")
        bidding = Bidding(
            order_id=order.id,
            worker_id=self.worker.id,
            price=90,
            message="报价",
            eta="45分钟",
            is_selected=False,
        )
        self.db.add(bidding)
        self.db.commit()

        self.worker.certified = 1
        self.db.commit()
        with self.assertRaises(HTTPException) as raised:
            await order_service.select_worker(
                self.db, self.user, order.id, bidding.id
            )
        self.assertEqual(raised.exception.status_code, 403)

        self.db.expire_all()
        unchanged_order = self.db.get(Order, order.id)
        unchanged_bidding = self.db.get(Bidding, bidding.id)
        self.assertEqual(unchanged_order.status, "pending")
        self.assertIsNone(unchanged_order.worker_id)
        self.assertFalse(unchanged_bidding.is_selected)

    async def test_detail_releases_only_counterparty_real_phone(self) -> None:
        assigned = self._order(
            "CONTACT",
            status="accepted",
            worker_id=self.worker.id,
        )

        owner_view = await get_order(
            assigned.id,
            account=(self.user, "user"),
            db=self.db,
        )
        self.assertEqual(owner_view["data"]["worker_phone"], self.worker.phone)
        self.assertNotIn("user_phone", owner_view["data"])

        worker_view = await get_order(
            assigned.id,
            account=(self.worker, "worker"),
            db=self.db,
        )
        self.assertEqual(worker_view["data"]["user_phone"], self.user.phone)
        self.assertNotIn("worker_phone", worker_view["data"])

        owner_list = await list_orders(status=None, user=self.user, db=self.db)
        worker_list = await worker_orders(status=None, worker=self.worker, db=self.db)
        for item in owner_list["data"] + worker_list["data"]:
            self.assertNotIn("user_phone", item)
            self.assertNotIn("worker_phone", item)

        self.worker.phone = "139****9000"
        self.db.commit()
        masked_view = await get_order(
            assigned.id,
            account=(self.user, "user"),
            db=self.db,
        )
        self.assertNotIn("worker_phone", masked_view["data"])

    async def test_public_worker_profiles_do_not_expose_phone(self) -> None:
        self.assertNotIn("phone", _worker_to_dict(self.worker))
        with (
            patch(
                "app.api.reviews.review_service.get_review_stats",
                return_value={},
            ),
            patch(
                "app.api.reviews.review_service.get_reviews",
                return_value=([], 0),
            ),
        ):
            response = await public_review_worker_detail(
                self.worker.id,
                db=self.db,
            )
        self.assertNotIn("phone", response["data"])


if __name__ == "__main__":
    unittest.main()

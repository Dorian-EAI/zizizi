from __future__ import annotations

import json
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from tests._support import isolated_engine, session_factory
from app.database import Base
from app.models.message import Message
from app.models.order import Bidding, Order
from app.schemas.message import MessageResponse
from app.models.user import User, Worker
from app.services import message_service


class MessageDeepLinkContractTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        self.tables = [
            User.__table__,
            Worker.__table__,
            Order.__table__,
            Bidding.__table__,
            Message.__table__,
        ]
        Base.metadata.create_all(self.engine, tables=self.tables)
        self.Session = session_factory(self.engine)
        self.db = self.Session()

        self.user = User(
            openid="message-user",
            nickname="消息用户",
            phone="13800138000",
            is_active=True,
        )
        self.worker = Worker(
            openid="message-worker",
            nickname="消息师傅",
            real_name="消息师傅",
            phone="13900139000",
            id_card="encrypted-id",
            certified=2,
            service_types='["plumbing"]',
            is_active=True,
        )
        self.db.add_all([self.user, self.worker])
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine, tables=list(reversed(self.tables)))
        self.engine.dispose()

    def _order(self) -> Order:
        order = Order(
            order_no="ORD-MESSAGE-001",
            user_id=self.user.id,
            worker_id=self.worker.id,
            service_type="plumbing",
            service_name="上门维修",
            description="水管漏水",
            images="[]",
            address='{"address":"北京市朝阳区某小区","latitude":39.9,"longitude":116.4}',
            budget=100,
            final_price=Decimal("88.50"),
            urgent=False,
            urgent_amount=0,
            status="accepted",
            version=12,
        )
        self.db.add(order)
        self.db.commit()
        return order

    async def test_order_notification_payload_has_stable_deeplink_fields(self) -> None:
        order = self._order()
        bidding = Bidding(
            order_id=order.id,
            worker_id=self.worker.id,
            price=Decimal("88.50"),
            message="可以上门",
            eta="30分钟",
            is_selected=False,
        )
        self.db.add(bidding)
        self.db.commit()

        with patch(
            "app.services.message_service.send_wx_subscribe",
            new_callable=AsyncMock,
        ) as send_wx:
            await message_service.notify_order_bidding_new(self.db, order, bidding)

        message = self.db.query(Message).one()
        payload = json.loads(message.payload)
        self.assertEqual(payload["role"], "user")
        self.assertEqual(payload["object_type"], "order")
        self.assertEqual(payload["object_id"], str(order.id))
        self.assertEqual(payload["order_id"], order.id)
        self.assertEqual(payload["event_version"], 12)
        self.assertEqual(payload["fallback_route"], "client_quote_list")
        self.assertEqual(payload["pending_action"], "view_quotes")
        self.assertEqual(payload["price"], 88.5)
        send_wx.assert_awaited_once()

    async def test_legacy_payload_is_normalized_and_decimal_safe(self) -> None:
        message = message_service.send_inbox_message(
            self.db,
            "worker",
            self.worker.id,
            "order",
            "旧式消息",
            "旧式 payload 仍应可跳转",
            {"order_id": 42, "amount": Decimal("12.34")},
        )

        payload = json.loads(message.payload)
        self.assertEqual(payload["role"], "worker")
        self.assertEqual(payload["object_type"], "order")
        self.assertEqual(payload["object_id"], "42")
        self.assertEqual(payload["event_version"], 0)
        self.assertEqual(payload["fallback_route"], "worker_orders")
        self.assertEqual(payload["amount"], 12.34)

    async def test_mark_read_response_serializes_stored_payload_json(self) -> None:
        message = message_service.send_inbox_message(
            self.db,
            "worker",
            self.worker.id,
            "order",
            "待处理消息",
            "标记已读响应应稳定返回结构化 payload",
            {"order_id": 42},
        )

        marked = message_service.mark_read(
            self.db,
            "worker",
            self.worker.id,
            message.id,
        )

        data = MessageResponse.model_validate(marked).model_dump(mode="json")
        self.assertTrue(data["is_read"])
        self.assertEqual(data["payload"]["role"], "worker")
        self.assertEqual(data["payload"]["object_type"], "order")
        self.assertEqual(data["payload"]["object_id"], "42")


if __name__ == "__main__":
    unittest.main()

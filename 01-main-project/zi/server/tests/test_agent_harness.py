from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from tests._support import isolated_engine, session_factory
from app.database import Base
from app.models.agent import AgentSession
from app.models.order import Order
from app.models.service import ServiceType
from app.models.user import Address, User
from app.services import agent_service


class AgentHarnessTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        self.tables = [
            User.__table__,
            Address.__table__,
            ServiceType.__table__,
            Order.__table__,
            AgentSession.__table__,
        ]
        Base.metadata.create_all(self.engine, tables=self.tables)
        self.Session = session_factory(self.engine)
        self.db = self.Session()

        self._provider = agent_service.settings.AI_PROVIDER
        agent_service.settings.AI_PROVIDER = "mock"

        self.user = User(
            openid="agent-user",
            nickname="自家人小王",
            phone="13800138000",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.db.add_all(
            [
                ServiceType(key="air_condition", name="空调维修", is_active=True),
                ServiceType(key="electric", name="水电维修", is_active=True),
                ServiceType(key="plumbing", name="管道疏通", is_active=True),
            ]
        )
        self.db.add(
            Address(
                user_id=self.user.id,
                name="王小家",
                phone="13800138000",
                province="广东省",
                city="深圳市",
                district="南山区",
                detail="科技园 1 栋 101",
                label="家",
                is_default=True,
                location_lat=22.5401,
                location_lng=113.9502,
            )
        )
        self.db.commit()

    def tearDown(self) -> None:
        agent_service.settings.AI_PROVIDER = self._provider
        self.db.close()
        Base.metadata.drop_all(self.engine, tables=list(reversed(self.tables)))
        self.engine.dispose()

    async def _turn(self, **kwargs):
        kwargs.setdefault("session_id", getattr(self, "_session_id", None))
        result = await agent_service.handle_turn(self.db, self.user, **kwargs)
        self._session_id = result["session_id"]
        return result

    def _orders(self):
        return self.db.query(Order).all()

    async def test_rule_flow_collects_draft_then_creates_once(self) -> None:
        result = await self._turn(message="家里空调不制冷，明天上午9点来修")
        self.assertEqual(result["status"], "awaiting_confirm")
        self.assertEqual(result["draft"]["service_type"], "air_condition")
        self.assertIn("科技园", result["draft"]["address_text"])
        self.assertIsNotNone(result["confirm_token"])
        self.assertEqual(len(self._orders()), 0)

        confirmed = await self._turn(
            action="confirm", confirm_token=result["confirm_token"]
        )
        self.assertEqual(confirmed["status"], "created")
        self.assertTrue(confirmed["order"]["order_no"].startswith("ORD"))
        self.assertEqual(len(self._orders()), 1)

        again = await self._turn(action="confirm", confirm_token=result["confirm_token"])
        self.assertEqual(again["order"]["id"], confirmed["order"]["id"])
        self.assertEqual(len(self._orders()), 1)

    async def test_confirm_rejects_stale_token(self) -> None:
        result = await self._turn(message="空调不制冷，明天上午9点")
        with self.assertRaises(agent_service.AgentConflict):
            await self._turn(action="confirm", confirm_token="forged-token")
        self.assertEqual(len(self._orders()), 0)
        self.assertEqual(result["status"], "awaiting_confirm")

    async def test_questioning_price_does_not_overwrite_problem_or_create(self) -> None:
        await self._turn(message="空调不制冷，明天上午9点")
        follow_up = await self._turn(message="这个大概多少钱？")
        self.assertEqual(follow_up["status"], "awaiting_confirm")
        self.assertEqual(follow_up["draft"]["description"], "空调不制冷")
        self.assertEqual(len(self._orders()), 0)

    async def test_missing_address_is_reported_without_creating(self) -> None:
        self.db.query(Address).delete()
        self.db.commit()
        result = await self._turn(message="厨房水管漏水，明天下午3点")
        self.assertEqual(result["status"], "collecting")
        self.assertIn("address", result["missing"])
        self.assertEqual(result["options"]["addresses"], [])
        self.assertEqual(len(self._orders()), 0)

    async def test_company_address_selected_by_label(self) -> None:
        self.db.add(
            Address(
                user_id=self.user.id,
                name="王先生",
                phone="13800138000",
                province="广东省",
                city="深圳市",
                district="福田区",
                detail="平安金融中心 8 楼",
                label="公司",
                is_default=False,
                location_lat=22.5367,
                location_lng=114.0596,
            )
        )
        self.db.commit()

        result = await self._turn(message="用公司地址，明天下午3点，水管漏水")
        self.assertEqual(result["status"], "awaiting_confirm")
        self.assertIn("平安金融中心", result["draft"]["address_text"])
        self.assertEqual(result["draft"]["service_type"], "electric")

    async def test_unbound_phone_blocks_order_creation(self) -> None:
        self.user.phone = None
        self.db.commit()

        result = await self._turn(message="空调不制冷，明天上午9点")
        self.assertEqual(result["status"], "awaiting_confirm")
        self.assertTrue(
            any(action["type"] == "navigate" for action in result["actions"])
        )
        with self.assertRaises(agent_service.AgentConflict):
            await self._turn(action="confirm", confirm_token=result["confirm_token"])
        self.assertEqual(len(self._orders()), 0)

    async def test_legacy_service_key_is_resolved_by_alias(self) -> None:
        self.db.query(ServiceType).filter(ServiceType.key == "air_condition").delete()
        self.db.add(ServiceType(key="aircon", name="空调维修（历史 key）", is_active=True))
        self.db.commit()

        result = await self._turn(message="空调不制冷，明天上午9点")
        self.assertEqual(result["status"], "awaiting_confirm")
        self.assertEqual(result["draft"]["service_type"], "aircon")

        confirmed = await self._turn(
            action="confirm", confirm_token=result["confirm_token"]
        )
        self.assertEqual(confirmed["status"], "created")
        order = self._orders()[0]
        self.assertEqual(order.service_type, "aircon")

    async def test_cancel_draft_clears_pending_confirmation(self) -> None:
        await self._turn(message="空调不制冷，明天上午9点")
        cancelled = await self._turn(action="cancel")
        self.assertEqual(cancelled["status"], "collecting")
        self.assertIsNone(cancelled["draft"])
        self.assertIsNone(cancelled["confirm_token"])
        self.assertEqual(len(self._orders()), 0)

    async def test_llm_tool_cannot_create_order_without_user_confirmation(self) -> None:
        result = await self._turn(message="空调不制冷，明天上午9点")
        session, state = agent_service._load_session(
            self.db, self.user, result["session_id"]
        )
        runner = agent_service._ToolRunner(
            self.db, self.user, session, state, latest_message="看看这个"
        )
        outcome = runner.tool_create_order({})
        self.assertFalse(outcome["ok"])
        self.assertEqual(len(self._orders()), 0)

    async def test_photo_without_text_asks_for_description_and_keeps_image(self) -> None:
        result = await self._turn(
            message="",
            image_urls=["https://cdn.example.com/repair/demo.jpg"],
        )
        self.assertEqual(result["status"], "collecting")
        self.assertIn("service_type", result["missing"])

        session = (
            self.db.query(AgentSession)
            .filter(AgentSession.session_no == result["session_id"])
            .first()
        )
        state = json.loads(session.state_json)
        self.assertEqual(
            state["slots"]["images"], ["https://cdn.example.com/repair/demo.jpg"]
        )

    async def test_llm_tool_loop_builds_draft_and_creates_after_confirm(self) -> None:
        agent_service.settings.AI_PROVIDER = "doubao"
        responses = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    self._tool_call(
                        "c1",
                        "set_problem",
                        {"service_type": "air_condition", "description": "空调不制冷"},
                    ),
                    self._tool_call("c2", "set_appointment", {"text": "明天上午9点"}),
                ],
            },
            {"role": "assistant", "content": "信息齐了，请确认订单。"},
        ]

        async def fake_completion(messages, **kwargs):
            return responses.pop(0)

        with patch.object(
            agent_service.ai_service, "chat_completion", new=fake_completion
        ):
            result = await self._turn(message="空调不制冷，明天上午9点来修")

        self.assertEqual(result["status"], "awaiting_confirm")
        self.assertEqual(result["draft"]["service_type"], "air_condition")
        self.assertIn("科技园", result["draft"]["address_text"])
        self.assertEqual(len(self._orders()), 0)

        confirmed = await self._turn(
            action="confirm", confirm_token=result["confirm_token"]
        )
        self.assertEqual(confirmed["status"], "created")
        self.assertEqual(len(self._orders()), 1)

    async def test_llm_create_tool_is_blocked_without_explicit_confirmation(self) -> None:
        agent_service.settings.AI_PROVIDER = "doubao"
        responses = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    self._tool_call(
                        "c1",
                        "set_problem",
                        {"service_type": "air_condition", "description": "空调不制冷"},
                    ),
                    self._tool_call("c2", "set_appointment", {"text": "明天上午9点"}),
                ],
            },
            {"role": "assistant", "content": "信息齐了，请确认订单。"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [self._tool_call("c3", "create_order", {})],
            },
            {"role": "assistant", "content": "还需要你确认后才能提交。"},
        ]

        async def fake_completion(messages, **kwargs):
            return responses.pop(0)

        with patch.object(
            agent_service.ai_service, "chat_completion", new=fake_completion
        ):
            await self._turn(message="空调不制冷，明天上午9点来修")
            guarded = await self._turn(message="看看这个")

        self.assertEqual(guarded["status"], "awaiting_confirm")
        self.assertEqual(len(self._orders()), 0)

    async def test_order_query_reports_latest_order(self) -> None:
        draft = await self._turn(message="空调不制冷，明天上午9点")
        created = await self._turn(
            action="confirm", confirm_token=draft["confirm_token"]
        )
        order_no = created["order"]["order_no"]

        asked = await self._turn(message="我的订单到哪了")
        self.assertEqual(asked["status"], "created")
        self.assertIn(order_no, asked["reply"])
        self.assertTrue(any(action["type"] == "navigate" for action in asked["actions"]))
        self.assertEqual(len(self._orders()), 1)

    async def test_llm_order_query_tool_returns_navigation(self) -> None:
        draft = await self._turn(message="空调不制冷，明天上午9点")
        await self._turn(action="confirm", confirm_token=draft["confirm_token"])
        agent_service.settings.AI_PROVIDER = "doubao"

        responses = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [self._tool_call("c1", "list_my_orders", {})],
            },
            {"role": "assistant", "content": "你的订单目前待师傅接单。"},
        ]

        async def fake_completion(messages, **kwargs):
            return responses.pop(0)

        with patch.object(
            agent_service.ai_service, "chat_completion", new=fake_completion
        ):
            asked = await self._turn(message="我的订单到哪了")

        self.assertEqual(asked["status"], "created")
        self.assertIn("待师傅接单", asked["reply"])
        self.assertTrue(any(action["type"] == "navigate" for action in asked["actions"]))

    @staticmethod
    def _tool_call(call_id: str, name: str, args: dict) -> dict:
        return {
            "id": call_id,
            "type": "function",
            "function": {
                "name": name,
                "arguments": json.dumps(args, ensure_ascii=False),
            },
        }

    def test_invalid_photo_base64_is_rejected(self) -> None:
        with self.assertRaises(agent_service.AgentInputError):
            agent_service._decode_base64_image("not-a-real-image")

    def test_appointment_parser_supports_relative_day_and_period(self) -> None:
        parsed = agent_service._parse_appointment("明天上午9点")
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed[1].startswith("明天 09:00"))
        self.assertIsNotNone(agent_service._parse_appointment("下午3点"))
        self.assertIsNone(agent_service._parse_appointment("随便什么时候"))

    async def test_ambiguous_confirmation_does_not_create_order(self) -> None:
        await self._turn(message="空调不制冷，明天上午9点")
        for message in ("确认一下价格", "确认地址对不对", "确认下时间"):
            result = await self._turn(message=message)
            self.assertEqual(result["status"], "awaiting_confirm")
            self.assertEqual(len(self._orders()), 0)

    async def test_explicit_text_confirmation_creates_order(self) -> None:
        await self._turn(message="空调不制冷，明天上午9点")
        confirmed = await self._turn(message="确认下单")
        self.assertEqual(confirmed["status"], "created")
        self.assertEqual(len(self._orders()), 1)

    async def test_order_query_detection_avoids_service_questions(self) -> None:
        self.assertTrue(agent_service._is_order_query("我的订单"))
        self.assertTrue(agent_service._is_order_query("师傅到哪了"))
        self.assertFalse(agent_service._is_order_query("空调还要多久修好"))
        self.assertFalse(agent_service._is_order_query("确认一下价格"))

    def test_service_keyword_priority(self) -> None:
        self.assertEqual(agent_service._detect_service("墙面渗水"), "wall_repair")
        self.assertEqual(agent_service._detect_service("卫生间水管漏水"), "electric")
        self.assertEqual(agent_service._detect_service("马桶漏水"), "plumbing")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import asyncio
import json
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from tests._support import isolated_engine, session_factory
from app.api import member as member_api
from app.database import Base
from app.models.coupon import Coupon, CouponTemplate
from app.models.pricing import PeakTimeConfig
from app.models.user import User
from app.models.wallet import PaymentOrder, RefundOrder
from app.schemas.pricing import CalculateAmountResponse
from app.services import member_service, pricing_service


class MemberTruthfulnessTests(unittest.TestCase):
    """会员接口只展示数据库事实和已上线能力。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tables = [
            User.__table__,
            PaymentOrder.__table__,
            RefundOrder.__table__,
            CouponTemplate.__table__,
            Coupon.__table__,
            PeakTimeConfig.__table__,
        ]

    def setUp(self) -> None:
        self.engine = isolated_engine()
        Base.metadata.create_all(self.engine, tables=self.tables)
        self.db = session_factory(self.engine)()
        self.user = User(
            openid="member-truth-user",
            member_level=3,
            growth_value=8500,
        )
        self.other_user = User(openid="member-truth-other")
        self.db.add_all([self.user, self.other_user])
        self.db.commit()

    def tearDown(self) -> None:
        self.db.rollback()
        self.db.close()
        self.engine.dispose()

    def _payment(
        self,
        payment_no: str,
        amount: str,
        *,
        paid_at: datetime,
        status: str = "paid",
        user_id: int | None = None,
        order_no: str | None = "ORD-MEMBER-TRUTH",
    ) -> PaymentOrder:
        return PaymentOrder(
            payment_no=payment_no,
            order_no=order_no,
            amount=Decimal(amount),
            method="wechat",
            payer_type="user",
            payer_id=user_id or self.user.id,
            status=status,
            paid_at=paid_at,
        )

    def test_member_info_uses_net_paid_orders_and_currently_usable_coupons(self) -> None:
        month_start, month_end = member_service._utc_month_bounds()
        paid_at = month_start + timedelta(days=1)

        paid = self._payment("PAY-MEMBER-100", "100.00", paid_at=paid_at)
        partially_refunded = self._payment(
            "PAY-MEMBER-50",
            "50.00",
            paid_at=paid_at,
            status="partially_refunded",
            order_no="ORD-MEMBER-TRUTH-2",
        )
        self.db.add_all([
            paid,
            partially_refunded,
            self._payment(
                "PAY-RECHARGE-IGNORED",
                "999.00",
                paid_at=paid_at,
                order_no=None,
            ),
            self._payment(
                "PAY-PENDING-IGNORED",
                "400.00",
                paid_at=paid_at,
                status="pending",
                order_no="ORD-PENDING",
            ),
            self._payment(
                "PAY-PRIOR-MONTH-IGNORED",
                "70.00",
                paid_at=month_start - timedelta(seconds=1),
                order_no="ORD-PRIOR",
            ),
            self._payment(
                "PAY-OTHER-USER-IGNORED",
                "80.00",
                paid_at=min(paid_at, month_end - timedelta(seconds=1)),
                user_id=self.other_user.id,
                order_no="ORD-OTHER",
            ),
        ])
        self.db.flush()
        self.db.add_all([
            RefundOrder(
                refund_no="REF-MEMBER-SUCCESS",
                payment_no=partially_refunded.payment_no,
                order_no=partially_refunded.order_no,
                amount=Decimal("20.00"),
                total_amount=partially_refunded.amount,
                method=partially_refunded.method,
                payer_type="user",
                payer_id=self.user.id,
                status="success",
                refunded_at=paid_at,
            ),
            RefundOrder(
                refund_no="REF-MEMBER-FAILED",
                payment_no=paid.payment_no,
                order_no=paid.order_no,
                amount=Decimal("90.00"),
                total_amount=paid.amount,
                method=paid.method,
                payer_type="user",
                payer_id=self.user.id,
                status="failed",
                refunded_at=paid_at,
            ),
        ])

        now = datetime.utcnow()
        active_template = CouponTemplate(
            name="可用券",
            type="fixed",
            value=Decimal("10.00"),
            min_spend=Decimal("0.00"),
            valid_start=now - timedelta(days=1),
            valid_end=now + timedelta(days=5),
            is_active=True,
        )
        inactive_template = CouponTemplate(
            name="已下架券",
            type="fixed",
            value=Decimal("10.00"),
            valid_end=now + timedelta(days=5),
            is_active=False,
        )
        future_template = CouponTemplate(
            name="未生效券",
            type="fixed",
            value=Decimal("10.00"),
            valid_start=now + timedelta(days=1),
            valid_end=now + timedelta(days=5),
            is_active=True,
        )
        self.db.add_all([active_template, inactive_template, future_template])
        self.db.flush()
        self.db.add_all([
            Coupon(
                template_id=active_template.id,
                user_id=self.user.id,
                code="COUPON-USABLE",
                status="available",
                expire_at=now + timedelta(days=2),
            ),
            Coupon(
                template_id=active_template.id,
                user_id=self.user.id,
                code="COUPON-EXPIRED",
                status="available",
                expire_at=now - timedelta(seconds=1),
            ),
            Coupon(
                template_id=active_template.id,
                user_id=self.user.id,
                code="COUPON-USED",
                status="used",
                expire_at=now + timedelta(days=2),
            ),
            Coupon(
                template_id=inactive_template.id,
                user_id=self.user.id,
                code="COUPON-INACTIVE-TEMPLATE",
                status="available",
                expire_at=now + timedelta(days=2),
            ),
            Coupon(
                template_id=future_template.id,
                user_id=self.user.id,
                code="COUPON-FUTURE-TEMPLATE",
                status="available",
                expire_at=now + timedelta(days=2),
            ),
            Coupon(
                template_id=active_template.id,
                user_id=self.other_user.id,
                code="COUPON-OTHER-USER",
                status="available",
                expire_at=now + timedelta(days=2),
            ),
        ])
        self.db.commit()

        response = asyncio.run(member_api.get_member_info(user=self.user, db=self.db))

        self.assertEqual(response["data"]["month_spend"], 130.0)
        self.assertEqual(response["data"]["coupon_count"], 1)
        self.assertEqual(response["data"]["growth_value"], 8500)

    def test_benefits_only_describe_the_implemented_growth_levels(self) -> None:
        levels = member_service.get_all_levels_benefits()
        self.assertEqual([level["min_growth"] for level in levels], [0, 500, 2000, 8000])
        self.assertTrue(all("discount_rate" not in level for level in levels))
        self.assertTrue(
            all(
                benefit == {
                    "key": "growth_level",
                    "name": "成长等级",
                    "desc": benefit["desc"],
                    "status": "implemented",
                }
                for level in levels
                for benefit in level["benefits"]
            )
        )

        advertised = json.dumps(levels, ensure_ascii=False)
        for unimplemented_claim in (
            "会员折扣",
            "优先派单",
            "响应",
            "免费上门",
            "免上门",
            "生日礼包",
            "专属客服",
            "延保",
        ):
            self.assertNotIn(unimplemented_claim, advertised)

    def test_member_discount_is_explicitly_unavailable_in_service_and_pricing(self) -> None:
        member_result = member_service.calc_member_discount(self.db, self.user, 123.45)
        self.assertEqual(member_result["final_amount"], 123.45)
        self.assertEqual(member_result["discount_amount"], 0)
        self.assertEqual(member_result["member_discount_rate"], 1.0)
        self.assertFalse(member_result["available"])
        self.assertEqual(member_result["status"], "unavailable")
        self.assertTrue(member_result["reason"])

        with patch.object(
            pricing_service,
            "get_current_surcharge",
            return_value={
                "is_peak_time": False,
                "surcharge_rate": 0.0,
                "surcharge_max": 0,
            },
        ):
            amount = pricing_service.calculate_order_amount(
                self.db,
                self.user,
                base_amount=10000,
            )

        self.assertEqual(amount["member_discount"], 0)
        self.assertEqual(amount["member_discount_status"], "unavailable")
        self.assertTrue(amount["member_discount_reason"])
        self.assertEqual(amount["final_amount"], 10000)
        CalculateAmountResponse.model_validate(amount)

    def test_coupon_is_calculated_from_subtotal_without_fictional_member_discount(self) -> None:
        template = CouponTemplate(
            name="真实十元券",
            type="fixed",
            value=Decimal("10.00"),
            min_spend=Decimal("100.00"),
            is_active=True,
        )
        self.db.add(template)
        self.db.flush()
        coupon = Coupon(
            template_id=template.id,
            user_id=self.user.id,
            code="COUPON-REAL-PRICE",
            status="available",
        )
        self.db.add(coupon)
        self.db.commit()

        with patch.object(
            pricing_service,
            "get_current_surcharge",
            return_value={
                "is_peak_time": False,
                "surcharge_rate": 0.0,
                "surcharge_max": 0,
            },
        ):
            amount = pricing_service.calculate_order_amount(
                self.db,
                self.user,
                base_amount=10000,
                coupon_id=coupon.id,
            )

        self.assertEqual(amount["member_discount"], 0)
        self.assertEqual(amount["coupon_discount"], 1000)
        self.assertEqual(amount["final_amount"], 9000)


if __name__ == "__main__":
    unittest.main()

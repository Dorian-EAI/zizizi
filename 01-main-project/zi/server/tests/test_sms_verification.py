from __future__ import annotations

import unittest
from unittest.mock import patch

from tests._support import import_all_models  # sets the test environment first
from app.services import sms_service
from app.utils.redis_client import RedisClient


class SMSVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        with sms_service._DEV_CACHE_LOCK:
            sms_service._DEV_CODE_CACHE.clear()
            sms_service._DEV_RATE_CACHE.clear()
            sms_service._DEV_FAILURE_CACHE.clear()

    def tearDown(self) -> None:
        with sms_service._DEV_CACHE_LOCK:
            sms_service._DEV_CODE_CACHE.clear()
            sms_service._DEV_RATE_CACHE.clear()
            sms_service._DEV_FAILURE_CACHE.clear()

    @patch.object(sms_service.redis_client, "delete", return_value=True)
    @patch.object(sms_service.redis_client, "consume_verification_code", return_value=None)
    @patch.object(sms_service.redis_client, "reserve_verification_send", return_value=None)
    @patch.object(sms_service.redis_client, "set", return_value=False)
    @patch.object(sms_service.redis_client, "exists", return_value=False)
    def test_development_mock_code_is_one_time(
        self, _exists, _set, _reserve, _consume, _delete
    ) -> None:
        phone = "13800000001"
        with (
            patch.object(sms_service.settings, "APP_ENV", "development"),
            patch.object(sms_service.settings, "SMS_PROVIDER", "mock"),
        ):
            returned = sms_service.send_verification_code(phone, code="123456")
            self.assertEqual(returned, "123456")
            self.assertTrue(sms_service.verify_code(phone, "123456"))
            self.assertFalse(sms_service.verify_code(phone, "123456"))

    @patch.object(sms_service.redis_client, "consume_verification_code", return_value=None)
    @patch.object(sms_service.redis_client, "reserve_verification_send", return_value=None)
    @patch.object(sms_service.redis_client, "delete", return_value=True)
    @patch.object(sms_service.redis_client, "set", return_value=False)
    @patch.object(sms_service.redis_client, "exists", return_value=False)
    def test_codes_are_purpose_scoped_and_locked_after_five_failures(
        self, _exists, _set, _delete, _reserve, _consume
    ) -> None:
        phone = "13800000004"
        with (
            patch.object(sms_service.settings, "APP_ENV", "development"),
            patch.object(sms_service.settings, "SMS_PROVIDER", "mock"),
        ):
            sms_service.send_verification_code(
                phone,
                code="112233",
                purpose="worker_certification",
            )
            self.assertFalse(
                sms_service.verify_code(phone, "112233", purpose="bind_phone")
            )
            for _ in range(5):
                self.assertFalse(
                    sms_service.verify_code(
                        phone,
                        "000000",
                        purpose="worker_certification",
                    )
                )
            self.assertFalse(
                sms_service.verify_code(
                    phone,
                    "112233",
                    purpose="worker_certification",
                )
            )

    @patch.object(sms_service.redis_client, "delete", return_value=True)
    @patch.object(sms_service.redis_client, "reserve_verification_send", return_value=True)
    @patch.object(sms_service.redis_client, "set", return_value=True)
    @patch.object(sms_service.redis_client, "exists", return_value=False)
    def test_production_rejects_mock_delivery(
        self, _exists, _set, _reserve, delete
    ) -> None:
        with (
            patch.object(sms_service.settings, "APP_ENV", "production"),
            patch.object(sms_service.settings, "SMS_PROVIDER", "mock"),
        ):
            with self.assertRaises(sms_service.SMSServiceError):
                sms_service.send_verification_code(
                    "13800000002",
                    code="654321",
                )
        self.assertGreaterEqual(delete.call_count, 2)

    @patch.object(sms_service.redis_client, "delete", return_value=True)
    @patch.object(sms_service.redis_client, "reserve_verification_send", return_value=True)
    @patch.object(sms_service.redis_client, "set", return_value=True)
    @patch.object(sms_service.redis_client, "exists", return_value=False)
    def test_staging_also_rejects_mock_delivery(
        self, _exists, _set, _reserve, delete
    ) -> None:
        with (
            patch.object(sms_service.settings, "APP_ENV", "staging"),
            patch.object(sms_service.settings, "SMS_PROVIDER", "mock"),
        ):
            with self.assertRaises(sms_service.SMSServiceError):
                sms_service.send_verification_code(
                    "13800000003",
                    code="654321",
                )
        self.assertGreaterEqual(delete.call_count, 2)

    def test_redis_reservation_executes_atomic_script(self) -> None:
        class FakeRedis:
            def __init__(self, result):
                self.result = result
                self.calls = []

            def eval(self, *args):
                self.calls.append(args)
                return self.result

        for raw_result, expected in ((1, True), (0, False)):
            with self.subTest(raw_result=raw_result):
                wrapper = RedisClient()
                fake = FakeRedis(raw_result)
                wrapper._client = fake
                wrapper._enabled = True
                with patch.object(wrapper, "_connect", return_value=True):
                    actual = wrapper.reserve_verification_send(
                        "rate", "code", "failure", "123456"
                    )
                self.assertIs(actual, expected)
                self.assertEqual(fake.calls[0][1], 3)


if __name__ == "__main__":
    unittest.main()

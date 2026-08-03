from __future__ import annotations

import unittest
from unittest.mock import patch

from tests._support import import_all_models  # sets the test environment first
from app.services import sms_service


class SMSVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        with sms_service._DEV_CACHE_LOCK:
            sms_service._DEV_CODE_CACHE.clear()
            sms_service._DEV_RATE_CACHE.clear()

    def tearDown(self) -> None:
        with sms_service._DEV_CACHE_LOCK:
            sms_service._DEV_CODE_CACHE.clear()
            sms_service._DEV_RATE_CACHE.clear()

    @patch.object(sms_service.redis_client, "delete", return_value=True)
    @patch.object(sms_service.redis_client, "get_str", return_value=None)
    @patch.object(sms_service.redis_client, "set", return_value=False)
    @patch.object(sms_service.redis_client, "exists", return_value=False)
    def test_development_mock_code_is_one_time(
        self, _exists, _set, _get_str, _delete
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

    @patch.object(sms_service.redis_client, "delete", return_value=True)
    @patch.object(sms_service.redis_client, "set", return_value=True)
    @patch.object(sms_service.redis_client, "exists", return_value=False)
    def test_production_rejects_mock_delivery(
        self, _exists, _set, delete
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
    @patch.object(sms_service.redis_client, "set", return_value=True)
    @patch.object(sms_service.redis_client, "exists", return_value=False)
    def test_staging_also_rejects_mock_delivery(
        self, _exists, _set, delete
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


if __name__ == "__main__":
    unittest.main()

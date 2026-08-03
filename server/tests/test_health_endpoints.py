from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests import _support  # noqa: F401 - configure isolated app settings first
from app.main import app
from app.utils.redis_client import redis_client


class HealthEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Requests made without entering the context manager intentionally skip
        # scheduler startup while still exercising FastAPI's full ASGI stack.
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()

    def test_health(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["status"], "ok")

    @patch.object(redis_client, "ping", return_value=False)
    def test_ready_in_non_production_with_database_available(self, _ping) -> None:
        response = self.client.get("/ready")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["status"], "ready")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from tests._support import import_all_models, isolated_engine, session_factory

import_all_models()

from app.config import settings
from app.database import Base
from app.models.agreement import PageContent
from app.models.faq import FAQCategory
from app.services import content_service


class ContentDeploymentSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        Base.metadata.create_all(self.engine)
        self.Session = session_factory(self.engine)
        self.db = self.Session()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_deployed_missing_legal_page_fails_without_seeding(self) -> None:
        with patch.object(settings, "APP_ENV", "production"):
            with self.assertRaises(HTTPException) as raised:
                content_service.get_page(self.db, "privacy")

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(self.db.query(PageContent).count(), 0)

    def test_deployed_missing_faqs_returns_empty_without_seeding(self) -> None:
        with patch.object(settings, "APP_ENV", "staging"):
            result = content_service.list_faqs(self.db)

        self.assertEqual(result, [])
        self.assertEqual(self.db.query(FAQCategory).count(), 0)

    def test_development_default_page_is_read_only(self) -> None:
        with patch.object(settings, "APP_ENV", "development"):
            result = content_service.get_page(self.db, "agreement")

        self.assertEqual(result["key"], "agreement")
        self.assertTrue(result["content"])
        self.assertEqual(self.db.query(PageContent).count(), 0)


if __name__ == "__main__":
    unittest.main()

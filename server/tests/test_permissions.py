from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from tests._support import isolated_engine, session_factory
from app.dependencies import get_current_admin, require_super_admin
from app.models.admin import Admin


class PermissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        Admin.__table__.create(self.engine)
        self.Session = session_factory(self.engine)

    def tearDown(self) -> None:
        Admin.__table__.drop(self.engine)
        self.engine.dispose()

    @patch("app.dependencies.redis_client.is_token_blacklisted", return_value=False)
    @patch("app.dependencies.decode_access_token")
    def test_user_token_cannot_authenticate_as_admin(
        self, decode_access_token, _is_blacklisted
    ) -> None:
        decode_access_token.return_value = {"sub": "1", "type": "user"}
        db = self.Session()
        try:
            with self.assertRaises(HTTPException) as raised:
                get_current_admin(authorization="Bearer user-token", db=db)
            self.assertEqual(raised.exception.status_code, 401)
        finally:
            db.close()

    @patch("app.dependencies.redis_client.is_token_blacklisted", return_value=False)
    @patch("app.dependencies.decode_access_token")
    def test_inactive_admin_is_forbidden(
        self, decode_access_token, _is_blacklisted
    ) -> None:
        db = self.Session()
        try:
            admin = Admin(
                username="disabled-admin",
                password_hash="not-used",
                role="operator",
                is_active=False,
            )
            db.add(admin)
            db.commit()
            decode_access_token.return_value = {
                "sub": str(admin.id),
                "type": "admin",
            }
            with self.assertRaises(HTTPException) as raised:
                get_current_admin(authorization="Bearer admin-token", db=db)
            self.assertEqual(raised.exception.status_code, 403)
        finally:
            db.close()

    def test_operator_cannot_use_super_admin_action(self) -> None:
        operator = Admin(
            id=1,
            username="operator",
            password_hash="not-used",
            role="operator",
            is_active=True,
        )
        with self.assertRaises(HTTPException) as raised:
            require_super_admin(operator)
        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()

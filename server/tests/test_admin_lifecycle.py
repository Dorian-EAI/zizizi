from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from tests._support import isolated_engine, session_factory
from app.dependencies import get_current_admin, get_current_admin_for_password_change
from app.models.admin import Admin, AdminAuditLog
from app.services import admin_service
from app.utils.security import hash_password, verify_password


class AdminLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        Admin.__table__.create(self.engine)
        AdminAuditLog.__table__.create(self.engine)
        self.Session = session_factory(self.engine)

    def tearDown(self) -> None:
        AdminAuditLog.__table__.drop(self.engine)
        Admin.__table__.drop(self.engine)
        self.engine.dispose()

    def _add_admin(self, username: str, *, must_change: bool = True) -> Admin:
        db = self.Session()
        try:
            admin = Admin(
                username=username,
                password_hash=hash_password("InitialPass!234"),
                role="super_admin",
                must_change_password=must_change,
                is_active=True,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            db.expunge(admin)
            return admin
        finally:
            db.close()

    @patch("app.dependencies.redis_client.is_token_blacklisted", return_value=False)
    @patch("app.dependencies.decode_access_token")
    def test_initial_password_blocks_admin_actions_but_allows_change(
        self, decode_access_token, _blacklisted
    ) -> None:
        admin = self._add_admin("bootstrap")
        decode_access_token.return_value = {
            "sub": str(admin.id),
            "type": "admin",
            "ver": 1,
        }
        db = self.Session()
        try:
            with self.assertRaises(HTTPException) as raised:
                get_current_admin(authorization="Bearer token", db=db)
            self.assertEqual(raised.exception.status_code, 428)
            allowed = get_current_admin_for_password_change(
                authorization="Bearer token", db=db
            )
            self.assertEqual(allowed.id, admin.id)
        finally:
            db.close()

    def test_change_password_invalidates_tokens_and_clears_first_login_flag(self) -> None:
        admin = self._add_admin("change-me")
        db = self.Session()
        try:
            current = db.query(Admin).filter(Admin.id == admin.id).one()
            admin_service.change_admin_password(
                db,
                current,
                "InitialPass!234",
                "ReplacementPass!567",
            )
            db.refresh(current)
            self.assertFalse(current.must_change_password)
            self.assertEqual(current.token_version, 2)
            self.assertTrue(verify_password("ReplacementPass!567", current.password_hash))
        finally:
            db.close()

    def test_last_super_admin_cannot_be_disabled(self) -> None:
        actor = self._add_admin("only-super", must_change=False)
        db = self.Session()
        try:
            current = db.query(Admin).filter(Admin.id == actor.id).one()
            with self.assertRaises(HTTPException) as raised:
                admin_service.set_admin_active(db, current.id, False, current)
            self.assertIn(raised.exception.status_code, {400, 409})
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

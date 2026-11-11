from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.schemas.admin import AdminCreateRequest
from app.utils.security import hash_password, verify_password


class PasswordSecurityTests(unittest.TestCase):
    def test_bcrypt_round_trip_and_wrong_password(self) -> None:
        hashed = hash_password("Strong-Admin-Password!2026")
        self.assertTrue(hashed.startswith(("$2a$", "$2b$")))
        self.assertTrue(verify_password("Strong-Admin-Password!2026", hashed))
        self.assertFalse(verify_password("wrong-password", hashed))

    def test_malformed_hash_and_overlong_input_fail_closed(self) -> None:
        self.assertFalse(verify_password("password", "not-a-bcrypt-hash"))
        self.assertFalse(verify_password("密" * 25, hash_password("valid-password")))
        with self.assertRaises(ValueError):
            hash_password("x" * 73)

    def test_admin_schema_rejects_utf8_password_over_bcrypt_limit(self) -> None:
        with self.assertRaises(ValidationError):
            AdminCreateRequest(username="root2", password="密" * 25)


if __name__ == "__main__":
    unittest.main()

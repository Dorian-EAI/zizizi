"""Deployment environments must never inherit development fallbacks."""

from __future__ import annotations

import unittest

from tests._support import import_all_models

import_all_models()

from app.config import Settings


class EnvironmentSecurityTests(unittest.TestCase):
    def test_unknown_environment_is_rejected(self) -> None:
        config = Settings(APP_ENV="prod", _env_file=None)
        with self.assertRaisesRegex(RuntimeError, "APP_ENV"):
            config.validate_security()

    def test_staging_runs_deployment_security_validation(self) -> None:
        config = Settings(APP_ENV="staging", WX_PAY_MOCK_ENABLED=True, _env_file=None)
        with self.assertRaisesRegex(RuntimeError, "WX_PAY_MOCK_ENABLED"):
            config.validate_security()

    def test_environment_whitespace_cannot_bypass_deployment_validation(self) -> None:
        for app_env in ("production ", " staging"):
            with self.subTest(app_env=app_env):
                config = Settings(APP_ENV=app_env, WX_PAY_MOCK_ENABLED=True, _env_file=None)
                self.assertTrue(config.is_deployed)
                with self.assertRaisesRegex(RuntimeError, "WX_PAY_MOCK_ENABLED"):
                    config.validate_security()

    def test_deployment_rejects_weak_boundary_configuration(self) -> None:
        cases = (
            ({"CORS_ORIGINS": "http://admin.example.com"}, "CORS_ORIGINS"),
            ({"ALLOWED_HOSTS": "*"}, "ALLOWED_HOSTS"),
            ({"FIELD_ENC_KEY": "a"}, "FIELD_ENC_KEY"),
            ({"RATE_LIMIT_STORAGE": "memory://"}, "RATE_LIMIT_STORAGE"),
        )
        for overrides, expected in cases:
            with self.subTest(overrides=overrides):
                config = Settings(APP_ENV="production", _env_file=None, **overrides)
                with self.assertRaisesRegex(RuntimeError, expected):
                    config.validate_security()

    def test_relative_sqlite_path_is_anchored_to_server_directory(self) -> None:
        config = Settings(
            APP_ENV="development",
            DB_DRIVER="sqlite",
            SQLITE_PATH="data/test.db",
            _env_file=None,
        )
        self.assertIn("/server/data/test.db", config.database_url.replace("\\", "/"))

    def test_unknown_database_driver_is_rejected_even_in_development(self) -> None:
        config = Settings(APP_ENV="development", DB_DRIVER="postgres", _env_file=None)
        with self.assertRaisesRegex(RuntimeError, "DB_DRIVER"):
            config.validate_security()

    def test_mysql_credentials_are_url_encoded(self) -> None:
        config = Settings(
            APP_ENV="development",
            DB_DRIVER="mysql",
            DB_USER="repair+user",
            DB_PASSWORD="p@ss:/?# word",
            DB_NAME="repair db",
            _env_file=None,
        )
        self.assertIn("repair%2Buser:p%40ss%3A%2F%3F%23+word", config.database_url)
        self.assertIn("/repair+db?charset=utf8mb4", config.database_url)

    def test_runtime_enum_settings_are_normalized_on_input(self) -> None:
        config = Settings(
            APP_ENV=" Development ",
            DB_DRIVER=" SQLITE ",
            SMS_PROVIDER=" MOCK ",
            AI_PROVIDER=" MOCK ",
            OSS_PROVIDER=" LOCAL ",
            MAP_PROVIDER=" LOCAL ",
            JWT_ALGORITHM=" hs256 ",
            _env_file=None,
        )
        self.assertEqual(config.APP_ENV, "development")
        self.assertEqual(config.DB_DRIVER, "sqlite")
        self.assertEqual(config.SMS_PROVIDER, "mock")
        self.assertEqual(config.AI_PROVIDER, "mock")
        self.assertEqual(config.OSS_PROVIDER, "local")
        self.assertEqual(config.MAP_PROVIDER, "local")
        self.assertEqual(config.JWT_ALGORITHM, "HS256")


if __name__ == "__main__":
    unittest.main()

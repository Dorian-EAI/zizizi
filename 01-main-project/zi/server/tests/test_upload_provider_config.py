from __future__ import annotations

import asyncio
import json
import sys
import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.config import settings
from app.dependencies import require_super_admin
from app.models.admin import Admin, AdminAuditLog
from app.api.upload import DeleteFileRequest, delete_file, router as upload_router
from app.services.upload_service import (
    _build_oss_host,
    _certificate_object_key,
    delete_file_by_url,
    get_managed_object_identity,
    upload_image,
)
from tests._support import isolated_engine, session_factory


_IMAGE_KEY = "images/2026/08/03/0123456789abcdef0123456789abcdef.png"
_CERTIFICATE_KEY = "certificate/42/2026/08/03/0123456789abcdef0123456789abcdef.png"


class UploadProviderConfigTests(unittest.TestCase):
    def test_aliyun_endpoint_is_bucket_qualified(self) -> None:
        self.assertEqual(
            _build_oss_host("repair-prod", "https://oss-cn-shenzhen.aliyuncs.com"),
            "https://repair-prod.oss-cn-shenzhen.aliyuncs.com",
        )

    def test_bucket_qualified_endpoint_is_not_duplicated(self) -> None:
        self.assertEqual(
            _build_oss_host(
                "repair-prod",
                "https://repair-prod.oss-cn-shenzhen.aliyuncs.com/",
            ),
            "https://repair-prod.oss-cn-shenzhen.aliyuncs.com",
        )

    def test_cdn_domain_takes_precedence(self) -> None:
        self.assertEqual(
            _build_oss_host("repair-prod", "oss-cn-shenzhen.aliyuncs.com", "cdn.example.com/"),
            "https://cdn.example.com",
        )

    def test_certificate_upload_is_scoped_to_worker(self) -> None:
        with tempfile.TemporaryDirectory() as upload_dir, patch.object(
            settings, "UPLOAD_DIR", upload_dir
        ), patch.object(settings, "OSS_PROVIDER", "local"):
            result = upload_image(
                "certificate",
                b"\x89PNG\r\n\x1a\nminimal",
                "id-front.png",
                owner_id=42,
            )
        self.assertTrue(result["url"].startswith("/uploads/certificate/42/"))
        self.assertTrue(_certificate_object_key(result["url"], 42).startswith("certificate/42/"))
        with self.assertRaises(HTTPException):
            _certificate_object_key(result["url"], 43)

    def test_certificate_upload_requires_owner(self) -> None:
        with self.assertRaises(HTTPException):
            upload_image(
                "certificate",
                b"\x89PNG\r\n\x1a\nminimal",
                "id-front.png",
            )

    def test_aliyun_delete_accepts_only_exact_managed_host_and_key(self) -> None:
        bucket = Mock()
        fake_oss2 = SimpleNamespace(
            Auth=Mock(return_value="auth"),
            Bucket=Mock(return_value=bucket),
        )
        url = f"https://repair-prod.oss-cn-shenzhen.aliyuncs.com/{_IMAGE_KEY}"
        with patch.object(settings, "OSS_PROVIDER", "aliyun"), patch.object(
            settings, "OSS_BUCKET", "repair-prod"
        ), patch.object(
            settings, "OSS_ENDPOINT", "https://oss-cn-shenzhen.aliyuncs.com"
        ), patch.object(
            settings, "OSS_CDN_DOMAIN", "https://cdn.repair.example.cn"
        ), patch.dict(sys.modules, {"oss2": fake_oss2}):
            self.assertEqual(get_managed_object_identity(url), ("aliyun", _IMAGE_KEY))
            self.assertTrue(delete_file_by_url(url))

            invalid_urls = (
                f"https://repair-prod.oss-cn-shenzhen.aliyuncs.com.evil.cn/{_IMAGE_KEY}",
                f"http://repair-prod.oss-cn-shenzhen.aliyuncs.com/{_IMAGE_KEY}",
                f"https://repair-prod.oss-cn-shenzhen.aliyuncs.com/{_IMAGE_KEY}?version=1",
                "https://repair-prod.oss-cn-shenzhen.aliyuncs.com/images/../../secret.txt",
                f"https://repair-prod.oss-cn-shenzhen.aliyuncs.com/{_CERTIFICATE_KEY.replace('42/', '')}",
                f"https://cdn.repair.example.cn/{_CERTIFICATE_KEY}",
            )
            for invalid in invalid_urls:
                with self.subTest(url=invalid), self.assertRaises(HTTPException) as raised:
                    delete_file_by_url(invalid)
                self.assertEqual(raised.exception.status_code, 400)
        bucket.delete_object.assert_called_once_with(_IMAGE_KEY)

    def test_tencent_delete_uses_cos_sdk_with_exact_bucket_and_key(self) -> None:
        client = Mock()
        fake_cos = SimpleNamespace(
            CosConfig=Mock(return_value="config"),
            CosS3Client=Mock(return_value=client),
        )
        url = f"https://repair-prod-123.cos.ap-guangzhou.myqcloud.com/{_CERTIFICATE_KEY}"
        with patch.object(settings, "OSS_PROVIDER", "tencent"), patch.object(
            settings, "COS_BUCKET", "repair-prod-123"
        ), patch.object(settings, "COS_REGION", "ap-guangzhou"), patch.object(
            settings, "COS_CDN_DOMAIN", "https://cdn.repair.example.cn"
        ), patch.dict(sys.modules, {"qcloud_cos": fake_cos}):
            self.assertTrue(delete_file_by_url(url))
        client.delete_object.assert_called_once_with(
            Bucket="repair-prod-123",
            Key=_CERTIFICATE_KEY,
        )

    def test_delete_route_requires_super_admin_and_persists_result_audit(self) -> None:
        route = next(route for route in upload_router.routes if route.path == "/api/upload/file")
        dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
        self.assertIn(require_super_admin, dependency_calls)

        engine = isolated_engine()
        Admin.__table__.create(engine)
        AdminAuditLog.__table__.create(engine)
        Session = session_factory(engine)
        db = Session()
        try:
            admin = Admin(
                username="storage-admin",
                password_hash="not-used-in-this-test",
                role="super_admin",
                must_change_password=False,
                is_active=True,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            with tempfile.TemporaryDirectory() as upload_dir, patch.object(
                settings, "UPLOAD_DIR", upload_dir
            ), patch.object(settings, "OSS_PROVIDER", "local"):
                uploaded = upload_image(
                    "images",
                    b"\x89PNG\r\n\x1a\nminimal",
                    "repair.png",
                )
                response = asyncio.run(
                    delete_file(DeleteFileRequest(url=uploaded["url"]), admin=admin, db=db)
                )
                self.assertTrue(response["data"]["deleted"])
            audit = db.query(AdminAuditLog).one()
            self.assertEqual(audit.action, "delete_upload_file")
            self.assertEqual(json.loads(audit.detail)["status"], "deleted")
            self.assertNotIn("http", audit.detail)
        finally:
            db.close()
            AdminAuditLog.__table__.drop(engine)
            Admin.__table__.drop(engine)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()

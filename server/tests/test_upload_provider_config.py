from __future__ import annotations

import unittest

from app.services.upload_service import _build_oss_host


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


if __name__ == "__main__":
    unittest.main()

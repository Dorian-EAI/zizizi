from __future__ import annotations

import unittest

from fastapi import HTTPException

from app.services import export_service


class ExportSafetyTests(unittest.TestCase):
    def test_formula_prefixes_are_neutralized(self) -> None:
        for value in ("=1+1", "+cmd", "-2+3", "@SUM(A1)", "\tformula", "\rformula"):
            with self.subTest(value=value):
                self.assertEqual(export_service._sanitize_spreadsheet_value(value), "'" + value)
        self.assertEqual(export_service._sanitize_spreadsheet_value("普通文本"), "普通文本")

    def test_export_row_limit_fails_before_buffer_generation(self) -> None:
        class FakeQuery:
            def limit(self, value):
                self.limit_value = value
                return self

            def all(self):
                return [object()] * (export_service.MAX_EXPORT_ROWS + 1)

        with self.assertRaises(HTTPException) as raised:
            export_service._bounded_all(FakeQuery(), "测试导出")
        self.assertEqual(raised.exception.status_code, 413)

    def test_finance_range_is_bounded(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            export_service.export_finance_report(
                object(), start_date="2024-01-01", end_date="2026-01-01"
            )
        self.assertEqual(raised.exception.status_code, 413)


if __name__ == "__main__":
    unittest.main()

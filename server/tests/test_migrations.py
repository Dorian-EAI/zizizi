from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from tests._support import import_all_models
from app.database import Base


SERVER_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_LOCATION = SERVER_ROOT / "alembic"
BASELINE_REVISION = "59fdc7715893"


def _sqlite_url(path: Path) -> str:
    return "sqlite:///" + path.resolve().as_posix()


def _config(database_url: str, output_buffer=None) -> Config:
    cfg = Config(output_buffer=output_buffer)
    cfg.set_main_option("script_location", str(SCRIPT_LOCATION))
    cfg.attributes["database_url"] = database_url
    return cfg


class MigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import_all_models()

    def test_empty_database_upgrades_and_matches_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "fresh.db"
            cfg = _config(_sqlite_url(database))
            command.upgrade(cfg, "head")

            engine = create_engine(_sqlite_url(database))
            try:
                actual = set(inspect(engine).get_table_names())
                expected = set(Base.metadata.tables)
                self.assertEqual(actual - {"alembic_version"}, expected)
            finally:
                engine.dispose()

            # Autogenerate must see no drift between the checked-in migration
            # and the complete ORM metadata.
            command.check(cfg)

    def test_unversioned_legacy_schema_is_not_modified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "legacy.db"
            url = _sqlite_url(database)
            engine = create_engine(url)
            try:
                with engine.begin() as connection:
                    connection.execute(text("CREATE TABLE orders (id INTEGER PRIMARY KEY)"))
            finally:
                engine.dispose()

            with self.assertRaisesRegex(RuntimeError, "alembic stamp"):
                command.upgrade(_config(url), "head")

            engine = create_engine(url)
            try:
                inspector = inspect(engine)
                self.assertIn("orders", inspector.get_table_names())
                self.assertEqual(
                    [column["name"] for column in inspector.get_columns("orders")],
                    ["id"],
                )
            finally:
                engine.dispose()

    def test_mysql_offline_sql_can_be_generated(self) -> None:
        output = io.StringIO()
        cfg = _config(
            "mysql+pymysql://migration:secret@localhost/zjr_test?charset=utf8mb4",
            output_buffer=output,
        )
        command.upgrade(cfg, "head", sql=True)
        sql = output.getvalue().upper()
        self.assertIn("CREATE TABLE ORDERS", sql)
        self.assertIn("NUMERIC(12, 2)", sql)
        self.assertIn(BASELINE_REVISION.upper(), sql)


if __name__ == "__main__":
    unittest.main()

"""Shared helpers for isolated database tests."""

from __future__ import annotations

import importlib
import os
import pkgutil

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


# These values are applied before application modules are imported.  Tests must
# never connect to the developer's configured MySQL/SQLite database.
os.environ["APP_ENV"] = "testing"
os.environ["APP_DEBUG"] = "false"
os.environ["DB_DRIVER"] = "sqlite"
os.environ["SQLITE_PATH"] = ":memory:"


def import_all_models() -> None:
    import app.models

    prefix = app.models.__name__ + "."
    for module in pkgutil.iter_modules(app.models.__path__, prefix):
        if not module.name.rsplit(".", 1)[-1].startswith("_"):
            importlib.import_module(module.name)


def isolated_engine():
    """Return a process-local SQLite engine shared by all test sessions."""
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def session_factory(engine):
    return sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

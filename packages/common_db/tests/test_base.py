"""Smoke tests for step 1 of the unification plan.

Step 1 only ships the package skeleton: Base, URL helpers, session factory,
empty models package. These tests confirm imports work and the skeleton is
in the shape later steps expect.
"""
from __future__ import annotations

import importlib
import os

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

import common_db
from common_db import Base, async_db_url, make_async_session, sync_db_url


class TestPackageSurface:
    def test_public_exports(self) -> None:
        assert set(common_db.__all__) >= {
            "Base",
            "async_db_url",
            "sync_db_url",
            "make_async_session",
        }

    def test_base_is_declarative_base(self) -> None:
        assert issubclass(Base, DeclarativeBase)

    def test_metadata_is_populated(self) -> None:
        # Step 2 registers all 20 tables on the shared metadata. If any
        # table goes missing here, a service has been silently un-wired.
        # Importing the models package is what triggers registration.
        import common_db.models  # noqa: F401
        assert set(Base.metadata.tables.keys()) >= {
            "users",
            "support_tickets",
            "support_messages",
            "transactions",
            "promos",
            "tariff_plans",
            "menu_screens",
            "webapp_menu_nodes",
        }

    def test_models_subpackage_exports_classes(self) -> None:
        models_pkg = importlib.import_module("common_db.models")
        assert hasattr(models_pkg, "__all__")
        assert {"User", "SupportTicket", "SupportMessage", "Transaction"} <= set(
            models_pkg.__all__
        )


class TestUrlHelpers:
    def setup_method(self) -> None:
        self._saved = {
            "DATABASE_URL": os.environ.pop("DATABASE_URL", None),
            "DB_PATH": os.environ.pop("DB_PATH", None),
        }

    def teardown_method(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_async_url_uses_database_url_when_set(self) -> None:
        os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:pw@host/db"
        assert async_db_url() == "postgresql+asyncpg://user:pw@host/db"

    def test_async_url_falls_back_to_sqlite_default(self) -> None:
        assert async_db_url(default_sqlite_path="x.sqlite3") == "sqlite+aiosqlite:///x.sqlite3"

    def test_async_url_respects_db_path_env(self) -> None:
        os.environ["DB_PATH"] = "/tmp/from_env.sqlite3"
        assert async_db_url(default_sqlite_path="ignored") == "sqlite+aiosqlite:////tmp/from_env.sqlite3"

    def test_sync_url_converts_asyncpg_to_psycopg2(self) -> None:
        os.environ["DATABASE_URL"] = "postgresql+asyncpg://u:p@h/d"
        assert sync_db_url() == "postgresql+psycopg2://u:p@h/d"

    def test_sync_url_converts_aiosqlite_to_sqlite(self) -> None:
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///x.sqlite3"
        assert sync_db_url() == "sqlite:///x.sqlite3"

    def test_sync_url_passes_through_unrecognized(self) -> None:
        os.environ["DATABASE_URL"] = "postgresql://u:p@h/d"
        assert sync_db_url() == "postgresql://u:p@h/d"


class TestSessionFactory:
    def setup_method(self) -> None:
        self._saved = {
            "DATABASE_URL": os.environ.pop("DATABASE_URL", None),
            "DB_PATH": os.environ.pop("DB_PATH", None),
        }

    def teardown_method(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_make_async_session_returns_engine_and_factory(self) -> None:
        engine, session_factory = make_async_session(default_sqlite_path=":memory:")
        try:
            assert isinstance(engine, AsyncEngine)
            assert isinstance(session_factory, async_sessionmaker)
            # sqlite-default connect_args were applied automatically
            assert engine.url.get_backend_name() == "sqlite"
        finally:
            # Engines hold a connection pool — be tidy even for in-memory.
            import asyncio
            asyncio.run(engine.dispose())

    def test_make_async_session_honours_explicit_connect_args(self) -> None:
        engine, _ = make_async_session(
            default_sqlite_path=":memory:",
            connect_args={"timeout": 5},
        )
        try:
            # If a caller passes connect_args explicitly, we must not silently
            # overwrite them with the sqlite-default block.
            assert engine.url.get_backend_name() == "sqlite"
        finally:
            import asyncio
            asyncio.run(engine.dispose())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))

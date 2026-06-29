"""Resolve DB URL for any service in the project.

Reads `DATABASE_URL` first — when set, that's authoritative (Postgres in
prod, can also be sqlite+aiosqlite:/// for tests). Falls back to the legacy
`DB_PATH` env var + sqlite, which is how dev/CI currently work.

This is the single copy of what used to be duplicated byte-for-byte in
app/database/url.py, miniapp/backend/database/url.py and
dashboard/backend/database/url.py.
"""
from __future__ import annotations

import os


def async_db_url(default_sqlite_path: str | None = None) -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    db_path = os.environ.get("DB_PATH") or default_sqlite_path or "db.sqlite3"
    return f"sqlite+aiosqlite:///{db_path}"


def sync_db_url(default_sqlite_path: str | None = None) -> str:
    """Same resolution, but coerced to a sync driver (Alembic + pg_dump)."""
    url = os.environ.get("DATABASE_URL")
    if url:
        if url.startswith("postgresql+asyncpg://"):
            return "postgresql+psycopg2://" + url[len("postgresql+asyncpg://"):]
        if url.startswith("sqlite+aiosqlite:///"):
            return "sqlite:///" + url[len("sqlite+aiosqlite:///"):]
        return url
    db_path = os.environ.get("DB_PATH") or default_sqlite_path or "db.sqlite3"
    return f"sqlite:///{db_path}"

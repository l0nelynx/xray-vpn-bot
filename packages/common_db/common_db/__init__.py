"""Shared database layer (Base, URL helpers, session factory, models).

Public API:
    Base — shared DeclarativeBase (AsyncAttrs-enabled).
    async_db_url, sync_db_url — env-driven URL resolution.
    make_async_session — engine + sessionmaker factory per service.
    common_db.models — package of ORM model classes (added in step 2).
"""
from .base import Base
from .session import make_async_session
from .url import async_db_url, sync_db_url

__all__ = [
    "Base",
    "async_db_url",
    "sync_db_url",
    "make_async_session",
]

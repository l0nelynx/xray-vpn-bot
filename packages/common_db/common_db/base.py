"""Shared declarative Base for app/miniapp/dashboard.

All ORM models in common_db.models inherit from this Base, so its metadata
holds the single source of truth for the schema. Each service binds its own
engine to the same metadata via common_db.session.make_async_session.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base shared across all services."""
    pass

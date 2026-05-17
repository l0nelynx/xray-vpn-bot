"""Backwards-compatible re-export of shared URL helpers.

Lives in `common_db.url` now. This shim keeps `from app.database.url import
async_db_url` in app/database/models.py working without code changes.
New code should import directly from `common_db`.
"""
from common_db.url import async_db_url, sync_db_url

__all__ = ["async_db_url", "sync_db_url"]

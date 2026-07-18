"""Enqueue Remnawave webhook payloads onto the CRM ARQ queue."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

JOB_NAME = "execute_crm_webhook"
_pool = None


def _redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://redis:6379/0")


async def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
    except ImportError:
        logger.error("arq is not installed — cannot enqueue CRM webhook jobs")
        return None
    try:
        _pool = await create_pool(RedisSettings.from_dsn(_redis_url()))
    except Exception as exc:
        logger.error("Failed to connect to Redis for CRM webhooks: %s", exc)
        return None
    return _pool


async def enqueue_crm_webhook(payload: dict[str, Any]) -> bool:
    """Enqueue payload for crm-worker. Returns False if Redis/ARQ unavailable."""
    pool = await _get_pool()
    if pool is None:
        return False
    try:
        await pool.enqueue_job(JOB_NAME, payload)
        return True
    except Exception as exc:
        logger.error("Failed to enqueue CRM webhook job: %s", exc)
        return False

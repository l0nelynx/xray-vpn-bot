"""CRM Remnawave webhook enqueue helpers (ARQ)."""

from __future__ import annotations

from typing import Any

from arq import ArqRedis

JOB_NAME = "execute_crm_webhook"


async def enqueue_webhook(pool: ArqRedis | None, payload: dict[str, Any]) -> None:
    if pool is None:
        raise RuntimeError("Redis queue is unavailable")
    await pool.enqueue_job(JOB_NAME, payload)

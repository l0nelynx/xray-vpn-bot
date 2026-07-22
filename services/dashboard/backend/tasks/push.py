"""Push campaign enqueue helpers (ARQ)."""

from __future__ import annotations

from arq import ArqRedis

JOB_NAME = "execute_push_campaign"


async def enqueue_push_campaign(pool: ArqRedis | None, campaign_id: int) -> None:
    if pool is None:
        raise RuntimeError("Redis queue is unavailable")
    await pool.enqueue_job(JOB_NAME, campaign_id)

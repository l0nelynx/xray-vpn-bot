"""Giveaway ARQ enqueue helpers."""

from __future__ import annotations

from arq import ArqRedis

JOB_NAME = "execute_giveaway_broadcast"


async def enqueue_giveaway_broadcast(pool: ArqRedis | None, giveaway_id: int) -> None:
    if pool is None:
        raise RuntimeError("Redis queue is unavailable")
    await pool.enqueue_job(JOB_NAME, giveaway_id)

"""ARQ worker settings for CRM campaign execution."""

from __future__ import annotations

import os

from arq import cron
from arq.connections import RedisSettings

from .config import get_redis_url
from .crm_event_runner import tick_crm_events
from .crm_runner import execute_crm_campaign as run_campaign


async def execute_crm_campaign(ctx, campaign_id: int) -> None:
    """ARQ job entry point."""
    await run_campaign(campaign_id)


class WorkerSettings:
    functions = [execute_crm_campaign, tick_crm_events]
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", get_redis_url()))
    job_timeout = 3600
    max_tries = 1
    cron_jobs = [
        cron(tick_crm_events, minute={0, 15, 30, 45}),
    ]

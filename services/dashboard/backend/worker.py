"""ARQ worker settings for CRM + FCM push campaign execution."""

from __future__ import annotations

import os
from typing import Any

from arq import cron
from arq.connections import RedisSettings

from .config import get_redis_url
from .crm_event_runner import tick_crm_events
from .crm_runner import execute_crm_campaign as run_campaign
from .crm_webhook_runner import execute_crm_webhook as run_webhook
from .giveaway_runner import execute_giveaway_broadcast as run_giveaway_broadcast
from .push_runner import execute_push_campaign as run_push_campaign


async def execute_crm_campaign(ctx, campaign_id: int) -> None:
    """ARQ job entry point."""
    await run_campaign(campaign_id)


async def execute_push_campaign(ctx, campaign_id: int) -> None:
    """ARQ job entry point for FCM push campaigns."""
    await run_push_campaign(campaign_id)


async def execute_crm_webhook(ctx, payload: dict[str, Any]) -> None:
    """ARQ job entry point for Remnawave inbound webhooks."""
    await run_webhook(payload)


async def execute_giveaway_broadcast(ctx, giveaway_id: int) -> None:
    """ARQ job entry point for giveaway DM broadcast."""
    await run_giveaway_broadcast(giveaway_id)


class WorkerSettings:
    functions = [
        execute_crm_campaign,
        tick_crm_events,
        execute_push_campaign,
        execute_crm_webhook,
        execute_giveaway_broadcast,
    ]
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", get_redis_url()))
    job_timeout = 3600
    max_tries = 1
    cron_jobs = [
        cron(tick_crm_events, minute={0, 15, 30, 45}),
    ]

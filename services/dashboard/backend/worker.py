"""ARQ worker settings for CRM + FCM push campaign execution."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from arq import cron
from arq.connections import RedisSettings

from .config import get_redis_url, get_yaml_config, get_payments_secrets_key
from .crm_event_runner import tick_crm_events
from .crm_runner import execute_crm_campaign as run_campaign
from .crm_webhook_runner import execute_crm_webhook as run_webhook
from .giveaway_runner import execute_giveaway_broadcast as run_giveaway_broadcast
from .push_runner import execute_push_campaign as run_push_campaign
from .api_health_worker import api_health_tick


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


async def startup(ctx) -> None:
    from common_db.runtime_config import bootstrap_runtime_overlay, runtime_overlay_poll_loop
    from .database.session import async_session

    await bootstrap_runtime_overlay(
        async_session, get_yaml_config(), crypto_secret=get_payments_secrets_key(),
    )
    ctx["runtime_overlay_task"] = asyncio.create_task(runtime_overlay_poll_loop(async_session))


async def shutdown(ctx) -> None:
    task = ctx.pop("runtime_overlay_task", None)
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class WorkerSettings:
    on_startup = startup
    on_shutdown = shutdown
    functions = [
        execute_crm_campaign,
        tick_crm_events,
        execute_push_campaign,
        execute_crm_webhook,
        execute_giveaway_broadcast,
        api_health_tick,
    ]
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", get_redis_url()))
    job_timeout = 3600
    max_tries = 1
    cron_jobs = [
        cron(tick_crm_events, minute={0, 15, 30, 45}),
        cron(api_health_tick, minute=set(range(60))),
    ]

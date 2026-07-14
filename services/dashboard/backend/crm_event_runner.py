"""CRM scheduled event runner — fresh segment scan + campaign enqueue."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from arq import ArqRedis
from remnawave_client.segmentation import SEGMENT_ALL_USERS

from common_db.repo import crm as crm_repo
from common_db.repo import crm_events as events_repo

from .config import get_remnawave_token, get_remnawave_url
from .crm_service import scan_segment
from .database.session import async_session
from .tasks.crm import enqueue_campaign

logger = logging.getLogger(__name__)


def _rw_client():
    from remnawave_client import configure

    return configure(
        base_url=get_remnawave_url(),
        token=get_remnawave_token(),
        free_squad_id="",
    )


def _scan_kwargs(params: dict) -> dict:
    return {
        "days_threshold": int(params.get("days_threshold", 3)),
        "traffic_threshold": float(params.get("traffic_threshold", 0.8)),
        "invoice_max_age_hours": int(params.get("invoice_max_age_hours", 48)),
        "torrent_days": int(params.get("torrent_days", 7)),
        "preview_limit": None,
    }


async def run_crm_event(
    event_id: int,
    *,
    arq_pool: ArqRedis | None = None,
    force: bool = False,
) -> dict:
    """Execute one scheduled CRM event: scan → filter → campaign → queue."""
    rw = _rw_client()

    async with async_session() as session:
        event = await events_repo.get_event(session, event_id)
        if not event:
            return {"status": "not_found", "event_id": event_id}
        if not event.enabled and not force:
            return {"status": "disabled", "event_id": event_id}

        params = json.loads(event.segment_params or "{}")
        segment_type = event.segment_type or ""
        scan_kw = _scan_kwargs(params)

        users, total, warning = await scan_segment(
            session,
            rw,
            segment_type,
            **scan_kw,
        )
        tg_ids = [u["tg_id"] for u in users if u.get("tg_id") is not None]

        ever_sent: set[int] = set()
        recent_sent: set[int] = set()
        if event.repeat_policy == "once":
            ever_sent = await events_repo.get_sent_tg_ids_for_event(session, event_id)
        elif event.repeat_policy == "cooldown":
            since = (
                datetime.now(timezone.utc).replace(tzinfo=None)
                - timedelta(days=event.repeat_cooldown_days)
            ).isoformat(timespec="seconds")
            recent_sent = await events_repo.get_recent_sent_tg_ids(
                session, event_id, since_iso=since
            )

        filtered = events_repo.filter_tg_ids_by_repeat_policy(
            tg_ids,
            repeat_policy=event.repeat_policy,
            repeat_cooldown_days=event.repeat_cooldown_days,
            ever_sent=ever_sent,
            recent_sent=recent_sent,
        )

        if not filtered:
            await events_repo.mark_event_run(session, event)
            await session.commit()
            logger.info(
                "CRM event %s: empty audience after repeat filter (scan=%d)",
                event_id,
                total,
            )
            return {
                "status": "empty",
                "event_id": event_id,
                "scan_total": total,
                "warning": warning,
            }

        store_targets = None if segment_type == SEGMENT_ALL_USERS else filtered

        campaign = await crm_repo.create_campaign(
            session,
            name=event.name or f"Event #{event_id}",
            segment_type=segment_type,
            segment_params=params,
            message_text=event.message_text,
            attach_button=event.attach_button,
            bonus_days=event.bonus_days,
            bonus_traffic_gb=event.bonus_traffic_gb,
            created_by="system",
            target_tg_ids=store_targets,
            event_id=event_id,
        )
        campaign.total_targets = len(filtered)
        await crm_repo.queue_campaign(session, campaign)
        await events_repo.mark_event_run(session, event)
        await session.commit()
        campaign_id = campaign.id

    if arq_pool is None:
        logger.warning(
            "CRM event %s: no ARQ pool — campaign %s queued but not enqueued",
            event_id,
            campaign_id,
        )
        return {
            "status": "queued_no_worker",
            "event_id": event_id,
            "campaign_id": campaign_id,
            "total": len(filtered),
            "warning": warning,
        }

    await enqueue_campaign(arq_pool, campaign_id)
    logger.info(
        "CRM event %s → campaign %s queued for %d users",
        event_id,
        campaign_id,
        len(filtered),
    )
    return {
        "status": "queued",
        "event_id": event_id,
        "campaign_id": campaign_id,
        "total": len(filtered),
        "warning": warning,
    }


async def tick_crm_events(ctx) -> None:
    """ARQ cron: run all due CRM events."""
    pool = ctx.get("redis") if isinstance(ctx, dict) else None
    async with async_session() as session:
        due = await events_repo.list_due_events(session)
        await session.commit()

    for event in due:
        try:
            await run_crm_event(event.id, arq_pool=pool)
        except Exception:
            logger.exception("CRM event tick failed for event_id=%s", event.id)

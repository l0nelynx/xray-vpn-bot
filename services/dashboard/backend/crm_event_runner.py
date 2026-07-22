"""CRM scheduled event runner — fresh segment scan + campaign enqueue."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from arq import ArqRedis

from common_db.repo import crm as crm_repo
from common_db.repo import crm_events as events_repo

from .config import get_remnawave_token, get_remnawave_url
from .crm_conditions import evaluate_conditions_full
from .crm_model_adapter import get_actions, get_conditions, sync_flat_from_model
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


async def run_crm_event(
    event_id: int,
    *,
    arq_pool: ArqRedis | None = None,
    force: bool = False,
) -> dict:
    """Execute one scheduled CRM event: evaluate conditions → campaign → queue."""
    rw = _rw_client()

    async with async_session() as session:
        event = await events_repo.get_event(session, event_id)
        if not event:
            return {"status": "not_found", "event_id": event_id}
        if not event.enabled and not force:
            return {"status": "disabled", "event_id": event_id}

        conditions = get_conditions(event)
        actions = get_actions(event)
        flat = sync_flat_from_model(conditions=conditions, actions=actions)

        tg_ids, warning = await evaluate_conditions_full(session, rw, conditions)

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
                len(tg_ids),
            )
            return {
                "status": "empty",
                "event_id": event_id,
                "scan_total": len(tg_ids),
                "warning": warning,
            }

        # Store frozen audience on the campaign (runner uses target_tg_ids fast path)
        campaign_conditions = [
            c for c in conditions if c.get("type") != "tg_allowlist"
        ]
        campaign_conditions.append(
            {"type": "tg_allowlist", "tg_ids": filtered}
        )

        campaign = await crm_repo.create_campaign(
            session,
            name=event.name or f"Event #{event_id}",
            conditions=campaign_conditions,
            actions=actions,
            segment_type=flat.get("segment_type"),
            segment_params=dict(flat.get("segment_params") or {}),
            message_text=flat.get("message_text") or "",
            attach_button=bool(flat.get("attach_button")),
            bonus_days=flat.get("bonus_days"),
            bonus_traffic_gb=flat.get("bonus_traffic_gb"),
            created_by="system",
            target_tg_ids=filtered,
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

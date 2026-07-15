"""CRM campaign execution — runs in the ARQ crm-worker process."""

from __future__ import annotations

import asyncio
import json
import logging

from common_db.repo import crm as crm_repo
from common_db.repo.users import get_users_by_tg_ids

from .config import get_remnawave_token, get_remnawave_url
from .crm_actions import execute_user_actions
from .crm_conditions import evaluate_conditions_full
from .crm_model_adapter import get_actions, get_conditions
from .database.session import async_session
from .telegram import tg_bot_username

logger = logging.getLogger(__name__)


def _rw_client():
    from remnawave_client import configure

    return configure(
        base_url=get_remnawave_url(),
        token=get_remnawave_token(),
        free_squad_id="",
    )


async def resolve_targets(
    session,
    campaign,
    override_tg_ids: list[int] | None = None,
) -> list[int]:
    if override_tg_ids:
        return override_tg_ids
    params = json.loads(campaign.segment_params or "{}")
    stored = params.get("target_tg_ids")
    if stored:
        return list(stored)
    conditions = get_conditions(campaign)
    if not conditions:
        return []
    rw = _rw_client()
    tg_ids, _ = await evaluate_conditions_full(session, rw, conditions)
    return tg_ids


async def execute_crm_campaign(
    campaign_id: int,
    override_tg_ids: list[int] | None = None,
) -> None:
    """Run action pipeline for a queued campaign."""
    rw = _rw_client()
    crm_by_uuid: dict[str, dict] = {}

    try:
        async with async_session() as session:
            campaign = await crm_repo.get_campaign(session, campaign_id)
            if not campaign:
                return
            if campaign.status not in ("queued", "running"):
                logger.info(
                    "CRM campaign %s skip: status=%s", campaign_id, campaign.status
                )
                return

            tg_ids = await resolve_targets(session, campaign, override_tg_ids)
            if not tg_ids:
                await crm_repo.update_campaign_status(
                    session, campaign, status="failed", completed=True
                )
                await session.commit()
                return

            await crm_repo.update_campaign_status(
                session,
                campaign,
                status="running",
                total_targets=len(tg_ids),
                started=True,
            )
            await session.commit()

            actions = get_actions(campaign)
            event_id = getattr(campaign, "event_id", None)

        try:
            for u in await rw.get_all_users_for_crm():
                if u.get("uuid"):
                    crm_by_uuid[u["uuid"]] = u
        except Exception as exc:
            logger.error("CRM campaign %s: bulk RW fetch failed: %s", campaign_id, exc)

        bot_username = await tg_bot_username()

        async with async_session() as session:
            users = await get_users_by_tg_ids(session, tg_ids)
            user_by_tg = {u.tg_id: u for u in users if u.tg_id is not None}

        sent = failed = perks_ok = perks_fail = 0

        for i, tg_id in enumerate(tg_ids):
            db_user = user_by_tg.get(tg_id)
            perk_status = "skipped"
            message_status = "skipped"
            error_parts: list[str] = []

            if not db_user:
                failed += 1
                message_status = "failed"
                async with async_session() as session:
                    await crm_repo.add_delivery(
                        session,
                        campaign_id=campaign_id,
                        tg_id=tg_id,
                        vless_uuid=None,
                        perk_status="skipped",
                        message_status="failed",
                        error="user not found",
                    )
                    await session.commit()
                continue

            crm_user = crm_by_uuid.get(db_user.vless_uuid or "")

            async def _on_sent(eid=event_id, uid=tg_id):
                if not eid:
                    return
                async with async_session() as session:
                    from common_db.repo import crm_events as events_repo

                    await events_repo.record_event_delivery(
                        session, event_id=eid, tg_id=uid
                    )
                    await session.commit()

            async with async_session() as session:
                result = await execute_user_actions(
                    rw,
                    db_user,
                    crm_user,
                    actions,
                    bot_username=bot_username,
                    event_id=event_id,
                    on_message_sent=_on_sent if event_id else None,
                    session=session,
                )

                if result.perks_applied:
                    perks_ok += 1
                    perk_status = "applied"
                elif result.perks_failed:
                    perks_fail += 1
                    perk_status = "failed"
                error_parts.extend(result.errors)

                if result.message_sent:
                    sent += 1
                    message_status = "sent"
                elif result.message_failed:
                    failed += 1
                    message_status = "failed"
                elif not result.message_skipped:
                    message_status = "failed"
                    failed += 1

                await crm_repo.add_delivery(
                    session,
                    campaign_id=campaign_id,
                    tg_id=tg_id,
                    vless_uuid=db_user.vless_uuid,
                    perk_status=perk_status,
                    message_status=message_status,
                    error="; ".join(error_parts) if error_parts else None,
                )
                await session.commit()

            if (i + 1) % 25 == 0:
                async with async_session() as session:
                    campaign = await crm_repo.get_campaign(session, campaign_id)
                    if campaign:
                        await crm_repo.update_campaign_progress(
                            session,
                            campaign,
                            messages_sent=sent,
                            messages_failed=failed,
                            perks_applied=perks_ok,
                            perks_failed=perks_fail,
                        )
                        await session.commit()
                await asyncio.sleep(1)

        async with async_session() as session:
            campaign = await crm_repo.get_campaign(session, campaign_id)
            if campaign:
                await crm_repo.update_campaign_status(
                    session,
                    campaign,
                    status="completed",
                    messages_sent=sent,
                    messages_failed=failed,
                    perks_applied=perks_ok,
                    perks_failed=perks_fail,
                    completed=True,
                )
                await session.commit()

        logger.info(
            "CRM campaign %s done: sent=%d failed=%d perks_ok=%d perks_fail=%d",
            campaign_id,
            sent,
            failed,
            perks_ok,
            perks_fail,
        )
    except Exception:
        logger.exception("CRM campaign %s failed", campaign_id)
        async with async_session() as session:
            campaign = await crm_repo.get_campaign(session, campaign_id)
            if campaign and campaign.status == "running":
                await crm_repo.update_campaign_status(
                    session, campaign, status="failed", completed=True
                )
                await session.commit()
        raise

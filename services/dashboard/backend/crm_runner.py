"""CRM campaign execution — runs in the ARQ crm-worker process."""

from __future__ import annotations

import asyncio
import json
import logging

from common_db.repo import crm as crm_repo
from common_db.repo import crm_segments as seg_repo
from common_db.repo.users import get_users_by_tg_ids
from remnawave_client.segmentation import SEGMENT_ALL_USERS

from .config import get_remnawave_token, get_remnawave_url
from .crm_service import apply_campaign_perks
from .crm_variables import build_message_context, render_crm_message
from .database.session import async_session
from .telegram import tg_bot_username, tg_bot_open_url, tg_send

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
    if campaign.segment_type == SEGMENT_ALL_USERS:
        users = await seg_repo.get_broadcast_eligible_users(session)
        params = json.loads(campaign.segment_params or "{}")
        user_type = params.get("user_type", seg_repo.USER_TYPE_ALL)
        users = await seg_repo.filter_users_by_type(session, users, user_type)
        return [u.tg_id for u in users if u.tg_id is not None]
    params = json.loads(campaign.segment_params or "{}")
    stored = params.get("target_tg_ids")
    if stored:
        return list(stored)
    return []


async def execute_crm_campaign(
    campaign_id: int,
    override_tg_ids: list[int] | None = None,
) -> None:
    """Run perks + Telegram broadcast for a queued campaign."""
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

            message_text = campaign.message_text
            attach_button = campaign.attach_button
            bonus_days = campaign.bonus_days
            bonus_traffic_gb = campaign.bonus_traffic_gb
            event_id = getattr(campaign, "event_id", None)

        try:
            for u in await rw.get_all_users_for_crm():
                if u.get("uuid"):
                    crm_by_uuid[u["uuid"]] = u
        except Exception as exc:
            logger.error("CRM campaign %s: bulk RW fetch failed: %s", campaign_id, exc)

        reply_markup = None
        if attach_button:
            bot_username = await tg_bot_username()
            if bot_username:
                reply_markup = {
                    "inline_keyboard": [[
                        {"text": "Открыть бота", "url": tg_bot_open_url(bot_username)}
                    ]]
                }

        async with async_session() as session:
            users = await get_users_by_tg_ids(session, tg_ids)
            user_by_tg = {u.tg_id: u for u in users if u.tg_id is not None}

        sent = failed = perks_ok = perks_fail = 0

        for i, tg_id in enumerate(tg_ids):
            db_user = user_by_tg.get(tg_id)
            perk_status = "skipped"
            message_status = "failed"
            error_parts: list[str] = []

            if not db_user:
                failed += 1
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
            else:
                crm_user = crm_by_uuid.get(db_user.vless_uuid or "")
                has_perks = bool(bonus_days or bonus_traffic_gb)

                if has_perks and db_user.vless_uuid:
                    ok, perk_err = await apply_campaign_perks(
                        rw,
                        db_user,
                        crm_user,
                        bonus_days=bonus_days,
                        bonus_traffic_gb=bonus_traffic_gb,
                    )
                    if ok:
                        perks_ok += 1
                        perk_status = "applied"
                    else:
                        perks_fail += 1
                        perk_status = "failed"
                        if perk_err:
                            error_parts.append(perk_err)
                elif has_perks:
                    perks_fail += 1
                    perk_status = "failed"
                    error_parts.append("no vless_uuid for perks")

                ctx = build_message_context(
                    username=db_user.username,
                    crm_user=crm_user,
                )
                personalized = render_crm_message(message_text, ctx)

                if await tg_send(tg_id, personalized, reply_markup):
                    sent += 1
                    message_status = "sent"
                    if event_id:
                        async with async_session() as session:
                            from common_db.repo import crm_events as events_repo

                            await events_repo.record_event_delivery(
                                session, event_id=event_id, tg_id=tg_id
                            )
                            await session.commit()
                else:
                    failed += 1
                    error_parts.append("telegram send failed")

                async with async_session() as session:
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

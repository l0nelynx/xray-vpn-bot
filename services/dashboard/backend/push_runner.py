"""Push campaign execution — runs in the ARQ crm-worker process."""
from __future__ import annotations

import asyncio
import logging

from common_db.repo import fcm as fcm_repo
from common_db.repo import push as push_repo

from .database.session import async_session
from .fcm_sender import FcmError, fcm_configured, send_notification

logger = logging.getLogger(__name__)

# Bound concurrency so we don't open thousands of HTTP connections at once.
_SEND_CONCURRENCY = 20
_PROGRESS_EVERY = 25


async def _resolve_targets(session, campaign):
    audience = (campaign.audience or "all_tokens").strip()
    if audience == "user_ids":
        params = push_repo.get_audience_params(campaign)
        raw_ids = params.get("user_ids") or []
        user_ids: list[int] = []
        for item in raw_ids:
            try:
                user_ids.append(int(item))
            except (TypeError, ValueError):
                continue
        return await fcm_repo.list_tokens_for_users(session, user_ids)
    return await fcm_repo.list_tokens_all(session)


async def execute_push_campaign(campaign_id: int) -> None:
    """Run FCM delivery for a queued push campaign."""
    if not fcm_configured():
        async with async_session() as session:
            campaign = await push_repo.get_campaign(session, campaign_id)
            if campaign:
                await push_repo.update_campaign_status(
                    session,
                    campaign,
                    status="failed",
                    completed=True,
                )
                await session.commit()
        logger.error("Push campaign %s failed: FCM not configured", campaign_id)
        return

    async with async_session() as session:
        campaign = await push_repo.get_campaign(session, campaign_id)
        if not campaign:
            logger.warning("Push campaign %s not found", campaign_id)
            return
        if campaign.status not in ("queued", "running"):
            logger.info(
                "Push campaign %s skip: status=%s", campaign_id, campaign.status
            )
            return

        tokens = await _resolve_targets(session, campaign)
        title = campaign.title or ""
        body = campaign.body or ""
        data = push_repo.get_data(campaign)

        await push_repo.update_campaign_status(
            session,
            campaign,
            status="running",
            total_targets=len(tokens),
            started=True,
        )
        await session.commit()

    if not tokens:
        async with async_session() as session:
            campaign = await push_repo.get_campaign(session, campaign_id)
            if campaign:
                await push_repo.update_campaign_status(
                    session,
                    campaign,
                    status="completed",
                    sent=0,
                    failed=0,
                    total_targets=0,
                    completed=True,
                )
                await session.commit()
        return

    sem = asyncio.Semaphore(_SEND_CONCURRENCY)
    sent = 0
    failed = 0
    lock = asyncio.Lock()

    async def _one(row) -> None:
        nonlocal sent, failed
        async with sem:
            try:
                result = await send_notification(
                    token=row.token,
                    title=title,
                    body=body,
                    data=data,
                )
            except FcmError as exc:
                result_ok = False
                dead = False
                err_msg = str(exc)[:500]
                err_code = "CONFIG"
            else:
                result_ok = result.ok
                dead = result.dead_token
                err_msg = result.error_message
                err_code = result.error_code

            status = "sent" if result_ok else "failed"
            async with async_session() as session:
                await push_repo.add_delivery(
                    session,
                    campaign_id=campaign_id,
                    user_id=row.user_id,
                    token=row.token,
                    status=status,
                    error=None if result_ok else (err_code or err_msg),
                )
                if dead:
                    await fcm_repo.delete_token_by_value(session, row.token)
                await session.commit()

            async with lock:
                if result_ok:
                    sent += 1
                else:
                    failed += 1
                total_done = sent + failed
                if total_done % _PROGRESS_EVERY == 0 or total_done == len(tokens):
                    async with async_session() as session:
                        campaign = await push_repo.get_campaign(session, campaign_id)
                        if campaign:
                            await push_repo.update_campaign_progress(
                                session, campaign, sent=sent, failed=failed
                            )
                            await session.commit()

    try:
        await asyncio.gather(*[_one(row) for row in tokens])
        final_status = "completed"
    except Exception:
        logger.exception("Push campaign %s crashed", campaign_id)
        final_status = "failed"

    async with async_session() as session:
        campaign = await push_repo.get_campaign(session, campaign_id)
        if campaign:
            await push_repo.update_campaign_status(
                session,
                campaign,
                status=final_status,
                sent=sent,
                failed=failed,
                completed=True,
            )
            await session.commit()

    logger.info(
        "Push campaign %s %s: sent=%s failed=%s total=%s",
        campaign_id,
        final_status,
        sent,
        failed,
        len(tokens),
    )

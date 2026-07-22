"""Giveaway broadcast — runs in the ARQ worker process."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from common_db.repo import giveaways as giveaway_repo

from .database.models import User
from .database.session import async_session
from .telegram import tg_bot_deeplink, tg_bot_username, tg_send

logger = logging.getLogger(__name__)

_BROADCAST_BATCH = 25
_BROADCAST_DELAY = 1.0


async def execute_giveaway_broadcast(giveaway_id: int) -> dict:
    """DM all Telegram users about an active giveaway."""
    async with async_session() as session:
        giveaway = await giveaway_repo.get_giveaway(session, giveaway_id)
        if giveaway is None:
            return {"ok": False, "reason": "not_found"}
        text = (giveaway.channel_text or giveaway.title or "").strip()
        if not text:
            return {"ok": False, "reason": "empty_text"}

        tg_ids = [
            row[0]
            for row in (
                await session.execute(
                    select(User.tg_id).where(User.tg_id.is_not(None), User.tg_id > 0)
                )
            ).all()
            if row[0]
        ]

    username = await tg_bot_username()
    reply_markup = None
    if username:
        reply_markup = {
            "inline_keyboard": [[
                {
                    "text": "Участвовать",
                    "url": tg_bot_deeplink(username, f"gw_{giveaway_id}"),
                }
            ]]
        }

    sent = 0
    failed = 0
    for i, tg_id in enumerate(tg_ids):
        ok = await tg_send(int(tg_id), text, reply_markup)
        if ok:
            sent += 1
        else:
            failed += 1
        if (i + 1) % _BROADCAST_BATCH == 0:
            await asyncio.sleep(_BROADCAST_DELAY)

    logger.info(
        "Giveaway %s broadcast done: sent=%s failed=%s total=%s",
        giveaway_id,
        sent,
        failed,
        len(tg_ids),
    )
    return {"ok": True, "sent": sent, "failed": failed, "total": len(tg_ids)}

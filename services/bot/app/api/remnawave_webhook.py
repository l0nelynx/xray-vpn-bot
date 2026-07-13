"""Handle POST /bot/remnawave_webhook callbacks from the Remnawave panel."""

from __future__ import annotations

import logging
import time

from fastapi import BackgroundTasks, Request
from fastapi.responses import JSONResponse

from app.database import requests as rq
from app.locale.utils import get_user_lang
from app.settings import bot, secrets
from remnawave_client.webhooks import (
    RemnawaveWebhookPayload,
    extract_vless_uuid,
    is_torrent_block_report,
    parse_webhook,
    torrent_block_ip,
    torrent_block_minutes,
    verify_webhook_signature,
)

logger = logging.getLogger(__name__)

_TORRENT_WARN_COOLDOWN = 86400.0  # 24 hours
_last_torrent_warning: dict[int, float] = {}


def _cooldown_active(tg_id: int) -> bool:
    last = _last_torrent_warning.get(tg_id)
    if last is None:
        return False
    return (time.monotonic() - last) < _TORRENT_WARN_COOLDOWN


def _mark_warning_sent(tg_id: int) -> None:
    _last_torrent_warning[tg_id] = time.monotonic()


async def _notify_torrent_block(payload: RemnawaveWebhookPayload) -> None:
    vless_uuid = extract_vless_uuid(payload)
    if not vless_uuid:
        logger.info("Remnawave torrent webhook: no user uuid in payload, skip notify")
        return

    user = await rq.get_user_by_vless_uuid(vless_uuid)
    if not user:
        logger.info(
            "Remnawave torrent webhook: no local user for vless_uuid=%s", vless_uuid
        )
        return

    tg_id = user.get("tg_id")
    if not tg_id or user.get("is_banned"):
        return

    if _cooldown_active(tg_id):
        logger.debug(
            "Remnawave torrent webhook: cooldown active for tg_id=%s", tg_id
        )
        return

    ip = torrent_block_ip(payload) or "—"
    minutes = torrent_block_minutes(payload)
    lang = await get_user_lang(tg_id)

    try:
        await bot.send_message(
            chat_id=tg_id,
            text=lang.torrent_traffic_warning.format(
                ip=f"<code>{ip}</code>",
                minutes=minutes,
            ),
            parse_mode="HTML",
        )
        _mark_warning_sent(tg_id)
        logger.info(
            "Remnawave torrent warning sent to tg_id=%s (uuid=%s)",
            tg_id,
            vless_uuid,
        )
    except Exception as exc:
        logger.error(
            "Remnawave torrent warning failed for tg_id=%s: %s", tg_id, exc
        )


async def remnawave_webhook_handler(
    request: Request, background_tasks: BackgroundTasks
):
    """Verify signature, ack quickly, notify user on torrent_blocker.report."""
    raw = await request.body()
    signature = request.headers.get("X-Remnawave-Signature", "")
    secret = secrets.get("remnawave_webhook_secret", "") or ""

    if not verify_webhook_signature(raw, signature, secret):
        logger.warning("Remnawave webhook: invalid signature")
        return JSONResponse(
            {"status": "error", "message": "unauthorized"},
            status_code=401,
        )

    try:
        payload = parse_webhook(raw)
    except Exception as exc:
        logger.warning("Remnawave webhook: invalid payload: %s", exc)
        return JSONResponse(
            {"status": "error", "message": "invalid payload"},
            status_code=400,
        )

    if is_torrent_block_report(payload):
        background_tasks.add_task(_notify_torrent_block, payload)

    return {"status": "received"}

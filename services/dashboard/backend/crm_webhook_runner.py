"""Execute CRM webhook rules for an inbound Remnawave payload (ARQ worker)."""

from __future__ import annotations

import logging
from typing import Any

from common_db.repo import crm_webhooks as webhooks_repo
from common_db.repo.users import get_user_by_tg_id, get_user_by_vless_uuid
from remnawave_client.segmentation import normalize_user_for_crm
from remnawave_client.webhooks import (
    RemnawaveWebhookPayload,
    extract_telegram_id,
    extract_vless_uuid,
)

from .config import get_remnawave_token, get_remnawave_url
from .crm_actions import execute_user_actions
from .crm_variables import build_webhook_message_context
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


async def _resolve_db_user(session, payload: RemnawaveWebhookPayload):
    uuid = extract_vless_uuid(payload)
    if uuid:
        user = await get_user_by_vless_uuid(session, uuid)
        if user is not None:
            return user
    tg_id = extract_telegram_id(payload)
    if tg_id is not None:
        return await get_user_by_tg_id(session, tg_id)
    return None


async def _fetch_crm_user(rw_client, vless_uuid: str | None) -> dict | None:
    if not vless_uuid:
        return None
    try:
        raw = await rw_client.get_user_by_uuid(vless_uuid)
        if not raw:
            return None
        return normalize_user_for_crm(raw)
    except Exception as exc:
        logger.warning("CRM webhook: failed to fetch Remnawave user %s: %s", vless_uuid, exc)
        return None


async def execute_crm_webhook(payload_dict: dict[str, Any]) -> None:
    """Match enabled rules and run actions for the resolved local user."""
    try:
        payload = RemnawaveWebhookPayload.model_validate(payload_dict)
    except Exception as exc:
        logger.error("CRM webhook: invalid payload: %s", exc)
        return

    scope = payload.scope
    event = payload.event
    rw = _rw_client()
    bot_username = await tg_bot_username()

    async with async_session() as session:
        rules = await webhooks_repo.list_enabled_matching(
            session, scope=scope, event=event
        )
        if not rules:
            logger.debug("CRM webhook: no rules for scope=%s event=%s", scope, event)
            await session.commit()
            return

        # Count a match as soon as the inbound event hits an enabled rule.
        for rule in rules:
            await webhooks_repo.bump_stats(session, rule, webhooks_received=1)

        db_user = await _resolve_db_user(session, payload)
        if db_user is None:
            logger.info(
                "CRM webhook: no local user for scope=%s event=%s uuid=%s tg=%s",
                scope,
                event,
                extract_vless_uuid(payload),
                extract_telegram_id(payload),
            )
            await session.commit()
            return

        if getattr(db_user, "is_banned", False):
            logger.info("CRM webhook: skip banned tg_id=%s", db_user.tg_id)
            await session.commit()
            return

        if not db_user.tg_id:
            logger.info("CRM webhook: user id=%s has no tg_id", db_user.id)
            await session.commit()
            return

        crm_user = await _fetch_crm_user(rw, db_user.vless_uuid)
        message_ctx = build_webhook_message_context(
            username=db_user.username,
            crm_user=crm_user,
            payload=payload,
        )

        for rule in rules:
            cooldown = rule.cooldown_hours
            if cooldown is not None and cooldown > 0:
                if await webhooks_repo.has_recent_delivery(
                    session,
                    rule_id=rule.id,
                    tg_id=db_user.tg_id,
                    cooldown_hours=int(cooldown),
                ):
                    logger.debug(
                        "CRM webhook: cooldown rule=%s tg_id=%s",
                        rule.id,
                        db_user.tg_id,
                    )
                    continue

            actions = webhooks_repo.get_actions(rule)
            if not actions:
                continue

            result = await execute_user_actions(
                rw,
                db_user,
                crm_user,
                actions,
                bot_username=bot_username,
                event_id=None,
                session=session,
                message_ctx=message_ctx,
            )

            sent_delta = 1 if result.message_sent else 0
            failed_delta = 1 if result.message_failed else 0
            if sent_delta or failed_delta:
                await webhooks_repo.bump_stats(
                    session,
                    rule,
                    messages_sent=sent_delta,
                    messages_failed=failed_delta,
                )

            if result.message_sent or result.perks_applied:
                await webhooks_repo.record_delivery(
                    session, rule_id=rule.id, tg_id=db_user.tg_id
                )
            elif result.errors:
                logger.warning(
                    "CRM webhook rule=%s tg_id=%s errors=%s",
                    rule.id,
                    db_user.tg_id,
                    result.errors,
                )

        await session.commit()

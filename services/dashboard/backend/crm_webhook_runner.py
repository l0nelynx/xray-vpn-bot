"""Execute CRM webhook rules for an inbound Remnawave payload (ARQ worker)."""

from __future__ import annotations

import logging
from typing import Any

from common_db.repo import crm_webhooks as webhooks_repo
from common_db.repo.users import get_user_by_rw_id, get_user_by_tg_id
from remnawave_client.segmentation import normalize_user_for_crm
from remnawave_client.webhooks import (
    RemnawaveWebhookPayload,
    extract_telegram_id,
    extract_rw_id,
    extract_user_data,
    extract_user_email,
)

from .config import get_remnawave_token, get_remnawave_url
from .crm_actions import execute_user_actions
from .crm_email import normalize_webhook_email, send_crm_email
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
    rw_id = extract_rw_id(payload)
    if rw_id is not None:
        user = await get_user_by_rw_id(session, rw_id)
        if user is not None:
            return user
    tg_id = extract_telegram_id(payload)
    if tg_id is not None:
        return await get_user_by_tg_id(session, tg_id)
    return None


async def _fetch_crm_user(rw_client, rw_id: int | None) -> dict | None:
    if rw_id is None:
        return None
    try:
        raw = await rw_client.get_user_by_id(rw_id)
        if not raw:
            return None
        return normalize_user_for_crm(raw)
    except Exception as exc:
        logger.warning("CRM webhook: failed to fetch Remnawave user %s: %s", rw_id, exc)
        return None


def _payload_crm_user(payload: RemnawaveWebhookPayload) -> dict | None:
    user = extract_user_data(payload)
    if not user:
        return None
    try:
        traffic = user.get("userTraffic")
        raw = {**user, **traffic} if isinstance(traffic, dict) else user
        return normalize_user_for_crm(raw)
    except (TypeError, ValueError, OverflowError):
        logger.warning("CRM webhook: invalid account metadata for message variables")
        return None


async def execute_crm_webhook(payload_dict: dict[str, Any]) -> None:
    """Run account actions and optional delivery directly to the webhook email."""
    try:
        payload = RemnawaveWebhookPayload.model_validate(payload_dict)
    except Exception as exc:
        logger.error("CRM webhook: invalid payload: %s", exc)
        return

    scope = payload.scope
    event = payload.event
    rw = _rw_client()
    bot_username = None
    bot_username_loaded = False
    crm_user = None
    crm_user_loaded = False

    async with async_session() as session:
        rules = await webhooks_repo.list_enabled_matching(session, scope=scope, event=event)
        if not rules:
            return

        db_user = await _resolve_db_user(session, payload)
        local_allowed = db_user is not None and not getattr(db_user, "is_banned", False)
        if db_user is None:
            logger.info("CRM webhook: no local user for scope=%s event=%s", scope, event)

        webhook_email = normalize_webhook_email(extract_user_email(payload))
        payload_user = extract_user_data(payload)
        payload_username = payload_user.get("username")
        webhook_ctx = build_webhook_message_context(
            username=payload_username if isinstance(payload_username, str) else None,
            crm_user=_payload_crm_user(payload),
            payload=payload,
        )

        for rule in rules:
            await webhooks_repo.bump_stats(session, rule, webhooks_received=1)
            actions = webhooks_repo.get_actions(rule)
            webhook_emails = [
                a for a in actions if a.get("type") == "send_email"
                and a.get("enabled", True) and a.get("send_to_email_from_webhook", False)
            ]
            local_actions = [a for a in actions if a not in webhook_emails]
            cooldown = int(rule.cooldown_hours or 0)

            # Database-based actions keep their existing eligibility and cooldown.
            # Webhook email delivery below is independent of local account state.
            if local_allowed and any(a.get("enabled", True) for a in local_actions):
                recent = await webhooks_repo.has_recent_delivery(
                    session, rule_id=rule.id, tg_id=db_user.tg_id,
                    user_id=db_user.id, cooldown_hours=cooldown,
                )
                if not recent:
                    if not crm_user_loaded:
                        crm_user = await _fetch_crm_user(rw, db_user.rw_id)
                        crm_user_loaded = True
                    needs_bot = db_user.tg_id and any(
                        a.get("type") == "attach_button" and a.get("enabled", True)
                        for a in local_actions
                    )
                    if needs_bot and not bot_username_loaded:
                        bot_username = await tg_bot_username()
                        bot_username_loaded = True
                    message_ctx = build_webhook_message_context(
                        username=db_user.username, crm_user=crm_user, payload=payload,
                    )
                    result = await execute_user_actions(
                        rw, db_user, crm_user, local_actions,
                        bot_username=bot_username, session=session, message_ctx=message_ctx,
                    )
                    await webhooks_repo.bump_stats(
                        session, rule, messages_sent=int(result.message_sent),
                        messages_failed=int(result.message_failed),
                    )
                    if result.message_sent or result.perks_applied:
                        await webhooks_repo.record_delivery(
                            session, rule_id=rule.id, tg_id=db_user.tg_id, user_id=db_user.id,
                        )
                    elif result.errors:
                        logger.warning("CRM webhook rule=%s user_id=%s errors=%s", rule.id, db_user.id, result.errors)

            for action in webhook_emails:
                if not webhook_email:
                    logger.info("CRM webhook rule=%s: missing or invalid account email; skipped", rule.id)
                    continue
                if await webhooks_repo.has_recent_delivery(
                    session, rule_id=rule.id, tg_id=None, cooldown_hours=cooldown,
                    recipient_email=webhook_email,
                ):
                    continue
                try:
                    await send_crm_email(session, to=webhook_email, action=action, context=webhook_ctx)
                except Exception:
                    logger.exception("CRM webhook rule=%s email delivery failed", rule.id)
                    await webhooks_repo.bump_stats(session, rule, messages_failed=1)
                    continue
                await webhooks_repo.bump_stats(session, rule, messages_sent=1)
                await webhooks_repo.record_delivery(
                    session, rule_id=rule.id, tg_id=None, recipient_email=webhook_email,
                )

        await session.commit()

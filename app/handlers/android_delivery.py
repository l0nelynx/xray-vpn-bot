"""Subscription delivery for Android-API users.

Mirrors `subscription_service.deliver_subscription` but does NOT touch
Telegram (no `bot.send_message`, no localization) — Android clients poll
`/api/android/payments/transactions/{id}` for `delivery_status == 1`.

Intentionally narrow: PAID-only path. Free subscriptions are provisioned at
email-verify time by `miniapp/backend/android/provisioning.py`.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import app.database.requests as rq
from remnawave_client import (
    SubscriptionScenario,
    SubscriptionType,
    apply_extend,
    apply_new_user,
    apply_update,
    resolve_scenario,
)

logger = logging.getLogger(__name__)

_USERNAME_RE = re.compile(r"[^a-zA-Z0-9_]")


def _email_to_username(email: str) -> str:
    """Same algorithm as miniapp/backend/android/provisioning.email_to_username
    — duplicated here to avoid the bot importing from miniapp."""
    local, _, domain = email.strip().lower().partition("@")
    raw = f"{local}_at_{domain}" if domain else local
    sanitized = _USERNAME_RE.sub("_", raw).strip("_")
    return sanitized or "user"


def _parse_squad_slug(slug: Optional[str]) -> Optional[dict]:
    """Parse "sid:<squad_id>:esid:<external_squad_id>"; same format the
    Android invoice router writes to `transactions.tariff_slug`."""
    if not slug or not slug.startswith("sid:"):
        return None
    try:
        _, sid, marker, esid = slug.split(":", 3)
    except ValueError:
        return None
    if marker != "esid" or not sid or not esid:
        return None
    return {"squad_id": sid, "external_squad_id": esid}


async def deliver_android_paid(
    *,
    transaction_id: str,
    android_user_id: int,
    email: Optional[str],
    days: int,
    tariff_slug: Optional[str],
) -> dict:
    """Provision/extend a PAID Remnawave subscription for an Android user.

    Returns {"status": "success", "scenario": ..., "uuid": ..., "subscription_url": ...}
    on success, or {"status": "error", "message": ...} on failure.
    """
    if not email:
        return {"status": "error", "message": "android_user_missing_email"}

    # Android invoice writes either:
    #   1) "sid:<squad>:esid:<external>"  — старый формат (deprecated)
    #   2) обычный tariff_slug из webapp_menu_nodes — тогда squad ищем в боте.
    squad = _parse_squad_slug(tariff_slug)
    if not squad and tariff_slug:
        from app.database.tariff_repository import get_squad_for_tariff_slug
        squad = await get_squad_for_tariff_slug(tariff_slug)
    if not squad:
        return {"status": "error", "message": f"bad tariff_slug: {tariff_slug!r}"}

    username = _email_to_username(email)

    # Запрашиваем Remnawave напрямую — `tools.get_user_info` нормализует
    # ответ под старый Marzban-клиент и теряет поле `uuid`, из-за чего
    # ветка EXTEND падала с "extend without uuid".
    import app.api.remnawave.api as rem
    info = await rem.get_user_from_username(username)
    scenario = resolve_scenario(info, SubscriptionType.PAID)

    try:
        if scenario == SubscriptionScenario.NEW_USER:
            result = await apply_new_user(
                username=username,
                telegram_id=0,
                days=days,
                limit_gb=0,
                email=email,
                description="Android paid subscription",
                squad_id=squad["squad_id"],
                external_squad_id=squad["external_squad_id"],
            )
        elif scenario == SubscriptionScenario.EXTEND:
            uuid = (info or {}).get("uuid")
            if not uuid:
                return {"status": "error", "message": "extend without uuid"}
            from app.handlers.tools import get_user_days
            current_days = await get_user_days(info) or 0
            result = await apply_extend(
                user_uuid=uuid,
                username=username,
                days=days,
                current_days_left=current_days if isinstance(current_days, int) else 0,
                squad_id=squad["squad_id"],
                external_squad_id=squad["external_squad_id"],
                description="Android paid extend",
            )
        else:  # UPDATE / LIMITED / ALREADY_ACTIVE all fall through to update.
            uuid = (info or {}).get("uuid")
            if not uuid:
                return {"status": "error", "message": f"{scenario.value} without uuid"}
            result = await apply_update(
                user_uuid=uuid,
                username=username,
                days=days,
                limit_gb=0,
                squad_id=squad["squad_id"],
                external_squad_id=squad["external_squad_id"],
                status="active",
                description="Android paid update",
            )
    except Exception as exc:
        logger.error("android delivery for tx=%s failed: %s", transaction_id, exc)
        return {"status": "error", "message": str(exc)}

    if not result:
        return {"status": "error", "message": "remnawave_apply_returned_none"}

    rw_uuid = result.get("uuid") or (info or {}).get("uuid")
    if rw_uuid:
        # Persist vless_uuid so future flows (free refresh, /me) can
        # short-circuit. Best-effort: failure here doesn't block delivery.
        try:
            await _save_vless_uuid(android_user_id, rw_uuid)
        except Exception as exc:
            logger.warning("Failed to save vless_uuid for user %s: %s", android_user_id, exc)

    await rq.update_delivery_status(transaction_id, 1)
    return {
        "status": "success",
        "scenario": scenario.value,
        "uuid": rw_uuid,
        "subscription_url": result.get("subscription_url"),
    }


async def _save_vless_uuid(user_id: int, vless_uuid: str) -> None:
    from sqlalchemy import text
    from app.database.models import async_session
    async with async_session() as s:
        await s.execute(
            text("UPDATE users SET vless_uuid = :u WHERE id = :i"),
            {"u": vless_uuid, "i": user_id},
        )
        await s.commit()

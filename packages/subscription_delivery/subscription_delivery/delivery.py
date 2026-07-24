"""Android PAID subscription delivery — shared by the seller bot and the miniapp.

Previously this lived in the seller bot (``app/handlers/android_delivery.py``)
and the miniapp's Google Play IAP router reached into it with
``from app.handlers.android_delivery import deliver_android_paid``. That import
can never succeed in the miniapp container (its image has no ``app/``), so IAP
delivery silently failed. The logic is the same for both entry points (fiat
webhooks on the seller, Google Play IAP on the miniapp), so it lives here as a
single source of truth.

It is decoupled from either service via injected dependencies:
- ``session_factory``: an ``async_sessionmaker`` bound to the shared DB (each
  service already has one via common_db).
- ``notifier``: an ``async (text) -> None`` admin-log sink (each service has its
  own ``notify_log``).
- ``squad_resolver``: optional ``async (slug) -> {squad_id, external_squad_id}``
  used only for the plain webapp-slug fallback (the seller injects its tariff
  cache; the miniapp's IAP slugs already carry the squad as ``sid:..:esid:..``).
"""
from __future__ import annotations

import html
import logging
import re
import time
from typing import Awaitable, Callable, Optional

from sqlalchemy import text

from remnawave_client import (
    SubscriptionScenario,
    SubscriptionType,
    apply_extend,
    apply_new_user,
    apply_update,
    resolve_scenario,
)
from remnawave_client import api as rem

logger = logging.getLogger(__name__)

_USERNAME_RE = re.compile(r"[^a-zA-Z0-9_]")

SquadResolver = Callable[[str], Awaitable[Optional[dict]]]
Notifier = Callable[[str], Awaitable[None]]


def esc(value: object) -> str:
    """HTML-escape any value for safe embedding in <b>/<code> spans."""
    return html.escape(str(value), quote=False)


def email_to_username(email: str) -> str:
    """Deterministic username from an email — the canonical algorithm shared by
    delivery and miniapp free-provisioning."""
    local, _, domain = email.strip().lower().partition("@")
    raw = f"{local}_at_{domain}" if domain else local
    sanitized = _USERNAME_RE.sub("_", raw).strip("_")
    return sanitized or "user"


def _days_left(info: dict | None) -> int:
    """Remaining subscription days from a Remnawave ``expire`` timestamp."""
    expire = (info or {}).get("expire")
    if expire is None:
        return 0
    try:
        return max(0, round((expire - time.time()) / (24 * 60 * 60)))
    except (TypeError, ValueError):
        return 0


def _parse_squad_slug(slug: Optional[str]) -> Optional[dict]:
    """Parse "sid:<squad_id>:esid:<external_squad_id>" — the format the Android
    invoice/IAP routers write."""
    if not slug or not slug.startswith("sid:"):
        return None
    try:
        _, sid, marker, esid = slug.split(":", 3)
    except ValueError:
        return None
    if marker != "esid" or not sid or not esid:
        return None
    return {"squad_id": sid, "external_squad_id": esid}


async def _notify(
    notifier: Notifier,
    *,
    ok: bool,
    transaction_id: str,
    android_user_id: int,
    email: Optional[str],
    days: int,
    tariff_slug: Optional[str],
    reason: Optional[str] = None,
) -> None:
    icon = "📦" if ok else "❌"
    title = "Android subscription delivered" if ok else "Android delivery FAILED"
    extra = ""
    if not ok and reason:
        extra = f"\nerror: <code>{esc(reason[:300])}</code>"
    await notifier(
        f"{icon} <b>{title}</b>\n"
        f"user: <code>{android_user_id}</code> {esc(email or '—')}\n"
        f"days: <code>{days}</code>\n"
        f"slug: <code>{esc(tariff_slug or '—')}</code>\n"
        f"tx: <code>{esc(transaction_id)}</code>"
        f"{extra}"
    )


async def _update_delivery_status(session_factory, transaction_id: str, status: int) -> None:
    async with session_factory() as session:
        await session.execute(
            text("UPDATE transactions SET delivery_status = :s WHERE transaction_id = :t"),
            {"s": status, "t": transaction_id},
        )
        await session.commit()


async def _save_vless_uuid(session_factory, user_id: int, vless_uuid: str) -> None:
    async with session_factory() as session:
        await session.execute(
            text("UPDATE users SET vless_uuid = :u WHERE id = :i"),
            {"u": vless_uuid, "i": user_id},
        )
        await session.commit()


async def deliver_android_paid(
    *,
    transaction_id: str,
    android_user_id: int,
    email: Optional[str],
    days: int,
    tariff_slug: Optional[str],
    session_factory,
    notifier: Notifier,
    delivery_target: Optional[dict] = None,
    squad_resolver: Optional[SquadResolver] = None,
) -> dict:
    """Provision/extend a PAID Remnawave subscription for an Android user.

    Returns {"status": "success", "scenario", "uuid", "subscription_url"} on
    success, or {"status": "error", "message"} on failure. Never raises.
    """
    if not email:
        await _notify(
            notifier, ok=False, transaction_id=transaction_id,
            android_user_id=android_user_id, email=email, days=days,
            tariff_slug=tariff_slug, reason="android_user_missing_email",
        )
        return {"status": "error", "message": "android_user_missing_email"}

    # tariff_slug is either the "sid:..:esid:.." form (Android invoice/IAP) or a
    # plain webapp slug — the latter is resolved by the injected squad_resolver.
    squad = _parse_squad_slug(tariff_slug)
    if not squad and tariff_slug and squad_resolver is not None:
        squad = await squad_resolver(tariff_slug)
    target = dict(delivery_target or {})
    has_delivery_target = delivery_target is not None
    internal_ids = target.get("internal_squad_ids") or (
        [squad["squad_id"]] if squad else []
    )
    external_squad_id = target.get("external_squad_id") or (
        squad["external_squad_id"] if squad else None
    )
    if not internal_ids or not external_squad_id:
        await _notify(
            notifier, ok=False, transaction_id=transaction_id,
            android_user_id=android_user_id, email=email, days=days,
            tariff_slug=tariff_slug, reason=f"bad tariff_slug: {tariff_slug!r}",
        )
        return {"status": "error", "message": f"bad tariff_slug: {tariff_slug!r}"}

    username = email_to_username(email)

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
                squad_id=internal_ids[0],
                internal_squad_ids=internal_ids,
                external_squad_id=external_squad_id,
                traffic_limit_bytes=target.get("traffic_limit_bytes"),
                traffic_limit_strategy=target.get("traffic_limit_strategy"),
                tag=target.get("remnawave_tag"),
                description=target.get("remnawave_description") or "Android paid subscription",
            )
        elif scenario == SubscriptionScenario.EXTEND:
            uuid = (info or {}).get("uuid")
            if not uuid:
                await _notify(
                    notifier, ok=False, transaction_id=transaction_id,
                    android_user_id=android_user_id, email=email, days=days,
                    tariff_slug=tariff_slug, reason="extend without uuid",
                )
                return {"status": "error", "message": "extend without uuid"}
            result = await apply_extend(
                user_uuid=uuid,
                username=username,
                days=days,
                current_days_left=_days_left(info),
                squad_id=internal_ids[0],
                internal_squad_ids=internal_ids,
                external_squad_id=external_squad_id,
                description=(
                    target.get("remnawave_description")
                    if has_delivery_target
                    else "Android paid extend"
                ),
                traffic_limit_bytes=target.get("traffic_limit_bytes"),
                traffic_limit_strategy=target.get("traffic_limit_strategy"),
                tag=target.get("remnawave_tag"),
            )
        else:  # UPDATE / LIMITED / ALREADY_ACTIVE all fall through to update.
            uuid = (info or {}).get("uuid")
            if not uuid:
                await _notify(
                    notifier, ok=False, transaction_id=transaction_id,
                    android_user_id=android_user_id, email=email, days=days,
                    tariff_slug=tariff_slug, reason=f"{scenario.value} without uuid",
                )
                return {"status": "error", "message": f"{scenario.value} without uuid"}
            result = await apply_update(
                user_uuid=uuid,
                username=username,
                days=days,
                limit_gb=0,
                squad_id=internal_ids[0],
                internal_squad_ids=internal_ids,
                external_squad_id=external_squad_id,
                status="active",
                description=(
                    target.get("remnawave_description")
                    if has_delivery_target
                    else "Android paid update"
                ),
                traffic_limit_bytes=target.get("traffic_limit_bytes"),
                traffic_limit_strategy=target.get("traffic_limit_strategy"),
                tag=target.get("remnawave_tag"),
            )
    except Exception as exc:
        logger.error("android delivery for tx=%s failed: %s", transaction_id, exc)
        await _notify(
            notifier, ok=False, transaction_id=transaction_id,
            android_user_id=android_user_id, email=email, days=days,
            tariff_slug=tariff_slug, reason=str(exc),
        )
        return {"status": "error", "message": str(exc)}

    if not result:
        await _notify(
            notifier, ok=False, transaction_id=transaction_id,
            android_user_id=android_user_id, email=email, days=days,
            tariff_slug=tariff_slug, reason="remnawave_apply_returned_none",
        )
        return {"status": "error", "message": "remnawave_apply_returned_none"}

    rw_uuid = result.get("uuid") or (info or {}).get("uuid")
    if rw_uuid:
        # Best-effort: persist vless_uuid so future flows can short-circuit.
        try:
            await _save_vless_uuid(session_factory, android_user_id, rw_uuid)
        except Exception as exc:
            logger.warning("Failed to save vless_uuid for user %s: %s", android_user_id, exc)

    await _update_delivery_status(session_factory, transaction_id, 1)
    await _notify(
        notifier, ok=True, transaction_id=transaction_id,
        android_user_id=android_user_id, email=email, days=days,
        tariff_slug=tariff_slug,
    )
    return {
        "status": "success",
        "scenario": scenario.value,
        "uuid": rw_uuid,
        "subscription_url": result.get("subscription_url"),
    }


async def deliver_telegram_paid(
    *,
    transaction_id: str,
    tg_id: int,
    username: str,
    days: int,
    tariff_slug: Optional[str],
    session_factory,
    notifier: Notifier,
    delivery_target: Optional[dict] = None,
    squad_resolver: Optional[SquadResolver] = None,
) -> dict:
    """Provision/extend a PAID Remnawave subscription for a Telegram user."""
    squad = _parse_squad_slug(tariff_slug)
    if not squad and tariff_slug and squad_resolver is not None:
        squad = await squad_resolver(tariff_slug)
    target = dict(delivery_target or {})
    has_delivery_target = delivery_target is not None
    internal_ids = target.get("internal_squad_ids") or (
        [squad["squad_id"]] if squad else []
    )
    external_squad_id = target.get("external_squad_id") or (
        squad["external_squad_id"] if squad else None
    )
    if not internal_ids or not external_squad_id:
        await notifier(
            f"❌ <b>Telegram delivery FAILED</b>\n"
            f"user: <code>{tg_id}</code> @{esc(username)}\n"
            f"error: <code>bad tariff_slug: {esc(tariff_slug or '—')}</code>\n"
            f"tx: <code>{esc(transaction_id)}</code>"
        )
        return {"status": "error", "message": f"bad tariff_slug: {tariff_slug!r}"}

    info = await rem.get_user_from_username(username)
    scenario = resolve_scenario(info, SubscriptionType.PAID)

    try:
        if scenario == SubscriptionScenario.NEW_USER:
            result = await apply_new_user(
                username=username,
                telegram_id=tg_id,
                days=days,
                limit_gb=0,
                email=f"{username}@telegram.user",
                description=target.get("remnawave_description") or "Paid subscription (bonus credits)",
                squad_id=internal_ids[0],
                internal_squad_ids=internal_ids,
                external_squad_id=external_squad_id,
                traffic_limit_bytes=target.get("traffic_limit_bytes"),
                traffic_limit_strategy=target.get("traffic_limit_strategy"),
                tag=target.get("remnawave_tag"),
            )
        elif scenario == SubscriptionScenario.EXTEND:
            uuid = (info or {}).get("uuid")
            if not uuid:
                return {"status": "error", "message": "extend without uuid"}
            result = await apply_extend(
                user_uuid=uuid,
                username=username,
                days=days,
                current_days_left=_days_left(info),
                squad_id=internal_ids[0],
                internal_squad_ids=internal_ids,
                external_squad_id=external_squad_id,
                description=(
                    target.get("remnawave_description")
                    if has_delivery_target
                    else "Paid extend (bonus credits)"
                ),
                traffic_limit_bytes=target.get("traffic_limit_bytes"),
                traffic_limit_strategy=target.get("traffic_limit_strategy"),
                tag=target.get("remnawave_tag"),
            )
        else:
            uuid = (info or {}).get("uuid")
            if not uuid:
                return {"status": "error", "message": f"{scenario.value} without uuid"}
            result = await apply_update(
                user_uuid=uuid,
                username=username,
                days=days,
                limit_gb=0,
                squad_id=internal_ids[0],
                internal_squad_ids=internal_ids,
                external_squad_id=external_squad_id,
                status="active",
                description=(
                    target.get("remnawave_description")
                    if has_delivery_target
                    else "Paid update (bonus credits)"
                ),
                traffic_limit_bytes=target.get("traffic_limit_bytes"),
                traffic_limit_strategy=target.get("traffic_limit_strategy"),
                tag=target.get("remnawave_tag"),
            )
    except Exception as exc:
        logger.error("telegram delivery for tx=%s failed: %s", transaction_id, exc)
        await notifier(
            f"❌ <b>Telegram delivery FAILED</b>\n"
            f"user: <code>{tg_id}</code> @{esc(username)}\n"
            f"error: <code>{esc(str(exc)[:300])}</code>\n"
            f"tx: <code>{esc(transaction_id)}</code>"
        )
        return {"status": "error", "message": str(exc)}

    if not result:
        return {"status": "error", "message": "remnawave_apply_returned_none"}

    rw_uuid = result.get("uuid") or (info or {}).get("uuid")
    if rw_uuid and tg_id:
        try:
            async with session_factory() as session:
                await session.execute(
                    text(
                        "UPDATE users SET vless_uuid = :u WHERE tg_id = :t"
                    ),
                    {"u": rw_uuid, "t": tg_id},
                )
                await session.commit()
        except Exception as exc:
            logger.warning("Failed to save vless_uuid for tg_id %s: %s", tg_id, exc)

    await _update_delivery_status(session_factory, transaction_id, 1)
    await notifier(
        f"📦 <b>Subscription delivered (bonus credits)</b>\n"
        f"user: <code>{tg_id}</code> @{esc(username)}\n"
        f"days: <code>{days}</code>\n"
        f"slug: <code>{esc(tariff_slug or '—')}</code>\n"
        f"tx: <code>{esc(transaction_id)}</code>"
    )
    return {
        "status": "success",
        "scenario": scenario.value,
        "uuid": rw_uuid,
        "subscription_url": result.get("subscription_url"),
    }

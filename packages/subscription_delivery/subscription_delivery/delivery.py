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
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

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

_USERNAME_RE = re.compile(r"[^a-zA-Z0-9_-]")
_MAX_RW_USERNAME_LENGTH = 36
_MAX_USERNAME_ATTEMPTS = 100

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


def build_remnawave_username(
    tg_username: str | None,
    db_user_id: int,
    ordinal: int = 0,
) -> str:
    """Build a stable, collision-resistant Remnawave username.

    ``ordinal`` is zero for the first local subscription, one for the second,
    and so on. Only the display-name component may be truncated.
    """
    if int(db_user_id) < 0 or int(ordinal) < 0:
        raise ValueError("user id and ordinal must be non-negative")
    base = _USERNAME_RE.sub("", (tg_username or "").lstrip("@").lower()) or "user"
    suffix = f"_{int(db_user_id)}" + (f"_{int(ordinal)}" if ordinal else "")
    available = _MAX_RW_USERNAME_LENGTH - len(suffix)
    if available < 1:
        raise ValueError("db user id and subscription number exceed username limit")
    candidate = f"{base[:available]}{suffix}"
    if len(candidate) < 3:
        candidate = f"user{suffix}"
    return candidate


def provisioning_description(
    *, transaction_id: str, db_user_id: int, tg_id: int | None,
    source: str, original_tg_username: str | None, description: str | None,
) -> str:
    metadata = (
        f"provisioning:{transaction_id}; db_user_id:{db_user_id}; "
        f"tg_id:{tg_id if tg_id is not None else 'none'}; source:{source}; "
        f"tg_username:{original_tg_username or 'none'}"
    )
    return f"{metadata}; {description}" if description else metadata


def _rw_id(info: dict | None) -> int | None:
    raw = (info or {}).get("rw_id")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
    db_user_id: int,
    tg_id: int | None,
    tg_username: str | None,
    email: Optional[str],
    days: int,
    tariff_slug: Optional[str],
    purchase_source: str,
    rw_username: str | None = None,
    rw_id: int | None = None,
    subscription_number: int | None = None,
    action: str | None = None,
    reason: Optional[str] = None,
) -> None:
    icon = "📦" if ok else "❌"
    title = (
        f"Subscription delivered ({purchase_source})"
        if ok else f"Subscription delivery FAILED ({purchase_source})"
    )
    extra = ""
    if not ok and reason:
        extra = f"\nerror: <code>{esc(reason[:300])}</code>"
    identity = (
        f"TG <code>{tg_id}</code> @{esc(tg_username or '—')}"
        if tg_id is not None else esc(email or "—")
    )
    delivery = ""
    if ok:
        delivery = (
            f"\nremnawave: <code>{esc(rw_username or '—')}</code> "
            f"(<code>{rw_id if rw_id is not None else '—'}</code>)"
            f"\nsubscription: <code>{subscription_number or '—'}</code>"
            f"\naction: <code>{esc(action or '—')}</code>"
        )
    await notifier(
        f"{icon} <b>{title}</b>\n"
        f"DB user: <code>{db_user_id}</code> {identity}\n"
        f"days: <code>{days}</code>\n"
        f"slug: <code>{esc(tariff_slug or '—')}</code>\n"
        f"tx: <code>{esc(transaction_id)}</code>"
        f"{delivery}"
        f"{extra}"
    )


async def _update_delivery_status(
    session_factory,
    transaction_id: str,
    status: int,
    *,
    error: str | None = None,
    pending: bool = False,
) -> None:
    async with session_factory() as session:
        await session.execute(
            text(
                "UPDATE transactions SET delivery_status = :s, delivery_error = :e"
                + (", order_status = 'pending'" if pending else "")
                + " WHERE transaction_id = :t"
            ),
            {"s": status, "e": error, "t": transaction_id},
        )
        await session.commit()


async def _local_context(session_factory, user_id: int) -> dict | None:
    async with session_factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT u.id, u.tg_id, u.username, u.email, u.rw_id, "
                    "u.vless_uuid, COUNT(s.id) AS subscription_count "
                    "FROM users u LEFT JOIN user_subscriptions s ON s.user_id = u.id "
                    "WHERE u.id = :u "
                    "GROUP BY u.id, u.tg_id, u.username, u.email, u.rw_id, u.vless_uuid"
                ),
                {"u": user_id},
            )
        ).mappings().first()
        return dict(row) if row else None


async def _subscription_owner(session_factory, rw_id: int) -> int | None:
    async with session_factory() as session:
        value = await session.scalar(
            text(
                "SELECT owner_id FROM ("
                "SELECT user_id AS owner_id, 0 AS priority FROM user_subscriptions WHERE rw_id = :r "
                "UNION ALL "
                "SELECT id AS owner_id, 1 AS priority FROM users WHERE rw_id = :r"
                ") owners ORDER BY priority LIMIT 1"
            ),
            {"r": rw_id},
        )
        return int(value) if value is not None else None


async def _subscription_number(session_factory, user_id: int, rw_id: int) -> int:
    async with session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT rw_id FROM user_subscriptions WHERE user_id = :u "
                    "ORDER BY id"
                ),
                {"u": user_id},
            )
        ).all()
    for index, row in enumerate(rows, start=1):
        if int(row[0]) == int(rw_id):
            return index
    return len(rows) + 1


async def _attach_subscription(
    session_factory,
    *,
    user_id: int,
    rw_id: int,
    rw_uuid: str | None,
    transaction_id: str,
    source: str,
) -> tuple[str, int]:
    """Attach rw_id atomically and return (action, one-based number)."""
    action = "recovered"
    try:
        async with session_factory() as session:
            subscription_owner = await session.scalar(
                text("SELECT user_id FROM user_subscriptions WHERE rw_id = :r"),
                {"r": rw_id},
            )
            legacy_owner = await session.scalar(
                text("SELECT id FROM users WHERE rw_id = :r"), {"r": rw_id}
            )
            owner = subscription_owner if subscription_owner is not None else legacy_owner
            if owner is not None:
                if int(owner) != int(user_id):
                    raise ValueError("target_owner_conflict")
            if subscription_owner is not None:
                action = "existing"
            else:
                count = int(
                    await session.scalar(
                        text("SELECT COUNT(*) FROM user_subscriptions WHERE user_id = :u"),
                        {"u": user_id},
                    ) or 0
                )
                now = _now_iso()
                await session.execute(
                    text(
                        "INSERT INTO user_subscriptions "
                        "(user_id, rw_id, source, is_primary, created_at, updated_at) "
                        "VALUES (:u, :r, :source, :primary, :now, :now)"
                    ),
                    {
                        "u": user_id,
                        "r": rw_id,
                        "source": f"purchase_{source}"[:30],
                        "primary": count == 0,
                        "now": now,
                    },
                )
                if count == 0:
                    await session.execute(
                        text("UPDATE users SET rw_id = :r, vless_uuid = :v WHERE id = :u"),
                        {"r": rw_id, "v": rw_uuid, "u": user_id},
                    )
            await session.execute(
                text(
                    "UPDATE transactions SET target_rw_id = :r, delivery_error = NULL "
                    "WHERE transaction_id = :t"
                ),
                {"r": rw_id, "t": transaction_id},
            )
            if rw_uuid:
                await session.execute(
                    text(
                        "UPDATE users SET rw_id = :r, vless_uuid = :v "
                        "WHERE id = :u AND EXISTS ("
                        "SELECT 1 FROM user_subscriptions s WHERE s.user_id = :u "
                        "AND s.rw_id = :r AND s.is_primary = true)"
                    ),
                    {"r": rw_id, "v": rw_uuid, "u": user_id},
                )
            await session.commit()
    except IntegrityError:
        owner = await _subscription_owner(session_factory, rw_id)
        if owner != int(user_id):
            raise ValueError("target_owner_conflict")
        action = "existing"
        async with session_factory() as session:
            await session.execute(
                text(
                    "UPDATE transactions SET target_rw_id = :r, delivery_error = NULL "
                    "WHERE transaction_id = :t"
                ),
                {"r": rw_id, "t": transaction_id},
            )
            if rw_uuid:
                await session.execute(
                    text(
                        "UPDATE users SET rw_id = :r, vless_uuid = :v "
                        "WHERE id = :u AND EXISTS ("
                        "SELECT 1 FROM user_subscriptions s WHERE s.user_id = :u "
                        "AND s.rw_id = :r AND s.is_primary = true)"
                    ),
                    {"r": rw_id, "v": rw_uuid, "u": user_id},
                )
            await session.commit()
    return action, await _subscription_number(session_factory, user_id, rw_id)


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
    target_rw_id: int | None = None,
    tg_id: int | None = None,
    tg_username: str | None = None,
    purchase_source: str = "android",
) -> dict:
    """Safely provision or extend a subscription for any account surface.

    ``android_user_id`` is retained as the parameter name for API compatibility,
    but it is always the local ``users.id``. Ownership is never inferred from a
    Telegram username, email, or the Remnawave profile name.
    """
    db_user_id = int(android_user_id)
    local = await _local_context(session_factory, db_user_id)
    if local is None:
        await _update_delivery_status(
            session_factory, transaction_id, 0,
            error="local_user_not_found", pending=True,
        )
        return {"status": "pending", "message": "local_user_not_found"}
    tg_id = tg_id if tg_id is not None else local.get("tg_id")
    tg_username = tg_username if tg_username is not None else local.get("username")
    email = email or local.get("email")

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
        reason = f"bad tariff_slug: {tariff_slug!r}"
        await _update_delivery_status(
            session_factory, transaction_id, 0,
            error=reason[:255], pending=True,
        )
        await _notify(
            notifier, ok=False, transaction_id=transaction_id,
            db_user_id=db_user_id, tg_id=tg_id, tg_username=tg_username,
            email=email, days=days, tariff_slug=tariff_slug,
            purchase_source=purchase_source,
            reason=reason,
        )
        return {"status": "pending", "message": reason}

    if target_rw_id is not None:
        owner = await _subscription_owner(session_factory, int(target_rw_id))
        if owner is not None and owner != db_user_id:
            await _update_delivery_status(
                session_factory, transaction_id, 0,
                error="target_owner_conflict", pending=True,
            )
            await _notify(
                notifier, ok=False, transaction_id=transaction_id,
                db_user_id=db_user_id, tg_id=tg_id, tg_username=tg_username,
                email=email, days=days, tariff_slug=tariff_slug,
                purchase_source=purchase_source, reason="target_owner_conflict",
            )
            return {"status": "pending", "message": "target_owner_conflict"}
        info = await rem.get_user_from_id(int(target_rw_id))
    else:
        owner = None
        info = None

    created = False
    ordinal: int | None = None
    marker = f"provisioning:{transaction_id}"
    if info is None:
        start = int(local.get("subscription_count") or 0)
        info = None
        for ordinal in range(start, start + _MAX_USERNAME_ATTEMPTS):
            candidate = build_remnawave_username(tg_username, db_user_id, ordinal)
            occupied = await rem.get_user_from_username(candidate)
            if occupied:
                if marker in str(occupied.get("description") or ""):
                    info = occupied
                    break
                continue
            description = provisioning_description(
                transaction_id=transaction_id,
                db_user_id=db_user_id,
                tg_id=tg_id,
                source=purchase_source,
                original_tg_username=tg_username,
                description=target.get("remnawave_description"),
            )
            try:
                result = await apply_new_user(
                    username=candidate,
                    telegram_id=tg_id or 0,
                    days=days,
                    limit_gb=0,
                    email=email,
                    squad_id=internal_ids[0],
                    internal_squad_ids=internal_ids,
                    external_squad_id=external_squad_id,
                    traffic_limit_bytes=target.get("traffic_limit_bytes"),
                    traffic_limit_strategy=target.get("traffic_limit_strategy"),
                    tag=target.get("remnawave_tag"),
                    description=description,
                )
            except Exception as exc:
                logger.warning("create failed for %s, checking marker: %s", candidate, exc)
                appeared = await rem.get_user_from_username(candidate)
                if appeared and marker in str(appeared.get("description") or ""):
                    info = appeared
                    break
                if appeared:
                    continue
                await _update_delivery_status(
                    session_factory, transaction_id, 0,
                    error=str(exc)[:255], pending=True,
                )
                await _notify(
                    notifier, ok=False, transaction_id=transaction_id,
                    db_user_id=db_user_id, tg_id=tg_id, tg_username=tg_username,
                    email=email, days=days, tariff_slug=tariff_slug,
                    purchase_source=purchase_source, reason=str(exc),
                )
                return {"status": "pending", "message": str(exc)}
            appeared = await rem.get_user_from_username(candidate)
            if appeared:
                if marker in str(appeared.get("description") or ""):
                    info = appeared
                    created = bool(result)
                    break
                # A concurrent foreign create won the name. Never attach it.
                continue
            if result:
                info = dict(result)
                info.setdefault("username", candidate)
                info.setdefault("description", description)
            else:
                await _update_delivery_status(
                    session_factory, transaction_id, 0,
                    error="remnawave_apply_returned_none", pending=True,
                )
                return {"status": "pending", "message": "remnawave_apply_returned_none"}
            created = True
            break
        if info is None:
            await _update_delivery_status(
                session_factory, transaction_id, 0,
                error="rw_username_allocation_failed", pending=True,
            )
            await _notify(
                notifier, ok=False, transaction_id=transaction_id,
                db_user_id=db_user_id, tg_id=tg_id, tg_username=tg_username,
                email=email, days=days, tariff_slug=tariff_slug,
                purchase_source=purchase_source,
                reason="rw_username_allocation_failed",
            )
            return {"status": "pending", "message": "rw_username_allocation_failed"}

    actual_rw_id = _rw_id(info)
    if actual_rw_id is None:
        await _update_delivery_status(
            session_factory, transaction_id, 0,
            error="remnawave_missing_rw_id", pending=True,
        )
        return {"status": "pending", "message": "remnawave_missing_rw_id"}
    try:
        action, subscription_number = await _attach_subscription(
            session_factory,
            user_id=db_user_id,
            rw_id=actual_rw_id,
            rw_uuid=(info or {}).get("uuid"),
            transaction_id=transaction_id,
            source=purchase_source,
        )
    except ValueError as exc:
        await _update_delivery_status(
            session_factory, transaction_id, 0,
            error="target_owner_conflict", pending=True,
        )
        await _notify(
            notifier, ok=False, transaction_id=transaction_id,
            db_user_id=db_user_id, tg_id=tg_id, tg_username=tg_username,
            email=email, days=days, tariff_slug=tariff_slug,
            purchase_source=purchase_source, reason=str(exc),
        )
        return {"status": "pending", "message": "target_owner_conflict"}
    if created:
        action = "created"

    username = str((info or {}).get("username") or build_remnawave_username(
        tg_username, db_user_id, ordinal or 0
    ))
    scenario = resolve_scenario(info, SubscriptionType.PAID)

    try:
        if created or marker in str((info or {}).get("description") or ""):
            result = info
        elif scenario == SubscriptionScenario.EXTEND:
            uuid = (info or {}).get("uuid")
            if not uuid:
                await _update_delivery_status(
                    session_factory, transaction_id, 0,
                    error="extend_without_uuid", pending=True,
                )
                return {"status": "pending", "message": "extend without uuid"}
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
                    else f"{purchase_source} paid extend"
                ),
                traffic_limit_bytes=target.get("traffic_limit_bytes"),
                traffic_limit_strategy=target.get("traffic_limit_strategy"),
                tag=target.get("remnawave_tag"),
            )
        else:  # UPDATE / LIMITED / ALREADY_ACTIVE all fall through to update.
            uuid = (info or {}).get("uuid")
            if not uuid:
                reason = f"{scenario.value}_without_uuid"
                await _update_delivery_status(
                    session_factory, transaction_id, 0,
                    error=reason, pending=True,
                )
                return {"status": "pending", "message": reason}
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
                    else f"{purchase_source} paid update"
                ),
                traffic_limit_bytes=target.get("traffic_limit_bytes"),
                traffic_limit_strategy=target.get("traffic_limit_strategy"),
                tag=target.get("remnawave_tag"),
            )
    except Exception as exc:
        logger.error("subscription delivery for tx=%s failed: %s", transaction_id, exc)
        await _update_delivery_status(
            session_factory, transaction_id, 0, error=str(exc)[:255], pending=True
        )
        await _notify(
            notifier, ok=False, transaction_id=transaction_id,
            db_user_id=db_user_id, tg_id=tg_id, tg_username=tg_username,
            email=email, days=days, tariff_slug=tariff_slug,
            purchase_source=purchase_source, reason=str(exc),
        )
        return {"status": "pending", "message": str(exc)}

    if not result:
        await _update_delivery_status(
            session_factory, transaction_id, 0,
            error="remnawave_apply_returned_none", pending=True,
        )
        await _notify(
            notifier, ok=False, transaction_id=transaction_id,
            db_user_id=db_user_id, tg_id=tg_id, tg_username=tg_username,
            email=email, days=days, tariff_slug=tariff_slug,
            purchase_source=purchase_source,
            reason="remnawave_apply_returned_none",
        )
        return {"status": "pending", "message": "remnawave_apply_returned_none"}

    rw_uuid = result.get("uuid") or (info or {}).get("uuid")

    await _update_delivery_status(session_factory, transaction_id, 1)
    await _notify(
        notifier, ok=True, transaction_id=transaction_id,
        db_user_id=db_user_id, tg_id=tg_id, tg_username=tg_username,
        email=email, days=days, tariff_slug=tariff_slug,
        purchase_source=purchase_source, rw_username=username, rw_id=actual_rw_id,
        subscription_number=subscription_number, action=action,
    )
    return {
        "status": "success",
        "scenario": scenario.value,
        "uuid": rw_uuid,
        "subscription_url": result.get("subscription_url"),
        "rw_id": actual_rw_id,
        "username": username,
        "action": action,
    }


async def _deliver_telegram_paid_legacy(
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

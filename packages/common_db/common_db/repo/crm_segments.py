"""CRM segmentation queries against the local database."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Transaction, User
from .users import PAID_ORDER_STATUSES

USER_TYPE_ALL = "all"
USER_TYPE_FREE = "free"
USER_TYPE_PAID_VIP = "paid_vip"

USER_TYPE_OPTIONS: list[dict[str, str]] = [
    {"value": USER_TYPE_ALL, "label": "Все"},
    {"value": USER_TYPE_FREE, "label": "Free"},
    {"value": USER_TYPE_PAID_VIP, "label": "Paid / VIP"},
]


async def filter_users_by_type(
    session: AsyncSession,
    users: list[User],
    user_type: str,
) -> list[User]:
    """Filter scan/broadcast users by Free vs Paid/VIP (local DB)."""
    if not users or not user_type or user_type == USER_TYPE_ALL:
        return users

    now_iso = datetime.now().isoformat(timespec="seconds")
    user_ids = [u.id for u in users]
    paid_rows = await session.scalars(
        select(Transaction.user_id)
        .where(
            Transaction.user_id.in_(user_ids),
            Transaction.order_status.in_(PAID_ORDER_STATUSES),
            Transaction.expire_date > now_iso,
        )
        .distinct()
    )
    paid_ids = set(paid_rows)

    if user_type == USER_TYPE_FREE:
        return [
            u for u in users
            if u.id not in paid_ids and not (u.vip and u.vip > 0)
        ]
    if user_type == USER_TYPE_PAID_VIP:
        return [
            u for u in users
            if u.id in paid_ids or (u.vip and u.vip > 0)
        ]
    return users


async def get_broadcast_eligible_users(session: AsyncSession) -> list[User]:
    """All non-banned users with a Telegram id (mass broadcast audience)."""
    result = await session.scalars(
        select(User).where(
            User.tg_id.is_not(None),
            User.is_banned != True,  # noqa: E712
        )
    )
    return list(result)


async def get_remnawave_broadcast_users(session: AsyncSession) -> list[User]:
    """Local users eligible for Telegram CRM actions."""
    result = await session.scalars(
        select(User).where(
            User.tg_id.is_not(None),
            User.is_banned != True,  # noqa: E712
            User.api_provider == "remnawave",
            User.vless_uuid.is_not(None),
        )
    )
    return list(result)


async def users_with_unpaid_invoices(
    session: AsyncSession,
    *,
    max_age_hours: int = 48,
) -> list[User]:
    """Users with open ``created`` transactions in the last ``max_age_hours``."""
    cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat(
        timespec="seconds"
    )
    stmt = (
        select(User)
        .join(Transaction, Transaction.user_id == User.id)
        .where(
            User.tg_id.is_not(None),
            User.is_banned != True,  # noqa: E712
            Transaction.order_status == "created",
            Transaction.created_at.is_not(None),
            Transaction.created_at >= cutoff,
        )
        .distinct()
    )
    result = await session.scalars(stmt)
    return list(result)


async def users_by_vless_uuids(
    session: AsyncSession, uuids: set[str]
) -> list[User]:
    if not uuids:
        return []
    result = await session.scalars(
        select(User).where(
            User.vless_uuid.in_(list(uuids)),
            User.tg_id.is_not(None),
            User.is_banned != True,  # noqa: E712
        )
    )
    return list(result)

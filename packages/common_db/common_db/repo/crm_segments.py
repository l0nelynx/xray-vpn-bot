"""CRM segmentation queries against the local database."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Transaction, User


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

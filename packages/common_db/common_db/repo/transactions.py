"""Transaction repository helpers."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Transaction


async def cleanup_stale_transactions(session: AsyncSession, *, hours: int = 168) -> int:
    """Delete ``created`` transactions older than ``hours`` (or with no timestamp)."""
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")
    result = await session.execute(
        delete(Transaction).where(
            Transaction.order_status == "created",
            (Transaction.created_at == None) | (Transaction.created_at < cutoff),  # noqa: E711
        )
    )
    return result.rowcount or 0


async def get_by_payment_key(
    session: AsyncSession,
    payment_key: str,
) -> Transaction | None:
    """Resolve either our UUID or a gateway-owned invoice identifier."""
    result = await session.execute(
        select(Transaction).where(
            or_(
                Transaction.transaction_id == payment_key,
                Transaction.provider_invoice_id == payment_key,
            )
        )
    )
    return result.scalar_one_or_none()

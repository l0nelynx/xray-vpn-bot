"""Transaction repository helpers."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete
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

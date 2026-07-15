"""Pay for a menu tariff using bonus credits (full amount only)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Transaction
from .balance import PAYMENT_METHOD_BONUS_CREDITS, debit_if_sufficient


@dataclass(frozen=True, slots=True)
class CreditPurchaseResult:
    transaction_id: str
    days: int
    tariff_slug: str
    credits_spent: int
    balance_after: int


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def purchase_with_credits(
    session: AsyncSession,
    *,
    user_id: int,
    username: str,
    tg_id: int | None,
    days: int,
    tariff_slug: str,
    android_user_id: int | None = None,
) -> CreditPurchaseResult | None:
    """Debit credits and create a confirmed BONUS_CREDITS transaction.

    Returns None if balance is insufficient. Caller owns commit and delivery.
    """
    if days <= 0:
        raise ValueError("days must be positive")

    transaction_id = str(uuid.uuid4())
    debited = await debit_if_sufficient(
        session,
        user_id,
        days,
        reference=transaction_id,
    )
    if not debited:
        return None

    from .balance import get_balance

    balance_after = await get_balance(session, user_id)

    session.add(
        Transaction(
            transaction_id=transaction_id,
            vless_uuid="None",
            username=username,
            order_status="confirmed",
            delivery_status=0,
            days_ordered=days,
            user_id=user_id,
            payment_method=PAYMENT_METHOD_BONUS_CREDITS,
            amount=0.0,
            created_at=_now_iso(),
            tariff_slug=tariff_slug,
            android_user_id=android_user_id,
        )
    )
    await session.flush()
    return CreditPurchaseResult(
        transaction_id=transaction_id,
        days=days,
        tariff_slug=tariff_slug,
        credits_spent=days,
        balance_after=balance_after,
    )


__all__ = ["CreditPurchaseResult", "purchase_with_credits"]

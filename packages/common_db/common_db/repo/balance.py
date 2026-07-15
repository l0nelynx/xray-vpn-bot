"""Bonus credits — ledger-backed wallet (1 credit = 1 subscription day)."""
from __future__ import annotations

import math
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CreditLedger, User
from ..models.credit_ledger import (
    SOURCE_ADMIN,
    SOURCE_CRM,
    SOURCE_MIGRATION,
    SOURCE_PAYMENT,
    SOURCE_PROMO,
)

PAYMENT_METHOD_BONUS_CREDITS = "BONUS_CREDITS"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def discount_percent_to_credits(discount_percent: int) -> int:
    """Legacy conversion: 5 credits per 10% discount, rounded up."""
    return math.ceil(discount_percent / 10 * 5)


async def _lock_user(session: AsyncSession, user_id: int) -> User | None:
    return await session.scalar(
        select(User).where(User.id == user_id).with_for_update()
    )


async def get_balance(session: AsyncSession, user_id: int) -> int:
    user = await session.get(User, user_id)
    return user.bonus_credits if user else 0


async def credit(
    session: AsyncSession,
    user_id: int,
    amount: int,
    source: str,
    reference: str | None = None,
) -> int:
    """Add credits. Returns new balance. Caller owns commit."""
    if amount <= 0:
        raise ValueError("credit amount must be positive")
    user = await _lock_user(session, user_id)
    if user is None:
        raise ValueError(f"user {user_id} not found")
    user.bonus_credits += amount
    new_balance = user.bonus_credits
    session.add(
        CreditLedger(
            user_id=user_id,
            amount=amount,
            source=source,
            reference=reference,
            balance_after=new_balance,
            created_at=_now_iso(),
        )
    )
    await session.flush()
    return new_balance


async def debit_if_sufficient(
    session: AsyncSession,
    user_id: int,
    amount: int,
    source: str = SOURCE_PAYMENT,
    reference: str | None = None,
) -> bool:
    """Deduct credits if balance allows. Returns False if insufficient."""
    if amount <= 0:
        raise ValueError("debit amount must be positive")
    user = await _lock_user(session, user_id)
    if user is None or user.bonus_credits < amount:
        return False
    user.bonus_credits -= amount
    new_balance = user.bonus_credits
    session.add(
        CreditLedger(
            user_id=user_id,
            amount=-amount,
            source=source,
            reference=reference,
            balance_after=new_balance,
            created_at=_now_iso(),
        )
    )
    await session.flush()
    return True


__all__ = [
    "PAYMENT_METHOD_BONUS_CREDITS",
    "SOURCE_ADMIN",
    "SOURCE_CRM",
    "SOURCE_MIGRATION",
    "SOURCE_PAYMENT",
    "SOURCE_PROMO",
    "credit",
    "debit_if_sufficient",
    "discount_percent_to_credits",
    "get_balance",
]

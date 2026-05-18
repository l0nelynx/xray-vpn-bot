"""Promo code lookups and effective-discount resolution.

The promo system has three lookups everyone does:
- "what promo does THIS user own?" — by tg_id
- "is this code valid?" — by promo_code
- "what discount should we apply to this user's purchase?" — uses both
  the user's promo, the owner's promo, and PromoSettings as a fallback

The third query is the hairy one — it lived in three different versions
across miniapp/promo, miniapp/payments, and app/requests. Two of them
didn't fall back to PromoSettings at all, which would have silently
applied a 0% discount on prod if anyone ever ran with a missing
settings row. This module collapses all three into one helper with the
right semantics.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Promo
from .system import get_default_discount_percent


# --- lookups --------------------------------------------------------------


async def get_promo_by_tg_id(
    session: AsyncSession, tg_id: int
) -> Promo | None:
    """Return the promo owned by ``tg_id``, or None."""
    return await session.scalar(select(Promo).where(Promo.tg_id == tg_id))


async def get_promo_by_code(
    session: AsyncSession, promo_code: str
) -> Promo | None:
    """Return the promo registered under ``promo_code``, or None."""
    if not promo_code:
        return None
    return await session.scalar(
        select(Promo).where(Promo.promo_code == promo_code)
    )


# --- effective-discount resolution ----------------------------------------


@dataclass(frozen=True, slots=True)
class EffectiveDiscount:
    """The discount a user gets at checkout when their activated promo is
    still unconsumed. Returned by ``get_effective_discount``."""

    promo_code: str
    discount_percent: int


async def get_effective_discount(
    session: AsyncSession, tg_id: int
) -> EffectiveDiscount | None:
    """Return the discount the user currently qualifies for, or None.

    Mirrors ``app/database/requests.py::get_used_promo_with_discount``
    exactly: returns None unless the user has a promo, has activated
    someone else's code, and hasn't consumed it yet. The discount
    cascade is:

        owner.discount_percent  (if not NULL)
        → PromoSettings.default_discount_percent  (with auto-seed via
          common_db.repo.system; never returns 0 silently on a fresh DB)

    This replaces a copy in miniapp/payments where the cascade fell
    back to plain ``None`` if PromoSettings was missing — a bug
    waiting for a fresh DB to expose it.
    """
    user_promo = await get_promo_by_tg_id(session, tg_id)
    if not user_promo or not user_promo.used_promo or user_promo.used_promo_consumed:
        return None

    owner = await get_promo_by_code(session, user_promo.used_promo)
    if owner is not None and owner.discount_percent is not None:
        return EffectiveDiscount(
            promo_code=user_promo.used_promo,
            discount_percent=owner.discount_percent,
        )

    fallback = await get_default_discount_percent(session)
    return EffectiveDiscount(
        promo_code=user_promo.used_promo, discount_percent=fallback
    )


__all__ = [
    "EffectiveDiscount",
    "get_effective_discount",
    "get_promo_by_code",
    "get_promo_by_tg_id",
]

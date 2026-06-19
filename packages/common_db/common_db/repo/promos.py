"""Promo/referral code logic — the single source of truth for all services.

The bot, miniapp and dashboard all funnel through here so a code behaves
identically everywhere (this collapses the old split where the bot read a
flat config discount while miniapp/dashboard read the DB cascade).

Concepts:
- ``promos`` is the *catalog* of codes. A user's own code is ``promo_type
  == 'referral'``; admin/marketing codes are ``'promotional'``.
- ``promo_redemptions`` is the *history*: one row each time a user redeems a
  code. At most one row per user is ``status == 'active'`` (discount unspent);
  it flips to ``'consumed'`` on the first paid delivery.

Redemption rules (enforced by ``can_redeem``):
- the code must exist and not be the user's own;
- the user can't redeem the same code twice;
- only one active (unconsumed) redemption at a time, any type;
- a *referral* code is only valid for users with no transactions yet.

Discounts are *snapshotted* onto the redemption row at redeem time via the
cascade ``owner.discount_percent → PromoSettings.default → 20`` so later edits
don't retroactively change an already-granted discount.
"""
from __future__ import annotations

import random
import string
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ..models import Promo, PromoRedemption, User
from ..models.promo_redemptions import REDEMPTION_ACTIVE, REDEMPTION_CONSUMED
from ..models.promos import PROMO_TYPE_PROMOTIONAL, PROMO_TYPE_REFERRAL
from .system import get_default_discount_percent
from .users import user_has_any_transaction

_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 8


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# --- catalog lookups ------------------------------------------------------


async def get_promo_by_tg_id(session: AsyncSession, tg_id: int) -> Promo | None:
    """Return the promo *owned* by ``tg_id``, or None."""
    return await session.scalar(select(Promo).where(Promo.tg_id == tg_id))


async def get_promo_by_code(session: AsyncSession, promo_code: str) -> Promo | None:
    """Return the promo registered under ``promo_code``, or None."""
    if not promo_code:
        return None
    return await session.scalar(
        select(Promo).where(Promo.promo_code == promo_code)
    )


async def _generate_unique_code(session: AsyncSession) -> str:
    """Generate an 8-char A–Z0–9 code not already in the catalog."""
    while True:
        code = "".join(random.choices(_CODE_ALPHABET, k=_CODE_LENGTH))
        if await get_promo_by_code(session, code) is None:
            return code


async def get_or_create_referral_code(session: AsyncSession, tg_id: int) -> str:
    """Return the user's own referral code, creating the promo row if absent.

    Used by both invite UIs (bot ``invite_friends`` and miniapp Invite page).
    Does not commit — caller owns the transaction.
    """
    promo = await get_promo_by_tg_id(session, tg_id)
    if promo is not None:
        return promo.promo_code
    code = await _generate_unique_code(session)
    session.add(
        Promo(tg_id=tg_id, promo_code=code, promo_type=PROMO_TYPE_REFERRAL)
    )
    await session.flush()
    return code


# --- redemptions ----------------------------------------------------------


async def get_active_redemption(
    session: AsyncSession, tg_id: int
) -> PromoRedemption | None:
    """The user's current unconsumed redemption, or None."""
    return await session.scalar(
        select(PromoRedemption).where(
            PromoRedemption.tg_id == tg_id,
            PromoRedemption.status == REDEMPTION_ACTIVE,
        )
    )


async def get_redemption_for_code(
    session: AsyncSession, tg_id: int, promo_code: str
) -> PromoRedemption | None:
    """Any redemption (active or consumed) of ``promo_code`` by ``tg_id``."""
    return await session.scalar(
        select(PromoRedemption).where(
            PromoRedemption.tg_id == tg_id,
            PromoRedemption.promo_code == promo_code,
        )
    )


async def has_referral_redemption(session: AsyncSession, tg_id: int) -> bool:
    """True if the user has ever redeemed a referral-type code."""
    return bool(
        await session.scalar(
            select(
                func.count()
            ).select_from(PromoRedemption).where(
                PromoRedemption.tg_id == tg_id,
                PromoRedemption.promo_type == PROMO_TYPE_REFERRAL,
            )
        )
    )


# Reason codes returned by can_redeem — services map these to localized
# bot messages / miniapp HTTP errors. Keep stable; they're a contract.
REASON_OK = "ok"
REASON_INVALID = "invalid"               # code doesn't exist
REASON_OWN_CODE = "own_code"             # can't use your own code
REASON_ALREADY_USED = "already_used"     # already redeemed this exact code
REASON_ACTIVE_EXISTS = "active_exists"   # another unconsumed redemption pending
REASON_REFERRAL_NOT_NEW = "referral_not_new"  # referral code, user not new
REASON_REFERRAL_ONLY_ONE = "referral_only_one"  # already used a referral code


@dataclass(frozen=True, slots=True)
class RedeemResult:
    ok: bool
    reason: str
    promo_code: str | None = None
    promo_type: str | None = None
    discount_percent: int | None = None


async def _resolve_discount(session: AsyncSession, promo: Promo) -> int:
    """Cascade: owner override (incl. explicit 0) → PromoSettings default."""
    if promo.discount_percent is not None:
        return promo.discount_percent
    return await get_default_discount_percent(session)


async def can_redeem(
    session: AsyncSession, tg_id: int, promo_code: str
) -> RedeemResult:
    """Validate whether ``tg_id`` may redeem ``promo_code`` right now.

    Returns a RedeemResult with ``ok`` + a ``reason`` code (and, on success,
    the resolved type/discount so the caller can avoid a second lookup).
    Pure read — does not mutate.
    """
    promo = await get_promo_by_code(session, promo_code)
    if promo is None:
        return RedeemResult(False, REASON_INVALID)

    if promo.tg_id == tg_id:
        return RedeemResult(False, REASON_OWN_CODE)

    if await get_redemption_for_code(session, tg_id, promo_code) is not None:
        return RedeemResult(False, REASON_ALREADY_USED)

    if await get_active_redemption(session, tg_id) is not None:
        return RedeemResult(False, REASON_ACTIVE_EXISTS)

    if promo.promo_type == PROMO_TYPE_REFERRAL:
        if await has_referral_redemption(session, tg_id):
            return RedeemResult(False, REASON_REFERRAL_ONLY_ONE)
        if await user_has_any_transaction(session, tg_id):
            return RedeemResult(False, REASON_REFERRAL_NOT_NEW)

    discount = await _resolve_discount(session, promo)
    return RedeemResult(
        True,
        REASON_OK,
        promo_code=promo.promo_code,
        promo_type=promo.promo_type,
        discount_percent=discount,
    )


async def redeem_promo(
    session: AsyncSession, tg_id: int, promo_code: str
) -> RedeemResult:
    """Validate + record a redemption. On success inserts an active
    ``promo_redemptions`` row (discount snapshotted) and ensures the user has
    their own referral code. Does not commit — caller owns the transaction.
    """
    check = await can_redeem(session, tg_id, promo_code)
    if not check.ok:
        return check

    # Ensure the redeemer has their own referral code (so they can invite
    # others too) — mirrors the bot's historical create-on-activate behavior.
    await get_or_create_referral_code(session, tg_id)

    session.add(
        PromoRedemption(
            tg_id=tg_id,
            promo_code=check.promo_code,
            promo_type=check.promo_type,
            discount_percent=check.discount_percent,
            status=REDEMPTION_ACTIVE,
            created_at=_now_iso(),
        )
    )
    await session.flush()
    return check


async def consume_active_redemption(
    session: AsyncSession, tg_id: int
) -> PromoRedemption | None:
    """Flip the user's active redemption to consumed (after paid delivery).

    Returns the consumed redemption (so the caller can read its promo_code
    for referral-reward routing), or None if there was none.
    """
    redemption = await get_active_redemption(session, tg_id)
    if redemption is None:
        return None
    redemption.status = REDEMPTION_CONSUMED
    redemption.consumed_at = _now_iso()
    await session.flush()
    return redemption


# --- effective discount (checkout) ----------------------------------------


@dataclass(frozen=True, slots=True)
class EffectiveDiscount:
    promo_code: str
    discount_percent: int


async def get_effective_discount(
    session: AsyncSession, tg_id: int
) -> EffectiveDiscount | None:
    """The discount the user currently qualifies for, or None.

    Reads the *active redemption's* snapshot — no re-derivation. Returns None
    when the user has no active (unconsumed) redemption.
    """
    redemption = await get_active_redemption(session, tg_id)
    if redemption is None:
        return None
    return EffectiveDiscount(
        promo_code=redemption.promo_code,
        discount_percent=redemption.discount_percent,
    )


# --- admin/dashboard listing ----------------------------------------------


async def list_promos_paginated(
    session: AsyncSession, page: int, per_page: int
) -> tuple[list[dict], int]:
    """Paginated promo catalog with owner username + redemption count.

    One implementation shared by the bot admin panel and the dashboard
    (previously duplicated with a 0-based vs 1-based offset divergence —
    this is 1-based: page 1 is the first page).
    """
    page = max(1, page)
    usage_sq = (
        select(func.count())
        .select_from(PromoRedemption)
        .where(PromoRedemption.promo_code == Promo.promo_code)
        .correlate(Promo)
        .scalar_subquery()
        .label("usage_count")
    )

    base = select(Promo, User.username, usage_sq).outerjoin(
        User, Promo.tg_id == User.tg_id
    )

    total = await session.scalar(select(func.count()).select_from(Promo)) or 0
    offset = (page - 1) * per_page
    result = await session.execute(
        base.order_by(Promo.id).offset(offset).limit(per_page)
    )

    items = [
        {
            "promo_code": promo.promo_code,
            "promo_type": promo.promo_type,
            "owner_username": owner_username,
            "owner_tg_id": promo.tg_id,
            "usage_count": usage_count or 0,
            "days_purchased": promo.days_purchased,
            "days_rewarded": promo.days_rewarded,
            "discount_percent": promo.discount_percent,
        }
        for promo, owner_username, usage_count in result.all()
    ]
    return items, total


async def get_promo_redeemers(
    session: AsyncSession, promo_code: str
) -> list[dict]:
    """Users who redeemed ``promo_code`` (tg_id + username)."""
    result = await session.execute(
        select(PromoRedemption.tg_id, User.username)
        .outerjoin(User, PromoRedemption.tg_id == User.tg_id)
        .where(PromoRedemption.promo_code == promo_code)
    )
    return [{"tg_id": row[0], "username": row[1]} for row in result.all()]


__all__ = [
    "EffectiveDiscount",
    "RedeemResult",
    "REASON_ACTIVE_EXISTS",
    "REASON_ALREADY_USED",
    "REASON_INVALID",
    "REASON_OK",
    "REASON_OWN_CODE",
    "REASON_REFERRAL_NOT_NEW",
    "REASON_REFERRAL_ONLY_ONE",
    "can_redeem",
    "consume_active_redemption",
    "get_active_redemption",
    "get_effective_discount",
    "get_or_create_referral_code",
    "get_promo_by_code",
    "get_promo_by_tg_id",
    "get_promo_redeemers",
    "get_redemption_for_code",
    "has_referral_redemption",
    "list_promos_paginated",
    "redeem_promo",
]

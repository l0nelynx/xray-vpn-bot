"""Promo/referral code logic — the single source of truth for all services.

Concepts:
- ``promos`` is the *catalog* of codes (referral or promotional).
- ``promo_redemptions`` is an *audit log* of activations (for gating rules).
- Credits are granted immediately to ``users.bonus_credits`` via credit_ledger.

Redemption rules (enforced by ``can_redeem``):
- the code must exist and not be the user's own;
- the user can't redeem the same code twice;
- a *referral* code is only valid for users with no transactions yet;
- at most one referral redemption ever per user.
"""
from __future__ import annotations

import random
import string
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Promo, PromoRedemption, Transaction, User
from ..models.credit_ledger import SOURCE_PROMO
from ..models.promos import PROMO_TYPE_REFERRAL
from .balance import credit as balance_credit, get_balance
from .system import get_default_credit_grant
from .users import (
    PAID_ORDER_STATUSES,
    get_user_by_id,
    get_user_by_tg_id,
    user_has_any_transaction,
)

_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 8


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# --- catalog lookups ------------------------------------------------------


async def get_promo_by_tg_id(session: AsyncSession, tg_id: int) -> Promo | None:
    return await session.scalar(select(Promo).where(Promo.tg_id == tg_id))


async def get_promo_by_code(session: AsyncSession, promo_code: str) -> Promo | None:
    if not promo_code:
        return None
    return await session.scalar(
        select(Promo).where(Promo.promo_code == promo_code)
    )


async def _generate_unique_code(session: AsyncSession) -> str:
    while True:
        code = "".join(random.choices(_CODE_ALPHABET, k=_CODE_LENGTH))
        if await get_promo_by_code(session, code) is None:
            return code


async def get_or_create_referral_code(session: AsyncSession, tg_id: int) -> str:
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


async def get_redemption_for_code(
    session: AsyncSession, tg_id: int, promo_code: str
) -> PromoRedemption | None:
    return await session.scalar(
        select(PromoRedemption).where(
            PromoRedemption.tg_id == tg_id,
            PromoRedemption.promo_code == promo_code,
        )
    )


async def get_latest_redemption(
    session: AsyncSession, tg_id: int
) -> PromoRedemption | None:
    """Most recent redemption — used for referral reward routing on purchase."""
    return await session.scalar(
        select(PromoRedemption)
        .where(PromoRedemption.tg_id == tg_id)
        .order_by(PromoRedemption.id.desc())
        .limit(1)
    )


async def has_referral_redemption(session: AsyncSession, tg_id: int) -> bool:
    return bool(
        await session.scalar(
            select(func.count()).select_from(PromoRedemption).where(
                PromoRedemption.tg_id == tg_id,
                PromoRedemption.promo_type == PROMO_TYPE_REFERRAL,
            )
        )
    )


REASON_OK = "ok"
REASON_INVALID = "invalid"
REASON_OWN_CODE = "own_code"
REASON_ALREADY_USED = "already_used"
REASON_REFERRAL_NOT_NEW = "referral_not_new"
REASON_REFERRAL_ONLY_ONE = "referral_only_one"
REASON_NO_USER = "no_user"


@dataclass(frozen=True, slots=True)
class RedeemResult:
    ok: bool
    reason: str
    promo_code: str | None = None
    promo_type: str | None = None
    credit_grant: int | None = None
    new_balance: int | None = None


async def _resolve_credit_grant(session: AsyncSession, promo: Promo) -> int:
    if promo.credit_grant is not None:
        return promo.credit_grant
    return await get_default_credit_grant(session)


async def _resolve_user_for_redeem(
    session: AsyncSession, tg_id: int
) -> User | None:
    """Map redemption tg_id to a users row (real tg_id or synthetic -user.id)."""
    user = await get_user_by_tg_id(session, tg_id)
    if user is not None:
        return user
    if tg_id < 0:
        return await get_user_by_id(session, -tg_id)
    return None


async def can_redeem(
    session: AsyncSession, tg_id: int, promo_code: str
) -> RedeemResult:
    promo = await get_promo_by_code(session, promo_code)
    if promo is None:
        return RedeemResult(False, REASON_INVALID)

    if promo.tg_id == tg_id:
        return RedeemResult(False, REASON_OWN_CODE)

    if await get_redemption_for_code(session, tg_id, promo_code) is not None:
        return RedeemResult(False, REASON_ALREADY_USED)

    if promo.promo_type == PROMO_TYPE_REFERRAL:
        if await has_referral_redemption(session, tg_id):
            return RedeemResult(False, REASON_REFERRAL_ONLY_ONE)
        if await user_has_any_transaction(session, tg_id):
            return RedeemResult(False, REASON_REFERRAL_NOT_NEW)

    grant = await _resolve_credit_grant(session, promo)
    return RedeemResult(
        True,
        REASON_OK,
        promo_code=promo.promo_code,
        promo_type=promo.promo_type,
        credit_grant=grant,
    )


async def redeem_promo(
    session: AsyncSession, tg_id: int, promo_code: str
) -> RedeemResult:
    """Validate, record audit row, credit user's balance immediately."""
    check = await can_redeem(session, tg_id, promo_code)
    if not check.ok:
        return check

    user = await _resolve_user_for_redeem(session, tg_id)
    if user is None:
        return RedeemResult(False, REASON_NO_USER)

    await get_or_create_referral_code(session, tg_id)

    session.add(
        PromoRedemption(
            tg_id=tg_id,
            promo_code=check.promo_code,
            promo_type=check.promo_type,
            created_at=_now_iso(),
        )
    )

    grant = check.credit_grant or 0
    if grant > 0:
        new_balance = await balance_credit(
            session,
            user.id,
            grant,
            SOURCE_PROMO,
            reference=check.promo_code,
        )
    else:
        new_balance = await get_balance(session, user.id)
    await session.flush()

    if check.promo_type == PROMO_TYPE_REFERRAL:
        promo = await get_promo_by_code(session, check.promo_code)
        if promo is not None:
            from . import giveaways as _giveaways
            from ..models.giveaways import TICKET_SOURCE_INVITEE_REF

            await _giveaways.try_grant_invitee_ticket(
                session,
                referrer_tg_id=promo.tg_id,
                invitee_tg_id=tg_id,
                source=TICKET_SOURCE_INVITEE_REF,
            )

    return RedeemResult(
        True,
        REASON_OK,
        promo_code=check.promo_code,
        promo_type=check.promo_type,
        credit_grant=grant,
        new_balance=new_balance,
    )


# --- admin/dashboard listing ----------------------------------------------


async def list_promos_paginated(
    session: AsyncSession, page: int, per_page: int
) -> tuple[list[dict], int]:
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
            "points_rewarded": promo.points_rewarded,
            "credit_grant": promo.credit_grant,
        }
        for promo, owner_username, usage_count in result.all()
    ]
    return items, total


async def get_promo_redeemers(
    session: AsyncSession, promo_code: str
) -> list[dict]:
    result = await session.execute(
        select(PromoRedemption.tg_id, User.username)
        .outerjoin(User, PromoRedemption.tg_id == User.tg_id)
        .where(PromoRedemption.promo_code == promo_code)
    )
    return [{"tg_id": row[0], "username": row[1]} for row in result.all()]


async def list_referral_stats_paginated(
    session: AsyncSession,
    *,
    page: int = 1,
    per_page: int = 20,
    sort: str = "referral_count",
    order: str = "desc",
    search: str = "",
    metric: str = "total",
) -> tuple[list[dict], int]:
    """Leaderboard of referral-code owners by total or paying invitees."""
    page = max(1, page)
    per_page = max(1, min(per_page, 100))

    referral_count_sq = (
        select(func.count())
        .select_from(PromoRedemption)
        .where(PromoRedemption.promo_code == Promo.promo_code)
        .correlate(Promo)
        .scalar_subquery()
        .label("referral_count")
    )
    paying_referral_count_sq = (
        select(func.count(func.distinct(PromoRedemption.tg_id)))
        .select_from(PromoRedemption)
        .join(User, User.tg_id == PromoRedemption.tg_id)
        .join(Transaction, Transaction.user_id == User.id)
        .where(
            PromoRedemption.promo_code == Promo.promo_code,
            Transaction.order_status.in_(PAID_ORDER_STATUSES),
        )
        .correlate(Promo)
        .scalar_subquery()
        .label("paying_referral_count")
    )

    base = (
        select(
            Promo,
            User.username,
            referral_count_sq,
            paying_referral_count_sq,
        )
        .outerjoin(User, Promo.tg_id == User.tg_id)
        .where(Promo.promo_type == PROMO_TYPE_REFERRAL)
    )

    if search.strip():
        like = f"%{search.strip()}%"
        conds = [Promo.promo_code.ilike(like), User.username.ilike(like)]
        if search.strip().lstrip("-").isdigit():
            conds.append(Promo.tg_id == int(search.strip()))
        base = base.where(or_(*conds))

    total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0

    sort_columns = {
        "owner_tg_id": Promo.tg_id,
        "owner_username": User.username,
        "promo_code": Promo.promo_code,
        "referral_count": referral_count_sq,
        "paying_referral_count": paying_referral_count_sq,
        "days_purchased": Promo.days_purchased,
        "points_rewarded": Promo.points_rewarded,
    }
    default_sort = (
        "paying_referral_count" if metric == "paying" else "referral_count"
    )
    sort_col = sort_columns.get(sort, sort_columns[default_sort])
    base = base.order_by(sort_col.asc() if order == "asc" else sort_col.desc())

    offset = (page - 1) * per_page
    rows = (await session.execute(base.offset(offset).limit(per_page))).all()
    items = [
        {
            "owner_tg_id": promo.tg_id,
            "owner_username": owner_username,
            "promo_code": promo.promo_code,
            "referral_count": referral_count or 0,
            "paying_referral_count": paying_referral_count or 0,
            "days_purchased": promo.days_purchased,
            "points_rewarded": promo.points_rewarded,
        }
        for promo, owner_username, referral_count, paying_referral_count in rows
    ]
    return items, total


__all__ = [
    "RedeemResult",
    "REASON_ALREADY_USED",
    "REASON_INVALID",
    "REASON_NO_USER",
    "REASON_OK",
    "REASON_OWN_CODE",
    "REASON_REFERRAL_NOT_NEW",
    "REASON_REFERRAL_ONLY_ONE",
    "can_redeem",
    "get_latest_redemption",
    "get_or_create_referral_code",
    "get_promo_by_code",
    "get_promo_by_tg_id",
    "get_promo_redeemers",
    "get_redemption_for_code",
    "has_referral_redemption",
    "list_promos_paginated",
    "list_referral_stats_paginated",
    "redeem_promo",
]

"""Referral reward computation — shared DB logic for paid purchases."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Promo
from ..models.credit_ledger import SOURCE_PROMO
from .balance import credit
from .promos import get_latest_redemption
from .system import get_points_reward_per_30, get_reward_cap_points
from .users import get_user_by_tg_id


@dataclass(frozen=True, slots=True)
class ReferralRewardInfo:
    owner_tg_id: int
    owner_user_id: int
    promo_code: str
    reward_points: int
    days_purchased: int
    points_rewarded_before: int
    points_rewarded_after: int


async def record_purchase_and_compute_reward(
    session: AsyncSession,
    buyer_tg_id: int,
    days: int,
) -> ReferralRewardInfo | None:
    """Bump invitee days on the referral code and credit owner bonus points."""
    redemption = await get_latest_redemption(session, buyer_tg_id)
    if redemption is None:
        return None

    promo = await session.scalar(
        select(Promo).where(Promo.promo_code == redemption.promo_code)
    )
    if promo is None:
        return None

    owner = await get_user_by_tg_id(session, promo.tg_id)
    if owner is None:
        return None

    promo.days_purchased += days
    points_per_30 = await get_points_reward_per_30(session)
    reward_cap_points = await get_reward_cap_points(session)

    total_purchased = promo.days_purchased
    already_rewarded = promo.points_rewarded
    reward_points = (total_purchased // 30) * points_per_30 - already_rewarded
    reward_points = max(0, min(reward_points, reward_cap_points - already_rewarded))

    if reward_points > 0:
        promo.points_rewarded = already_rewarded + reward_points
        await credit(
            session,
            owner.id,
            reward_points,
            SOURCE_PROMO,
            reference=f"referral:{promo.promo_code}",
        )

    await session.flush()
    if reward_points <= 0:
        return None

    return ReferralRewardInfo(
        owner_tg_id=promo.tg_id,
        owner_user_id=owner.id,
        promo_code=promo.promo_code,
        reward_points=reward_points,
        days_purchased=total_purchased,
        points_rewarded_before=already_rewarded,
        points_rewarded_after=already_rewarded + reward_points,
    )


__all__ = ["ReferralRewardInfo", "record_purchase_and_compute_reward"]

"""Referral reward computation — shared DB logic for paid purchases."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Promo
from .promos import get_latest_redemption
from .system import get_days_reward_per_30, get_reward_cap_days


@dataclass(frozen=True, slots=True)
class ReferralRewardInfo:
    owner_tg_id: int
    promo_code: str
    reward_days: int
    days_purchased: int
    days_rewarded_before: int
    days_rewarded_after: int


async def record_purchase_and_compute_reward(
    session: AsyncSession,
    buyer_tg_id: int,
    days: int,
) -> ReferralRewardInfo | None:
    """Bump invitee days on the referral code and compute owner reward."""
    redemption = await get_latest_redemption(session, buyer_tg_id)
    if redemption is None:
        return None

    promo = await session.scalar(
        select(Promo).where(Promo.promo_code == redemption.promo_code)
    )
    if promo is None:
        return None

    promo.days_purchased += days
    days_reward_per_30 = await get_days_reward_per_30(session)
    reward_cap_days = await get_reward_cap_days(session)

    total_purchased = promo.days_purchased
    already_rewarded = promo.days_rewarded
    reward_days = (total_purchased // 30) * days_reward_per_30 - already_rewarded
    reward_days = max(0, min(reward_days, reward_cap_days - already_rewarded))

    if reward_days > 0:
        promo.days_rewarded = already_rewarded + reward_days

    await session.flush()
    if reward_days <= 0:
        return None

    return ReferralRewardInfo(
        owner_tg_id=promo.tg_id,
        promo_code=promo.promo_code,
        reward_days=reward_days,
        days_purchased=total_purchased,
        days_rewarded_before=already_rewarded,
        days_rewarded_after=already_rewarded + reward_days,
    )


__all__ = ["ReferralRewardInfo", "record_purchase_and_compute_reward"]

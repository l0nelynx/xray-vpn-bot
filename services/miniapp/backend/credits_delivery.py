"""Orchestrate bonus-credit purchase + Remnawave delivery + referral."""
from __future__ import annotations

import logging

from common_db.repo import credits_pay as _repo_credits_pay
from common_db.repo import referral_rewards as _repo_referral
from subscription_delivery import deliver_android_paid, deliver_telegram_paid

from .database.session import async_session
from .notify_log import notify_log

logger = logging.getLogger(__name__)


async def _noop_squad_resolver(_slug: str):
    return None


async def pay_and_deliver(
    *,
    user_id: int,
    tg_id: int | None,
    username: str,
    days: int,
    tariff_slug: str,
    android_user_id: int | None = None,
    email: str | None = None,
    referral_tg_id: int | None = None,
) -> dict:
    """Debit credits, create transaction, deliver subscription."""
    async with async_session() as session:
        purchase = await _repo_credits_pay.purchase_with_credits(
            session,
            user_id=user_id,
            username=username,
            tg_id=tg_id,
            days=days,
            tariff_slug=tariff_slug,
            android_user_id=android_user_id,
        )
        if purchase is None:
            await session.rollback()
            return {"status": "error", "message": "insufficient_credits"}

        reward = None
        rtg = referral_tg_id if referral_tg_id is not None else tg_id
        if rtg:
            reward = await _repo_referral.record_purchase_and_compute_reward(
                session, rtg, days
            )
        await session.commit()

    tx_id = purchase.transaction_id

    if android_user_id and not tg_id:
        result = await deliver_android_paid(
            transaction_id=tx_id,
            android_user_id=android_user_id,
            email=email,
            days=days,
            tariff_slug=tariff_slug,
            session_factory=async_session,
            notifier=notify_log,
            squad_resolver=_noop_squad_resolver,
        )
    elif tg_id:
        result = await deliver_telegram_paid(
            transaction_id=tx_id,
            tg_id=tg_id,
            username=username,
            days=days,
            tariff_slug=tariff_slug,
            session_factory=async_session,
            notifier=notify_log,
            squad_resolver=_noop_squad_resolver,
        )
    else:
        return {"status": "error", "message": "no_delivery_target"}

    if result.get("status") != "success":
        return result

    return {
        "status": "success",
        "transaction_id": tx_id,
        "balance_after": purchase.balance_after,
        "credits_spent": purchase.credits_spent,
        "referral_reward": reward.reward_days if reward else 0,
        "subscription_url": result.get("subscription_url"),
    }

"""Orchestrate bonus-credit purchase + Remnawave delivery + referral."""
from __future__ import annotations

import logging

from sqlalchemy import text
from common_db.repo import credits_pay as _repo_credits_pay
from common_db.repo import referral_rewards as _repo_referral
from subscription_delivery import deliver_android_paid

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
    points_cost: int,
    days: int,
    tariff_slug: str,
    delivery_target: dict | None = None,
    android_user_id: int | None = None,
    email: str | None = None,
    referral_tg_id: int | None = None,
    target_rw_id: int | None = None,
    purchase_source: str = "legacy_unknown",
) -> dict:
    """Debit RUB points, create transaction, deliver subscription."""
    async with async_session() as session:
        # Validate ownership before the irreversible balance debit. An absent
        # local link is recoverable; a link owned by another account is not.
        if target_rw_id is not None:
            owner = await session.scalar(
                text(
                    "SELECT owner_id FROM ("
                    "SELECT user_id AS owner_id, 0 AS priority FROM user_subscriptions WHERE rw_id = :r "
                    "UNION ALL SELECT id AS owner_id, 1 AS priority FROM users WHERE rw_id = :r"
                    ") owners ORDER BY priority LIMIT 1"
                ),
                {"r": int(target_rw_id)},
            )
            if owner is not None and int(owner) != int(user_id):
                await notify_log(
                    "🚨 <b>Credit delivery blocked</b>\n"
                    f"error: <code>target_owner_conflict</code>\n"
                    f"DB user: <code>{user_id}</code>\n"
                    f"rw_id: <code>{target_rw_id}</code>"
                )
                return {"status": "pending", "message": "target_owner_conflict"}
        purchase = await _repo_credits_pay.purchase_with_credits(
            session,
            user_id=user_id,
            username=username,
            tg_id=tg_id,
            points_cost=points_cost,
            days=days,
            tariff_slug=tariff_slug,
            android_user_id=android_user_id,
            target_rw_id=target_rw_id,
            purchase_source=purchase_source,
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

    result = await deliver_android_paid(
        transaction_id=tx_id,
        android_user_id=user_id,
        email=email,
        days=days,
        tariff_slug=tariff_slug,
        session_factory=async_session,
        notifier=notify_log,
        delivery_target=delivery_target,
        squad_resolver=_noop_squad_resolver,
        target_rw_id=target_rw_id,
        tg_id=tg_id,
        tg_username=username if tg_id is not None else None,
        purchase_source=purchase_source,
    )

    if result.get("status") != "success":
        return result

    return {
        "status": "success",
        "transaction_id": tx_id,
        "balance_after": purchase.balance_after,
        "points_spent": purchase.points_spent,
        "credits_spent": purchase.credits_spent,
        "referral_reward": reward.reward_points if reward else 0,
        "subscription_url": result.get("subscription_url"),
    }

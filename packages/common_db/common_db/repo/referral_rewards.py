"""Idempotent owner rewards from completed purchases, independent of delivery UI."""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select, update
from ..models import Promo, PromoRedemption, Transaction, User
from ..models.referral_recovery import ReferralNotice, ReferralReceipt, ReferralRecovery
from .balance import credit, PAYMENT_METHOD_BONUS_CREDITS
from .system import get_points_reward_per_30, get_reward_cap_points


async def lock_rewards(session):
    # Real UPDATE serializes SQLite too. Every reward and recovery locks first.
    result = await session.execute(update(ReferralRecovery).where(
        ReferralRecovery.id == 1
    ).values(id=1))
    if result.rowcount != 1:
        raise RuntimeError("Referral schema is not initialized; run migrations")
    return await session.get(ReferralRecovery, 1, populate_existing=True)


def timestamp(value):
    if not value:
        raise ValueError("missing_date")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def eligible(tx):
    return (tx.delivery_status == 1 and tx.order_status in ("confirmed", "delivered")
            and tx.days_ordered > 0
            and (tx.payment_method == PAYMENT_METHOD_BONUS_CREDITS or (tx.amount or 0) > 0))


async def resolve_referral(session, tx, lookup=None):
    buyer = lookup["users"].get(tx.user_id) if lookup is not None else await session.get(User, tx.user_id)
    if buyer is None:
        raise ValueError("buyer_missing")
    identities = [-buyer.id]
    if buyer.tg_id is not None:
        identities.append(buyer.tg_id)
    if lookup is not None:
        rows = sorted((r for identity in identities for r in lookup["redemptions"].get(identity, [])), key=lambda r: r.id)
    else:
        rows = (await session.scalars(select(PromoRedemption).where(
            PromoRedemption.tg_id.in_(identities), PromoRedemption.promo_type == "referral"
        ).order_by(PromoRedemption.id))).all()
    if not rows:
        return None
    if len({r.promo_code for r in rows}) > 1:
        raise ValueError("multiple_referrers")
    redemption = rows[0]
    if timestamp(redemption.created_at) > timestamp(tx.created_at):
        return None
    promo = lookup["promos"].get(redemption.promo_code) if lookup is not None else await session.scalar(
        select(Promo).where(Promo.promo_code == redemption.promo_code, Promo.promo_type == "referral"))
    if promo is None:
        raise ValueError("referral_code_missing")
    owners = lookup["owners"].get(promo.tg_id, []) if lookup is not None else (
        await session.scalars(select(User).where(User.tg_id == promo.tg_id))).all()
    if not owners and promo.tg_id < 0:
        owner = lookup["users"].get(-promo.tg_id) if lookup is not None else await session.get(User, -promo.tg_id)
    elif len(owners) == 1:
        owner = owners[0]
    else:
        raise ValueError("owner_missing_or_ambiguous")
    if owner is None:
        raise ValueError("owner_missing")
    if owner.id == buyer.id:
        return None
    return promo, owner


async def record_purchase_and_compute_reward(session, transaction_id: str):
    await lock_rewards(session)
    if await session.get(ReferralReceipt, transaction_id):
        return 0
    tx = await session.get(Transaction, transaction_id, populate_existing=True)
    if tx is None or not eligible(tx):
        return 0
    resolved = await resolve_referral(session, tx)
    receipt = ReferralReceipt(transaction_id=transaction_id, kind="live", points=0)
    session.add(receipt)
    if resolved is None:
        await session.flush()
        return 0
    promo, owner = resolved
    receipt.promo_code = promo.promo_code
    promo.days_purchased += tx.days_ordered
    rate = await get_points_reward_per_30(session)
    cap = await get_reward_cap_points(session)
    points = max(0, min((promo.days_purchased // 30) * rate, cap) - promo.points_rewarded)
    if points:
        await credit(session, owner.id, points, "promo", f"referral:{promo.promo_code}")
        promo.points_rewarded += points
        receipt.points = points
        session.add(ReferralNotice(
            key=f"purchase:{transaction_id}", user_id=owner.id, tg_id=owner.tg_id,
            text=f"Реферальный бонус! За покупку приглашённого пользователя вам начислено {points} баллов.",
            status="pending" if owner.tg_id else "unavailable",
        ))
    from . import giveaways
    from ..models.giveaways import TICKET_SOURCE_INVITEE_PURCHASE
    await giveaways.try_grant_invitee_ticket(
        session, referrer_tg_id=promo.tg_id,
        invitee_tg_id=(await session.get(User, tx.user_id)).tg_id or -tx.user_id,
        source=TICKET_SOURCE_INVITEE_PURCHASE,
    )
    await session.flush()
    return points

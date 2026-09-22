"""Restart-safe purchase reconciliation and an at-most-once Telegram outbox."""
import asyncio
import logging
import time

from sqlalchemy import select, update, or_

from .models import Transaction
from .models.referral_recovery import ReferralReceipt, ReferralNotice
from .repo.referral_rewards import record_purchase_and_compute_reward

logger = logging.getLogger(__name__)


async def process_purchases(session_factory, excluded=()):
    async with session_factory() as session:
        ids = (await session.scalars(select(Transaction.transaction_id).where(
            Transaction.delivery_status == 1,
            Transaction.order_status.in_(["confirmed", "delivered"]),
            Transaction.days_ordered > 0,
            or_(Transaction.amount > 0, Transaction.payment_method == "BONUS_CREDITS"),
            ~Transaction.transaction_id.in_(select(ReferralReceipt.transaction_id)),
            ~Transaction.transaction_id.in_(list(excluded)),
        ).order_by(Transaction.transaction_id).limit(100))).all()
    failures = []
    for tx_id in ids:
        try:
            async with session_factory() as session:
                await record_purchase_and_compute_reward(session, tx_id)
                await session.commit()
        except Exception:
            failures.append(tx_id)
            logger.exception("Referral reward will be retried: transaction=%s", tx_id)
    return failures


async def send_notices(session_factory, sender):
    async with session_factory() as session:
        # A crash after Telegram accepted a request cannot be distinguished
        # from a crash before it. Never silently resend such messages.
        await session.execute(update(ReferralNotice).where(
            ReferralNotice.status == "sending", ReferralNotice.claimed_at < time.time() - 120
        ).values(status="unknown", error="Delivery result unknown after interruption"))
        keys = (await session.scalars(select(ReferralNotice.key).where(
            ReferralNotice.status == "pending"
        ).order_by(ReferralNotice.key).limit(10))).all()
        await session.commit()
    for key in keys:
        async with session_factory() as session:
            claimed = await session.execute(update(ReferralNotice).where(
                ReferralNotice.key == key, ReferralNotice.status == "pending"
            ).values(status="sending", claimed_at=time.time()))
            if claimed.rowcount != 1:
                await session.rollback()
                continue
            row = await session.get(ReferralNotice, key)
            tg_id, message = row.tg_id, row.text
            await session.commit()
        try:
            status, error = await sender(tg_id, message)
        except Exception:
            status, error = "unknown", "Telegram response unavailable"
        async with session_factory() as session:
            await session.execute(update(ReferralNotice).where(
                ReferralNotice.key == key, ReferralNotice.status == "sending"
            ).values(status=status, error=error))
            await session.commit()
        await asyncio.sleep(0.1)


async def referral_loop(session_factory, sender=None):
    retry_after = {}
    while True:
        try:
            retry_after = {k: v for k, v in retry_after.items() if v > time.monotonic()}
            for tx_id in await process_purchases(session_factory, retry_after):
                retry_after[tx_id] = time.monotonic() + 300
            if sender:
                await send_notices(session_factory, sender)
        except Exception:
            logger.exception("Referral worker iteration failed; retrying")
        await asyncio.sleep(5)

"""Referral recovery and live rewards: real DB, no external services."""
import asyncio
from unittest.mock import AsyncMock
from unittest.mock import patch
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from common_db import Base
from common_db.models import User, Promo, PromoRedemption, PromoSettings, Transaction, CreditLedger
from common_db.models.referral_recovery import ReferralRecovery, ReferralReceipt, ReferralNotice
from common_db.repo.referral_rewards import record_purchase_and_compute_reward as reward
from common_db.repo.referral_recovery import preview, execute
from common_db.repo.balance import credit, debit_if_sufficient
from common_db.referral_worker import process_purchases, send_notices


async def setup(url="sqlite+aiosqlite:///:memory:"):
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        s.add_all([
            ReferralRecovery(id=1, status="ready"),
            PromoSettings(id=1, points_reward_per_30=30, reward_cap_points=1800),
            User(id=1, tg_id=100, username="owner"),
            User(id=2, tg_id=200, username="buyer"),
            Promo(id=1, tg_id=100, promo_code="REF100", promo_type="referral"),
            PromoRedemption(id=1, tg_id=200, promo_code="REF100", promo_type="referral", created_at="2026-01-01"),
        ])
        await s.commit()
    return engine, factory


def purchase(id="tx", **kwargs):
    values = dict(transaction_id=id, user_id=2, vless_uuid="none", order_status="confirmed", delivery_status=1,
                  payment_method="CARD", amount=100, days_ordered=30, created_at="2026-02-01")
    values.update(kwargs)
    return Transaction(**values)


def scenario(fn):
    def run():
        async def go():
            engine, factory = await setup()
            try:
                await fn(factory)
            finally:
                await engine.dispose()
        asyncio.run(go())
    return run


@scenario
async def test_owner_without_subscription_and_duplicate_purchase(factory):
    async with factory() as s:
        s.add(purchase())
        await s.commit()
    for _ in range(2):
        async with factory() as s:
            await reward(s, "tx")
            await s.commit()
    async with factory() as s:
        assert (await s.get(User, 1)).bonus_credits == 30
        assert (await s.get(Promo, 1)).days_purchased == 30
        assert await s.scalar(select(func.count()).select_from(CreditLedger)) == 1
        assert await s.scalar(select(func.count()).select_from(ReferralNotice)) == 1


@scenario
async def test_promotional_redemption_does_not_override_referrer(factory):
    async with factory() as s:
        s.add_all([purchase(), PromoRedemption(id=2, tg_id=200, promo_code="SALE", promo_type="promotional", created_at="2026-01-02")])
        await s.commit()
    assert await process_purchases(factory) == []
    async with factory() as s:
        assert (await s.get(User, 1)).bonus_credits == 30


@scenario
async def test_synthetic_identity_owner_and_buyer(factory):
    async with factory() as s:
        (await s.get(User, 1)).tg_id = None
        (await s.get(User, 2)).tg_id = None
        (await s.get(Promo, 1)).tg_id = -1
        (await s.get(PromoRedemption, 1)).tg_id = -2
        s.add(purchase())
        await s.commit()
    assert await process_purchases(factory) == []
    async with factory() as s:
        assert (await s.get(User, 1)).bonus_credits == 30
        assert (await s.get(ReferralNotice, "purchase:tx")).status == "unavailable"


@scenario
async def test_only_delivered_paid_post_redemption_purchases(factory):
    async with factory() as s:
        s.add_all([purchase("free", amount=0), purchase("pending", delivery_status=0),
                   purchase("cancelled", order_status="cancelled"), purchase("early", created_at="2025-01-01"),
                   purchase("credits", payment_method="BONUS_CREDITS", amount=0)])
        await s.commit()
    await process_purchases(factory)
    async with factory() as s:
        assert (await s.get(User, 1)).bonus_credits == 30
        assert (await s.get(Promo, 1)).days_purchased == 30


@scenario
async def test_partial_months_and_cap(factory):
    async with factory() as s:
        (await s.get(PromoSettings, 1)).reward_cap_points = 35
        s.add_all([purchase("a", days_ordered=15), purchase("b", days_ordered=15), purchase("c", days_ordered=30)])
        await s.commit()
    await process_purchases(factory)
    async with factory() as s:
        assert (await s.get(User, 1)).bonus_credits == 35
        assert (await s.get(Promo, 1)).days_purchased == 60


@scenario
async def test_recovery_manual_grants_spending_and_idempotency(factory):
    async with factory() as s:
        s.add_all([purchase("a", days_ordered=90), ReferralReceipt(transaction_id="a", kind="legacy", points=0)])
        await credit(s, 1, 30, "promo", "referral:REF100")
        await credit(s, 1, 20, "admin", "admin:1")
        await debit_if_sufficient(s, 1, 50)
        (await s.get(Promo, 1)).points_rewarded = 30
        (await s.get(Promo, 1)).days_purchased = 30
        await s.commit()
    async with factory() as s:
        snap = await preview(s)
        assert snap["plan"]["missing"] == 40
        assert snap["plan"]["bonus"] == 4
        assert snap["plan"]["rows"][0]["spent"] == 50
        await s.commit()
    for _ in range(2):
        async with factory() as s:
            await execute(s, snap["id"])
            await s.commit()
    async with factory() as s:
        assert (await s.get(User, 1)).bonus_credits == 44
        assert (await s.get(Promo, 1)).points_rewarded == 90
        assert (await s.get(Promo, 1)).days_purchased == 90
        assert await s.scalar(select(func.count()).select_from(ReferralNotice)) == 1
        s.add(purchase("new"))
        await s.commit()
    await process_purchases(factory)
    async with factory() as s:
        assert (await s.get(User, 1)).bonus_credits == 74


@scenario
async def test_spending_own_promo_grant_does_not_reduce_reward(factory):
    async with factory() as s:
        s.add(purchase())
        await credit(s, 1, 100, "promo", "OTHER_CODE")
        await debit_if_sufficient(s, 1, 100)
        await s.commit()
    async with factory() as s:
        snap = await preview(s)
        assert snap["plan"]["missing"] == 30


@scenario
async def test_round_up_manual_override_and_fully_compensated(factory):
    async with factory() as s:
        s.add(purchase())
        await credit(s, 1, 30, "admin", "admin:1")
        await s.commit()
    async with factory() as s:
        assert (await preview(s))["plan"]["total"] == 0
        snap = await preview(s, {"1": 29})
        assert snap["plan"]["missing"] == snap["plan"]["bonus"] == 1
        await s.commit()
    async with factory() as s:
        await execute(s, snap["id"])
        await s.commit()
        assert (await s.get(User, 1)).bonus_credits == 32


@scenario
async def test_stale_preview_blocks_changed_balance(factory):
    async with factory() as s:
        s.add(purchase())
        await s.commit()
        snap = await preview(s)
        await s.commit()
    async with factory() as s:
        await credit(s, 1, 5, "admin")
        await s.commit()
    async with factory() as s:
        with pytest.raises(ValueError, match="preview_stale"):
            await execute(s, snap["id"])
        await s.rollback()
        assert (await s.get(ReferralRecovery, 1)).status == "ready"


@scenario
async def test_unprocessed_live_purchase_is_absorbed_by_recovery(factory):
    async with factory() as s:
        s.add(purchase())
        await s.commit()
        snap = await preview(s)
        await s.commit()
        await execute(s, snap["id"])
        await s.commit()
    await process_purchases(factory)
    async with factory() as s:
        assert (await s.get(User, 1)).bonus_credits == 33
        assert (await s.get(Promo, 1)).days_purchased == 30


@scenario
async def test_recovery_rollback_no_partial_grants(factory):
    async with factory() as s:
        s.add(purchase())
        await s.commit()
        snap = await preview(s)
        await s.commit()
        await execute(s, snap["id"])
        await s.rollback()
    async with factory() as s:
        assert (await s.get(User, 1)).bonus_credits == 0
        assert await s.scalar(select(func.count()).select_from(ReferralNotice)) == 0
        await execute(s, snap["id"])
        await s.commit()
        assert (await s.get(User, 1)).bonus_credits == 33


@scenario
async def test_notification_failure_does_not_rollback_or_repeat_credit(factory):
    async with factory() as s:
        s.add(purchase())
        await s.commit()
        snap = await preview(s)
        await s.commit()
        await execute(s, snap["id"])
        await s.commit()
    sender = AsyncMock(return_value=("failed", "bot blocked"))
    await send_notices(factory, sender)
    await send_notices(factory, sender)
    assert sender.await_count == 1
    async with factory() as s:
        assert (await s.get(User, 1)).bonus_credits == 33
        assert (await s.get(ReferralNotice, "recovery:1")).status == "failed"


@scenario
async def test_interrupted_notice_is_not_resent(factory):
    async with factory() as s:
        s.add(ReferralNotice(key="recovery:1", user_id=1, tg_id=100, text="hi", status="sending", claimed_at=0))
        await s.commit()
    sender = AsyncMock(return_value=("sent", None))
    await send_notices(factory, sender)
    sender.assert_not_awaited()
    async with factory() as s:
        assert (await s.get(ReferralNotice, "recovery:1")).status == "unknown"


@scenario
async def test_missing_owner_is_visible_and_blocks_recovery(factory):
    async with factory() as s:
        (await s.get(Promo, 1)).tg_id = 999
        s.add(purchase())
        await s.commit()
        snap = await preview(s)
        assert snap["plan"]["issues"]
        await s.commit()
        with pytest.raises(ValueError, match="resolve_issues"):
            await execute(s, snap["id"])
    assert await process_purchases(factory) == ["tx"]
    async with factory() as s:
        assert await s.get(ReferralReceipt, "tx") is None


def test_concurrent_workers_and_execute_are_serialized(tmp_path):
    async def go():
        engine, factory = await setup(f"sqlite+aiosqlite:///{tmp_path / 'concurrent.db'}")
        try:
            async with factory() as s:
                s.add(purchase())
                await s.commit()
            async def run():
                async with factory() as s:
                    await reward(s, "tx")
                    await s.commit()
            await asyncio.gather(run(), run())
            async with factory() as s:
                assert (await s.get(User, 1)).bonus_credits == 30
                s.add(purchase("old"))
                await s.commit()
                snap = await preview(s)
                await s.commit()
            async def recover():
                async with factory() as s:
                    await execute(s, snap["id"])
                    await s.commit()
            await asyncio.gather(recover(), recover())
            async with factory() as s:
                assert (await s.get(User, 1)).bonus_credits == 63
        finally:
            await engine.dispose()
    asyncio.run(go())


@scenario
async def test_live_failure_rolls_back_receipt_and_balance_then_retries(factory):
    async with factory() as s:
        s.add(purchase())
        await s.commit()
    with patch("common_db.repo.giveaways.try_grant_invitee_ticket", new=AsyncMock(side_effect=RuntimeError("transient"))):
        assert await process_purchases(factory) == ["tx"]
    async with factory() as s:
        assert (await s.get(User, 1)).bonus_credits == 0
        assert (await s.get(Promo, 1)).days_purchased == 0
        assert await s.get(ReferralReceipt, "tx") is None
    assert await process_purchases(factory) == []
    async with factory() as s:
        assert (await s.get(User, 1)).bonus_credits == 30


@scenario
async def test_legacy_pending_credit_delivery_blocks_until_completed(factory):
    async with factory() as s:
        s.add_all([purchase(payment_method="BONUS_CREDITS", amount=0, delivery_status=0),
                   ReferralReceipt(transaction_id="tx", kind="legacy", points=0)])
        await s.commit()
        assert (await preview(s))["plan"]["issues"][0]["reason"] == "legacy_credit_delivery_pending"
        await s.commit()
        (await s.get(Transaction, "tx")).delivery_status = 1
        await s.commit()
    await process_purchases(factory)
    async with factory() as s:
        assert (await s.get(User, 1)).bonus_credits == 0
        assert (await preview(s))["plan"]["missing"] == 30

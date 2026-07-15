"""Tests for referral owner rewards in bonus points."""
from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.models import Promo, PromoRedemption, PromoSettings, User
from common_db.models.promos import PROMO_TYPE_REFERRAL
from common_db.repo import balance as repo_balance
from common_db.repo import referral_rewards as repo_referral


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:")


async def _setup(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _run(coro):
    return asyncio.run(coro)


def test_referral_owner_receives_points_on_purchase() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(PromoSettings(id=1, default_credit_grant=100, points_reward_per_30=30, reward_cap_points=1800))
                session.add(User(id=1, tg_id=100, username="owner"))
                session.add(User(id=2, tg_id=200, username="buyer"))
                session.add(Promo(id=1, tg_id=100, promo_code="REF100", promo_type=PROMO_TYPE_REFERRAL))
                session.add(PromoRedemption(id=1, tg_id=200, promo_code="REF100", promo_type=PROMO_TYPE_REFERRAL, created_at="2026-01-01"))
                await session.commit()

            async with Session() as session:
                info = await repo_referral.record_purchase_and_compute_reward(session, 200, 30)
                await session.commit()
                assert info is not None
                assert info.reward_points == 30
                assert info.points_rewarded_after == 30
                assert await repo_balance.get_balance(session, 1) == 30

            async with Session() as session:
                info2 = await repo_referral.record_purchase_and_compute_reward(session, 200, 30)
                await session.commit()
                assert info2 is not None
                assert info2.reward_points == 30
                assert await repo_balance.get_balance(session, 1) == 60
        finally:
            await engine.dispose()

    _run(go())


def test_referral_reward_respects_cap() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(PromoSettings(id=1, default_credit_grant=100, points_reward_per_30=100, reward_cap_points=150))
                session.add(User(id=1, tg_id=100, username="owner"))
                session.add(User(id=2, tg_id=200, username="buyer"))
                session.add(Promo(id=1, tg_id=100, promo_code="REF100", promo_type=PROMO_TYPE_REFERRAL, points_rewarded=100))
                session.add(PromoRedemption(id=1, tg_id=200, promo_code="REF100", promo_type=PROMO_TYPE_REFERRAL, created_at="2026-01-01"))
                await session.commit()

            async with Session() as session:
                promo = await session.get(Promo, 1)
                promo.days_purchased = 60
                await session.commit()

            async with Session() as session:
                info = await repo_referral.record_purchase_and_compute_reward(session, 200, 30)
                await session.commit()
                assert info is not None
                assert info.reward_points == 50
                assert info.points_rewarded_after == 150
                assert await repo_balance.get_balance(session, 1) == 50
        finally:
            await engine.dispose()

    _run(go())

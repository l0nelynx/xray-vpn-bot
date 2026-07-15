"""Tests for common_db.repo.promos — credit-based promo/referral logic."""
from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.models import Promo, PromoSettings, Transaction, User
from common_db.models.promos import PROMO_TYPE_PROMOTIONAL, PROMO_TYPE_REFERRAL
from common_db.repo import balance as repo_balance
from common_db.repo import promos as repo_promos
from common_db.repo import system as repo_system


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:")


async def _setup(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _run(coro):
    return asyncio.run(coro)


def test_redeem_credits_balance_immediately() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(PromoSettings(id=1, default_credit_grant=10))
                session.add(Promo(id=1, tg_id=2002, promo_code="BOB",
                                  promo_type=PROMO_TYPE_REFERRAL, credit_grant=15))
                session.add(User(id=5, tg_id=1001, username="u"))
                await session.commit()
                res = await repo_promos.redeem_promo(session, 1001, "BOB")
                await session.commit()
                assert res.ok and res.credit_grant == 15 and res.new_balance == 15
            async with Session() as session:
                assert await repo_balance.get_balance(session, 5) == 15
        finally:
            await engine.dispose()

    _run(go())


def test_redeem_falls_back_to_settings_default_credit_grant() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(PromoSettings(id=1, default_credit_grant=12))
                session.add(Promo(id=1, tg_id=2002, promo_code="BOB",
                                  promo_type=PROMO_TYPE_REFERRAL, credit_grant=None))
                session.add(User(id=5, tg_id=1001, username="u"))
                await session.commit()
                res = await repo_promos.redeem_promo(session, 1001, "BOB")
                await session.commit()
                assert res.ok and res.credit_grant == 12
        finally:
            await engine.dispose()

    _run(go())


def test_redeem_owner_zero_credit_grant() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(PromoSettings(id=1, default_credit_grant=50))
                session.add(Promo(id=1, tg_id=2002, promo_code="BOB",
                                  promo_type=PROMO_TYPE_PROMOTIONAL, credit_grant=0))
                session.add(User(id=5, tg_id=1001, username="u"))
                await session.commit()
                res = await repo_promos.redeem_promo(session, 1001, "BOB")
                await session.commit()
                assert res.ok and res.credit_grant == 0 and res.new_balance == 0
        finally:
            await engine.dispose()

    _run(go())


def test_promotional_reusable_different_codes() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(PromoSettings(id=1, default_credit_grant=5))
                session.add(Promo(id=1, tg_id=-1, promo_code="AAA",
                                  promo_type=PROMO_TYPE_PROMOTIONAL, credit_grant=5))
                session.add(Promo(id=2, tg_id=-2, promo_code="BBB",
                                  promo_type=PROMO_TYPE_PROMOTIONAL, credit_grant=3))
                session.add(User(id=5, tg_id=1001, username="u"))
                await session.commit()
                assert (await repo_promos.redeem_promo(session, 1001, "AAA")).ok
                await session.commit()
                assert (await repo_promos.redeem_promo(session, 1001, "BBB")).ok
                await session.commit()
                assert await repo_balance.get_balance(session, 5) == 8
                r = await repo_promos.can_redeem(session, 1001, "AAA")
                assert not r.ok and r.reason == repo_promos.REASON_ALREADY_USED
        finally:
            await engine.dispose()

    _run(go())


def test_referral_only_one_ever() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(PromoSettings(id=1, default_credit_grant=10))
                session.add(Promo(id=1, tg_id=-1, promo_code="REF1",
                                  promo_type=PROMO_TYPE_REFERRAL))
                session.add(Promo(id=2, tg_id=-2, promo_code="REF2",
                                  promo_type=PROMO_TYPE_REFERRAL))
                session.add(User(id=5, tg_id=1001, username="u"))
                await session.commit()
                assert (await repo_promos.redeem_promo(session, 1001, "REF1")).ok
                await session.commit()
                r = await repo_promos.can_redeem(session, 1001, "REF2")
                assert not r.ok and r.reason == repo_promos.REASON_REFERRAL_ONLY_ONE
        finally:
            await engine.dispose()

    _run(go())


def test_redeem_seeds_settings_on_fresh_db() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(Promo(id=1, tg_id=2002, promo_code="BOB",
                                  promo_type=PROMO_TYPE_PROMOTIONAL))
                session.add(User(id=5, tg_id=1001, username="u"))
                await session.commit()
                res = await repo_promos.redeem_promo(session, 1001, "BOB")
                await session.commit()
                assert res.ok
                assert res.credit_grant == repo_system.DEFAULT_CREDIT_GRANT
        finally:
            await engine.dispose()

    _run(go())

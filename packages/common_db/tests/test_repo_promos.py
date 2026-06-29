"""Tests for common_db.repo.promos — redemption-based promo/referral logic.

The system models codes in ``promos`` and redemptions in
``promo_redemptions``. The interesting behavior:
- can_redeem enforces: invalid / own-code / already-used / one-active /
  referral-only-one / referral-only-new.
- redeem_promo snapshots the effective discount (owner override → settings
  default) onto the redemption row.
- get_effective_discount reads the active redemption's snapshot.
- consume_active_redemption flips active → consumed.
"""
from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401  -- register on Base.metadata
from common_db.models import Promo, PromoRedemption, PromoSettings, Transaction, User
from common_db.models.promos import PROMO_TYPE_PROMOTIONAL, PROMO_TYPE_REFERRAL
from common_db.repo import promos as repo_promos
from common_db.repo import system as repo_system


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:")


async def _setup(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _run(coro):
    return asyncio.run(coro)


# --- catalog lookups ------------------------------------------------------


def test_get_promo_by_code_empty_returns_none() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                assert await repo_promos.get_promo_by_code(session, "") is None
        finally:
            await engine.dispose()

    _run(go())


def test_get_or_create_referral_code_creates_and_is_stable() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                code1 = await repo_promos.get_or_create_referral_code(session, 1001)
                await session.commit()
                assert code1 and len(code1) == 8
                promo = await repo_promos.get_promo_by_tg_id(session, 1001)
                assert promo is not None
                assert promo.promo_type == PROMO_TYPE_REFERRAL
            async with Session() as session:
                code2 = await repo_promos.get_or_create_referral_code(session, 1001)
                assert code2 == code1  # stable, no duplicate row
        finally:
            await engine.dispose()

    _run(go())


# --- can_redeem: rejection paths ------------------------------------------


def test_can_redeem_invalid_code() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                r = await repo_promos.can_redeem(session, 1001, "NOPE")
                assert not r.ok and r.reason == repo_promos.REASON_INVALID
        finally:
            await engine.dispose()

    _run(go())


def test_can_redeem_own_code() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(Promo(id=1, tg_id=1001, promo_code="ALICE"))
                await session.commit()
                r = await repo_promos.can_redeem(session, 1001, "ALICE")
                assert not r.ok and r.reason == repo_promos.REASON_OWN_CODE
        finally:
            await engine.dispose()

    _run(go())


def test_can_redeem_referral_blocked_for_user_with_transactions() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(Promo(id=1, tg_id=2002, promo_code="BOB",
                                  promo_type=PROMO_TYPE_REFERRAL))
                session.add(User(id=5, tg_id=1001, username="u"))
                await session.flush()
                session.add(Transaction(
                    transaction_id="t1", vless_uuid="x", order_status="delivered",
                    delivery_status=1, days_ordered=30, user_id=5,
                ))
                await session.commit()
                r = await repo_promos.can_redeem(session, 1001, "BOB")
                assert not r.ok and r.reason == repo_promos.REASON_REFERRAL_NOT_NEW
        finally:
            await engine.dispose()

    _run(go())


def test_can_redeem_promotional_allowed_for_user_with_transactions() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(PromoSettings(id=1, default_discount_percent=20))
                session.add(Promo(id=1, tg_id=-1, promo_code="SUMMER",
                                  promo_type=PROMO_TYPE_PROMOTIONAL,
                                  discount_percent=30))
                session.add(User(id=5, tg_id=1001, username="u"))
                await session.flush()
                session.add(Transaction(
                    transaction_id="t1", vless_uuid="x", order_status="delivered",
                    delivery_status=1, days_ordered=30, user_id=5,
                ))
                await session.commit()
                r = await repo_promos.can_redeem(session, 1001, "SUMMER")
                assert r.ok and r.discount_percent == 30
        finally:
            await engine.dispose()

    _run(go())


# --- redeem_promo + effective discount ------------------------------------


def test_redeem_snapshots_owner_discount_and_effective_reads_it() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(PromoSettings(id=1, default_discount_percent=5))
                session.add(Promo(id=1, tg_id=2002, promo_code="BOB",
                                  promo_type=PROMO_TYPE_REFERRAL,
                                  discount_percent=33))
                await session.commit()
                res = await repo_promos.redeem_promo(session, 1001, "BOB")
                await session.commit()
                assert res.ok and res.discount_percent == 33
            async with Session() as session:
                ed = await repo_promos.get_effective_discount(session, 1001)
                assert ed is not None
                assert ed.promo_code == "BOB" and ed.discount_percent == 33
        finally:
            await engine.dispose()

    _run(go())


def test_redeem_falls_back_to_settings_default_when_owner_null() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(PromoSettings(id=1, default_discount_percent=25))
                session.add(Promo(id=1, tg_id=2002, promo_code="BOB",
                                  promo_type=PROMO_TYPE_REFERRAL,
                                  discount_percent=None))
                await session.commit()
                res = await repo_promos.redeem_promo(session, 1001, "BOB")
                await session.commit()
                assert res.ok and res.discount_percent == 25
        finally:
            await engine.dispose()

    _run(go())


def test_redeem_owner_zero_is_not_treated_as_null() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(PromoSettings(id=1, default_discount_percent=50))
                session.add(Promo(id=1, tg_id=2002, promo_code="BOB",
                                  promo_type=PROMO_TYPE_PROMOTIONAL,
                                  discount_percent=0))
                await session.commit()
                res = await repo_promos.redeem_promo(session, 1001, "BOB")
                await session.commit()
                assert res.ok and res.discount_percent == 0
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
                # No PromoSettings row — fresh DB.
                session.add(Promo(id=1, tg_id=2002, promo_code="BOB",
                                  promo_type=PROMO_TYPE_PROMOTIONAL,
                                  discount_percent=None))
                await session.commit()
                res = await repo_promos.redeem_promo(session, 1001, "BOB")
                await session.commit()
                assert res.ok
                assert res.discount_percent == repo_system.DEFAULT_PROMO_DISCOUNT_PERCENT
                assert res.discount_percent == 20
        finally:
            await engine.dispose()

    _run(go())


# --- one-active / already-used / referral-only-one rules ------------------


def test_one_active_redemption_blocks_second() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(PromoSettings(id=1, default_discount_percent=20))
                session.add(Promo(id=1, tg_id=-1, promo_code="AAA",
                                  promo_type=PROMO_TYPE_PROMOTIONAL))
                session.add(Promo(id=2, tg_id=-2, promo_code="BBB",
                                  promo_type=PROMO_TYPE_PROMOTIONAL))
                await session.commit()
                assert (await repo_promos.redeem_promo(session, 1001, "AAA")).ok
                await session.commit()
                r = await repo_promos.can_redeem(session, 1001, "BBB")
                assert not r.ok and r.reason == repo_promos.REASON_ACTIVE_EXISTS
        finally:
            await engine.dispose()

    _run(go())


def test_promotional_reusable_after_consume_but_not_same_code() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(PromoSettings(id=1, default_discount_percent=20))
                session.add(Promo(id=1, tg_id=-1, promo_code="AAA",
                                  promo_type=PROMO_TYPE_PROMOTIONAL))
                session.add(Promo(id=2, tg_id=-2, promo_code="BBB",
                                  promo_type=PROMO_TYPE_PROMOTIONAL))
                await session.commit()
                assert (await repo_promos.redeem_promo(session, 1001, "AAA")).ok
                await session.commit()
                # consume the active one
                consumed = await repo_promos.consume_active_redemption(session, 1001)
                await session.commit()
                assert consumed is not None and consumed.promo_code == "AAA"
                # now a different promotional code is allowed
                assert (await repo_promos.redeem_promo(session, 1001, "BBB")).ok
                await session.commit()
                # but re-redeeming AAA is rejected (already used)
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
                session.add(PromoSettings(id=1, default_discount_percent=20))
                session.add(Promo(id=1, tg_id=-1, promo_code="REF1",
                                  promo_type=PROMO_TYPE_REFERRAL))
                session.add(Promo(id=2, tg_id=-2, promo_code="REF2",
                                  promo_type=PROMO_TYPE_REFERRAL))
                await session.commit()
                assert (await repo_promos.redeem_promo(session, 1001, "REF1")).ok
                await session.commit()
                await repo_promos.consume_active_redemption(session, 1001)
                await session.commit()
                # second referral code rejected even after the first consumed
                r = await repo_promos.can_redeem(session, 1001, "REF2")
                assert not r.ok and r.reason == repo_promos.REASON_REFERRAL_ONLY_ONE
        finally:
            await engine.dispose()

    _run(go())


def test_effective_discount_none_without_active() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                ed = await repo_promos.get_effective_discount(session, 1001)
                assert ed is None
        finally:
            await engine.dispose()

    _run(go())

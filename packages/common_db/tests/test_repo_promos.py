"""Tests for common_db.repo.promos — lookups + effective-discount cascade.

The cascade is the interesting bit: owner's discount_percent (if set) wins,
otherwise we fall back to PromoSettings.default_discount_percent, which
auto-seeds on a fresh DB (so we never silently return 0% on prod).
"""
from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401  -- register on Base.metadata
from common_db.models import Promo, PromoSettings
from common_db.repo import promos as repo_promos
from common_db.repo import system as repo_system


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:")


async def _setup(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _run(coro):
    return asyncio.run(coro)


# --- get_promo_by_tg_id ---------------------------------------------------


def test_get_promo_by_tg_id_returns_promo() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(Promo(id=1, tg_id=1001, promo_code="ALICE"))
                await session.commit()
            async with Session() as session:
                p = await repo_promos.get_promo_by_tg_id(session, 1001)
                assert p is not None and p.promo_code == "ALICE"
        finally:
            await engine.dispose()

    _run(go())


def test_get_promo_by_tg_id_returns_none_for_unknown() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                p = await repo_promos.get_promo_by_tg_id(session, 9999)
                assert p is None
        finally:
            await engine.dispose()

    _run(go())


# --- get_promo_by_code ----------------------------------------------------


def test_get_promo_by_code_returns_promo() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(Promo(id=1, tg_id=1001, promo_code="ALICE"))
                await session.commit()
            async with Session() as session:
                p = await repo_promos.get_promo_by_code(session, "ALICE")
                assert p is not None and p.tg_id == 1001
        finally:
            await engine.dispose()

    _run(go())


def test_get_promo_by_code_empty_returns_none() -> None:
    """Empty string must short-circuit — otherwise it would match any row
    where promo_code happens to be '' (and worse, leak intent)."""

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


# --- get_effective_discount: None paths -----------------------------------


def test_effective_discount_none_when_no_promo() -> None:
    """User has no promo row at all → not eligible."""

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


def test_effective_discount_none_when_promo_has_no_used_promo() -> None:
    """User has their own code but never activated anyone else's → no discount."""

    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(
                    Promo(id=1, tg_id=1001, promo_code="ALICE", used_promo=None)
                )
                await session.commit()
            async with Session() as session:
                ed = await repo_promos.get_effective_discount(session, 1001)
                assert ed is None
        finally:
            await engine.dispose()

    _run(go())


def test_effective_discount_none_when_consumed() -> None:
    """Once the activated promo has been spent on a purchase, the discount
    is no longer available — must return None."""

    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(
                    Promo(id=1, tg_id=2002, promo_code="BOB", discount_percent=15)
                )
                session.add(
                    Promo(
                        id=2,
                        tg_id=1001,
                        promo_code="ALICE",
                        used_promo="BOB",
                        used_promo_consumed=True,
                    )
                )
                await session.commit()
            async with Session() as session:
                ed = await repo_promos.get_effective_discount(session, 1001)
                assert ed is None
        finally:
            await engine.dispose()

    _run(go())


# --- get_effective_discount: cascade --------------------------------------


def test_effective_discount_uses_owner_percent_when_set() -> None:
    """When the owner of the activated promo has a non-NULL
    discount_percent, that takes precedence over PromoSettings."""

    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                # PromoSettings says 5% default — should be ignored.
                session.add(PromoSettings(id=1, default_discount_percent=5))
                session.add(
                    Promo(id=1, tg_id=2002, promo_code="BOB", discount_percent=33)
                )
                session.add(
                    Promo(
                        id=2,
                        tg_id=1001,
                        promo_code="ALICE",
                        used_promo="BOB",
                        used_promo_consumed=False,
                    )
                )
                await session.commit()
            async with Session() as session:
                ed = await repo_promos.get_effective_discount(session, 1001)
                assert ed is not None
                assert ed.promo_code == "BOB"
                assert ed.discount_percent == 33
        finally:
            await engine.dispose()

    _run(go())


def test_effective_discount_falls_back_to_promo_settings() -> None:
    """When the owner's discount_percent is NULL, fall back to the
    configured PromoSettings.default_discount_percent."""

    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(PromoSettings(id=1, default_discount_percent=25))
                session.add(
                    Promo(id=1, tg_id=2002, promo_code="BOB", discount_percent=None)
                )
                session.add(
                    Promo(
                        id=2,
                        tg_id=1001,
                        promo_code="ALICE",
                        used_promo="BOB",
                        used_promo_consumed=False,
                    )
                )
                await session.commit()
            async with Session() as session:
                ed = await repo_promos.get_effective_discount(session, 1001)
                assert ed is not None
                assert ed.promo_code == "BOB"
                assert ed.discount_percent == 25
        finally:
            await engine.dispose()

    _run(go())


def test_effective_discount_seeds_promo_settings_on_fresh_db() -> None:
    """The bug-fix case: miniapp/payments used to fall back to plain None
    if PromoSettings was missing, which would silently apply 0% discount.
    We now auto-seed PromoSettings via common_db.repo.system and return
    the DEFAULT_PROMO_DISCOUNT_PERCENT (20)."""

    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                # Note: NO PromoSettings row inserted — simulates a fresh DB.
                session.add(
                    Promo(id=1, tg_id=2002, promo_code="BOB", discount_percent=None)
                )
                session.add(
                    Promo(
                        id=2,
                        tg_id=1001,
                        promo_code="ALICE",
                        used_promo="BOB",
                        used_promo_consumed=False,
                    )
                )
                await session.commit()
            async with Session() as session:
                ed = await repo_promos.get_effective_discount(session, 1001)
                assert ed is not None
                assert ed.promo_code == "BOB"
                assert ed.discount_percent == repo_system.DEFAULT_PROMO_DISCOUNT_PERCENT
                assert ed.discount_percent == 20  # belt-and-braces against future change
        finally:
            await engine.dispose()

    _run(go())


def test_effective_discount_owner_zero_is_not_treated_as_null() -> None:
    """0 is a *legitimate* override that explicitly disables the discount.
    It must NOT trigger the PromoSettings fallback — we only fall back
    when the column is literally NULL."""

    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(PromoSettings(id=1, default_discount_percent=50))
                session.add(
                    Promo(id=1, tg_id=2002, promo_code="BOB", discount_percent=0)
                )
                session.add(
                    Promo(
                        id=2,
                        tg_id=1001,
                        promo_code="ALICE",
                        used_promo="BOB",
                        used_promo_consumed=False,
                    )
                )
                await session.commit()
            async with Session() as session:
                ed = await repo_promos.get_effective_discount(session, 1001)
                assert ed is not None
                assert ed.discount_percent == 0, (
                    "explicit zero override must win over PromoSettings"
                )
        finally:
            await engine.dispose()

    _run(go())


def test_effective_discount_when_owner_row_missing() -> None:
    """User activated a promo code that no longer has an owner row (e.g.
    owner deleted their account). The cascade should fall through to
    PromoSettings rather than crash or return None."""

    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(PromoSettings(id=1, default_discount_percent=10))
                session.add(
                    Promo(
                        id=2,
                        tg_id=1001,
                        promo_code="ALICE",
                        used_promo="ZOMBIE",  # no Promo row with this code
                        used_promo_consumed=False,
                    )
                )
                await session.commit()
            async with Session() as session:
                ed = await repo_promos.get_effective_discount(session, 1001)
                assert ed is not None
                assert ed.promo_code == "ZOMBIE"
                assert ed.discount_percent == 10
        finally:
            await engine.dispose()

    _run(go())

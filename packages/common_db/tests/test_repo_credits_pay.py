"""Tests for common_db.repo.credits_pay (RUB points debit)."""
from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.models import User
from common_db.repo import balance as repo_balance
from common_db.repo import credits_pay as repo_credits_pay


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:")


async def _setup(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _run(coro):
    return asyncio.run(coro)


def test_purchase_with_credits_debits_points() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(User(id=1, tg_id=100, username="u", bonus_credits=500))
                await session.commit()
            async with Session() as session:
                purchase = await repo_credits_pay.purchase_with_credits(
                    session,
                    user_id=1,
                    username="u",
                    tg_id=100,
                    points_cost=450,
                    days=30,
                    tariff_slug="pro",
                )
                await session.commit()
                assert purchase is not None
                assert purchase.points_spent == 450
                assert purchase.credits_spent == 450
                assert purchase.balance_after == 50
                assert purchase.days == 30
                assert purchase.tariff_slug == "pro"
            async with Session() as session:
                assert await repo_balance.get_balance(session, 1) == 50
        finally:
            await engine.dispose()

    _run(go())


def test_purchase_with_credits_insufficient_returns_none() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(User(id=1, tg_id=100, username="u", bonus_credits=100))
                await session.commit()
            async with Session() as session:
                purchase = await repo_credits_pay.purchase_with_credits(
                    session,
                    user_id=1,
                    username="u",
                    tg_id=100,
                    points_cost=450,
                    days=30,
                    tariff_slug="pro",
                )
                assert purchase is None
                assert await repo_balance.get_balance(session, 1) == 100
        finally:
            await engine.dispose()

    _run(go())

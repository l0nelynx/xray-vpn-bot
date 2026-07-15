"""Tests for common_db.repo.balance."""
from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.models import User
from common_db.repo import balance as repo_balance


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:")


async def _setup(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _run(coro):
    return asyncio.run(coro)


def test_credit_and_debit() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(User(id=1, tg_id=100, username="u"))
                await session.commit()
            async with Session() as session:
                bal = await repo_balance.credit(session, 1, 10, "promo", "CODE")
                await session.commit()
                assert bal == 10
            async with Session() as session:
                assert await repo_balance.get_balance(session, 1) == 10
                ok = await repo_balance.debit_if_sufficient(session, 1, 7, "payment", "tx1")
                await session.commit()
                assert ok
                assert await repo_balance.get_balance(session, 1) == 3
            async with Session() as session:
                ok = await repo_balance.debit_if_sufficient(session, 1, 5)
                assert not ok
        finally:
            await engine.dispose()

    _run(go())


def test_discount_percent_to_credits() -> None:
    assert repo_balance.discount_percent_to_credits(20) == 10
    assert repo_balance.discount_percent_to_credits(15) == 8
    assert repo_balance.discount_percent_to_credits(10) == 5
    assert repo_balance.discount_percent_to_credits(0) == 0

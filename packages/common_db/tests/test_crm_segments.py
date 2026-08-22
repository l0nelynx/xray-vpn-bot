"""Tests for CRM DB segmentation helpers."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.models import Transaction, User
from common_db.repo import crm_segments as seg_repo


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:")


async def _setup(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _run(coro):
    return asyncio.run(coro)


def _iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds")


def test_users_with_unpaid_invoices() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            now = datetime.now()
            async with Session() as session:
                u1 = User(id=1, tg_id=100, username="paid_user", api_provider="remnawave", rw_id=11, vless_uuid="uuid-1")
                u2 = User(id=2, tg_id=200, username="unpaid_user", api_provider="remnawave", rw_id=22, vless_uuid="uuid-2")
                u3 = User(id=3, tg_id=None, username="android", api_provider="remnawave")
                session.add_all([u1, u2, u3])

                session.add(
                    Transaction(
                        transaction_id="tx-old",
                        vless_uuid="u-old",
                        order_status="created",
                        delivery_status=0,
                        days_ordered=30,
                        user_id=2,
                        created_at=_iso(now - timedelta(hours=72)),
                    )
                )
                session.add(
                    Transaction(
                        transaction_id="tx-fresh",
                        vless_uuid="u-fresh",
                        order_status="created",
                        delivery_status=0,
                        days_ordered=30,
                        user_id=2,
                        created_at=_iso(now - timedelta(hours=2)),
                    )
                )
                session.add(
                    Transaction(
                        transaction_id="tx-delivered",
                        vless_uuid="u-del",
                        order_status="delivered",
                        delivery_status=1,
                        days_ordered=30,
                        user_id=1,
                        created_at=_iso(now - timedelta(hours=1)),
                        expire_date=_iso(now + timedelta(days=30)),
                    )
                )
                await session.flush()

                users = await seg_repo.users_with_unpaid_invoices(
                    session, max_age_hours=48
                )
                tg_ids = {u.tg_id for u in users}
                assert tg_ids == {200}

                broadcast = await seg_repo.get_remnawave_broadcast_users(session)
                assert {u.tg_id for u in broadcast} == {100, 200}
        finally:
            await engine.dispose()

    _run(go())


def test_get_broadcast_eligible_users() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add_all([
                    User(id=1, tg_id=100, username="ok", is_banned=False),
                    User(id=2, tg_id=200, username="banned", is_banned=True),
                    User(id=3, tg_id=None, username="android", is_banned=False),
                    User(id=4, tg_id=400, username="also_ok", is_banned=False),
                ])
                await session.flush()

                users = await seg_repo.get_broadcast_eligible_users(session)
                tg_ids = {u.tg_id for u in users}
                assert tg_ids == {100, 400}
        finally:
            await engine.dispose()

    _run(go())

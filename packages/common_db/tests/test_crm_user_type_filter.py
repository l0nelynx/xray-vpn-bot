"""Tests for CRM user type filter (Free vs Paid/VIP)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.models import Transaction, User
from common_db.repo import crm_segments as seg_repo


def _run(coro):
    return asyncio.run(coro)


def test_filter_users_by_type_free_and_paid_vip() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add_all([
                    User(id=1, tg_id=101, username="free_user", vip=0),
                    User(id=2, tg_id=202, username="vip_user", vip=1),
                    User(id=3, tg_id=303, username="paid_user", vip=0),
                ])
                expire = (datetime.now() + timedelta(days=30)).isoformat(timespec="seconds")
                session.add(
                    Transaction(
                        transaction_id="tx1",
                        user_id=3,
                        vless_uuid="uuid-paid",
                        order_status="delivered",
                        delivery_status=1,
                        days_ordered=30,
                        expire_date=expire,
                        created_at=datetime.now().isoformat(timespec="seconds"),
                    )
                )
                await session.flush()

                users = list(await session.scalars(select(User)))

                free = await seg_repo.filter_users_by_type(
                    session, users, seg_repo.USER_TYPE_FREE
                )
                paid_vip = await seg_repo.filter_users_by_type(
                    session, users, seg_repo.USER_TYPE_PAID_VIP
                )

                assert {u.username for u in free} == {"free_user"}
                assert {u.username for u in paid_vip} == {"vip_user", "paid_user"}
        finally:
            await engine.dispose()

    _run(go())

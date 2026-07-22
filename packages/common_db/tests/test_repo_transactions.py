"""Tests for transaction repository helpers."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.models import Transaction, User
from common_db.repo import transactions as transactions_repo


def _run(coro):
    return asyncio.run(coro)


def test_cleanup_stale_transactions_deletes_old_created() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            Session = async_sessionmaker(engine, expire_on_commit=False)
            old_ts = (datetime.now() - timedelta(days=10)).isoformat(timespec="seconds")
            fresh_ts = datetime.now().isoformat(timespec="seconds")

            async with Session() as session:
                session.add(User(id=1, tg_id=101, username="u1", is_banned=False))
                session.add_all([
                    Transaction(
                        transaction_id="old-created",
                        vless_uuid="u1",
                        order_status="created",
                        delivery_status=0,
                        days_ordered=30,
                        user_id=1,
                        created_at=old_ts,
                    ),
                    Transaction(
                        transaction_id="fresh-created",
                        vless_uuid="u1",
                        order_status="created",
                        delivery_status=0,
                        days_ordered=30,
                        user_id=1,
                        created_at=fresh_ts,
                    ),
                    Transaction(
                        transaction_id="old-confirmed",
                        vless_uuid="u1",
                        order_status="confirmed",
                        delivery_status=1,
                        days_ordered=30,
                        user_id=1,
                        created_at=old_ts,
                    ),
                ])
                await session.commit()

                deleted = await transactions_repo.cleanup_stale_transactions(
                    session, hours=168
                )
                await session.commit()
                assert deleted == 1

                remaining = await session.scalars(select(Transaction))
                ids = {t.transaction_id for t in remaining.all()}
                assert ids == {"fresh-created", "old-confirmed"}
        finally:
            await engine.dispose()

    _run(go())

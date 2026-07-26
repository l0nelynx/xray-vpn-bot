"""Tests for account-managed Remnawave subscriptions."""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.models import User
from common_db.repo import subscriptions


def _run(coro):
    return asyncio.run(coro)


def test_attach_first_subscription_becomes_primary_and_updates_legacy_pointer() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(User(id=1, email="one@example.com"))
                await session.flush()
                linked = await subscriptions.attach(
                    session, user_id=1, rw_id=101, source="marketplace"
                )
                await session.commit()
                assert linked.is_primary is True
                assert (await session.get(User, 1)).rw_id == 101
        finally:
            await engine.dispose()

    _run(go())


def test_subscription_cannot_be_silently_moved_between_accounts() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add_all([User(id=1), User(id=2)])
                await session.flush()
                await subscriptions.attach(
                    session, user_id=1, rw_id=202, source="marketplace"
                )
                with pytest.raises(ValueError, match="subscription_already_linked"):
                    await subscriptions.attach(
                        session, user_id=2, rw_id=202, source="subscription_page"
                    )
        finally:
            await engine.dispose()

    _run(go())


def test_set_primary_keeps_all_subscriptions_and_moves_legacy_pointer() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(User(id=1))
                await session.flush()
                first = await subscriptions.attach(
                    session, user_id=1, rw_id=301, source="legacy"
                )
                second = await subscriptions.attach(
                    session, user_id=1, rw_id=302, source="marketplace"
                )
                chosen = await subscriptions.set_primary(
                    session, user_id=1, subscription_id=second.id
                )
                await session.commit()

                rows = await subscriptions.list_for_user(session, 1)
                assert chosen is not None and chosen.rw_id == 302
                assert len(rows) == 2
                assert [row.rw_id for row in rows if row.is_primary] == [302]
                assert (await session.get(User, 1)).rw_id == 302
                assert first.id != second.id
        finally:
            await engine.dispose()

    _run(go())


def test_primary_must_change_before_detach_and_last_detach_clears_legacy_ids() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(User(id=1, vless_uuid="legacy-uuid"))
                await session.flush()
                first = await subscriptions.attach(
                    session, user_id=1, rw_id=401, source="legacy"
                )
                second = await subscriptions.attach(
                    session, user_id=1, rw_id=402, source="marketplace"
                )

                with pytest.raises(ValueError, match="primary_change_required"):
                    await subscriptions.detach(
                        session, user_id=1, subscription_id=first.id
                    )

                await subscriptions.set_primary(
                    session, user_id=1, subscription_id=second.id
                )
                await subscriptions.detach(
                    session, user_id=1, subscription_id=first.id
                )
                await subscriptions.detach(
                    session, user_id=1, subscription_id=second.id
                )
                await session.commit()

                user = await session.get(User, 1)
                assert user is not None
                assert user.rw_id is None
                assert user.vless_uuid is None
                assert await subscriptions.list_for_user(session, 1) == []
        finally:
            await engine.dispose()

    _run(go())


def test_rename_label_can_also_clear_it() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(User(id=1))
                await session.flush()
                linked = await subscriptions.attach(
                    session,
                    user_id=1,
                    rw_id=501,
                    source="dashboard",
                    label="Office",
                )
                renamed = await subscriptions.rename_label(
                    session,
                    user_id=1,
                    subscription_id=linked.id,
                    label=None,
                )
                assert renamed is not None and renamed.label is None
        finally:
            await engine.dispose()

    _run(go())

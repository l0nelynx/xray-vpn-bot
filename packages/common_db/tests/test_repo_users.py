"""Tests for common_db.repo.users — lookups + is-paid predicates."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.models import Transaction, User
from common_db.repo import users as repo_users


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:")


async def _setup(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _run(coro):
    return asyncio.run(coro)


def _iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds")


# --- fixtures (inline; pytest fixtures + asyncio.run don't mix cleanly) ---


async def _seed_users(session, *triples: tuple[int, int, str]) -> dict[int, User]:
    """Create users from (id, tg_id, username) triples. Return id->User."""
    users: dict[int, User] = {}
    for uid, tg_id, username in triples:
        u = User(id=uid, tg_id=tg_id, username=username)
        session.add(u)
        users[uid] = u
    await session.flush()
    return users


async def _seed_tx(
    session,
    *,
    transaction_id: str,
    user_id: int,
    status: str,
    expire: datetime | None,
    days_ordered: int = 30,
    amount: float | None = 100.0,
) -> Transaction:
    tx = Transaction(
        transaction_id=transaction_id,
        vless_uuid="uuid-" + transaction_id,
        order_status=status,
        delivery_status=1,
        days_ordered=days_ordered,
        expire_date=_iso(expire) if expire else None,
        user_id=user_id,
        amount=amount,
    )
    session.add(tx)
    await session.flush()
    return tx


# --- get_user_by_tg_id ----------------------------------------------------


def test_get_user_by_tg_id_returns_user() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                await _seed_users(session, (1, 1001, "alice"), (2, 1002, "bob"))
                await session.commit()
            async with Session() as session:
                u = await repo_users.get_user_by_tg_id(session, 1002)
                assert u is not None and u.username == "bob"
        finally:
            await engine.dispose()

    _run(go())


def test_get_user_by_tg_id_returns_none_for_unknown() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                u = await repo_users.get_user_by_tg_id(session, 9999)
                assert u is None
        finally:
            await engine.dispose()

    _run(go())


# --- get_user_by_id / get_user_by_email -----------------------------------


def test_get_user_by_id_and_email() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                u = User(id=1, tg_id=1001, username="alice", email="a@x.io")
                session.add(u)
                await session.commit()
            async with Session() as session:
                by_id = await repo_users.get_user_by_id(session, 1)
                by_email = await repo_users.get_user_by_email(session, "a@x.io")
                assert by_id is not None and by_id.username == "alice"
                assert by_email is not None and by_email.id == 1
                # empty/None email → None, not an exception, not the first user
                assert await repo_users.get_user_by_email(session, "") is None
        finally:
            await engine.dispose()

    _run(go())


# --- is_paid predicates ----------------------------------------------------


def test_user_has_active_paid_transaction_true_for_confirmed_unexpired() -> None:
    async def go() -> None:
        now = datetime(2026, 5, 18, 12, 0, 0)
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                await _seed_users(session, (1, 1001, "alice"))
                await _seed_tx(
                    session,
                    transaction_id="t1",
                    user_id=1,
                    status="confirmed",
                    expire=now + timedelta(days=30),
                )
                await session.commit()
            async with Session() as session:
                assert await repo_users.user_has_active_paid_transaction(
                    session, 1001, now=now
                ) is True
        finally:
            await engine.dispose()

    _run(go())


def test_user_has_active_paid_transaction_false_for_expired() -> None:
    async def go() -> None:
        now = datetime(2026, 5, 18, 12, 0, 0)
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                await _seed_users(session, (1, 1001, "alice"))
                await _seed_tx(
                    session,
                    transaction_id="t1",
                    user_id=1,
                    status="delivered",
                    expire=now - timedelta(days=1),  # expired yesterday
                )
                await session.commit()
            async with Session() as session:
                assert await repo_users.user_has_active_paid_transaction(
                    session, 1001, now=now
                ) is False
        finally:
            await engine.dispose()

    _run(go())


def test_user_has_active_paid_transaction_false_for_created_status() -> None:
    async def go() -> None:
        now = datetime(2026, 5, 18, 12, 0, 0)
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                await _seed_users(session, (1, 1001, "alice"))
                # 'created' status = invoice issued but not paid yet
                await _seed_tx(
                    session,
                    transaction_id="t1",
                    user_id=1,
                    status="created",
                    expire=now + timedelta(days=30),
                )
                await session.commit()
            async with Session() as session:
                assert await repo_users.user_has_active_paid_transaction(
                    session, 1001, now=now
                ) is False
        finally:
            await engine.dispose()

    _run(go())


def test_count_paid_users_distinct() -> None:
    async def go() -> None:
        now = datetime(2026, 5, 18, 12, 0, 0)
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                await _seed_users(
                    session,
                    (1, 1001, "alice"),
                    (2, 1002, "bob"),
                    (3, 1003, "carol"),
                    (4, 1004, "dave"),
                )
                # alice: 2 active paid txs → counted once
                await _seed_tx(session, transaction_id="a1", user_id=1, status="confirmed",
                               expire=now + timedelta(days=30))
                await _seed_tx(session, transaction_id="a2", user_id=1, status="delivered",
                               expire=now + timedelta(days=60))
                # bob: 1 active paid tx
                await _seed_tx(session, transaction_id="b1", user_id=2, status="delivered",
                               expire=now + timedelta(days=10))
                # carol: expired → not counted
                await _seed_tx(session, transaction_id="c1", user_id=3, status="delivered",
                               expire=now - timedelta(days=1))
                # dave: created (unpaid) → not counted
                await _seed_tx(session, transaction_id="d1", user_id=4, status="created",
                               expire=now + timedelta(days=30))
                await session.commit()
            async with Session() as session:
                n = await repo_users.count_paid_users(session, now=now)
                assert n == 2  # alice + bob
        finally:
            await engine.dispose()

    _run(go())


def test_count_paid_users_empty_db() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                assert await repo_users.count_paid_users(session) == 0
        finally:
            await engine.dispose()

    _run(go())


def test_count_users_returns_total() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                await _seed_users(session, (1, 1001, "a"), (2, 1002, "b"), (3, 1003, "c"))
                await session.commit()
            async with Session() as session:
                assert await repo_users.count_users(session) == 3
        finally:
            await engine.dispose()

    _run(go())


# --- active_paid_user_ids_subquery ----------------------------------------


def test_active_paid_user_ids_subquery_is_usable_in_filter() -> None:
    """The subquery is meant to be used with .in_() — verify that wiring."""

    async def go() -> None:
        from sqlalchemy import select

        now = datetime(2026, 5, 18, 12, 0, 0)
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                await _seed_users(session, (1, 1001, "paid"), (2, 1002, "free"))
                await _seed_tx(session, transaction_id="t1", user_id=1, status="delivered",
                               expire=now + timedelta(days=30))
                await session.commit()
            async with Session() as session:
                paid_sq = repo_users.active_paid_user_ids_subquery(now)
                paid_users = (
                    await session.scalars(
                        select(User).where(User.id.in_(paid_sq))
                    )
                ).all()
                assert {u.username for u in paid_users} == {"paid"}
        finally:
            await engine.dispose()

    _run(go())


# --- bulk reads -----------------------------------------------------------


def test_get_all_tg_ids_skips_nulls() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(User(id=1, tg_id=1001, username="a"))
                session.add(User(id=2, tg_id=None, username="android-only"))
                session.add(User(id=3, tg_id=1003, username="c"))
                await session.commit()
            async with Session() as session:
                ids = await repo_users.get_all_tg_ids(session)
                assert sorted(ids) == [1001, 1003]
        finally:
            await engine.dispose()

    _run(go())


def test_get_users_by_tg_ids_empty_input() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                result = await repo_users.get_users_by_tg_ids(session, [])
                assert result == []
        finally:
            await engine.dispose()

    _run(go())


def test_get_users_by_tg_ids_returns_matches() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                await _seed_users(session, (1, 1001, "a"), (2, 1002, "b"), (3, 1003, "c"))
                await session.commit()
            async with Session() as session:
                result = await repo_users.get_users_by_tg_ids(session, [1001, 1003, 9999])
                assert sorted(u.username for u in result) == ["a", "c"]
        finally:
            await engine.dispose()

    _run(go())


def test_persist_remnawave_uuid() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(User(id=1, tg_id=100, username="free_user"))
                await session.commit()
            async with Session() as session:
                ok = await repo_users.persist_remnawave_uuid(
                    session,
                    tg_id=100,
                    vless_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    username="free_user",
                )
                await session.commit()
                assert ok is True
                user = await repo_users.get_user_by_tg_id(session, 100)
                assert user is not None
                assert user.vless_uuid == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
                assert user.api_provider == "remnawave"
        finally:
            await engine.dispose()

    _run(go())


def test_persist_remnawave_uuid_with_rw_id() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(User(id=1, tg_id=100, username="free_user"))
                await session.commit()
            async with Session() as session:
                ok = await repo_users.persist_remnawave_uuid(
                    session,
                    tg_id=100,
                    vless_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    username="free_user",
                    rw_id=4242,
                )
                await session.commit()
                assert ok is True
                user = await repo_users.get_user_by_tg_id(session, 100)
                assert user is not None
                assert user.rw_id == 4242
        finally:
            await engine.dispose()

    _run(go())

"""Tests for common_db.repo.system — singleton-row helpers.

Each test spins up a fresh in-memory sqlite engine so behaviour stays
isolated. We don't use pytest-asyncio (not in deps); ``asyncio.run`` is
fine for these short single-shot coroutines.
"""
from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401  -- register models on Base.metadata
from common_db.models import CacheVersion, PromoSettings, TelmtFreeParams
from common_db.repo import system as repo_system


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:")


async def _setup(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _run(coro):
    return asyncio.run(coro)


# --- get_or_create_singleton ---------------------------------------------


def test_get_or_create_singleton_inserts_when_missing() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                row = await repo_system.get_or_create_singleton(
                    session, PromoSettings, defaults={"default_discount_percent": 42}
                )
                await session.commit()
                assert row.id == 1
                assert row.default_discount_percent == 42
        finally:
            await engine.dispose()

    _run(go())


def test_get_or_create_singleton_returns_existing() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            # Seed with a non-default value so we can tell apart.
            async with Session() as session:
                session.add(PromoSettings(id=1, default_discount_percent=99))
                await session.commit()
            async with Session() as session:
                row = await repo_system.get_or_create_singleton(
                    session,
                    PromoSettings,
                    defaults={"default_discount_percent": 42},
                )
                assert row.default_discount_percent == 99, (
                    "defaults must NOT overwrite existing row"
                )
        finally:
            await engine.dispose()

    _run(go())


# --- PromoSettings ---------------------------------------------------------


def test_get_promo_settings_creates_with_default() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                row = await repo_system.get_promo_settings(session)
                assert row.id == 1
                assert (
                    row.default_discount_percent
                    == repo_system.DEFAULT_PROMO_DISCOUNT_PERCENT
                )
        finally:
            await engine.dispose()

    _run(go())


def test_get_default_discount_percent_unwraps_value() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                pct = await repo_system.get_default_discount_percent(session)
                await session.commit()
                assert isinstance(pct, int)
                assert pct == repo_system.DEFAULT_PROMO_DISCOUNT_PERCENT
        finally:
            await engine.dispose()

    _run(go())


# --- TelmtFreeParams ------------------------------------------------------


def test_get_telmt_free_params_creates_with_defaults() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                row = await repo_system.get_telmt_free_params(session)
                assert row.id == 1
                assert row.max_tcp_conns is None
                assert row.max_unique_ips is None
                assert row.data_quota_bytes is None
                assert row.expire_days == repo_system.DEFAULT_TELMT_EXPIRE_DAYS
        finally:
            await engine.dispose()

    _run(go())


# --- CacheVersion ---------------------------------------------------------


def test_get_cache_version_starts_at_zero() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                v = await repo_system.get_cache_version(session)
                await session.commit()
                assert v == 0
        finally:
            await engine.dispose()

    _run(go())


def test_bump_cache_version_increments_atomically() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                v1 = await repo_system.bump_cache_version(session)
                v2 = await repo_system.bump_cache_version(session)
                v3 = await repo_system.bump_cache_version(session)
                await session.commit()
                assert (v1, v2, v3) == (1, 2, 3)
            # Verify persistence across sessions.
            async with Session() as session:
                v = await repo_system.get_cache_version(session)
                assert v == 3
        finally:
            await engine.dispose()

    _run(go())


def test_bump_cache_version_on_empty_table_seeds_first() -> None:
    """If no row exists yet (fresh DB), bump still works: seeds then bumps."""

    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                # Sanity: table is empty.
                from sqlalchemy import func, select

                assert (
                    await session.scalar(select(func.count()).select_from(CacheVersion))
                    == 0
                )
                v = await repo_system.bump_cache_version(session)
                await session.commit()
                assert v == 1
        finally:
            await engine.dispose()

    _run(go())


# --- contract: no commit inside helpers ----------------------------------


def test_helpers_do_not_commit() -> None:
    """The repo contract says callers own commits. Verify by NOT committing
    in the test and watching the row vanish on a second connection."""

    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                await repo_system.get_promo_settings(session)
                # No commit here on purpose.
            # Fresh session: row must NOT have persisted.
            async with Session() as session:
                from sqlalchemy import func, select

                count = await session.scalar(
                    select(func.count()).select_from(PromoSettings)
                )
                assert count == 0, (
                    "helper committed despite contract — see repo/__init__.py"
                )
        finally:
            await engine.dispose()

    _run(go())
